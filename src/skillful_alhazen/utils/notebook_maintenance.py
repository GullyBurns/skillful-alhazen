"""
Unified notebook maintenance tool for Skillful-Alhazen.

Subcommands:
    survey     - Survey database health: entity counts, freshness, triage recommendations
    audit      - Run quality audit for a single skill
    audit-all  - Discover and audit all skills with quality-checks.yaml
    refresh    - Triage + archive + clean stale namespaces
    verify     - Combined survey + audit-all health report

Usage:
    uv run python src/skillful_alhazen/utils/notebook_maintenance.py survey
    uv run python src/skillful_alhazen/utils/notebook_maintenance.py audit --skill jobhunt --checks local_skills/jobhunt/quality-checks.yaml
    uv run python src/skillful_alhazen/utils/notebook_maintenance.py audit-all
    uv run python src/skillful_alhazen/utils/notebook_maintenance.py refresh [--manifest triage.yaml] [--dry-run]
    uv run python src/skillful_alhazen/utils/notebook_maintenance.py verify
"""

import argparse
import json
import os
import subprocess
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from skillful_alhazen.utils.skill_helpers import get_timestamp

# ---------------------------------------------------------------------------
# TypeDB connection
# ---------------------------------------------------------------------------
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")


def _connect():
    """Return (driver, database)."""
    from typedb.driver import Credentials, DriverOptions, TypeDB

    user = os.getenv("TYPEDB_USERNAME", "admin")
    pwd = os.getenv("TYPEDB_PASSWORD", "password")
    driver = TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(user, pwd),
        DriverOptions(is_tls_enabled=False),
    )
    return driver, TYPEDB_DATABASE


def _query(driver, database, q):
    from typedb.driver import TransactionType

    with driver.transaction(database, TransactionType.READ) as tx:
        return list(tx.query(q.strip()).resolve())


# ---------------------------------------------------------------------------
# survey
# ---------------------------------------------------------------------------

# Entity types to survey -- covers the full schema hierarchy.
# Each entry is (type_name, has_created_at).
ENTITY_TYPES = [
    # Core abstract subs
    ("collection", True),
    ("artifact", True),
    ("fragment", True),
    ("note", True),
    # domain-thing subs
    ("domain-thing", True),
    ("agent", True),
    ("ai-agent", True),
    ("person", True),
    ("operator-user", True),
    ("author", True),
    ("jobhunt-contact", True),
    ("organization", True),
    ("jobhunt-company", True),
    ("interaction", True),
    # Skill-specific entity types (discovered dynamically below)
]


def _discover_entity_types(driver, database):
    """Query TypeDB to find all concrete entity types with instances."""
    from typedb.driver import TransactionType

    results = {}

    # Use the pattern that works: match $e isa! $t to get exact types
    with driver.transaction(database, TransactionType.READ) as tx:
        rows = list(tx.query(
            'match $e isa! $t, has id $id; fetch { "type": $t };'
        ).resolve())

    # Count by type
    type_counts = {}
    for row in rows:
        label = row.get("type", {}).get("label", "unknown")
        type_counts[label] = type_counts.get(label, 0) + 1

    for type_name, count in type_counts.items():
        results[type_name] = {"count": count}

    # Freshness: try to get min/max created-at for each type
    for type_name, info in results.items():
        try:
            freshness_q = f"""
                match $x isa {type_name}, has created-at $d;
                reduce $oldest = min($d), $newest = max($d);
            """
            rows = _query(driver, database, freshness_q)
            if rows:
                info["oldest"] = str(rows[0].get("oldest", ""))
                info["newest"] = str(rows[0].get("newest", ""))
        except Exception:
            info["oldest"] = None
            info["newest"] = None

    return results


def _namespace_from_type(type_name):
    """Extract namespace prefix from a type name (text before first '-')."""
    if "-" in type_name:
        return type_name.split("-")[0]
    return "core"


def _recommend(info):
    """Produce a triage recommendation for a namespace group."""
    has_dates = any(
        t.get("newest") not in (None, "", "None") for t in info.values()
    )
    if not has_dates:
        return "archive"

    # Check if newest date is within last 90 days
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)

    recent = False
    old = False
    for t in info.values():
        newest = t.get("newest")
        if newest and newest not in ("None", ""):
            try:
                dt = datetime.fromisoformat(str(newest).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    recent = True
                else:
                    old = True
            except (ValueError, TypeError):
                pass

    if recent and not old:
        return "keep"
    if recent and old:
        return "partial"
    return "archive"


def cmd_survey(_args):
    """Survey database entity health."""
    driver, database = _connect()
    print("Surveying database...", file=sys.stderr)

    type_data = _discover_entity_types(driver, database)
    driver.close()

    if not type_data:
        print("No entities found in database.", file=sys.stderr)
        json.dump({"namespaces": {}, "total_entities": 0}, sys.stdout, indent=2)
        print()
        return

    # Group by namespace
    namespaces = defaultdict(dict)
    for type_name, info in type_data.items():
        ns = _namespace_from_type(type_name)
        namespaces[ns][type_name] = info

    # Build report
    report = {"timestamp": get_timestamp(), "namespaces": {}, "total_entities": 0}
    total = 0

    for ns in sorted(namespaces):
        types = namespaces[ns]
        ns_count = sum(t["count"] for t in types.values())
        total += ns_count

        # Aggregate freshness across namespace
        oldest_all = None
        newest_all = None
        for t in types.values():
            for field, agg_fn, current in [
                ("oldest", min, oldest_all),
                ("newest", max, newest_all),
            ]:
                val = t.get(field)
                if val and val not in ("None", ""):
                    if current is None:
                        if field == "oldest":
                            oldest_all = val
                        else:
                            newest_all = val
                    else:
                        if field == "oldest":
                            oldest_all = min(oldest_all, val)
                        else:
                            newest_all = max(newest_all, val)

        recommendation = _recommend(types)

        report["namespaces"][ns] = {
            "entity_count": ns_count,
            "types": {
                name: {"count": info["count"], "oldest": info.get("oldest"), "newest": info.get("newest")}
                for name, info in sorted(types.items())
            },
            "oldest": oldest_all,
            "newest": newest_all,
            "recommendation": recommendation,
        }

    report["total_entities"] = total

    # stderr summary
    print(f"\n{'=' * 55}", file=sys.stderr)
    print(f"  Notebook Survey  |  {total} entities  |  {len(namespaces)} namespaces", file=sys.stderr)
    print(f"{'=' * 55}", file=sys.stderr)
    for ns, info in sorted(report["namespaces"].items()):
        rec = info["recommendation"].upper()
        print(f"  {ns:20s}  {info['entity_count']:5d} entities  [{rec}]", file=sys.stderr)
    print(f"{'=' * 55}\n", file=sys.stderr)

    json.dump(report, sys.stdout, indent=2, default=str)
    print()


# ---------------------------------------------------------------------------
# audit / audit-all
# ---------------------------------------------------------------------------

def cmd_audit(args):
    """Run quality audit for a single skill (delegates to audit_runner)."""
    cmd = [
        "uv", "run", "python", "src/skillful_alhazen/utils/audit_runner.py", "run",
        "--checks", args.checks,
    ]
    if args.file_issues:
        cmd.append("--file-issues")
    subprocess.run(cmd)


def cmd_audit_all(_args):
    """Discover and run audits for all skills with quality-checks.yaml."""
    checks_files = sorted(Path("local_skills").glob("*/quality-checks.yaml"))
    if not checks_files:
        print("No quality-checks.yaml files found in local_skills/", file=sys.stderr)
        return

    all_reports = []
    for checks_file in checks_files:
        skill_name = checks_file.parent.name
        print(f"\n--- Auditing {skill_name} ---", file=sys.stderr)
        result = subprocess.run(
            [
                "uv", "run", "python", "src/skillful_alhazen/utils/audit_runner.py", "run",
                "--checks", str(checks_file),
            ],
            capture_output=True, text=True,
        )
        # Print stderr from audit_runner
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        # Collect JSON report
        if result.stdout.strip():
            try:
                report = json.loads(result.stdout)
                all_reports.append(report)
            except json.JSONDecodeError:
                print(f"  Warning: could not parse audit output for {skill_name}", file=sys.stderr)

    # Combined output
    combined = {
        "timestamp": get_timestamp(),
        "skills_audited": len(all_reports),
        "reports": all_reports,
        "summary": {
            "total_checks": sum(r["summary"]["total_checks"] for r in all_reports),
            "total_failing": sum(r["summary"]["checks_failing"] for r in all_reports),
            "total_passing": sum(r["summary"]["checks_passing"] for r in all_reports),
        },
    }
    json.dump(combined, sys.stdout, indent=2)
    print()


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------

def _archive_namespace(driver, database, ns_name, types_info, archive_dir, dry_run):
    """Archive entities for a namespace: export to JSON, optionally delete."""
    from typedb.driver import TransactionType

    archive_data = {}
    entity_count = 0

    for type_name, info in types_info.items():
        # Fetch entities with explicit common attributes
        fetch_q = f"""
            match $x isa {type_name}, has id $id;
            fetch {{
                "id": $x.id,
                "name": $x.name,
                "description": $x.description
            }};
        """
        try:
            rows = _query(driver, database, fetch_q)
        except Exception:
            # Some types may not have name/description -- fall back to id only
            fetch_q = f"""
                match $x isa {type_name}, has id $id;
                fetch {{ "id": $x.id }};
            """
            try:
                rows = _query(driver, database, fetch_q)
            except Exception as e:
                print(f"    Skip {type_name}: {e}", file=sys.stderr)
                continue

        if rows:
            archive_data[type_name] = rows
            entity_count += len(rows)

    if not archive_data:
        print(f"  {ns_name}: nothing to archive", file=sys.stderr)
        return

    # Write JSON archive
    archive_dir.mkdir(parents=True, exist_ok=True)
    json_path = archive_dir / f"{ns_name}.json"
    with open(json_path, "w") as f:
        json.dump(archive_data, f, indent=2, default=str)

    # Zip it
    zip_path = archive_dir / f"{ns_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(json_path, f"{ns_name}.json")
    json_path.unlink()  # remove uncompressed after zipping

    print(f"  {ns_name}: archived {entity_count} entities -> {zip_path}", file=sys.stderr)

    if dry_run:
        print(f"  {ns_name}: --dry-run, skipping delete", file=sys.stderr)
        return

    # Delete archived entities
    for type_name, rows in archive_data.items():
        for row in rows:
            eid = row.get("id", "")
            if not eid:
                continue
            try:
                with driver.transaction(database, TransactionType.WRITE) as tx:
                    tx.query(f'match $x isa {type_name}, has id "{eid}"; delete $x;').resolve()
                    tx.commit()
            except Exception as e:
                print(f"    Could not delete {type_name} id={eid}: {e}", file=sys.stderr)

    print(f"  {ns_name}: deleted {entity_count} entities from TypeDB", file=sys.stderr)


def cmd_refresh(args):
    """Triage + archive + clean stale namespaces."""
    refresh_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    cache_dir = Path(os.getenv("ALHAZEN_CACHE_DIR", os.path.expanduser("~/.alhazen/cache")))
    archive_dir = cache_dir / "notebook-archive" / refresh_id

    # Load or generate manifest
    if args.manifest:
        with open(args.manifest) as f:
            manifest = yaml.safe_load(f)
    else:
        # Auto-generate from survey
        print("No manifest provided, running survey to generate one...", file=sys.stderr)
        driver, database = _connect()
        type_data = _discover_entity_types(driver, database)

        # Group by namespace
        ns_groups = defaultdict(dict)
        for type_name, info in type_data.items():
            ns = _namespace_from_type(type_name)
            ns_groups[ns][type_name] = info

        manifest = {"namespaces": {}}
        for ns, types in ns_groups.items():
            rec = _recommend(types)
            manifest["namespaces"][ns] = {"action": rec, "types": list(types.keys())}

        driver.close()
        print(f"Auto-generated manifest with {len(manifest['namespaces'])} namespaces", file=sys.stderr)

    # Process each namespace
    driver, database = _connect()
    actions_taken = []

    for ns_name, ns_spec in manifest.get("namespaces", {}).items():
        action = ns_spec.get("action", "keep")
        types_list = ns_spec.get("types", [])

        if action == "keep":
            print(f"  {ns_name}: KEEP (skipping)", file=sys.stderr)
            actions_taken.append({"namespace": ns_name, "action": "keep"})
            continue

        if action == "archive":
            # Build types_info from list
            types_info = {}
            for t in types_list:
                try:
                    rows = _query(driver, database, f"match $x isa {t}; reduce $c = count;")
                    count = rows[0]["c"] if rows else 0
                    types_info[t] = {"count": count}
                except Exception:
                    continue
            _archive_namespace(driver, database, ns_name, types_info, archive_dir, args.dry_run)
            actions_taken.append({"namespace": ns_name, "action": "archive", "archive_dir": str(archive_dir)})

        elif action == "partial":
            print(f"  {ns_name}: PARTIAL (filter-based triage not yet implemented, skipping)", file=sys.stderr)
            actions_taken.append({"namespace": ns_name, "action": "partial", "status": "skipped"})

        elif action == "drop":
            print(f"  {ns_name}: DROP (deleting entities with no relations)", file=sys.stderr)
            # For safety, just log -- actual drop requires explicit confirmation
            actions_taken.append({"namespace": ns_name, "action": "drop", "status": "logged_only"})

        else:
            print(f"  {ns_name}: unknown action '{action}', skipping", file=sys.stderr)

    driver.close()

    result = {
        "refresh_id": refresh_id,
        "timestamp": get_timestamp(),
        "archive_dir": str(archive_dir),
        "dry_run": args.dry_run,
        "actions": actions_taken,
    }
    json.dump(result, sys.stdout, indent=2)
    print()


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def cmd_verify(_args):
    """Run survey + audit-all and produce a combined health report."""
    print("=== Phase 1: Survey ===", file=sys.stderr)

    # Survey
    driver, database = _connect()
    type_data = _discover_entity_types(driver, database)
    driver.close()

    ns_groups = defaultdict(dict)
    total = 0
    for type_name, info in type_data.items():
        ns = _namespace_from_type(type_name)
        ns_groups[ns][type_name] = info
        total += info["count"]

    survey_summary = {
        "total_entities": total,
        "namespaces": len(ns_groups),
        "recommendations": {
            ns: _recommend(types) for ns, types in ns_groups.items()
        },
    }

    print(f"  {total} entities across {len(ns_groups)} namespaces", file=sys.stderr)

    # Audit-all
    print("\n=== Phase 2: Audit All ===", file=sys.stderr)
    checks_files = sorted(Path("local_skills").glob("*/quality-checks.yaml"))
    audit_reports = []
    for checks_file in checks_files:
        skill_name = checks_file.parent.name
        print(f"  Auditing {skill_name}...", file=sys.stderr)
        result = subprocess.run(
            [
                "uv", "run", "python", "src/skillful_alhazen/utils/audit_runner.py", "run",
                "--checks", str(checks_file),
            ],
            capture_output=True, text=True,
        )
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        if result.stdout.strip():
            try:
                audit_reports.append(json.loads(result.stdout))
            except json.JSONDecodeError:
                pass

    total_checks = sum(r["summary"]["total_checks"] for r in audit_reports)
    total_failing = sum(r["summary"]["checks_failing"] for r in audit_reports)

    health = {
        "timestamp": get_timestamp(),
        "survey": survey_summary,
        "audit": {
            "skills_audited": len(audit_reports),
            "total_checks": total_checks,
            "total_failing": total_failing,
            "total_passing": total_checks - total_failing,
        },
        "health_score": round(
            (1 - total_failing / total_checks) * 100, 1
        ) if total_checks > 0 else 100.0,
    }

    print(f"\n{'=' * 55}", file=sys.stderr)
    print(f"  Health Score: {health['health_score']}%", file=sys.stderr)
    print(f"  Entities: {total}  |  Checks: {total_checks} ({total_failing} failing)", file=sys.stderr)
    print(f"{'=' * 55}\n", file=sys.stderr)

    json.dump(health, sys.stdout, indent=2)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Unified notebook maintenance tool")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("survey", help="Survey database health")

    p_audit = sub.add_parser("audit", help="Run quality audit for a skill")
    p_audit.add_argument("--skill", required=True, help="Skill name")
    p_audit.add_argument("--checks", required=True, help="Path to quality-checks.yaml")
    p_audit.add_argument("--file-issues", action="store_true", help="Create GitHub issues")

    sub.add_parser("audit-all", help="Audit all skills with quality-checks.yaml")

    p_refresh = sub.add_parser("refresh", help="Triage + archive + clean")
    p_refresh.add_argument("--manifest", help="Path to triage manifest YAML")
    p_refresh.add_argument("--dry-run", action="store_true", help="Preview without deleting")

    sub.add_parser("verify", help="Run survey + audit-all health check")

    args = parser.parse_args()

    dispatch = {
        "survey": cmd_survey,
        "audit": cmd_audit,
        "audit-all": cmd_audit_all,
        "refresh": cmd_refresh,
        "verify": cmd_verify,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
