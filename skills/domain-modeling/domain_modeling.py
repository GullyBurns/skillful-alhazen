#!/usr/bin/env python3
"""
Domain Modeling Skill CLI - Track the design process of knowledge domain skills.

Usage:
    uv run python .claude/skills/domain-modeling/domain_modeling.py <command> [options]

Commands:
    Domain lifecycle:
        init-domain         Create a domain design tracking project
        list-domains        List all tracked domains
        show-domain         Show full domain history
        set-task            Set the natural-language task the skill performs

    Skill snapshots:
        snapshot-skill      Capture all skill files with git metadata
        snapshot-schema     [DEPRECATED] Use snapshot-skill instead
        list-versions       List skill snapshots for a domain
        list-files          List files captured in a snapshot
        show-file           Show content of a captured file
        add-plan            Attach a plan document to a snapshot
        install-hook        Install git post-commit hook for auto-snapshots

    Design decisions:
        add-decision        Record a schema design decision
        add-rationale       Add reasoning for a decision
        link-gap            Link a schema-gap as motivation for a decision
        list-decisions      List decisions for a domain

    Experiments:
        start-experiment    Start a design hypothesis experiment
        record-result       Record an experiment observation
        complete-experiment Mark experiment as complete
        list-experiments    List experiments for a domain

    Representation errors:
        report-error        Report a schema representation failure
        resolve-error       Mark an error as resolved
        list-errors         List errors for a domain

    Export:
        export-design       Export annotated Markdown design changelog

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

try:
    from skillful_alhazen.utils.skill_helpers import escape_string, generate_id, get_timestamp
    from skillful_alhazen.utils.cache import should_cache, save_to_cache

    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False

    def escape_string(s: str) -> str:
        if s is None:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")

    def generate_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def get_timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    def should_cache(content) -> bool:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return len(content) >= 50 * 1024

    def save_to_cache(artifact_id, content, mime_type):
        return None


# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def json_default(obj):
    """JSON serializer for non-standard types (e.g. datetime)."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def out(data):
    """Output JSON to stdout."""
    print(json.dumps(data, default=json_default))


def s(attr_name: str, value: str) -> str:
    """Build a 'has attr "value"' clause for string attributes."""
    return f'has {attr_name} "{escape_string(str(value))}"'


def dt(attr_name: str, value: str) -> str:
    """Build a 'has attr datetime' clause (unquoted)."""
    return f"has {attr_name} {value}"


def num(attr_name: str, value) -> str:
    """Build a 'has attr number' clause (unquoted)."""
    return f"has {attr_name} {value}"


def insert_entity(tx, entity_type: str, clauses: list[str]) -> None:
    """Execute a typed entity insert."""
    q = f"insert $e isa {entity_type}, {', '.join(clauses)};"
    tx.query(q).resolve()


def insert_relation(tx, relation_type: str, roles: dict[str, tuple[str, str]]) -> None:
    """
    Execute a relation insert given matched entities.

    roles: dict mapping role_name -> (entity_type, entity_id)
    """
    match_clauses = []
    role_clauses = []
    for i, (role, (etype, eid)) in enumerate(roles.items()):
        var = f"$e{i}"
        match_clauses.append(f'{var} isa {etype}, has id "{escape_string(eid)}";')
        role_clauses.append(f"{role}: {var}")

    match_str = " ".join(match_clauses)
    roles_str = ", ".join(role_clauses)
    q = f"match {match_str} insert ({roles_str}) isa {relation_type};"
    tx.query(q).resolve()


def update_attr(tx, entity_type: str, entity_id: str, attr_name: str, new_value: str) -> None:
    """Delete old attribute value and insert new one (for single-valued updates)."""
    # Delete old value (TypeDB 3.x syntax: delete has $v of $e)
    del_q = f"""
        match $e isa {entity_type}, has id "{escape_string(entity_id)}",
              has {attr_name} $v;
        delete has $v of $e;
    """
    tx.query(del_q).resolve()
    # Insert new value
    ins_q = f"""
        match $e isa {entity_type}, has id "{escape_string(entity_id)}";
        insert $e has {attr_name} "{escape_string(new_value)}";
    """
    tx.query(ins_q).resolve()


def run_git(cmd: list, cwd: str = ".") -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def get_git_metadata(repo_dir: str = ".") -> dict:
    """Collect git state from repo_dir. Returns empty strings on failure."""
    return {
        "commit": run_git(["rev-parse", "HEAD"], cwd=repo_dir) or "",
        "repo": run_git(["remote", "get-url", "origin"], cwd=repo_dir) or "",
        "branch": run_git(["branch", "--show-current"], cwd=repo_dir) or "",
        "message": run_git(["log", "-1", "--pretty=%s"], cwd=repo_dir) or "",
        "parent": run_git(["log", "--pretty=%P", "-1"], cwd=repo_dir) or "",
    }


def fetch_query(driver, q: str) -> list[dict]:
    """Execute a fetch query and return results as list of dicts."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        return list(tx.query(q).resolve())


# =============================================================================
# DOMAIN LIFECYCLE
# =============================================================================


def cmd_init_domain(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    domain_id = generate_id("dm-domain")
    ts = get_timestamp()

    clauses = [
        s("id", domain_id),
        s("name", args.name),
        dt("created-at", ts),
    ]
    if args.description:
        clauses.append(s("description", args.description))
    if args.skill:
        clauses.append(s("dm-skill-name", args.skill))

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-domain", clauses)
            tx.commit()

    out({"success": True, "id": domain_id, "name": args.name})


def cmd_list_domains(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    q = """
        match $d isa dm-domain;
        fetch { "id": $d.id, "name": $d.name, "description": $d.description,
                "skill": $d.dm-skill-name, "created": $d.created-at };
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    domains = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "description": r.get("description"),
            "skill": r.get("skill"),
            "created": r.get("created"),
        }
        for r in results
    ]
    out({"success": True, "count": len(domains), "domains": domains})


def cmd_show_domain(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    domain_id = args.id
    eid = escape_string(domain_id)

    with get_driver() as driver:
        # Domain info
        d_q = f"""
            match $d isa dm-domain, has id "{eid}";
            fetch {{ "id": $d.id, "name": $d.name, "description": $d.description,
                    "skill": $d.dm-skill-name, "task": $d.dm-skill-task, "created": $d.created-at }};
        """
        d_res = fetch_query(driver, d_q)
        if not d_res:
            out({"success": False, "error": f"Domain not found: {domain_id}"})
            return
        domain = d_res[0]

        # Versions
        v_q = f"""
            match $sv isa dm-skill-snapshot;
                  $d isa dm-domain, has id "{eid}";
                  (skill-snapshot: $sv, domain: $d) isa dm-version-of;
            fetch {{ "id": $sv.id, "tag": $sv.dm-version-tag, "commit": $sv.dm-git-commit,
                    "branch": $sv.dm-git-branch, "message": $sv.dm-git-message,
                    "created": $sv.created-at }};
        """
        versions = fetch_query(driver, v_q)

        # Decisions
        dec_q = f"""
            match $dec isa dm-design-decision;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $dec, domain: $d) isa dm-in-domain;
            fetch {{ "id": $dec.id, "name": $dec.name, "type": $dec.dm-decision-type,
                    "summary": $dec.dm-decision-summary,
                    "alternatives": $dec.dm-alternatives-text }};
        """
        decisions = fetch_query(driver, dec_q)

        # Decision -> version mapping
        dv_q = f"""
            match $dec isa dm-design-decision;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $dec, domain: $d) isa dm-in-domain;
                  $sv isa dm-skill-snapshot;
                  (decision: $dec, skill-snapshot: $sv) isa dm-decision-in;
            fetch {{ "decision_id": $dec.id, "version_id": $sv.id }};
        """
        dv_map_res = fetch_query(driver, dv_q)
        dv_map = {r["decision_id"]: r["version_id"] for r in dv_map_res}

        # Experiments
        exp_q = f"""
            match $exp isa dm-experiment;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $exp, domain: $d) isa dm-in-domain;
            fetch {{ "id": $exp.id, "name": $exp.name, "hypothesis": $exp.dm-hypothesis,
                    "status": $exp.dm-experiment-status, "created": $exp.created-at }};
        """
        experiments = fetch_query(driver, exp_q)

        # Errors
        err_q = f"""
            match $err isa dm-representation-error;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $err, domain: $d) isa dm-in-domain;
            fetch {{ "id": $err.id, "name": $err.name, "type": $err.dm-error-type,
                    "severity": $err.dm-error-severity, "status": $err.dm-error-status,
                    "description": $err.description }};
        """
        errors = fetch_query(driver, err_q)

        # Goals + evaluations
        goal_q = f"""
            match $g isa dm-goal;
                  $d isa dm-domain, has id "{eid}";
                  (system: $d, goal: $g) isa dm-system-goal;
            fetch {{ "id": $g.id, "name": $g.name, "description": $g.description,
                    "phase": $g.dm-phase-number }};
        """
        goals = fetch_query(driver, goal_q)

        goal_evals_map = {}
        for g in goals:
            gid = escape_string(g.get("id", ""))
            eval_q = f"""
                match $e isa dm-goal-eval;
                      $g isa dm-goal, has id "{gid}";
                      (goal: $g, evaluation: $e) isa dm-goal-evaluation;
                fetch {{ "id": $e.id, "name": $e.name,
                        "criterion_type": $e.dm-evaluation-criterion-type,
                        "success_condition": $e.dm-evaluation-success-condition }};
            """
            goal_evals_map[g.get("id")] = fetch_query(driver, eval_q)

        # Phase entities grouped by type
        phase_items = {}
        for ptype in ["dm-entity-schema", "dm-source-schema", "dm-derivation-skill", "dm-analysis-skill"]:
            pq = f"""
                match $p isa {ptype};
                      $d isa dm-domain, has id "{eid}";
                      (subject: $p, domain: $d) isa dm-in-domain;
                fetch {{ "id": $p.id, "name": $p.name, "feasibility": $p.dm-feasibility,
                        "phase": $p.dm-phase-number }};
            """
            phase_items[ptype] = fetch_query(driver, pq)

        # Count open design gaps per phase entity
        open_gap_counts = {}
        gap_count_q = f"""
            match $g isa dm-design-gap, has dm-error-status "open";
                  $d isa dm-domain, has id "{eid}";
                  (subject: $g, domain: $d) isa dm-in-domain;
            fetch {{ "id": $g.id, "phase": $g.dm-phase-number }};
        """
        for row in fetch_query(driver, gap_count_q):
            pn = row.get("phase")
            if pn is not None:
                open_gap_counts[pn] = open_gap_counts.get(pn, 0) + 1

    out({
        "success": True,
        "domain": domain,
        "versions": versions,
        "decisions": decisions,
        "decision_version_map": dv_map,
        "experiments": experiments,
        "errors": errors,
        "goals": goals,
        "goal_evaluations": goal_evals_map,
        "phase_items": phase_items,
        "open_gap_counts_by_phase": open_gap_counts,
    })


# =============================================================================
# SKILL SNAPSHOTS
# =============================================================================

# File type map: (glob_pattern, dm-file-type, format)
# Patterns are matched against file names (not paths)
_SKILL_FILE_RULES = [
    ("schema.tql", "schema", "typeql"),
    ("SKILL.md", "prompt-short", "markdown"),
    ("USAGE.md", "prompt-full", "markdown"),
    ("skill.yaml", "manifest", "yaml"),
]


def _discover_skill_files(skill_dir: Path) -> list[tuple[Path, str, str]]:
    """
    Walk skill_dir and return (path, dm-file-type, format) for all capturable files.
    Returns list of tuples sorted by file type then name.
    """
    found = []
    if not skill_dir.is_dir():
        return found

    for path in sorted(skill_dir.iterdir()):
        if not path.is_file():
            continue
        fname = path.name
        for pattern, ftype, fmt in _SKILL_FILE_RULES:
            if fname == pattern:
                found.append((path, ftype, fmt))
                break
        else:
            # Main Python CLI script: *.py matching skill dir name
            if fname.endswith(".py") and fname == skill_dir.name + ".py":
                found.append((path, "script", "python"))

    # tests/ directory
    tests_dir = skill_dir / "tests"
    if tests_dir.is_dir():
        for path in sorted(tests_dir.glob("*.py")):
            if path.is_file():
                found.append((path, "test", "python"))

    # experiments/ directory
    experiments_dir = skill_dir / "experiments"
    if experiments_dir.is_dir():
        for path in sorted(experiments_dir.iterdir()):
            if path.is_file() and path.suffix in (".py", ".ipynb"):
                found.append((path, "experiment", path.suffix.lstrip(".")))

    return found


def _insert_skill_file_tx(tx, snapshot_id: str, path: Path, ftype: str, fmt: str,
                          plan_order: int | None = None) -> str:
    """Insert one dm-skill-file entity and link it to snapshot within an open transaction."""
    content = path.read_text(encoding="utf-8", errors="replace")
    file_id = generate_id("dm-skill-file")
    ts = get_timestamp()

    clauses = [
        s("id", file_id),
        s("name", path.name),
        dt("created-at", ts),
        s("dm-file-type", ftype),
        s("format", fmt),
    ]
    if plan_order is not None:
        clauses.append(num("dm-plan-order", plan_order))

    if should_cache(content):
        cache_result = save_to_cache(file_id, content, "text/plain")
        if cache_result:
            clauses.append(s("cache-path", cache_result["cache_path"]))
            clauses.append(num("file-size", cache_result["file_size"]))
    else:
        clauses.append(s("content", content))

    insert_entity(tx, "dm-skill-file", clauses)
    insert_relation(tx, "dm-snapshot-contains", {
        "snapshot": ("dm-skill-snapshot", snapshot_id),
        "file": ("dm-skill-file", file_id),
    })
    return file_id


def _insert_skill_file(driver, snapshot_id: str, path: Path, ftype: str, fmt: str,
                       plan_order: int | None = None) -> str:
    """Insert one dm-skill-file entity and link it to snapshot using its own transaction."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        file_id = _insert_skill_file_tx(tx, snapshot_id, path, ftype, fmt, plan_order)
        tx.commit()
    return file_id


def cmd_snapshot_skill(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    skill_dir = Path(args.skill_dir)
    if not skill_dir.is_dir():
        out({"success": False, "error": f"Skill directory not found: {args.skill_dir}"})
        return

    repo_dir = args.repo_dir or "."
    git = get_git_metadata(repo_dir)

    if hasattr(args, "commit") and args.commit:
        git["commit"] = args.commit

    domain_id = args.domain_id
    eid = escape_string(domain_id)

    with get_driver() as driver:
        # Idempotency: skip if this commit already snapshotted for this domain
        if git["commit"]:
            check_q = f"""
                match $sv isa dm-skill-snapshot, has dm-git-commit "{escape_string(git['commit'])}";
                      $d isa dm-domain, has id "{eid}";
                      (skill-snapshot: $sv, domain: $d) isa dm-version-of;
                fetch {{ "id": $sv.id, "tag": $sv.dm-version-tag }};
            """
            existing = fetch_query(driver, check_q)
            if existing:
                out({
                    "success": True,
                    "status": "already_snapshotted",
                    "id": existing[0].get("id"),
                    "tag": existing[0].get("tag"),
                    "commit": git["commit"],
                })
                return

        # Find parent snapshot for dm-supercedes
        parent_snapshot_id = None
        if git["parent"]:
            parent_sha = git["parent"].split()[0]
            parent_q = f"""
                match $sv isa dm-skill-snapshot, has dm-git-commit "{escape_string(parent_sha)}";
                      $d isa dm-domain, has id "{eid}";
                      (skill-snapshot: $sv, domain: $d) isa dm-version-of;
                fetch {{ "id": $sv.id }};
            """
            parent_res = fetch_query(driver, parent_q)
            if parent_res:
                parent_snapshot_id = parent_res[0].get("id")

        # Build snapshot entity
        snapshot_id = generate_id("dm-skill-snapshot")
        ts = get_timestamp()
        tag = args.version or f"snapshot-{ts[:10]}"

        clauses = [
            s("id", snapshot_id),
            s("name", tag),
            dt("created-at", ts),
            s("dm-version-tag", tag),
            s("format", "text"),
        ]
        if git["commit"]:
            clauses.append(s("dm-git-commit", git["commit"]))
        if git["repo"]:
            clauses.append(s("dm-git-repo", git["repo"]))
        if git["branch"]:
            clauses.append(s("dm-git-branch", git["branch"]))
        if git["message"]:
            clauses.append(s("dm-git-message", git["message"]))

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-skill-snapshot", clauses)

            insert_relation(tx, "dm-version-of", {
                "skill-snapshot": ("dm-skill-snapshot", snapshot_id),
                "domain": ("dm-domain", domain_id),
            })

            if parent_snapshot_id:
                insert_relation(tx, "dm-supercedes", {
                    "newer-snapshot": ("dm-skill-snapshot", snapshot_id),
                    "older-snapshot": ("dm-skill-snapshot", parent_snapshot_id),
                })

            tx.commit()

        # Discover and capture files (within the same driver context)
        files = _discover_skill_files(skill_dir)
        captured = []
        for path, ftype, fmt in files:
            file_id = _insert_skill_file(driver, snapshot_id, path, ftype, fmt)
            captured.append({"id": file_id, "name": path.name, "type": ftype, "format": fmt})

    out({
        "success": True,
        "id": snapshot_id,
        "tag": tag,
        "commit": git["commit"],
        "branch": git["branch"],
        "message": git["message"],
        "parent_snapshot_id": parent_snapshot_id,
        "files_captured": len(captured),
        "files": captured,
    })


def cmd_snapshot_schema(args):
    """DEPRECATED: use snapshot-skill instead. Kept for backward compatibility."""
    print(
        "Warning: snapshot-schema is deprecated. Use snapshot-skill --skill-dir instead.",
        file=sys.stderr,
    )
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    # Build a minimal args-like object to delegate to cmd_snapshot_skill
    # with the schema file's parent directory as skill_dir
    schema_path = Path(args.schema_file)
    if not schema_path.exists():
        out({"success": False, "error": f"Schema file not found: {args.schema_file}"})
        return

    class _FakeArgs:
        domain_id = args.domain_id
        skill_dir = str(schema_path.parent)
        version = getattr(args, "version", None)
        repo_dir = getattr(args, "repo_dir", ".")
        commit = getattr(args, "commit", None)

    cmd_snapshot_skill(_FakeArgs())


def cmd_set_task(args):
    """Set (or update) the natural-language task for a domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            update_attr(tx, "dm-domain", args.domain_id, "dm-skill-task", args.task)
            tx.commit()

    out({"success": True, "domain_id": args.domain_id, "task": args.task})


def cmd_list_versions(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    eid = escape_string(args.domain_id)
    q = f"""
        match $sv isa dm-skill-snapshot;
              $d isa dm-domain, has id "{eid}";
              (skill-snapshot: $sv, domain: $d) isa dm-version-of;
        fetch {{ "id": $sv.id, "tag": $sv.dm-version-tag, "commit": $sv.dm-git-commit,
                "branch": $sv.dm-git-branch, "message": $sv.dm-git-message,
                "created": $sv.created-at }};
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    out({"success": True, "domain_id": args.domain_id, "count": len(results), "versions": results})


def cmd_list_files(args):
    """List all dm-skill-file entities within a snapshot."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    sid = escape_string(args.snapshot_id)
    q = f"""
        match $snap isa dm-skill-snapshot, has id "{sid}";
              $f isa dm-skill-file;
              (snapshot: $snap, file: $f) isa dm-snapshot-contains;
              $ftype $f.dm-file-type;
              $fname $f.name;
        fetch {{ "id": $f.id, "name": $f.name, "type": $f.dm-file-type,
                "format": $f.format, "created": $f.created-at }};
    """
    # Simpler query that works without binding attribute vars
    q = f"""
        match $snap isa dm-skill-snapshot, has id "{sid}";
              $f isa dm-skill-file;
              (snapshot: $snap, file: $f) isa dm-snapshot-contains;
        fetch {{ "id": $f.id, "name": $f.name, "type": $f.dm-file-type,
                "format": $f.format, "order": $f.dm-plan-order, "created": $f.created-at }};
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    out({"success": True, "snapshot_id": args.snapshot_id, "count": len(results), "files": results})


def cmd_show_file(args):
    """Show content of a captured dm-skill-file."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    fid = escape_string(args.file_id)
    q = f"""
        match $f isa dm-skill-file, has id "{fid}";
        fetch {{ "id": $f.id, "name": $f.name, "type": $f.dm-file-type,
                "format": $f.format, "content": $f.content,
                "cache-path": $f.cache-path }};
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    if not results:
        out({"success": False, "error": f"File not found: {args.file_id}"})
        return

    row = results[0]
    content = row.get("content")
    cache_path = row.get("cache-path")

    # Load from cache if content not inline
    if not content and cache_path:
        try:
            from skillful_alhazen.utils.cache import load_from_cache_text
            content = load_from_cache_text(cache_path)
        except Exception:
            content = None

    out({
        "success": True,
        "id": row.get("id"),
        "name": row.get("name"),
        "type": row.get("type"),
        "format": row.get("format"),
        "content": content,
        "cache_path": cache_path,
    })


def cmd_add_plan(args):
    """Attach a plan document (Markdown file) to an existing snapshot."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    plan_path = Path(args.plan_file)
    if not plan_path.exists():
        out({"success": False, "error": f"Plan file not found: {args.plan_file}"})
        return

    order = args.order if hasattr(args, "order") and args.order else None
    with get_driver() as driver:
        file_id = _insert_skill_file(
            driver, args.snapshot_id, plan_path, "plan", "markdown", plan_order=order
        )
        if args.description:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                q = f"""
                    match $f isa dm-skill-file, has id "{escape_string(file_id)}";
                    insert $f has description "{escape_string(args.description)}";
                """
                tx.query(q).resolve()
                tx.commit()

    out({
        "success": True,
        "id": file_id,
        "snapshot_id": args.snapshot_id,
        "plan_file": str(plan_path),
        "order": order,
    })


def cmd_install_hook(args):
    """Write a post-commit hook that auto-snapshots the skill on every commit."""
    repo_dir = Path(args.repo_dir or ".")
    hook_path = repo_dir / ".git" / "hooks" / "post-commit"

    if not (repo_dir / ".git").exists():
        out({"success": False, "error": f"Not a git repository: {repo_dir}"})
        return

    domain_id = escape_string(args.domain_id)
    skill_dir = escape_string(args.skill_dir)

    hook_snippet = f"""
# --- domain-modeling: auto-snapshot skill on commit ---
uv run python .claude/skills/domain-modeling/domain_modeling.py \\
    snapshot-skill \\
    --domain-id "{domain_id}" \\
    --skill-dir "{skill_dir}" \\
    --repo-dir "$(git rev-parse --show-toplevel)" \\
    2>/dev/null || true
# --- end domain-modeling ---
"""

    if hook_path.exists():
        existing = hook_path.read_text()
        if "domain-modeling: auto-snapshot" in existing:
            out({"success": True, "status": "already_installed", "hook_path": str(hook_path)})
            return
        hook_path.write_text(existing.rstrip() + "\n" + hook_snippet)
    else:
        hook_path.write_text("#!/bin/bash\n" + hook_snippet)

    print(f"Run: chmod +x {hook_path}", file=sys.stderr)
    out({
        "success": True,
        "status": "installed",
        "hook_path": str(hook_path),
        "note": f"Make executable with: chmod +x {hook_path}",
    })


# =============================================================================
# DESIGN DECISIONS
# =============================================================================


def cmd_add_decision(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    decision_id = generate_id("dm-decision")
    ts = get_timestamp()

    clauses = [
        s("id", decision_id),
        s("name", args.summary[:80] if args.summary else "decision"),
        dt("created-at", ts),
        s("dm-decision-type", args.type),
        s("dm-decision-summary", args.summary),
    ]
    if args.alternatives:
        clauses.append(s("dm-alternatives-text", args.alternatives))

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-design-decision", clauses)

            # Link to domain
            insert_relation(tx, "dm-in-domain", {
                "subject": ("dm-design-decision", decision_id),
                "domain": ("dm-domain", args.domain_id),
            })

            # Link to skill snapshot if specified
            if args.version_id:
                insert_relation(tx, "dm-decision-in", {
                    "decision": ("dm-design-decision", decision_id),
                    "skill-snapshot": ("dm-skill-snapshot", args.version_id),
                })

            tx.commit()

    out({"success": True, "id": decision_id, "type": args.type, "summary": args.summary})


def cmd_add_rationale(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    rationale_id = generate_id("dm-rationale")
    ts = get_timestamp()

    clauses = [
        s("id", rationale_id),
        s("name", f"rationale-{ts[:10]}"),
        dt("created-at", ts),
        s("content", args.rationale),
    ]
    if args.alternatives:
        clauses.append(s("description", args.alternatives))

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-design-rationale", clauses)

            insert_relation(tx, "dm-rationale-for", {
                "rationale": ("dm-design-rationale", rationale_id),
                "decision": ("dm-design-decision", args.decision_id),
            })

            tx.commit()

    out({"success": True, "id": rationale_id, "decision_id": args.decision_id})


def cmd_link_gap(args):
    """Link a schema-gap ID to a design decision (stored as dm-linked-gap-id attribute)."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    decision_id = escape_string(args.decision_id)
    gap_id = escape_string(args.gap_id)

    q = f"""
        match $d isa dm-design-decision, has id "{decision_id}";
        insert $d has dm-linked-gap-id "{gap_id}";
    """
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(q).resolve()
            tx.commit()

    out({"success": True, "decision_id": args.decision_id, "gap_id": args.gap_id})


def cmd_list_decisions(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    eid = escape_string(args.domain_id)
    type_filter = f', has dm-decision-type "{escape_string(args.type)}"' if args.type else ""

    q = f"""
        match $d isa dm-design-decision{type_filter};
              $dom isa dm-domain, has id "{eid}";
              (subject: $d, domain: $dom) isa dm-in-domain;
        fetch {{ "id": $d.id, "type": $d.dm-decision-type, "summary": $d.dm-decision-summary,
                "alternatives": $d.dm-alternatives-text, "created": $d.created-at }};
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    out({"success": True, "domain_id": args.domain_id, "count": len(results), "decisions": results})


# =============================================================================
# EXPERIMENTS
# =============================================================================


def cmd_start_experiment(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    exp_id = generate_id("dm-experiment")
    ts = get_timestamp()

    clauses = [
        s("id", exp_id),
        s("name", args.hypothesis[:80] if args.hypothesis else "experiment"),
        dt("created-at", ts),
        s("dm-hypothesis", args.hypothesis),
        s("dm-experiment-status", "running"),
    ]

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-experiment", clauses)

            insert_relation(tx, "dm-in-domain", {
                "subject": ("dm-experiment", exp_id),
                "domain": ("dm-domain", args.domain_id),
            })

            if args.version_id:
                insert_relation(tx, "dm-tests", {
                    "experiment": ("dm-experiment", exp_id),
                    "subject": ("dm-skill-snapshot", args.version_id),
                })

            tx.commit()

    out({"success": True, "id": exp_id, "hypothesis": args.hypothesis, "status": "running"})


def cmd_record_result(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    result_id = generate_id("dm-result")
    ts = get_timestamp()

    clauses = [
        s("id", result_id),
        s("name", f"{args.metric}={args.value}"),
        dt("created-at", ts),
        s("dm-metric-name", args.metric),
        num("dm-metric-value", float(args.value)),
    ]
    if args.notes:
        clauses.append(s("content", args.notes))

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-experiment-result", clauses)

            insert_relation(tx, "dm-result-of", {
                "result": ("dm-experiment-result", result_id),
                "experiment": ("dm-experiment", args.experiment_id),
            })

            tx.commit()

    out({
        "success": True,
        "id": result_id,
        "experiment_id": args.experiment_id,
        "metric": args.metric,
        "value": args.value,
    })


def cmd_complete_experiment(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            update_attr(tx, "dm-experiment", args.experiment_id, "dm-experiment-status", "complete")
            tx.commit()

    out({"success": True, "id": args.experiment_id, "status": "complete"})


def cmd_list_experiments(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    eid = escape_string(args.domain_id)
    status_filter = (
        f', has dm-experiment-status "{escape_string(args.status)}"' if args.status else ""
    )

    q = f"""
        match $e isa dm-experiment{status_filter};
              $dom isa dm-domain, has id "{eid}";
              (subject: $e, domain: $dom) isa dm-in-domain;
        fetch {{ "id": $e.id, "hypothesis": $e.dm-hypothesis,
                "status": $e.dm-experiment-status, "created": $e.created-at }};
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    out({"success": True, "domain_id": args.domain_id, "count": len(results), "experiments": results})


# =============================================================================
# REPRESENTATION ERRORS
# =============================================================================


def cmd_report_error(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    error_id = generate_id("dm-error")
    ts = get_timestamp()

    clauses = [
        s("id", error_id),
        s("name", args.summary[:80] if args.summary else "error"),
        dt("created-at", ts),
        s("dm-error-type", args.type),
        s("dm-error-severity", args.severity or "moderate"),
        s("dm-error-status", "open"),
        s("description", args.summary),
    ]

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-representation-error", clauses)

            insert_relation(tx, "dm-in-domain", {
                "subject": ("dm-representation-error", error_id),
                "domain": ("dm-domain", args.domain_id),
            })

            if args.version_id:
                insert_relation(tx, "dm-error-in", {
                    "error": ("dm-representation-error", error_id),
                    "skill-snapshot": ("dm-skill-snapshot", args.version_id),
                })

            tx.commit()

    out({
        "success": True,
        "id": error_id,
        "type": args.type,
        "severity": args.severity or "moderate",
        "status": "open",
    })


def cmd_resolve_error(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            update_attr(tx, "dm-representation-error", args.error_id, "dm-error-status", "resolved")

            if args.decision_id:
                insert_relation(tx, "dm-resolved-by", {
                    "error": ("dm-representation-error", args.error_id),
                    "resolution": ("dm-design-decision", args.decision_id),
                })

            tx.commit()

    out({"success": True, "id": args.error_id, "status": "resolved", "decision_id": args.decision_id})


def cmd_list_errors(args):
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    eid = escape_string(args.domain_id)
    status_filter = (
        f', has dm-error-status "{escape_string(args.status)}"' if args.status else ""
    )

    q = f"""
        match $e isa dm-representation-error{status_filter};
              $dom isa dm-domain, has id "{eid}";
              (subject: $e, domain: $dom) isa dm-in-domain;
        fetch {{ "id": $e.id, "type": $e.dm-error-type, "severity": $e.dm-error-severity,
                "status": $e.dm-error-status, "description": $e.description,
                "created": $e.created-at }};
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    out({"success": True, "domain_id": args.domain_id, "count": len(results), "errors": results})


# =============================================================================
# EXPORT
# =============================================================================


def cmd_export_design(args):
    """Export an annotated Markdown design changelog ordered by commit history."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    domain_id = args.domain_id
    eid = escape_string(domain_id)

    with get_driver() as driver:
        # Domain info
        d_q = f"""
            match $d isa dm-domain, has id "{eid}";
            fetch {{ "id": $d.id, "name": $d.name, "skill": $d.dm-skill-name, "task": $d.dm-skill-task }};
        """
        d_res = fetch_query(driver, d_q)
        if not d_res:
            out({"success": False, "error": f"Domain not found: {domain_id}"})
            return
        domain = d_res[0]

        # Versions (sorted by created-at in Python)
        v_q = f"""
            match $sv isa dm-skill-snapshot;
                  $d isa dm-domain, has id "{eid}";
                  (skill-snapshot: $sv, domain: $d) isa dm-version-of;
            fetch {{ "id": $sv.id, "tag": $sv.dm-version-tag, "commit": $sv.dm-git-commit,
                    "branch": $sv.dm-git-branch, "message": $sv.dm-git-message,
                    "created": $sv.created-at }};
        """
        versions = fetch_query(driver, v_q)
        versions_by_id = {v.get("id"): v for v in versions}

        # Decisions + version mapping
        dec_q = f"""
            match $dec isa dm-design-decision;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $dec, domain: $d) isa dm-in-domain;
            fetch {{ "id": $dec.id, "type": $dec.dm-decision-type,
                    "summary": $dec.dm-decision-summary,
                    "alternatives": $dec.dm-alternatives-text,
                    "created": $dec.created-at }};
        """
        decisions = fetch_query(driver, dec_q)

        dv_q = f"""
            match $dec isa dm-design-decision;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $dec, domain: $d) isa dm-in-domain;
                  $sv isa dm-skill-snapshot;
                  (decision: $dec, skill-snapshot: $sv) isa dm-decision-in;
            fetch {{ "decision_id": $dec.id, "version_id": $sv.id }};
        """
        dv_map = {r["decision_id"]: r["version_id"] for r in fetch_query(driver, dv_q)}

        # Rationales
        rat_q = f"""
            match $rat isa dm-design-rationale;
                  $dec isa dm-design-decision;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $dec, domain: $d) isa dm-in-domain;
                  (rationale: $rat, decision: $dec) isa dm-rationale-for;
            fetch {{ "decision_id": $dec.id, "rationale_content": $rat.content }};
        """
        rat_map: dict[str, list] = {}
        for r in fetch_query(driver, rat_q):
            rat_map.setdefault(r["decision_id"], []).append(r.get("rationale_content", ""))

        # Experiments
        exp_q = f"""
            match $exp isa dm-experiment;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $exp, domain: $d) isa dm-in-domain;
            fetch {{ "id": $exp.id, "hypothesis": $exp.dm-hypothesis,
                    "status": $exp.dm-experiment-status, "created": $exp.created-at }};
        """
        experiments = fetch_query(driver, exp_q)

        # Experiment -> version mapping
        ev_q = f"""
            match $exp isa dm-experiment;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $exp, domain: $d) isa dm-in-domain;
                  $sv isa dm-skill-snapshot;
                  (experiment: $exp, subject: $sv) isa dm-tests;
            fetch {{ "exp_id": $exp.id, "version_id": $sv.id }};
        """
        ev_map = {r["exp_id"]: r["version_id"] for r in fetch_query(driver, ev_q)}

        # Results
        res_q = f"""
            match $res isa dm-experiment-result;
                  $exp isa dm-experiment;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $exp, domain: $d) isa dm-in-domain;
                  (result: $res, experiment: $exp) isa dm-result-of;
            fetch {{ "exp_id": $exp.id, "metric": $res.dm-metric-name,
                    "value": $res.dm-metric-value, "notes": $res.content }};
        """
        results_map: dict[str, list] = {}
        for r in fetch_query(driver, res_q):
            results_map.setdefault(r["exp_id"], []).append(r)

        # Errors
        err_q = f"""
            match $err isa dm-representation-error;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $err, domain: $d) isa dm-in-domain;
            fetch {{ "id": $err.id, "type": $err.dm-error-type, "severity": $err.dm-error-severity,
                    "status": $err.dm-error-status, "description": $err.description,
                    "created": $err.created-at }};
        """
        errors = fetch_query(driver, err_q)

        erv_q = f"""
            match $err isa dm-representation-error;
                  $d isa dm-domain, has id "{eid}";
                  (subject: $err, domain: $d) isa dm-in-domain;
                  $sv isa dm-skill-snapshot;
                  (error: $err, skill-snapshot: $sv) isa dm-error-in;
            fetch {{ "err_id": $err.id, "version_id": $sv.id }};
        """
        erv_map = {r["err_id"]: r["version_id"] for r in fetch_query(driver, erv_q)}

    # --- Build Markdown ---
    lines = []
    domain_name = domain.get("name", domain_id)
    skill = domain.get("skill", "")
    lines.append(f"# Design Changelog: {domain_name}")
    if skill:
        lines.append(f"\n_Skill: {skill}_  ")
    lines.append(f"_Domain ID: {domain_id}_\n")

    # Group items by version
    decs_by_version: dict[str | None, list] = {}
    for d in decisions:
        vid = dv_map.get(d["id"])
        decs_by_version.setdefault(vid, []).append(d)

    exps_by_version: dict[str | None, list] = {}
    for e in experiments:
        vid = ev_map.get(e["id"])
        exps_by_version.setdefault(vid, []).append(e)

    errs_by_version: dict[str | None, list] = {}
    for e in errors:
        vid = erv_map.get(e["id"])
        errs_by_version.setdefault(vid, []).append(e)

    def render_decisions(decs):
        if not decs:
            return
        lines.append("\n### Design Decisions\n")
        for d in decs:
            dtype = d.get("type") or "?"
            summary = d.get("summary") or d.get("name") or ""
            lines.append(f"- **[{dtype}]** {summary}")
            alts = d.get("alternatives")
            if alts:
                lines.append(f"  - _Alternatives:_ {alts}")
            for rat in rat_map.get(d["id"], []):
                if rat:
                    lines.append(f"  - _Rationale:_ {rat}")

    def render_experiments(exps):
        if not exps:
            return
        lines.append("\n### Experiments\n")
        for e in exps:
            hyp = e.get("hypothesis") or ""
            status = e.get("status") or "?"
            lines.append(f"- **({status})** {hyp}")
            for r in results_map.get(e["id"], []):
                metric = r.get("metric") or ""
                value = r.get("value")
                notes = r.get("notes") or ""
                val_str = f"{metric} = {value}" if value is not None else metric
                result_line = f"  - _Result:_ {val_str}"
                if notes:
                    result_line += f" — {notes}"
                lines.append(result_line)

    def render_errors(errs):
        if not errs:
            return
        lines.append("\n### Representation Errors\n")
        for e in errs:
            etype = e.get("type") or "?"
            severity = e.get("severity") or "?"
            status = e.get("status") or "?"
            desc = e.get("description") or ""
            lines.append(f"- **[{etype}]** _{severity}_ ({status}): {desc}")

    # Versioned sections
    for v in versions:
        vid = v.get("id")
        tag = v.get("tag") or "?"
        commit = v.get("commit") or ""
        branch = v.get("branch") or ""
        message = v.get("message") or ""
        created = v.get("created")
        if isinstance(created, datetime):
            created = created.isoformat()

        lines.append(f"\n---\n")
        lines.append(f"## {tag} — {message}")
        if commit:
            lines.append(f"\n**Commit:** `{commit[:12]}`  ")
        if branch:
            lines.append(f"**Branch:** {branch}  ")
        if created:
            lines.append(f"**Date:** {created}")

        render_decisions(decs_by_version.get(vid, []))
        render_experiments(exps_by_version.get(vid, []))
        render_errors(errs_by_version.get(vid, []))

    # Unversioned items
    unversioned_decs = decs_by_version.get(None, [])
    unversioned_exps = exps_by_version.get(None, [])
    unversioned_errs = errs_by_version.get(None, [])

    if unversioned_decs or unversioned_exps or unversioned_errs:
        lines.append("\n---\n")
        lines.append("## Unversioned Items")
        render_decisions(unversioned_decs)
        render_experiments(unversioned_exps)
        render_errors(unversioned_errs)

    markdown = "\n".join(lines)
    out({"success": True, "domain_id": domain_id, "markdown": markdown})


# =============================================================================
# 5-PHASE SYSTEM DESIGN WORKFLOW
# =============================================================================


def cmd_define_goal(args):
    """Insert dm-goal + dm-system-goal relation to domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    goal_id = generate_id("dm-goal")
    ts = get_timestamp()

    clauses = [
        s("id", goal_id),
        s("name", args.name),
        dt("created-at", ts),
    ]
    if args.description:
        clauses.append(s("description", args.description))
    clauses.append(num("dm-phase-number", 1))

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-goal", clauses)
            insert_relation(tx, "dm-system-goal", {
                "system": ("dm-domain", args.domain_id),
                "goal": ("dm-goal", goal_id),
            })
            insert_relation(tx, "dm-in-domain", {
                "subject": ("dm-goal", goal_id),
                "domain": ("dm-domain", args.domain_id),
            })
            tx.commit()

    out({"success": True, "id": goal_id, "name": args.name, "domain_id": args.domain_id})


def cmd_add_evaluation(args):
    """Insert dm-goal-eval + dm-goal-evaluation relation to goal."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    eval_id = generate_id("dm-goal-eval")
    ts = get_timestamp()

    clauses = [
        s("id", eval_id),
        s("name", args.name),
        s("description", args.description),
        dt("created-at", ts),
    ]
    clauses.append(num("dm-phase-number", 1))
    if args.criterion_type:
        clauses.append(s("dm-evaluation-criterion-type", args.criterion_type))
    if args.success_condition:
        clauses.append(s("dm-evaluation-success-condition", args.success_condition))
    if args.approach:
        clauses.append(s("dm-evaluation-approach", args.approach))

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-goal-eval", clauses)
            insert_relation(tx, "dm-goal-evaluation", {
                "goal": ("dm-goal", args.goal_id),
                "evaluation": ("dm-goal-eval", eval_id),
            })
            insert_relation(tx, "dm-in-domain", {
                "subject": ("dm-goal-eval", eval_id),
                "domain": ("dm-domain", args.domain_id),
            })
            tx.commit()

    out({"success": True, "id": eval_id, "goal_id": args.goal_id, "name": args.name})


def cmd_show_goal(args):
    """Fetch goal + all evaluations for a domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    eid = escape_string(args.domain_id)

    with get_driver() as driver:
        goal_q = f"""
            match $g isa dm-goal;
                  $d isa dm-domain, has id "{eid}";
                  (system: $d, goal: $g) isa dm-system-goal;
            fetch {{ "id": $g.id, "name": $g.name, "description": $g.description,
                    "phase": $g.dm-phase-number, "created": $g.created-at }};
        """
        goals = fetch_query(driver, goal_q)

        evaluations = []
        for goal in goals:
            gid = escape_string(goal.get("id", ""))
            eval_q = f"""
                match $e isa dm-goal-eval;
                      $g isa dm-goal, has id "{gid}";
                      (goal: $g, evaluation: $e) isa dm-goal-evaluation;
                fetch {{ "id": $e.id, "name": $e.name, "description": $e.description,
                        "criterion_type": $e.dm-evaluation-criterion-type,
                        "success_condition": $e.dm-evaluation-success-condition,
                        "approach": $e.dm-evaluation-approach,
                        "created": $e.created-at }};
            """
            evals = fetch_query(driver, eval_q)
            evaluations.append({"goal": goal, "evaluations": evals})

    out({"success": True, "domain_id": args.domain_id, "goals": evaluations})


def cmd_ingest_design_doc(args):
    """Store design document and link to domain via aboutness relation."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    doc_path = Path(args.file)
    if not doc_path.exists():
        out({"success": False, "error": f"File not found: {args.file}"})
        return

    with get_driver() as driver:
        file_id = _insert_skill_file(
            driver,
            args.snapshot_id if hasattr(args, "snapshot_id") and args.snapshot_id else args.domain_id,
            doc_path,
            "design-doc",
            args.format or "markdown",
        )
        # Link to domain via a description update on the file
        if args.description:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                q = f"""
                    match $f isa dm-skill-file, has id "{escape_string(file_id)}";
                    insert $f has description "{escape_string(args.description)}";
                """
                tx.query(q).resolve()
                tx.commit()

    out({
        "success": True,
        "id": file_id,
        "domain_id": args.domain_id,
        "file": str(doc_path),
        "format": args.format or "markdown",
    })


_PHASE_ENTITY_TYPES = [
    "dm-entity-schema",
    "dm-source-schema",
    "dm-derivation-skill",
    "dm-analysis-skill",
    "dm-goal",
    "dm-goal-eval",
    "dm-design-gap",
]


def _resolve_phase_entity_type(driver, entity_id: str) -> str | None:
    """Probe each known phase entity type to find the concrete type of this id."""
    eid = escape_string(entity_id)
    for etype in _PHASE_ENTITY_TYPES:
        q = f'match $p isa {etype}, has id "{eid}"; fetch {{ "id": $p.id }};'
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(q).resolve())
        if results:
            return etype
    return None


def _insert_phase_entity(driver, entity_type: str, domain_id: str, name: str,
                          phase_number: int, description: str = None,
                          feasibility: str = "unknown",
                          input_types: str = None, output_types: str = None,
                          depends_on_id: str = None) -> str:
    """Insert a phase entity (dm-entity-schema, dm-source-schema, etc.) + dm-in-domain."""
    entity_id = generate_id(entity_type)
    ts = get_timestamp()

    clauses = [
        s("id", entity_id),
        s("name", name),
        dt("created-at", ts),
        num("dm-phase-number", phase_number),
        s("dm-feasibility", feasibility),
    ]
    if description:
        clauses.append(s("description", description))
    if input_types:
        clauses.append(s("dm-input-types", input_types))
    if output_types:
        clauses.append(s("dm-output-types", output_types))

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        insert_entity(tx, entity_type, clauses)
        insert_relation(tx, "dm-in-domain", {
            "subject": (entity_type, entity_id),
            "domain": ("dm-domain", domain_id),
        })
        if depends_on_id:
            # depends_on_id could be any phase entity type — no isa hint, TypeDB infers from role
            match_str = f'$dep has id "{escape_string(depends_on_id)}";'
            match_str2 = f'$ent isa {entity_type}, has id "{escape_string(entity_id)}";'
            tx.query(f"match {match_str} {match_str2} insert (dependent: $ent, dependency: $dep) isa dm-phase-depends-on;").resolve()
        tx.commit()

    return entity_id


def cmd_add_entity_schema(args):
    """Insert dm-entity-schema + dm-in-domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        entity_id = _insert_phase_entity(
            driver, "dm-entity-schema", args.domain_id, args.name, 2,
            description=args.description,
            feasibility=args.feasibility or "unknown",
            depends_on_id=args.depends_on,
        )
    out({"success": True, "id": entity_id, "type": "dm-entity-schema", "domain_id": args.domain_id})


def cmd_add_source_schema(args):
    """Insert dm-source-schema + dm-in-domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        entity_id = _insert_phase_entity(
            driver, "dm-source-schema", args.domain_id, args.name, 3,
            description=args.description,
            feasibility=args.feasibility or "unknown",
            depends_on_id=args.depends_on,
        )
    out({"success": True, "id": entity_id, "type": "dm-source-schema", "domain_id": args.domain_id})


def cmd_add_derivation_skill(args):
    """Insert dm-derivation-skill + dm-in-domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        entity_id = _insert_phase_entity(
            driver, "dm-derivation-skill", args.domain_id, args.name, 4,
            description=args.description,
            feasibility=args.feasibility or "unknown",
            input_types=getattr(args, 'input_types', None),
            output_types=getattr(args, 'output_types', None),
            depends_on_id=args.depends_on,
        )
    out({"success": True, "id": entity_id, "type": "dm-derivation-skill", "domain_id": args.domain_id})


def cmd_add_analysis_skill(args):
    """Insert dm-analysis-skill + dm-in-domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        entity_id = _insert_phase_entity(
            driver, "dm-analysis-skill", args.domain_id, args.name, 5,
            description=args.description,
            feasibility=args.feasibility or "unknown",
            input_types=getattr(args, 'input_types', None),
            output_types=getattr(args, 'output_types', None),
            depends_on_id=args.depends_on,
        )
    out({"success": True, "id": entity_id, "type": "dm-analysis-skill", "domain_id": args.domain_id})


def cmd_add_phase_spec(args):
    """Insert dm-phase-spec + dm-phase-artifact(phase-subject, phase-spec) relation."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    spec_id = generate_id("dm-phase-spec")
    ts = get_timestamp()

    clauses = [
        s("id", spec_id),
        s("name", f"spec-{ts[:10]}"),
        dt("created-at", ts),
        s("content", args.content),
        s("format", "text"),
    ]
    if args.feasibility:
        clauses.append(s("dm-feasibility", args.feasibility))

    phase_id = args.phase_id

    with get_driver() as driver:
        phase_type = _resolve_phase_entity_type(driver, phase_id)
        if not phase_type:
            out({"success": False, "error": f"Phase entity not found: {phase_id}"})
            return
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-phase-spec", clauses)
            match_q = f'$ps isa {phase_type}, has id "{escape_string(phase_id)}";'
            spec_q = f'$sp isa dm-phase-spec, has id "{escape_string(spec_id)}";'
            rel_q = f"(phase-subject: $ps, phase-spec: $sp) isa dm-phase-artifact;"
            tx.query(f"match {match_q} {spec_q} insert {rel_q}").resolve()
            tx.commit()

    out({"success": True, "id": spec_id, "phase_id": phase_id})


def cmd_add_phase_gap(args):
    """Insert dm-design-gap + dm-phase-artifact(phase-subject, phase-gap) + dm-in-domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    gap_id = generate_id("dm-design-gap")
    ts = get_timestamp()

    clauses = [
        s("id", gap_id),
        s("name", args.description[:80]),
        s("description", args.description),
        dt("created-at", ts),
        s("dm-error-severity", args.severity or "moderate"),
        s("dm-error-status", "open"),
    ]

    phase_id = args.phase_id

    with get_driver() as driver:
        phase_type = _resolve_phase_entity_type(driver, phase_id)
        if not phase_type:
            out({"success": False, "error": f"Phase entity not found: {phase_id}"})
            return

        # Get phase number from the phase entity
        pn_q = f"""
            match $p isa {phase_type}, has id "{escape_string(phase_id)}",
                  has dm-phase-number $pn;
            fetch {{ "phase_number": $pn }};
        """
        pn_res = fetch_query(driver, pn_q)
        if pn_res:
            pn = pn_res[0].get("phase_number")
            if pn is not None:
                clauses.append(num("dm-phase-number", pn))

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_entity(tx, "dm-design-gap", clauses)
            match_q = f'$ps isa {phase_type}, has id "{escape_string(phase_id)}";'
            gap_q = f'$gp isa dm-design-gap, has id "{escape_string(gap_id)}";'
            rel_q = "(phase-subject: $ps, phase-gap: $gp) isa dm-phase-artifact;"
            tx.query(f"match {match_q} {gap_q} insert {rel_q}").resolve()
            # Link to domain
            insert_relation(tx, "dm-in-domain", {
                "subject": ("dm-design-gap", gap_id),
                "domain": ("dm-domain", args.domain_id),
            })
            tx.commit()

    out({"success": True, "id": gap_id, "phase_id": phase_id, "domain_id": args.domain_id})


def cmd_resolve_phase_gap(args):
    """Update dm-error-status to 'resolved'; optionally link to dm-design-decision."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            update_attr(tx, "dm-design-gap", args.gap_id, "dm-error-status", "resolved")
            if args.decision_id:
                insert_relation(tx, "dm-resolved-by", {
                    "error": ("dm-design-gap", args.gap_id),
                    "resolution": ("dm-design-decision", args.decision_id),
                })
            tx.commit()

    out({"success": True, "id": args.gap_id, "status": "resolved"})


def cmd_list_phase_gaps(args):
    """List dm-design-gap entities for a domain."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    eid = escape_string(args.domain_id)
    status = args.status or "open"
    status_filter = f', has dm-error-status "{escape_string(status)}"'

    q = f"""
        match $g isa dm-design-gap{status_filter};
              $d isa dm-domain, has id "{eid}";
              (subject: $g, domain: $d) isa dm-in-domain;
        fetch {{ "id": $g.id, "name": $g.name, "description": $g.description,
                "severity": $g.dm-error-severity, "status": $g.dm-error-status,
                "phase": $g.dm-phase-number, "created": $g.created-at }};
    """
    with get_driver() as driver:
        results = fetch_query(driver, q)

    out({"success": True, "domain_id": args.domain_id, "status": status,
         "count": len(results), "gaps": results})


def cmd_show_phase_item(args):
    """Fetch one phase entity with its specs and gaps."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    pid = escape_string(args.phase_id)

    with get_driver() as driver:
        phase_type = _resolve_phase_entity_type(driver, args.phase_id)
        if not phase_type:
            out({"success": False, "error": f"Phase item not found: {args.phase_id}"})
            return

        _HAS_IO = phase_type in ("dm-derivation-skill", "dm-analysis-skill")
        io_fields = ', "input_types": $p.dm-input-types, "output_types": $p.dm-output-types' if _HAS_IO else ""
        item_q = f"""
            match $p isa {phase_type}, has id "{pid}";
            fetch {{ "id": $p.id, "name": $p.name, "description": $p.description,
                    "feasibility": $p.dm-feasibility, "phase": $p.dm-phase-number{io_fields},
                    "created": $p.created-at }};
        """
        item_res = fetch_query(driver, item_q)
        if not item_res:
            out({"success": False, "error": f"Phase item not found: {args.phase_id}"})
            return
        item = item_res[0]

        spec_q = f"""
            match $p isa {phase_type}, has id "{pid}";
                  $sp isa dm-phase-spec;
                  (phase-subject: $p, phase-spec: $sp) isa dm-phase-artifact;
            fetch {{ "id": $sp.id, "content": $sp.content,
                    "feasibility": $sp.dm-feasibility, "created": $sp.created-at }};
        """
        specs = fetch_query(driver, spec_q)

        gap_q = f"""
            match $p isa {phase_type}, has id "{pid}";
                  $gp isa dm-design-gap;
                  (phase-subject: $p, phase-gap: $gp) isa dm-phase-artifact;
            fetch {{ "id": $gp.id, "name": $gp.name, "description": $gp.description,
                    "severity": $gp.dm-error-severity, "status": $gp.dm-error-status,
                    "created": $gp.created-at }};
        """
        gaps = fetch_query(driver, gap_q)

    out({"success": True, "item": item, "specs": specs, "gaps": gaps})


def cmd_export_design_phases(args):
    """Structured Markdown report: goal -> evaluations -> each phase entity with specs and gaps."""
    if not TYPEDB_AVAILABLE:
        out({"success": False, "error": "typedb-driver not installed"})
        return

    domain_id = args.domain_id
    eid = escape_string(domain_id)

    with get_driver() as driver:
        # Domain info
        d_q = f"""
            match $d isa dm-domain, has id "{eid}";
            fetch {{ "id": $d.id, "name": $d.name, "skill": $d.dm-skill-name }};
        """
        d_res = fetch_query(driver, d_q)
        if not d_res:
            out({"success": False, "error": f"Domain not found: {domain_id}"})
            return
        domain = d_res[0]

        # Goals
        goal_q = f"""
            match $g isa dm-goal;
                  $d isa dm-domain, has id "{eid}";
                  (system: $d, goal: $g) isa dm-system-goal;
            fetch {{ "id": $g.id, "name": $g.name, "description": $g.description }};
        """
        goals = fetch_query(driver, goal_q)

        # Evaluations per goal
        goal_evals = {}
        for g in goals:
            gid = escape_string(g.get("id", ""))
            eval_q = f"""
                match $e isa dm-goal-eval;
                      $g isa dm-goal, has id "{gid}";
                      (goal: $g, evaluation: $e) isa dm-goal-evaluation;
                fetch {{ "id": $e.id, "name": $e.name, "description": $e.description,
                        "criterion_type": $e.dm-evaluation-criterion-type,
                        "success_condition": $e.dm-evaluation-success-condition,
                        "approach": $e.dm-evaluation-approach }};
            """
            goal_evals[g.get("id")] = fetch_query(driver, eval_q)

        # Phase entities by type
        phase_types = [
            ("dm-entity-schema", 2, "Entity Schema"),
            ("dm-source-schema", 3, "Source Schema"),
            ("dm-derivation-skill", 4, "Derivation Skills"),
            ("dm-analysis-skill", 5, "Analysis Skills"),
        ]
        phase_data = {}
        for ptype, pnum, _ in phase_types:
            _has_io = ptype in ("dm-derivation-skill", "dm-analysis-skill")
            io_fields = ', "input_types": $p.dm-input-types, "output_types": $p.dm-output-types' if _has_io else ""
            pq = f"""
                match $p isa {ptype};
                      $d isa dm-domain, has id "{eid}";
                      (subject: $p, domain: $d) isa dm-in-domain;
                fetch {{ "id": $p.id, "name": $p.name, "description": $p.description,
                        "feasibility": $p.dm-feasibility{io_fields} }};
            """
            items = fetch_query(driver, pq)
            # For each item, get specs and gaps
            enriched = []
            for item in items:
                iid = escape_string(item.get("id", ""))
                sq = f"""
                    match $p isa {ptype}, has id "{iid}";
                          $sp isa dm-phase-spec;
                          (phase-subject: $p, phase-spec: $sp) isa dm-phase-artifact;
                    fetch {{ "id": $sp.id, "content": $sp.content,
                            "feasibility": $sp.dm-feasibility }};
                """
                gq = f"""
                    match $p isa {ptype}, has id "{iid}";
                          $gp isa dm-design-gap;
                          (phase-subject: $p, phase-gap: $gp) isa dm-phase-artifact;
                    fetch {{ "id": $gp.id, "description": $gp.description,
                            "severity": $gp.dm-error-severity, "status": $gp.dm-error-status }};
                """
                item["specs"] = fetch_query(driver, sq)
                item["gaps"] = fetch_query(driver, gq)
                enriched.append(item)
            phase_data[ptype] = enriched

    # Build Markdown
    lines = []
    domain_name = domain.get("name", domain_id)
    skill = domain.get("skill", "")
    lines.append(f"# System Design: {domain_name}")
    if skill:
        lines.append(f"\n_Skill: {skill}_  ")
    lines.append(f"_Domain ID: {domain_id}_\n")

    # Phase 1: Goals + Evaluations
    lines.append("\n---\n")
    lines.append("## Phase 1 -- System Goal\n")
    if not goals:
        lines.append("_No goals defined yet._\n")
    for g in goals:
        lines.append(f"### Goal: {g.get('name', '')}\n")
        desc = g.get("description")
        if desc:
            lines.append(f"{desc}\n")
        evals = goal_evals.get(g.get("id"), [])
        if evals:
            lines.append("\n**Evaluation Criteria:**\n")
            for e in evals:
                ctype = e.get("criterion_type") or ""
                name = e.get("name", "")
                lines.append(f"- **{name}**" + (f" _{ctype}_" if ctype else ""))
                desc_e = e.get("description")
                if desc_e:
                    lines.append(f"\n  {desc_e}")
                sc = e.get("success_condition")
                if sc:
                    lines.append(f"\n  _Success when:_ {sc}")
                approach = e.get("approach")
                if approach:
                    lines.append(f"\n  _Approach:_ {approach}")
                lines.append("")

    # Phases 2-5
    for ptype, pnum, plabel in phase_types:
        items = phase_data.get(ptype, [])
        lines.append(f"\n---\n")
        lines.append(f"## Phase {pnum} -- {plabel}\n")
        if not items:
            lines.append("_No items defined yet._\n")
            continue
        for item in items:
            name = item.get("name", "")
            feasibility = item.get("feasibility") or "unknown"
            lines.append(f"### {name} _(feasibility: {feasibility})_\n")
            desc = item.get("description")
            if desc:
                lines.append(f"{desc}\n")
            input_t = item.get("input_types")
            output_t = item.get("output_types")
            if input_t:
                lines.append(f"- **Inputs:** {input_t}")
            if output_t:
                lines.append(f"- **Outputs:** {output_t}")
            specs = item.get("specs", [])
            if specs:
                lines.append("\n**Specs:**\n")
                for sp in specs:
                    content = sp.get("content") or ""
                    feas = sp.get("feasibility") or ""
                    feas_str = f" _(feasibility: {feas})_" if feas else ""
                    lines.append(f"```\n{content}\n```{feas_str}\n")
            gaps = item.get("gaps", [])
            if gaps:
                open_gaps = [g for g in gaps if g.get("status") != "resolved"]
                if open_gaps:
                    lines.append("\n**Open Gaps:**\n")
                    for g in open_gaps:
                        sev = g.get("severity") or "?"
                        desc_g = g.get("description") or ""
                        lines.append(f"- [{sev}] {desc_g}")

    markdown = "\n".join(lines)
    out({"success": True, "domain_id": domain_id, "markdown": markdown})


# =============================================================================
# ARGUMENT PARSER
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Domain Modeling Skill - Track knowledge domain design processes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- Domain lifecycle ---
    p = subparsers.add_parser("init-domain", help="Create a domain design tracking project")
    p.add_argument("--name", required=True, help="Domain name (e.g. 'FDA regulatory')")
    p.add_argument("--description", help="Optional description")
    p.add_argument("--skill", help="Associated skill name (e.g. newskill)")

    p = subparsers.add_parser("list-domains", help="List all tracked domains")

    p = subparsers.add_parser("show-domain", help="Show full domain history")
    p.add_argument("--id", required=True, help="Domain ID")

    p = subparsers.add_parser("set-task", help="Set the natural-language task the skill performs")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--task", required=True, help="Natural language task description")

    # --- Skill snapshots ---
    p = subparsers.add_parser("snapshot-skill", help="Capture all skill files with git metadata")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--skill-dir", required=True, help="Path to skill directory")
    p.add_argument("--version", help="Version tag (e.g. v1.0); defaults to snapshot-YYYY-MM-DD")
    p.add_argument("--repo-dir", default=".", help="Git repo directory (default: .)")
    p.add_argument("--commit", help="Override git commit SHA (for retroactive documentation)")

    p = subparsers.add_parser("snapshot-schema",
                              help="[DEPRECATED] Use snapshot-skill. Capture schema state.")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--schema-file", required=True, help="Path to schema.tql file")
    p.add_argument("--version", help="Version tag (e.g. v1.0); defaults to snapshot-YYYY-MM-DD")
    p.add_argument("--repo-dir", default=".", help="Git repo directory (default: .)")
    p.add_argument("--commit", help="Override git commit SHA (for retroactive documentation)")

    p = subparsers.add_parser("list-versions", help="List skill snapshots for a domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")

    p = subparsers.add_parser("list-files", help="List files captured in a snapshot")
    p.add_argument("--snapshot-id", required=True, help="Snapshot ID")

    p = subparsers.add_parser("show-file", help="Show content of a captured file")
    p.add_argument("--file-id", required=True, help="File ID")

    p = subparsers.add_parser("add-plan", help="Attach a plan document to a snapshot")
    p.add_argument("--snapshot-id", required=True, help="Snapshot ID")
    p.add_argument("--plan-file", required=True, help="Path to plan Markdown file")
    p.add_argument("--order", type=int, help="Sequence number among plans (1, 2, ...)")
    p.add_argument("--description", help="Brief description of this plan")

    p = subparsers.add_parser("install-hook", help="Install git post-commit hook for auto-snapshots")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--skill-dir", required=True, help="Path to skill directory")
    p.add_argument("--repo-dir", default=".", help="Git repo directory (default: .)")

    # --- Design decisions ---
    p = subparsers.add_parser("add-decision", help="Record a schema design decision")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument(
        "--type", required=True,
        choices=["entity", "relation", "attribute", "hierarchy", "constraint"],
        help="Decision type",
    )
    p.add_argument("--summary", required=True, help="Brief description of the decision")
    p.add_argument("--version-id", help="Schema version where decision was made")
    p.add_argument("--alternatives", help="Alternative approaches considered")

    p = subparsers.add_parser("add-rationale", help="Add reasoning for a decision")
    p.add_argument("--decision-id", required=True, help="Decision ID")
    p.add_argument("--rationale", required=True, help="Reasoning text")
    p.add_argument("--alternatives", help="Why alternatives were rejected")

    p = subparsers.add_parser("link-gap", help="Link a schema-gap as motivation for a decision")
    p.add_argument("--decision-id", required=True, help="Decision ID")
    p.add_argument("--gap-id", required=True, help="Schema-gap ID from skilllog")

    p = subparsers.add_parser("list-decisions", help="List decisions for a domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument(
        "--type",
        choices=["entity", "relation", "attribute", "hierarchy", "constraint"],
        help="Filter by decision type",
    )

    # --- Experiments ---
    p = subparsers.add_parser("start-experiment", help="Start a design hypothesis experiment")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--hypothesis", required=True, help="What you are testing")
    p.add_argument("--version-id", help="Schema version being tested")

    p = subparsers.add_parser("record-result", help="Record an experiment observation")
    p.add_argument("--experiment-id", required=True, help="Experiment ID")
    p.add_argument("--metric", required=True, help="Metric name (e.g. coverage, accuracy)")
    p.add_argument("--value", required=True, type=float, help="Metric value")
    p.add_argument("--notes", help="Qualitative notes")

    p = subparsers.add_parser("complete-experiment", help="Mark experiment as complete")
    p.add_argument("--experiment-id", required=True, help="Experiment ID")

    p = subparsers.add_parser("list-experiments", help="List experiments for a domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument(
        "--status",
        choices=["planned", "running", "complete", "abandoned"],
        help="Filter by status",
    )

    # --- Representation errors ---
    p = subparsers.add_parser("report-error", help="Report a schema representation failure")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument(
        "--type", required=True,
        choices=[
            "type-mismatch", "missing-concept", "wrong-cardinality",
            "wrong-inheritance", "semantic-ambiguity",
            "over-generalization", "under-generalization",
        ],
        help="Error type",
    )
    p.add_argument("--summary", required=True, help="Description of what went wrong")
    p.add_argument(
        "--severity",
        choices=["minor", "moderate", "critical"],
        default="moderate",
        help="Error severity",
    )
    p.add_argument("--version-id", help="Schema version where error was found")

    p = subparsers.add_parser("resolve-error", help="Mark an error as resolved")
    p.add_argument("--error-id", required=True, help="Error ID")
    p.add_argument("--decision-id", help="Decision that resolved this error")

    p = subparsers.add_parser("list-errors", help="List errors for a domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument(
        "--status",
        choices=["open", "resolved", "accepted"],
        help="Filter by status",
    )

    # --- Export ---
    p = subparsers.add_parser("export-design", help="Export annotated Markdown design changelog")
    p.add_argument("--domain-id", required=True, help="Domain ID")

    # --- Phase 1: Goals ---
    p = subparsers.add_parser("define-goal", help="Define the system goal for a domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--name", required=True, help="Goal name")
    p.add_argument("--description", help="Goal description")

    p = subparsers.add_parser("add-evaluation", help="Add an evaluation criterion to a goal")
    p.add_argument("--goal-id", required=True, help="Goal ID")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--name", required=True, help="Criterion name")
    p.add_argument("--description", required=True, help="Full natural language criterion")
    p.add_argument("--criterion-type",
                   choices=["accuracy", "coverage", "usability", "completeness"],
                   help="Criterion type")
    p.add_argument("--success-condition", help="When X, system should Y")
    p.add_argument("--approach", help="How to assess performance")

    p = subparsers.add_parser("show-goal", help="Show goal + evaluations for a domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")

    p = subparsers.add_parser("ingest-design-doc", help="Store a design document and link to domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--file", required=True, help="Path to document file")
    p.add_argument("--format", default="markdown", help="File format (default: markdown)")
    p.add_argument("--description", help="Brief description")
    p.add_argument("--snapshot-id", help="Snapshot to attach to (optional)")

    # --- Phases 2-5: Phase entities ---
    p = subparsers.add_parser("add-entity-schema", help="Add Phase 2 entity schema description")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--name", required=True, help="Schema name")
    p.add_argument("--description", help="What types are defined (plain text)")
    p.add_argument("--feasibility", choices=["yes", "partial", "no", "unknown"],
                   default="unknown", help="Feasibility assessment")
    p.add_argument("--depends-on", help="Phase entity ID this builds on")

    p = subparsers.add_parser("add-source-schema", help="Add Phase 3 source/artifact schema")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--name", required=True, help="Source name")
    p.add_argument("--description", help="What sources/artifact types are needed")
    p.add_argument("--feasibility", choices=["yes", "partial", "no", "unknown"],
                   default="unknown", help="Feasibility assessment")
    p.add_argument("--depends-on", help="Phase entity ID this builds on")

    p = subparsers.add_parser("add-derivation-skill", help="Add Phase 4 derivation/ingestion skill")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--name", required=True, help="Skill name")
    p.add_argument("--description", help="What this skill does")
    p.add_argument("--input-types", help="Artifact types consumed (free text)")
    p.add_argument("--output-types", help="Entity types produced (free text)")
    p.add_argument("--feasibility", choices=["yes", "partial", "no", "unknown"],
                   default="unknown", help="Feasibility assessment")
    p.add_argument("--depends-on", help="Phase entity ID this builds on")

    p = subparsers.add_parser("add-analysis-skill", help="Add Phase 5 analysis skill")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--name", required=True, help="Skill name")
    p.add_argument("--description", help="What this skill does")
    p.add_argument("--input-types", help="Entity types queried (free text)")
    p.add_argument("--output-types", help="Output format/report type (free text)")
    p.add_argument("--feasibility", choices=["yes", "partial", "no", "unknown"],
                   default="unknown", help="Feasibility assessment")
    p.add_argument("--depends-on", help="Phase entity ID this builds on")

    # --- Shared phase operations ---
    p = subparsers.add_parser("add-phase-spec", help="Add a spec note to any phase entity")
    p.add_argument("--phase-id", required=True, help="Phase entity ID")
    p.add_argument("--content", required=True, help="Spec text (TypeQL, API desc, function sig, etc.)")
    p.add_argument("--feasibility", choices=["yes", "partial", "no", "unknown"],
                   help="Feasibility of this spec")

    p = subparsers.add_parser("add-phase-gap", help="Add a design gap to any phase entity")
    p.add_argument("--phase-id", required=True, help="Phase entity ID")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--description", required=True, help="Description of the gap")
    p.add_argument("--severity", choices=["minor", "moderate", "critical"],
                   default="moderate", help="Gap severity")

    p = subparsers.add_parser("resolve-phase-gap", help="Mark a design gap as resolved")
    p.add_argument("--gap-id", required=True, help="Gap ID")
    p.add_argument("--decision-id", help="Decision that resolved this gap")

    p = subparsers.add_parser("list-phase-gaps", help="List design gaps for a domain")
    p.add_argument("--domain-id", required=True, help="Domain ID")
    p.add_argument("--status", choices=["open", "resolved", "accepted"],
                   default="open", help="Filter by status")

    p = subparsers.add_parser("show-phase-item", help="Show a phase entity with its specs and gaps")
    p.add_argument("--phase-id", required=True, help="Phase entity ID")

    p = subparsers.add_parser("export-design-phases",
                              help="Export structured Markdown design phases report")
    p.add_argument("--domain-id", required=True, help="Domain ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init-domain": cmd_init_domain,
        "list-domains": cmd_list_domains,
        "show-domain": cmd_show_domain,
        "set-task": cmd_set_task,
        "snapshot-skill": cmd_snapshot_skill,
        "snapshot-schema": cmd_snapshot_schema,
        "list-versions": cmd_list_versions,
        "list-files": cmd_list_files,
        "show-file": cmd_show_file,
        "add-plan": cmd_add_plan,
        "install-hook": cmd_install_hook,
        "add-decision": cmd_add_decision,
        "add-rationale": cmd_add_rationale,
        "link-gap": cmd_link_gap,
        "list-decisions": cmd_list_decisions,
        "start-experiment": cmd_start_experiment,
        "record-result": cmd_record_result,
        "complete-experiment": cmd_complete_experiment,
        "list-experiments": cmd_list_experiments,
        "report-error": cmd_report_error,
        "resolve-error": cmd_resolve_error,
        "list-errors": cmd_list_errors,
        "export-design": cmd_export_design,
        "define-goal": cmd_define_goal,
        "add-evaluation": cmd_add_evaluation,
        "show-goal": cmd_show_goal,
        "ingest-design-doc": cmd_ingest_design_doc,
        "add-entity-schema": cmd_add_entity_schema,
        "add-source-schema": cmd_add_source_schema,
        "add-derivation-skill": cmd_add_derivation_skill,
        "add-analysis-skill": cmd_add_analysis_skill,
        "add-phase-spec": cmd_add_phase_spec,
        "add-phase-gap": cmd_add_phase_gap,
        "resolve-phase-gap": cmd_resolve_phase_gap,
        "list-phase-gaps": cmd_list_phase_gaps,
        "show-phase-item": cmd_show_phase_item,
        "export-design-phases": cmd_export_design_phases,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
