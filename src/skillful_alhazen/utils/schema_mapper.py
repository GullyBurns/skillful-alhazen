"""
Cross-database schema mapper orchestrator for TypeDB.

Maps data between two TypeDB databases using declarative YAML mapping rules.
Each rule is a paired (source_match, target_insert) TypeQL fragment. The
orchestrator is mechanical -- no domain logic.

Mapping Rule Format (YAML):
    name: disease
    description: Map source disease entities to dm-disease
    depends_on: []
    idempotent: true
    source_match: |
      match $d isa disease, has name $n, has category $cat;
      fetch { "n": $n, "cat": $cat };
    target_insert: |
      insert $td isa dm-disease, has id $skolem_id, has name $n, has dm-category $cat;
    skolem_keys: [$n]

Usage:
    uv run python src/skillful_alhazen/utils/schema_mapper.py run \
        --source-db source --target-db target --rules-dir ./rules
    uv run python src/skillful_alhazen/utils/schema_mapper.py reconcile \
        --source-db source --target-db target --rules-dir ./rules
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from skillful_alhazen.utils.skill_helpers import escape_string

# ---------------------------------------------------------------------------
# TypeDB connection
# ---------------------------------------------------------------------------

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    """Return a TypeDB driver using environment configuration."""
    from typedb.driver import Credentials, DriverOptions, TypeDB

    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


# ---------------------------------------------------------------------------
# Rule dataclass
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    """A single mapping rule parsed from YAML."""

    name: str
    description: str
    source_match: str
    target_insert: str
    skolem_keys: list[str]
    depends_on: list[str] = field(default_factory=list)
    idempotent: bool = True


# ---------------------------------------------------------------------------
# load_rules
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"name", "source_match", "target_insert", "skolem_keys"}


def load_rules(rules_dir: str | Path) -> list[Rule]:
    """Read all .yaml/.yml files in *rules_dir* and return parsed Rule objects.

    Raises ValueError on missing required fields.
    """
    rules_path = Path(rules_dir)
    if not rules_path.is_dir():
        raise FileNotFoundError(f"Rules directory not found: {rules_path}")

    rules: list[Rule] = []
    for yaml_file in sorted(rules_path.glob("*.y*ml")):
        with open(yaml_file) as fh:
            data = yaml.safe_load(fh)
        if data is None:
            continue

        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            raise ValueError(
                f"{yaml_file.name}: missing required fields: {', '.join(sorted(missing))}"
            )

        rules.append(
            Rule(
                name=data["name"],
                description=data.get("description", ""),
                source_match=data["source_match"].strip(),
                target_insert=data["target_insert"].strip(),
                skolem_keys=data["skolem_keys"],
                depends_on=data.get("depends_on", []) or [],
                idempotent=data.get("idempotent", True),
            )
        )

    return rules


# ---------------------------------------------------------------------------
# topological_sort
# ---------------------------------------------------------------------------

def topological_sort(rules: list[Rule]) -> list[Rule]:
    """Return *rules* in dependency order. Raises ValueError on cycles."""
    by_name: dict[str, Rule] = {r.name: r for r in rules}

    # Validate that all dependencies reference existing rules
    for rule in rules:
        for dep in rule.depends_on:
            if dep not in by_name:
                raise ValueError(
                    f"Rule '{rule.name}' depends on unknown rule '{dep}'"
                )

    # Kahn's algorithm
    in_degree: dict[str, int] = {r.name: 0 for r in rules}
    adjacency: dict[str, list[str]] = {r.name: [] for r in rules}
    for rule in rules:
        for dep in rule.depends_on:
            adjacency[dep].append(rule.name)
            in_degree[rule.name] += 1

    queue = [name for name, deg in in_degree.items() if deg == 0]
    ordered: list[str] = []

    while queue:
        # Sort for deterministic ordering among same-level rules
        queue.sort()
        node = queue.pop(0)
        ordered.append(node)
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(rules):
        remaining = set(r.name for r in rules) - set(ordered)
        raise ValueError(f"Cycle detected among rules: {', '.join(sorted(remaining))}")

    return [by_name[name] for name in ordered]


# ---------------------------------------------------------------------------
# skolemize
# ---------------------------------------------------------------------------

def skolemize(rule_name: str, values: list[str]) -> str:
    """Generate a deterministic ID from rule name and key values.

    Format: dm-{rule_name}-{sha256(key1|key2|...)[:12]}
    """
    payload = "|".join(str(v) for v in values)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"dm-{rule_name}-{digest}"


# ---------------------------------------------------------------------------
# Variable substitution
# ---------------------------------------------------------------------------

# Matches $variable tokens that are NOT inside quotes and are not $skolem_id
_VAR_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_-]*)")


def _format_value(val: Any) -> str:
    """Format a Python value for TypeQL insertion.

    Strings are quoted and escaped. Numbers and booleans are left bare.
    """
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    # Treat everything else as a string
    return f'"{escape_string(str(val))}"'


def substitute_variables(
    template: str,
    row: dict[str, Any],
    skolem_id: str,
) -> str:
    """Replace $variable placeholders in *template* with values from *row*.

    - $skolem_id is replaced with the generated deterministic ID (quoted).
    - Other $variables are looked up in *row* and formatted for TypeQL.
    """
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name == "skolem_id":
            return f'"{escape_string(skolem_id)}"'
        if var_name in row:
            return _format_value(row[var_name])
        # Leave unresolved variables as-is (they may be TypeQL variables
        # like $td that are bound in the insert, not from source data)
        return match.group(0)

    return _VAR_PATTERN.sub(replacer, template)


# ---------------------------------------------------------------------------
# Idempotent existence check
# ---------------------------------------------------------------------------

def _entity_exists(tx, skolem_id: str) -> bool:
    """Check if an entity with the given id already exists in the target db."""
    query = (
        f'match $x isa identifiable-entity, has id "{escape_string(skolem_id)}";'
        f' fetch {{ "id": $x.id }};'
    )
    try:
        results = list(tx.query(query).resolve())
        return len(results) > 0
    except Exception:
        return False


def _batch_exists(driver, target_db: str, skolem_ids: list[str], chunk_size: int = 500) -> set[str]:
    """Check which skolem IDs already exist in target DB. Returns set of existing IDs.

    Uses chunked queries to avoid TypeQL length limits. Single read transaction
    per chunk instead of one transaction per row.
    """
    from typedb.driver import TransactionType

    existing: set[str] = set()
    for i in range(0, len(skolem_ids), chunk_size):
        chunk = skolem_ids[i:i + chunk_size]
        with driver.transaction(target_db, TransactionType.READ) as tx:
            for sid in chunk:
                if _entity_exists(tx, sid):
                    existing.add(sid)
    return existing


# ---------------------------------------------------------------------------
# run_mapping
# ---------------------------------------------------------------------------

def run_mapping(
    source_db: str,
    target_db: str,
    rules: list[Rule],
    batch_size: int = 1000,
    dry_run: bool = False,
    single_rule: str | None = None,
) -> dict:
    """Execute mapping rules, reading from source_db and writing to target_db.

    Returns a summary dict suitable for JSON output.
    """
    from typedb.driver import TransactionType

    driver = get_driver()
    per_rule: list[dict] = []

    rules_to_run = rules
    if single_rule:
        rules_to_run = [r for r in rules if r.name == single_rule]
        if not rules_to_run:
            raise ValueError(f"Rule '{single_rule}' not found")

    total_rows = 0

    for rule in rules_to_run:
      try:
        t0 = time.time()
        _log(f"[{rule.name}] Starting...")

        # --- Read source ---
        with driver.transaction(source_db, TransactionType.READ) as tx:
            results = list(tx.query(rule.source_match).resolve())

        source_count = len(results)
        _log(f"[{rule.name}] Source rows: {source_count}")

        if dry_run:
            elapsed = time.time() - t0
            per_rule.append({
                "name": rule.name,
                "source_count": source_count,
                "target_count": 0,
                "skipped": 0,
                "delta": source_count,
                "time_seconds": round(elapsed, 2),
                "dry_run": True,
            })
            total_rows += source_count
            continue

        # --- Compute skolem IDs for all rows, deduplicate ---
        rows_with_ids: list[tuple[dict, str]] = []
        seen_sids: set[str] = set()
        deduped = 0
        for row in results:
            key_values = [str(row.get(key, "")) for key in rule.skolem_keys]
            sid = skolemize(rule.name, key_values)
            if sid in seen_sids:
                deduped += 1
                continue
            seen_sids.add(sid)
            rows_with_ids.append((row, sid))
        if deduped:
            _log(f"[{rule.name}] Deduplicated {deduped} rows ({len(rows_with_ids)} unique)")

        # --- Batch idempotency check (single read tx) ---
        existing_ids: set[str] = set()
        if rule.idempotent and rows_with_ids:
            all_sids = [sid for _, sid in rows_with_ids]
            existing_ids = _batch_exists(driver, target_db, all_sids)
            if existing_ids:
                _log(f"[{rule.name}] {len(existing_ids)} already exist, will skip")

        # --- Write target ---
        written = 0
        skipped = 0
        batch_queries: list[str] = []

        for row, sid in rows_with_ids:
            if sid in existing_ids:
                skipped += 1
                continue

            query = substitute_variables(rule.target_insert, row, sid)
            batch_queries.append(query)

            if len(batch_queries) >= batch_size:
                written += _flush_batch(driver, target_db, batch_queries)
                batch_queries = []

        # Final flush
        if batch_queries:
            written += _flush_batch(driver, target_db, batch_queries)

        elapsed = time.time() - t0
        _log(
            f"[{rule.name}] Done: {written} written, {skipped} skipped "
            f"({elapsed:.1f}s)"
        )

        per_rule.append({
            "name": rule.name,
            "source_count": source_count,
            "target_count": written,
            "skipped": skipped,
            "delta": source_count - written - skipped,
            "time_seconds": round(elapsed, 2),
        })
        total_rows += source_count
      except Exception as exc:
        elapsed = time.time() - t0
        _log(f"[{rule.name}] FAILED: {exc}", level="ERROR")
        per_rule.append({
            "name": rule.name,
            "error": str(exc)[:200],
            "time_seconds": round(elapsed, 2),
        })

    driver.close()

    return {
        "success": True,
        "rules_run": len(per_rule),
        "total_rows": total_rows,
        "per_rule": per_rule,
    }


def _flush_batch(driver, target_db: str, queries: list[str]) -> int:
    """Execute a batch of insert queries in a single write transaction.

    If the batch commit fails (e.g., constraint violations from duplicates),
    falls back to per-query transactions to save what we can.

    Returns the number of queries successfully executed.
    """
    from typedb.driver import TransactionType

    # Try batch first (fast path)
    try:
        with driver.transaction(target_db, TransactionType.WRITE) as tx:
            for q in queries:
                tx.query(q).resolve()
            tx.commit()
        return len(queries)
    except Exception:
        pass

    # Fallback: one transaction per query (slow but robust)
    count = 0
    for q in queries:
        try:
            with driver.transaction(target_db, TransactionType.WRITE) as tx:
                tx.query(q).resolve()
                tx.commit()
                count += 1
        except Exception:
            pass  # skip duplicates silently
    return count


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------

def reconcile(
    source_db: str,
    target_db: str,
    rules: list[Rule],
) -> dict:
    """For each rule, count source vs target rows and report deltas."""
    from typedb.driver import TransactionType

    driver = get_driver()
    per_rule: list[dict] = []

    for rule in rules:
        # Count source rows
        with driver.transaction(source_db, TransactionType.READ) as tx:
            source_results = list(tx.query(rule.source_match).resolve())
        source_count = len(source_results)

        # Count target rows by checking how many skolem IDs exist
        target_count = 0
        with driver.transaction(target_db, TransactionType.READ) as tx:
            for row in source_results:
                key_values = [str(row.get(k, "")) for k in rule.skolem_keys]
                sid = skolemize(rule.name, key_values)
                if _entity_exists(tx, sid):
                    target_count += 1

        delta = source_count - target_count
        status = "OK" if delta == 0 else f"MISSING {delta}"
        _log(
            f"[{rule.name}] source={source_count} target={target_count} "
            f"delta={delta} ({status})"
        )

        per_rule.append({
            "name": rule.name,
            "source_count": source_count,
            "target_count": target_count,
            "delta": delta,
        })

    driver.close()

    all_ok = all(r["delta"] == 0 for r in per_rule)
    return {
        "success": all_ok,
        "rules_checked": len(per_rule),
        "per_rule": per_rule,
    }


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str, level: str = "INFO") -> None:
    """Print a log message to stderr."""
    print(f"[schema-mapper][{level}] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-database schema mapper for TypeDB. "
        "Maps data between two TypeDB databases using declarative YAML rules.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_parser = subparsers.add_parser(
        "run",
        help="Execute mapping rules (read source, write target)",
    )
    run_parser.add_argument(
        "--source-db", required=True, help="Source TypeDB database name"
    )
    run_parser.add_argument(
        "--target-db", required=True, help="Target TypeDB database name"
    )
    run_parser.add_argument(
        "--rules-dir", required=True, help="Directory containing YAML rule files"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count source rows only, do not write to target",
    )
    run_parser.add_argument(
        "--rule",
        default=None,
        help="Run only this named rule (skip others)",
    )
    run_parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of inserts per write transaction (default: 1000)",
    )

    # --- reconcile ---
    rec_parser = subparsers.add_parser(
        "reconcile",
        help="Compare source row counts vs target entity counts",
    )
    rec_parser.add_argument(
        "--source-db", required=True, help="Source TypeDB database name"
    )
    rec_parser.add_argument(
        "--target-db", required=True, help="Target TypeDB database name"
    )
    rec_parser.add_argument(
        "--rules-dir", required=True, help="Directory containing YAML rule files"
    )

    args = parser.parse_args()

    try:
        raw_rules = load_rules(args.rules_dir)
        rules = topological_sort(raw_rules)

        if args.command == "run":
            result = run_mapping(
                source_db=args.source_db,
                target_db=args.target_db,
                rules=rules,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
                single_rule=args.rule,
            )
        elif args.command == "reconcile":
            result = reconcile(
                source_db=args.source_db,
                target_db=args.target_db,
                rules=rules,
            )
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, indent=2))

    except Exception as exc:
        error_result = {"success": False, "error": str(exc)}
        _log(str(exc), level="ERROR")
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
