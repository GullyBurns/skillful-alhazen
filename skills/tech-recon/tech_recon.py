#!/usr/bin/env python3
"""
Tech Recon CLI - Systematically investigate external software systems.

This script handles investigation and system management for the tech-recon skill.
Claude performs sensemaking; this script handles TypeDB operations.

Usage:
    python skills/tech-recon/tech_recon.py <command> [options]

Commands:
    start-investigation   Start a new investigation with optional systems
    list-investigations   List all investigations
    show-investigation    Show investigation details (systems + analyses counts)
    update-investigation  Update investigation status, goal, or criteria
    add-system            Add a system to an investigation
    approve-system        Approve a candidate system (set status to confirmed)
    list-systems          List systems for an investigation (optionally filtered)
    show-system           Show full system details with artifact + note counts
    discover-systems      Return investigation goal for Claude-driven discovery
    ingest-page           Fetch a web page and record it as an artifact
    ingest-repo           Fetch a GitHub repo README + file tree as artifacts
    ingest-pdf            Fetch a PDF and record it as an artifact
    ingest-docs           Fetch a docs site (multiple pages) as artifacts
    list-artifacts        List artifacts linked to a system
    show-artifact         Show full artifact details with content preview
    cache-stats           Show cache directory size by content type
    write-note            Write a note and attach it to a system or investigation
    list-notes            List notes attached to a subject entity
    show-note             Show full note details including all tags
    add-analysis          Add an Observable Plot analysis to an investigation
    list-analyses         List analyses linked to an investigation
    show-analysis         Show full analysis details including plot code and query
    run-analysis          Execute a stored analysis: run its TypeQL query + return data
    add-pipeline          Add a Hamilton pipeline analysis (stores script + config)
    run-pipeline          Execute a stored Hamilton pipeline and write outputs to TypeDB
    plan-analyses         Return investigation context for visualization planning
    explore-repo          Return clone path + file list for Explore subagent dispatch
    extract-fragments     Extract code/heading fragments from repo-clone or HTML artifacts
    compile-report        Return full note content + context for synthesis report writing
    evaluate-completion   Return coverage stats for completion assessment writing

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    TYPEDB_USERNAME   TypeDB username (default: admin)
    TYPEDB_PASSWORD   TypeDB password (default: password)
    GITHUB_TOKEN      GitHub personal access token (optional, for higher rate limits)
    ALHAZEN_CACHE_DIR Cache directory for large artifacts (default: ~/.alhazen/cache)
"""

import argparse
import json
import os
import sys
from urllib.parse import urljoin, urlparse

import requests

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("Warning: beautifulsoup4 not installed, ingest-docs unavailable", file=sys.stderr)

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

# Shared skill utilities
try:
    _SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.abspath(os.path.join(_SKILL_DIR, "..", ".."))
    sys.path.insert(0, _PROJECT_ROOT)
    from src.skillful_alhazen.utils.skill_helpers import escape_string, generate_id, get_timestamp
    from src.skillful_alhazen.utils.cache import (
        get_cache_dir,
        get_cache_stats,
        load_from_cache_text,
        save_to_cache,
        should_cache,
    )
    HELPERS_AVAILABLE = True
    CACHE_AVAILABLE = True
except ImportError as _imp_err:
    HELPERS_AVAILABLE = False
    CACHE_AVAILABLE = False
    import uuid
    from datetime import datetime, timezone

    def escape_string(s: str) -> str:
        """Escape special characters for TypeQL string literals."""
        if s is None:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")

    def generate_id(prefix: str) -> str:
        """Generate a unique ID with a domain prefix."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def get_timestamp() -> str:
        """Return current UTC timestamp in TypeQL datetime format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Fallback cache helpers
    def should_cache(content):
        if isinstance(content, str):
            content = content.encode("utf-8")
        return len(content) >= 50 * 1024

    def save_to_cache(artifact_id, content, mime_type):
        _cache_root = os.path.expanduser(os.getenv("ALHAZEN_CACHE_DIR", "~/.alhazen/cache"))
        _type_map = {
            "text/html": ("html", "html"),
            "application/pdf": ("pdf", "pdf"),
            "application/json": ("json", "json"),
            "text/plain": ("text", "txt"),
            "text/markdown": ("text", "md"),
        }
        type_dir, ext = _type_map.get(mime_type, ("other", "bin"))
        dir_path = os.path.join(_cache_root, type_dir)
        os.makedirs(dir_path, exist_ok=True)
        filename = f"{artifact_id}.{ext}"
        full_path = os.path.join(dir_path, filename)
        if isinstance(content, str):
            content = content.encode("utf-8")
        with open(full_path, "wb") as fh:
            fh.write(content)
        return {
            "cache_path": f"{type_dir}/{filename}",
            "file_size": len(content),
            "full_path": full_path,
        }

    def load_from_cache_text(cache_path, encoding="utf-8"):
        _cache_root = os.path.expanduser(os.getenv("ALHAZEN_CACHE_DIR", "~/.alhazen/cache"))
        full = os.path.join(_cache_root, cache_path)
        with open(full, encoding=encoding) as fh:
            return fh.read()

    def get_cache_dir():
        import pathlib
        p = pathlib.Path(os.path.expanduser(os.getenv("ALHAZEN_CACHE_DIR", "~/.alhazen/cache")))
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_cache_stats():
        cache_dir = get_cache_dir()
        stats = {"cache_dir": str(cache_dir), "total_files": 0, "total_size": 0, "by_type": {}}
        import pathlib
        for td in pathlib.Path(cache_dir).iterdir():
            if td.is_dir():
                tc = {"count": 0, "size": 0}
                for fp in td.iterdir():
                    if fp.is_file():
                        tc["count"] += 1
                        tc["size"] += fp.stat().st_size
                if tc["count"] > 0:
                    stats["by_type"][td.name] = tc
                    stats["total_files"] += tc["count"]
                    stats["total_size"] += tc["size"]
        return stats


# GitHub token for API access
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


# =============================================================================
# CONFIGURATION
# =============================================================================

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = os.getenv("TYPEDB_PORT", "1729")
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


# =============================================================================
# DRIVER
# =============================================================================


def get_driver():
    """Get a TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


# =============================================================================
# INVESTIGATION COMMANDS
# =============================================================================


def cmd_start_investigation(args):
    """Start a new tech-recon investigation, optionally with initial systems."""
    inv_id = generate_id("tri")
    ts = get_timestamp()
    name = escape_string(args.name)
    goal = escape_string(args.goal)
    criteria = escape_string(args.success_criteria)

    systems_to_add = []
    if args.systems:
        for s in args.systems.split(","):
            s = s.strip()
            if s:
                systems_to_add.append(s)

    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Insert investigation
            q = f'''
                insert $inv isa tech-recon-investigation,
                    has id "{inv_id}",
                    has name "{name}",
                    has goal-description "{goal}",
                    has success-criteria "{criteria}",
                    has tech-recon-status "scoping",
                    has created-at {ts};
            '''
            tx.query(q).resolve()

            # Insert systems and link them
            inserted_systems = []
            for sys_name in systems_to_add:
                sys_id = generate_id("trs")
                esc_name = escape_string(sys_name)
                sq = f'''
                    insert $sys isa tech-recon-system,
                        has id "{sys_id}",
                        has name "{esc_name}",
                        has tech-recon-status "confirmed",
                        has created-at {ts};
                '''
                tx.query(sq).resolve()

                # Link system to investigation
                lq = f'''
                    match
                        $inv isa tech-recon-investigation, has id "{inv_id}";
                        $sys isa tech-recon-system, has id "{sys_id}";
                    insert
                        (system: $sys, investigation: $inv) isa investigated-in;
                '''
                tx.query(lq).resolve()
                inserted_systems.append({"id": sys_id, "name": sys_name})

            tx.commit()

        driver.close()
        print(json.dumps({
            "success": True,
            "investigation": {
                "id": inv_id,
                "name": args.name,
                "status": "scoping",
                "systems_added": inserted_systems,
            },
        }))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_list_investigations(args):
    """List all tech-recon investigations."""
    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query('''
                match $inv isa tech-recon-investigation;
                fetch {
                    "id": $inv.id,
                    "name": $inv.name,
                    "status": $inv.tech-recon-status,
                    "goal": $inv.goal-description
                };
            ''').resolve())
        driver.close()

        investigations = []
        for r in results:
            investigations.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "status": r.get("status"),
                "goal": r.get("goal"),
            })

        print(json.dumps({"success": True, "investigations": investigations}))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_show_investigation(args):
    """Show investigation details with system and analysis counts."""
    inv_id = escape_string(args.id)
    driver = get_driver()
    try:
        # Fetch investigation details
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{
                    "id": $inv.id,
                    "name": $inv.name,
                    "status": $inv.tech-recon-status,
                    "goal": $inv.goal-description,
                    "criteria": $inv.success-criteria,
                    "iteration": $inv.iteration-number
                }};
            ''').resolve())

            if not results:
                print(json.dumps({"success": False, "error": f"Investigation {args.id} not found"}))
                sys.exit(1)

            inv = results[0]

            # Count systems
            sys_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system;
                    (system: $sys, investigation: $inv) isa investigated-in;
                fetch {{ "id": $sys.id }};
            ''').resolve())

            # Count analyses
            ana_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $ana isa tech-recon-analysis;
                    (analysis: $ana, investigation: $inv) isa analysis-of;
                fetch {{ "id": $ana.id }};
            ''').resolve())

        print(json.dumps({
            "success": True,
            "investigation": {
                "id": inv.get("id"),
                "name": inv.get("name"),
                "goal": inv.get("goal"),
                "criteria": inv.get("criteria"),
                "status": inv.get("status"),
                "iteration_number": inv.get("iteration") or 1,
                "systems_count": len(sys_results),
                "analyses_count": len(ana_results),
            },
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_update_investigation(args):
    """Update investigation status, goal, or success criteria."""
    if not any([args.status, args.goal, args.success_criteria]):
        print(json.dumps({"success": False, "error": "At least one of --status, --goal, --success-criteria is required"}))
        sys.exit(1)

    inv_id = escape_string(args.id)
    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Verify existence
            check = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $inv.id }};
            ''').resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"Investigation {args.id} not found"}))
                sys.exit(1)

            if args.status:
                new_status = escape_string(args.status)
                tx.query(f'''
                    match
                        $inv isa tech-recon-investigation, has id "{inv_id}",
                            has tech-recon-status $old_status;
                    delete has $old_status of $inv;
                    insert $inv has tech-recon-status "{new_status}";
                ''').resolve()

            if args.goal:
                new_goal = escape_string(args.goal)
                tx.query(f'''
                    match
                        $inv isa tech-recon-investigation, has id "{inv_id}",
                            has goal-description $old_goal;
                    delete has $old_goal of $inv;
                    insert $inv has goal-description "{new_goal}";
                ''').resolve()

            if args.success_criteria:
                new_criteria = escape_string(args.success_criteria)
                tx.query(f'''
                    match
                        $inv isa tech-recon-investigation, has id "{inv_id}",
                            has success-criteria $old_criteria;
                    delete has $old_criteria of $inv;
                    insert $inv has success-criteria "{new_criteria}";
                ''').resolve()

            tx.commit()

        driver.close()
        print(json.dumps({
            "success": True,
            "investigation": {
                "id": args.id,
                "updated": {
                    k: v for k, v in {
                        "status": args.status,
                        "goal": args.goal,
                        "success_criteria": args.success_criteria,
                    }.items() if v
                },
            },
        }))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


# =============================================================================
# DELETION COMMANDS
# =============================================================================


def cmd_delete_note(args):
    """Delete a note by ID. TypeDB automatically removes the aboutness relation."""
    note_id = escape_string(args.id)
    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(
                f'match $n isa note, has id "{note_id}"; fetch {{ "id": $n.id }};'
            ).resolve())
        if not check:
            print(json.dumps({"success": False, "error": f"Note {args.id} not found"}))
            sys.exit(1)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'match $n isa note, has id "{note_id}"; delete $n;').resolve()
            tx.commit()
        print(json.dumps({"success": True, "deleted": args.id}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_delete_system(args):
    """Delete a system and all its notes and artifacts.
    Dry-run by default — use --force to confirm.
    TypeDB automatically removes investigated-in and sourced-from relations.
    """
    sys_id = escape_string(args.id)
    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Verify system exists
            check = list(tx.query(
                f'match $s isa tech-recon-system, has id "{sys_id}"; fetch {{ "id": $s.id }};'
            ).resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"System {args.id} not found"}))
                sys.exit(1)
            # Find child notes (linked via aboutness)
            note_ids = [r["id"] for r in tx.query(f'''
                match $n isa note;
                      (note: $n, subject: $s) isa aboutness;
                      $s isa tech-recon-system, has id "{sys_id}";
                fetch {{ "id": $n.id }};
            ''').resolve()]
            # Find child artifacts (linked via sourced-from)
            artifact_ids = [r["id"] for r in tx.query(f'''
                match $a isa artifact;
                      (artifact: $a, source: $s) isa sourced-from;
                      $s isa tech-recon-system, has id "{sys_id}";
                fetch {{ "id": $a.id }};
            ''').resolve()]

        if not args.force:
            print(json.dumps({
                "success": False,
                "dry_run": True,
                "would_delete": {
                    "notes": len(note_ids),
                    "artifacts": len(artifact_ids),
                    "system": 1,
                },
                "message": "Dry run — use --force to confirm deletion",
            }))
            return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            for nid in note_ids:
                tx.query(f'match $n isa note, has id "{escape_string(nid)}"; delete $n;').resolve()
            for aid in artifact_ids:
                tx.query(f'match $a isa artifact, has id "{escape_string(aid)}"; delete $a;').resolve()
            tx.query(f'match $s isa tech-recon-system, has id "{sys_id}"; delete $s;').resolve()
            tx.commit()

        print(json.dumps({
            "success": True,
            "deleted": {
                "system": args.id,
                "notes": len(note_ids),
                "artifacts": len(artifact_ids),
            },
        }))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_delete_investigation(args):
    """Delete an investigation and all its systems, artifacts, notes, and analyses.
    Dry-run by default — use --force to confirm.
    """
    inv_id = escape_string(args.id)
    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(
                f'match $i isa tech-recon-investigation, has id "{inv_id}"; fetch {{ "id": $i.id }};'
            ).resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"Investigation {args.id} not found"}))
                sys.exit(1)
            # Find all systems
            system_ids = [r["id"] for r in tx.query(f'''
                match $s isa tech-recon-system;
                      (system: $s, investigation: $i) isa investigated-in;
                      $i isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $s.id }};
            ''').resolve()]
            # Find investigation-level notes
            inv_note_ids = [r["id"] for r in tx.query(f'''
                match $n isa note;
                      (note: $n, subject: $i) isa aboutness;
                      $i isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $n.id }};
            ''').resolve()]
            # Find analyses
            analysis_ids = [r["id"] for r in tx.query(f'''
                match $a isa tech-recon-analysis;
                      (analysis: $a, investigation: $i) isa analysis-of;
                      $i isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $a.id }};
            ''').resolve()]
            # Count system-level children for summary
            sys_note_count = 0
            sys_artifact_count = 0
            for sid in system_ids:
                esc = escape_string(sid)
                sys_note_count += len(list(tx.query(f'''
                    match $n isa note; (note: $n, subject: $s) isa aboutness;
                          $s isa tech-recon-system, has id "{esc}";
                    fetch {{ "id": $n.id }};
                ''').resolve()))
                sys_artifact_count += len(list(tx.query(f'''
                    match $a isa artifact; (artifact: $a, source: $s) isa sourced-from;
                          $s isa tech-recon-system, has id "{esc}";
                    fetch {{ "id": $a.id }};
                ''').resolve()))

        if not args.force:
            print(json.dumps({
                "success": False,
                "dry_run": True,
                "would_delete": {
                    "investigation": 1,
                    "systems": len(system_ids),
                    "system_notes": sys_note_count,
                    "system_artifacts": sys_artifact_count,
                    "investigation_notes": len(inv_note_ids),
                    "analyses": len(analysis_ids),
                },
                "message": "Dry run — use --force to confirm deletion",
            }))
            return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Delete all system-level children, then systems
            for sid in system_ids:
                esc = escape_string(sid)
                sys_notes = [r["id"] for r in tx.query(f'''
                    match $n isa note; (note: $n, subject: $s) isa aboutness;
                          $s isa tech-recon-system, has id "{esc}";
                    fetch {{ "id": $n.id }};
                ''').resolve()]
                sys_artifacts = [r["id"] for r in tx.query(f'''
                    match $a isa artifact; (artifact: $a, source: $s) isa sourced-from;
                          $s isa tech-recon-system, has id "{esc}";
                    fetch {{ "id": $a.id }};
                ''').resolve()]
                for nid in sys_notes:
                    tx.query(f'match $n isa note, has id "{escape_string(nid)}"; delete $n;').resolve()
                for aid in sys_artifacts:
                    tx.query(f'match $a isa artifact, has id "{escape_string(aid)}"; delete $a;').resolve()
                tx.query(f'match $s isa tech-recon-system, has id "{esc}"; delete $s;').resolve()
            # Delete investigation-level notes and analyses
            for nid in inv_note_ids:
                tx.query(f'match $n isa note, has id "{escape_string(nid)}"; delete $n;').resolve()
            for aid in analysis_ids:
                tx.query(f'match $a isa tech-recon-analysis, has id "{escape_string(aid)}"; delete $a;').resolve()
            # Delete investigation
            tx.query(f'match $i isa tech-recon-investigation, has id "{inv_id}"; delete $i;').resolve()
            tx.commit()

        print(json.dumps({
            "success": True,
            "deleted": {
                "investigation": args.id,
                "systems": len(system_ids),
                "system_notes": sys_note_count,
                "system_artifacts": sys_artifact_count,
                "investigation_notes": len(inv_note_ids),
                "analyses": len(analysis_ids),
            },
        }))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_advance_iteration(args):
    """Increment the investigation's current iteration counter."""
    inv_id = escape_string(args.investigation)
    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(f'''
                match $i isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $i.id }};
            ''').resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
                sys.exit(1)
            iter_results = list(tx.query(f'''
                match $i isa tech-recon-investigation, has id "{inv_id}", has iteration-number $n;
                fetch {{ "n": $n }};
            ''').resolve())
            current = iter_results[0].get("n") if iter_results else None

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            if current is not None:
                tx.query(f'''
                    match $i isa tech-recon-investigation, has id "{inv_id}",
                          has iteration-number $old;
                    delete has $old of $i;
                ''').resolve()
            new_iter = (current or 1) + 1
            tx.query(f'''
                match $i isa tech-recon-investigation, has id "{inv_id}";
                insert $i has iteration-number {new_iter};
            ''').resolve()
            tx.commit()

        print(json.dumps({"success": True, "investigation": args.investigation, "iteration": new_iter}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


# =============================================================================
# SYSTEM COMMANDS
# =============================================================================


def cmd_add_system(args):
    """Add a software system to an investigation."""
    inv_id = escape_string(args.investigation)
    sys_id = generate_id("trs")
    ts = get_timestamp()
    name = escape_string(args.name)
    url = escape_string(args.url)
    status = escape_string(args.status)

    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Verify investigation exists
            check = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $inv.id }};
            ''').resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
                sys.exit(1)

            # Build insert query with optional attributes
            optional_attrs = ""
            if args.github_url:
                optional_attrs += f', has github-url "{escape_string(args.github_url)}"'
            if args.language:
                optional_attrs += f', has tech-recon-language "{escape_string(args.language)}"'
            if args.license:
                optional_attrs += f', has license "{escape_string(args.license)}"'
            if args.star_count is not None:
                optional_attrs += f", has star-count {args.star_count}"

            sq = f'''
                insert $sys isa tech-recon-system,
                    has id "{sys_id}",
                    has name "{name}",
                    has tech-recon-url "{url}",
                    has tech-recon-status "{status}",
                    has created-at {ts}{optional_attrs};
            '''
            tx.query(sq).resolve()

            # Link to investigation
            lq = f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system, has id "{sys_id}";
                insert
                    (system: $sys, investigation: $inv) isa investigated-in;
            '''
            tx.query(lq).resolve()
            tx.commit()

        driver.close()
        print(json.dumps({
            "success": True,
            "system": {
                "id": sys_id,
                "name": args.name,
                "url": args.url,
                "status": args.status,
            },
        }))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_approve_system(args):
    """Approve a candidate system by updating its status to confirmed."""
    sys_id = escape_string(args.id)
    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            check = list(tx.query(f'''
                match $sys isa tech-recon-system, has id "{sys_id}";
                fetch {{ "id": $sys.id }};
            ''').resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"System {args.id} not found"}))
                sys.exit(1)

            tx.query(f'''
                match
                    $sys isa tech-recon-system, has id "{sys_id}",
                        has tech-recon-status $old_status;
                delete has $old_status of $sys;
                insert $sys has tech-recon-status "confirmed";
            ''').resolve()
            tx.commit()

        driver.close()
        print(json.dumps({
            "success": True,
            "system": {"id": args.id, "status": "confirmed"},
        }))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_list_systems(args):
    """List systems for an investigation, optionally filtered by status."""
    inv_id = escape_string(args.investigation)
    status_filter = args.status or "all"

    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if status_filter == "all":
                results = list(tx.query(f'''
                    match
                        $inv isa tech-recon-investigation, has id "{inv_id}";
                        $sys isa tech-recon-system;
                        (system: $sys, investigation: $inv) isa investigated-in;
                    fetch {{
                        "id": $sys.id,
                        "name": $sys.name,
                        "url": $sys.tech-recon-url,
                        "status": $sys.tech-recon-status,
                        "language": $sys.tech-recon-language,
                        "license": $sys.license,
                        "star_count": $sys.star-count
                    }};
                ''').resolve())
            else:
                esc_status = escape_string(status_filter)
                results = list(tx.query(f'''
                    match
                        $inv isa tech-recon-investigation, has id "{inv_id}";
                        $sys isa tech-recon-system, has tech-recon-status "{esc_status}";
                        (system: $sys, investigation: $inv) isa investigated-in;
                    fetch {{
                        "id": $sys.id,
                        "name": $sys.name,
                        "url": $sys.tech-recon-url,
                        "status": $sys.tech-recon-status,
                        "language": $sys.tech-recon-language,
                        "license": $sys.license,
                        "star_count": $sys.star-count
                    }};
                ''').resolve())

            # Bulk-count artifacts and notes per system for this investigation
            art_rows = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system;
                    (system: $sys, investigation: $inv) isa investigated-in;
                    $sys has id $sid;
                    $art isa tech-recon-artifact;
                    (artifact: $art, source: $sys) isa sourced-from;
                fetch {{ "sid": $sid }};
            ''').resolve())
            note_rows = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system;
                    (system: $sys, investigation: $inv) isa investigated-in;
                    $sys has id $sid;
                    $n isa tech-recon-note;
                    (note: $n, subject: $sys) isa aboutness;
                fetch {{ "sid": $sid }};
            ''').resolve())

        driver.close()

        art_counts: dict = {}
        for row in art_rows:
            sid = row.get("sid")
            if sid:
                art_counts[sid] = art_counts.get(sid, 0) + 1
        note_counts: dict = {}
        for row in note_rows:
            sid = row.get("sid")
            if sid:
                note_counts[sid] = note_counts.get(sid, 0) + 1

        systems = []
        for r in results:
            sid = r.get("id")
            systems.append({
                "id": sid,
                "name": r.get("name"),
                "url": r.get("url"),
                "status": r.get("status"),
                "language": r.get("language"),
                "license": r.get("license"),
                "star_count": r.get("star_count"),
                "artifacts_count": art_counts.get(sid, 0),
                "notes_count": note_counts.get(sid, 0),
            })

        print(json.dumps({"success": True, "systems": systems}))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_show_system(args):
    """Show full system details including artifact and note counts."""
    sys_id = escape_string(args.id)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $sys isa tech-recon-system, has id "{sys_id}";
                fetch {{
                    "id": $sys.id,
                    "name": $sys.name,
                    "url": $sys.tech-recon-url,
                    "status": $sys.tech-recon-status,
                    "github_url": $sys.github-url,
                    "language": $sys.tech-recon-language,
                    "license": $sys.license,
                    "star_count": $sys.star-count
                }};
            ''').resolve())

            if not results:
                print(json.dumps({"success": False, "error": f"System {args.id} not found"}))
                sys.exit(1)

            sys_data = results[0]

            # Count artifacts sourced from this system
            art_results = list(tx.query(f'''
                match
                    $sys isa tech-recon-system, has id "{sys_id}";
                    $art isa tech-recon-artifact;
                    (artifact: $art, source: $sys) isa sourced-from;
                fetch {{ "id": $art.id }};
            ''').resolve())

            # Count notes about this system
            note_results = list(tx.query(f'''
                match
                    $sys isa tech-recon-system, has id "{sys_id}";
                    $n isa tech-recon-note;
                    (note: $n, subject: $sys) isa aboutness;
                fetch {{ "id": $n.id }};
            ''').resolve())

        print(json.dumps({
            "success": True,
            "system": {
                "id": sys_data.get("id"),
                "name": sys_data.get("name"),
                "url": sys_data.get("url"),
                "status": sys_data.get("status"),
                "github_url": sys_data.get("github_url"),
                "language": sys_data.get("language"),
                "license": sys_data.get("license"),
                "star_count": sys_data.get("star_count"),
                "artifacts_count": len(art_results),
                "notes_count": len(note_results),
            },
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_discover_systems(args):
    """Return investigation goal/criteria and existing systems for Claude-driven discovery."""
    inv_id = escape_string(args.investigation)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{
                    "id": $inv.id,
                    "name": $inv.name,
                    "goal": $inv.goal-description,
                    "criteria": $inv.success-criteria
                }};
            ''').resolve())

            if not results:
                print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
                sys.exit(1)

            inv = results[0]

            # Get existing system names
            sys_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system;
                    (system: $sys, investigation: $inv) isa investigated-in;
                fetch {{ "name": $sys.name }};
            ''').resolve())

        existing_systems = [r.get("name") for r in sys_results if r.get("name")]

        print(json.dumps({
            "success": True,
            "investigation": {
                "id": inv.get("id"),
                "name": inv.get("name"),
                "goal": inv.get("goal"),
                "criteria": inv.get("criteria"),
                "existing_systems": existing_systems,
            },
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


# =============================================================================
# INGESTION HELPERS
# =============================================================================

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AlhazenBot/1.0; +https://github.com/GullyBurns/skillful-alhazen)"
    )
}

_GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    _GITHUB_HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


def _insert_artifact_and_link(tx, art_id, ts, artifact_type, url, fmt, cache_path, content, sys_id):
    """Insert a tech-recon-artifact and link it to a system via sourced-from.

    Exactly one of cache_path or content should be truthy. Both are optional TypeDB
    attributes (artifact may store content inline or by reference).
    """
    esc_url = escape_string(url)
    esc_type = escape_string(artifact_type)
    esc_fmt = escape_string(fmt)

    optional = ""
    if cache_path:
        esc_cp = escape_string(cache_path)
        optional += f', has cache-path "{esc_cp}"'
    if content:
        esc_content = escape_string(content[:10000])  # guard runaway inline content
        optional += f', has content "{esc_content}"'

    insert_q = f'''
        insert $art isa tech-recon-artifact,
            has id "{art_id}",
            has artifact-type "{esc_type}",
            has tech-recon-url "{esc_url}",
            has format "{esc_fmt}",
            has created-at {ts}{optional};
    '''
    tx.query(insert_q).resolve()

    link_q = f'''
        match
            $art isa tech-recon-artifact, has id "{art_id}";
            $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
        insert
            (artifact: $art, source: $sys) isa sourced-from;
    '''
    tx.query(link_q).resolve()


def _update_system_status_if_confirmed(tx, sys_id):
    """Update system status from 'confirmed' -> 'ingested'."""
    check = list(tx.query(f'''
        match $sys isa tech-recon-system, has id "{escape_string(sys_id)}", has tech-recon-status "confirmed";
        fetch {{ "id": $sys.id }};
    ''').resolve())
    if check:
        tx.query(f'''
            match
                $sys isa tech-recon-system, has id "{escape_string(sys_id)}",
                    has tech-recon-status $old_status;
            delete has $old_status of $sys;
            insert $sys has tech-recon-status "ingested";
        ''').resolve()


def _clone_repo(url: str, owner: str, repo: str):
    """Git clone --depth 1 into ALHAZEN_CACHE_DIR/repos/{owner}/{repo}. Return (clone_path, error_msg)."""
    import subprocess
    cache_dir = os.environ.get("ALHAZEN_CACHE_DIR", os.path.expanduser("~/.alhazen/cache"))
    clone_path = os.path.join(cache_dir, "repos", owner, repo)
    if os.path.isdir(os.path.join(clone_path, ".git")):
        return clone_path, None  # already cloned -- idempotent
    os.makedirs(os.path.dirname(clone_path), exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, clone_path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        return None, result.stderr.strip()
    return clone_path, None


def _insert_note_tx(tx, subject_id: str, topic: str, content: str, fmt: str, tags=None) -> str:
    """Insert a tech-recon-note and link it to subject_id via aboutness. Returns note_id.

    Accepts an open write transaction -- caller is responsible for commit.
    """
    note_id = generate_id("trn")
    ts = get_timestamp()
    esc_subj = escape_string(subject_id)
    esc_topic = escape_string(topic)
    esc_fmt = escape_string(fmt)
    esc_content = escape_string(content)

    tx.query(f'''
        insert $n isa tech-recon-note,
            has id "{note_id}",
            has name "{esc_topic}",
            has topic "{esc_topic}",
            has format "{esc_fmt}",
            has content "{esc_content}",
            has created-at {ts};
    ''').resolve()

    if tags:
        for raw_tag in tags:
            tag = escape_string(str(raw_tag).strip())
            if tag:
                tx.query(f'''
                    match $n isa tech-recon-note, has id "{note_id}";
                    insert $n has tech-recon-tag "{tag}";
                ''').resolve()

    tx.query(f'''
        match
            $e isa identifiable-entity, has id "{esc_subj}";
            $n isa tech-recon-note, has id "{note_id}";
        insert
            (note: $n, subject: $e) isa aboutness;
    ''').resolve()

    return note_id


# =============================================================================
# INGESTION COMMANDS
# =============================================================================


def cmd_ingest_page(args):
    """Fetch a web page and record it as a tech-recon-artifact."""
    url = args.url
    sys_id = args.system
    art_id = generate_id("tra")
    ts = get_timestamp()

    try:
        resp = requests.get(url, headers=_HTTP_HEADERS, timeout=30)
        resp.raise_for_status()
        html_content = resp.text

        cache_path = None
        inline_content = None
        if should_cache(html_content):
            meta = save_to_cache(art_id, html_content, "text/html")
            cache_path = meta["cache_path"]
        else:
            inline_content = html_content

        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Verify system exists
            check = list(tx.query(f'''
                match $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
                fetch {{ "id": $sys.id }};
            ''').resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"System {sys_id} not found"}))
                sys.exit(1)

            _insert_artifact_and_link(
                tx, art_id, ts, "webpage", url, "html",
                cache_path, inline_content, sys_id,
            )
            _update_system_status_if_confirmed(tx, sys_id)
            tx.commit()
        driver.close()

        print(json.dumps({
            "success": True,
            "artifact": {
                "id": art_id,
                "type": "webpage",
                "url": url,
                "format": "html",
                "cache_path": cache_path,
                "system_id": sys_id,
            },
        }))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_ingest_repo(args):
    """Fetch a GitHub repo README + file tree and record them as artifacts."""
    url = args.url.rstrip("/")
    sys_id = args.system
    ts = get_timestamp()

    # Parse owner/repo from URL
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) < 2:
        print(json.dumps({"success": False, "error": f"Cannot parse owner/repo from URL: {url}"}))
        sys.exit(1)
    owner, repo = parts[0], parts[1]

    artifacts = []

    try:
        # --- Fetch README ---
        readme_content = None
        readme_url = None
        for branch in ("main", "master"):
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            try:
                r = requests.get(raw_url, headers=_HTTP_HEADERS, timeout=30)
                if r.status_code == 200:
                    readme_content = r.text
                    readme_url = raw_url
                    break
            except requests.RequestException:
                continue

        # --- Fetch file tree ---
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        tree_resp = requests.get(tree_url, headers=_GITHUB_HEADERS, timeout=30)
        tree_resp.raise_for_status()
        tree_content = tree_resp.text

        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Verify system exists
            check = list(tx.query(f'''
                match $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
                fetch {{ "id": $sys.id }};
            ''').resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"System {sys_id} not found"}))
                sys.exit(1)

            # Insert README artifact
            if readme_content is not None:
                readme_id = generate_id("tra")
                cache_path = None
                inline = None
                if should_cache(readme_content):
                    meta = save_to_cache(readme_id, readme_content, "text/plain")
                    cache_path = meta["cache_path"]
                else:
                    inline = readme_content
                _insert_artifact_and_link(
                    tx, readme_id, ts, "source-file", readme_url, "text",
                    cache_path, inline, sys_id,
                )
                artifacts.append({
                    "id": readme_id,
                    "type": "source-file",
                    "url": readme_url,
                    "format": "text",
                    "cache_path": cache_path,
                    "system_id": sys_id,
                })

            # Insert file-tree artifact
            tree_id = generate_id("tra")
            tree_cache_path = None
            tree_inline = None
            if should_cache(tree_content):
                meta = save_to_cache(tree_id, tree_content, "application/json")
                tree_cache_path = meta["cache_path"]
            else:
                tree_inline = tree_content
            _insert_artifact_and_link(
                tx, tree_id, ts, "file-tree", tree_url, "json",
                tree_cache_path, tree_inline, sys_id,
            )
            artifacts.append({
                "id": tree_id,
                "type": "file-tree",
                "url": tree_url,
                "format": "json",
                "cache_path": tree_cache_path,
                "system_id": sys_id,
            })

            _update_system_status_if_confirmed(tx, sys_id)
            tx.commit()
        driver.close()

        clone_path = None
        clone_artifact_id = None
        clone_error = None
        if getattr(args, 'clone', False):
            clone_path, clone_error = _clone_repo(url, owner, repo)
            if clone_path:
                # Insert repo-clone artifact in a new transaction
                art_id = generate_id("tra")
                ts2 = get_timestamp()
                rel_cache_path = f"repos/{owner}/{repo}"
                driver2 = get_driver()
                try:
                    with driver2.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx2:
                        # Check for existing repo-clone artifact (idempotent)
                        existing = list(tx2.query(f'''
                            match
                                $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
                                $art isa tech-recon-artifact, has artifact-type "repo-clone";
                                (artifact: $art, source: $sys) isa sourced-from;
                            fetch {{ "id": $art.id, "cache_path": $art.cache-path }};
                        ''').resolve())
                        if existing:
                            clone_artifact_id = existing[0].get("id")
                        else:
                            esc_url = escape_string(url)
                            esc_cp = escape_string(rel_cache_path)
                            tx2.query(f'''
                                insert $art isa tech-recon-artifact,
                                    has id "{art_id}",
                                    has artifact-type "repo-clone",
                                    has tech-recon-url "{esc_url}",
                                    has format "directory",
                                    has cache-path "{esc_cp}",
                                    has created-at {ts2};
                            ''').resolve()
                            tx2.query(f'''
                                match
                                    $art isa tech-recon-artifact, has id "{art_id}";
                                    $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
                                insert
                                    (artifact: $art, source: $sys) isa sourced-from;
                            ''').resolve()
                            tx2.commit()
                            clone_artifact_id = art_id
                            artifacts.append({
                                "id": art_id,
                                "type": "repo-clone",
                                "url": url,
                                "format": "directory",
                                "cache_path": rel_cache_path,
                                "system_id": sys_id,
                            })
                finally:
                    driver2.close()

        result = {"success": True, "artifacts": artifacts}
        if getattr(args, 'clone', False):
            result["clone_path"] = clone_path
            result["clone_artifact_id"] = clone_artifact_id
            if clone_error:
                result["clone_error"] = clone_error
        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_explore_repo(args):
    """Return clone path + file list + dispatch instructions for a Claude Explore subagent."""
    sys_id = escape_string(args.system)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Find the repo-clone artifact for this system
            art_results = list(tx.query(f'''
                match
                    $sys isa tech-recon-system, has id "{sys_id}";
                    $art isa tech-recon-artifact, has artifact-type "repo-clone";
                    (artifact: $art, source: $sys) isa sourced-from;
                fetch {{
                    "id": $art.id,
                    "cache_path": $art.cache-path,
                    "url": $art.tech-recon-url
                }};
            ''').resolve())

            if not art_results:
                print(json.dumps({
                    "success": False,
                    "error": "No repo-clone artifact found for this system. Re-run ingest-repo (cloning is on by default; use --no-clone only if skipping is intentional)."
                }))
                sys.exit(1)

            art = art_results[0]
            rel_cache_path = art.get("cache_path", "")
            repo_url = art.get("url", "")
            artifact_id = art.get("id", "")

            # Get system name
            sys_results = list(tx.query(f'''
                match $sys isa tech-recon-system, has id "{sys_id}";
                fetch {{ "id": $sys.id, "name": $sys.name }};
            ''').resolve())
            sys_name = sys_results[0].get("name", "") if sys_results else ""

            # Fetch investigation context if provided
            goal = ""
            criteria = ""
            if args.investigation:
                inv_id = escape_string(args.investigation)
                inv_results = list(tx.query(f'''
                    match $inv isa tech-recon-investigation, has id "{inv_id}";
                    fetch {{
                        "goal": $inv.goal-description,
                        "criteria": $inv.success-criteria
                    }};
                ''').resolve())
                if inv_results:
                    goal = inv_results[0].get("goal", "")
                    criteria = inv_results[0].get("criteria", "")

        # Expand cache path
        cache_dir = os.environ.get("ALHAZEN_CACHE_DIR", os.path.expanduser("~/.alhazen/cache"))
        clone_path = os.path.join(cache_dir, rel_cache_path)

        if not os.path.isdir(clone_path):
            print(json.dumps({
                "success": False,
                "error": f"Clone path does not exist: {clone_path}. Re-run ingest-repo to clone."
            }))
            sys.exit(1)

        # Walk directory tree
        INCLUDE_EXTS = {'.py', '.ts', '.js', '.rs', '.go', '.java', '.md', '.tql',
                        '.yaml', '.yml', '.toml', '.json', '.prisma', '.tsx', '.jsx'}
        files = []
        for root, dirs, filenames in os.walk(clone_path):
            # Skip hidden dirs and common noise
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ('node_modules', '__pycache__', '.git', 'dist', 'build', '.next', 'target')]
            for fname in sorted(filenames):
                ext = os.path.splitext(fname)[1].lower()
                if ext in INCLUDE_EXTS:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, clone_path)
                    files.append(rel)

        # Sort by depth then name, limit to 200
        files.sort(key=lambda p: (p.count(os.sep), p))
        files = files[:200]

        print(json.dumps({
            "success": True,
            "system_id": args.system,
            "system_name": sys_name,
            "artifact_id": artifact_id,
            "clone_path": clone_path,
            "repo_url": repo_url,
            "file_count": len(files),
            "files": files,
            "investigation_goal": goal,
            "success_criteria": criteria,
            "instruction": (
                "Dispatch an Explore subagent over clone_path. The subagent should: "
                "(1) read README and key source files, "
                "(2) understand the architecture and how it addresses the investigation criteria, "
                "(3) call write-note for each topic found. "
                "See USAGE.md section on Repo Exploration for the full Explore subagent prompt template."
            ),
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_extract_fragments(args):
    """Extract code/heading fragments from a repo-clone or HTML artifact and store as notes."""
    if not HAS_BS4 and not True:  # BS4 check happens inside for HTML
        pass

    art_id = escape_string(args.artifact)
    max_fragments = args.max_fragments

    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            art_results = list(tx.query(f'''
                match $art isa tech-recon-artifact, has id "{art_id}";
                fetch {{
                    "id": $art.id,
                    "type": $art.artifact-type,
                    "cache_path": $art.cache-path,
                    "url": $art.tech-recon-url
                }};
            ''').resolve())

            if not art_results:
                print(json.dumps({"success": False, "error": f"Artifact {args.artifact} not found"}))
                sys.exit(1)

            art = art_results[0]
            artifact_type = art.get("type", "")
            rel_cache_path = art.get("cache_path", "")

            # Find the system linked to this artifact
            sys_results = list(tx.query(f'''
                match
                    $art isa tech-recon-artifact, has id "{art_id}";
                    $sys isa tech-recon-system;
                    (artifact: $art, source: $sys) isa sourced-from;
                fetch {{ "id": $sys.id, "name": $sys.name }};
            ''').resolve())

            if not sys_results:
                print(json.dumps({"success": False, "error": "No system linked to this artifact"}))
                sys.exit(1)

            sys_id = sys_results[0].get("id", "")

            # Fetch existing fragment tags for dedup
            existing_tags = set()
            existing_results = list(tx.query(f'''
                match
                    $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
                    $n isa tech-recon-note, has topic "fragment";
                    (note: $n, subject: $sys) isa aboutness;
                    $n has tech-recon-tag $tag;
                fetch {{ "tag": $tag }};
            ''').resolve())
            for r in existing_results:
                existing_tags.add(r.get("tag", ""))

        cache_dir = os.environ.get("ALHAZEN_CACHE_DIR", os.path.expanduser("~/.alhazen/cache"))
        fragments = []  # list of (heading, content) tuples

        if artifact_type == "repo-clone":
            if not rel_cache_path:
                print(json.dumps({"success": False, "error": "Artifact has no cache-path"}))
                sys.exit(1)
            clone_path = os.path.join(cache_dir, rel_cache_path)
            if not os.path.isdir(clone_path):
                print(json.dumps({"success": False, "error": f"Clone path not found: {clone_path}"}))
                sys.exit(1)

            import re
            CODE_EXTS = {'.py', '.ts', '.js', '.tsx', '.jsx', '.rs', '.go', '.java'}
            MD_EXTS = {'.md', '.mdx'}
            DATA_EXTS = {'.yaml', '.yml', '.toml', '.json'}
            ALL_EXTS = CODE_EXTS | MD_EXTS | DATA_EXTS

            # Patterns for top-level definitions
            CODE_SPLIT_RE = re.compile(
                r'^(class |def |async def |function |export function |export async function |pub fn |func )',
                re.MULTILINE,
            )

            for root, dirs, filenames in os.walk(clone_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                           ('node_modules', '__pycache__', '.git', 'dist', 'build', '.next', 'target')]
                for fname in sorted(filenames):
                    if len(fragments) >= max_fragments:
                        break
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in ALL_EXTS:
                        continue
                    full = os.path.join(root, fname)
                    # Skip large files
                    try:
                        if os.path.getsize(full) > 100 * 1024:
                            continue
                        with open(full, encoding='utf-8', errors='replace') as fh:
                            text = fh.read()
                    except OSError:
                        continue

                    rel = os.path.relpath(full, clone_path)

                    if ext in CODE_EXTS:
                        # Split on top-level definitions
                        parts = CODE_SPLIT_RE.split(text)
                        if len(parts) <= 1:
                            # No splits found -- store whole file
                            heading = rel
                            if heading not in existing_tags:
                                fragments.append((heading, text[:5000]))
                        else:
                            # Reconstruct: parts[0] is preamble, then pairs (keyword, body)
                            i = 1
                            while i < len(parts) - 1 and len(fragments) < max_fragments:
                                keyword = parts[i]
                                body = parts[i + 1]
                                # Extract name: first identifier on first line
                                first_line = body.split('\n')[0]
                                name_match = re.match(r'(\w+)', first_line)
                                fn_name = name_match.group(1) if name_match else str(i)
                                heading = f"{rel}::{fn_name}"
                                if heading not in existing_tags:
                                    fragments.append((heading, (keyword + body)[:5000]))
                                i += 2

                    elif ext in MD_EXTS:
                        # Split on ## headings
                        sections = re.split(r'^## ', text, flags=re.MULTILINE)
                        for sec in sections:
                            if len(fragments) >= max_fragments:
                                break
                            if not sec.strip():
                                continue
                            first_line = sec.split('\n')[0].strip()
                            heading = f"{rel}::{first_line}" if first_line else rel
                            if heading not in existing_tags:
                                fragments.append((heading, ('## ' + sec)[:5000]))

                    elif ext in DATA_EXTS:
                        # Split on top-level keys
                        lines = text.split('\n')
                        current_key = None
                        current_lines = []
                        for line in lines:
                            if line and not line[0].isspace() and ':' in line and not line.startswith('#'):
                                if current_key and current_lines:
                                    heading = f"{rel}::{current_key}"
                                    if heading not in existing_tags and len(fragments) < max_fragments:
                                        fragments.append((heading, '\n'.join(current_lines)[:5000]))
                                current_key = line.split(':')[0].strip()
                                current_lines = [line]
                            else:
                                current_lines.append(line)
                        if current_key and current_lines:
                            heading = f"{rel}::{current_key}"
                            if heading not in existing_tags and len(fragments) < max_fragments:
                                fragments.append((heading, '\n'.join(current_lines)[:5000]))

        else:
            # HTML artifact
            if not HAS_BS4:
                print(json.dumps({"success": False, "error": "beautifulsoup4 required for HTML extraction"}))
                sys.exit(1)
            if not rel_cache_path:
                print(json.dumps({"success": False, "error": "Artifact has no cache-path"}))
                sys.exit(1)
            try:
                html = load_from_cache_text(rel_cache_path)
            except Exception as e:
                print(json.dumps({"success": False, "error": f"Cannot load artifact: {e}"}))
                sys.exit(1)

            soup = BeautifulSoup(html, 'html.parser')
            for heading_tag in soup.find_all(['h2', 'h3'])[:max_fragments]:
                heading_text = heading_tag.get_text(strip=True)
                if not heading_text or heading_text in existing_tags:
                    continue
                # Grab text until next heading
                content_parts = []
                for sib in heading_tag.next_siblings:
                    if hasattr(sib, 'name') and sib.name in ('h2', 'h3'):
                        break
                    content_parts.append(sib.get_text(' ', strip=True) if hasattr(sib, 'get_text') else str(sib))
                fragments.append((heading_text, (heading_text + '\n\n' + ' '.join(content_parts))[:5000]))

        # Batch-insert all fragments
        inserted_notes = []
        if fragments:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                for heading, content in fragments:
                    note_id = _insert_note_tx(tx, sys_id, "fragment", content, "text", [heading])
                    inserted_notes.append({"id": note_id, "tag": heading})
                tx.commit()

        print(json.dumps({
            "success": True,
            "artifact_id": args.artifact,
            "artifact_type": artifact_type,
            "system_id": sys_id,
            "fragments_extracted": len(inserted_notes),
            "notes": inserted_notes,
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_ingest_pdf(args):
    """Fetch a PDF and record it as a tech-recon-artifact."""
    url = args.url
    sys_id = args.system
    art_id = generate_id("tra")
    ts = get_timestamp()

    try:
        resp = requests.get(url, headers=_HTTP_HEADERS, stream=True, timeout=60)
        resp.raise_for_status()
        pdf_bytes = resp.content

        # Save PDF to cache (always, regardless of size — PDFs are binary)
        import pathlib
        cache_root = get_cache_dir()
        pdf_dir = pathlib.Path(cache_root) / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        filename = url.split("/")[-1].split("?")[0] or "document.pdf"
        if not filename.lower().endswith(".pdf"):
            filename = f"{art_id}.pdf"
        full_path = pdf_dir / filename
        with open(full_path, "wb") as fh:
            fh.write(pdf_bytes)
        cache_path = f"pdf/{filename}"

        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            check = list(tx.query(f'''
                match $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
                fetch {{ "id": $sys.id }};
            ''').resolve())
            if not check:
                print(json.dumps({"success": False, "error": f"System {sys_id} not found"}))
                sys.exit(1)

            _insert_artifact_and_link(
                tx, art_id, ts, "pdf", url, "pdf",
                cache_path, None, sys_id,
            )
            _update_system_status_if_confirmed(tx, sys_id)
            tx.commit()
        driver.close()

        print(json.dumps({
            "success": True,
            "artifact": {
                "id": art_id,
                "type": "pdf",
                "url": url,
                "format": "pdf",
                "cache_path": cache_path,
                "system_id": sys_id,
            },
        }))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_ingest_docs(args):
    """Fetch a documentation site (multiple pages) and record each as an artifact."""
    if not HAS_BS4:
        print(json.dumps({
            "success": False,
            "error": "beautifulsoup4 not installed. Run: pip install beautifulsoup4",
        }))
        sys.exit(1)

    url = args.url
    sys_id = args.system
    max_pages = args.max_pages
    ts = get_timestamp()

    base_parsed = urlparse(url)
    base_domain = base_parsed.netloc

    def _same_domain(link_url):
        return urlparse(link_url).netloc == base_domain

    visited = set()
    to_visit = [url]
    artifacts = []

    try:
        driver = get_driver()

        # Verify system exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(f'''
                match $sys isa tech-recon-system, has id "{escape_string(sys_id)}";
                fetch {{ "id": $sys.id }};
            ''').resolve())
        if not check:
            driver.close()
            print(json.dumps({"success": False, "error": f"System {sys_id} not found"}))
            sys.exit(1)

        while to_visit and len(visited) < max_pages:
            page_url = to_visit.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)

            try:
                resp = requests.get(page_url, headers=_HTTP_HEADERS, timeout=30)
                if resp.status_code != 200:
                    print(f"Skipping {page_url}: HTTP {resp.status_code}", file=sys.stderr)
                    continue
                html_content = resp.text
            except requests.RequestException as req_err:
                print(f"Skipping {page_url}: {req_err}", file=sys.stderr)
                continue

            # Parse links for further crawl
            soup = BeautifulSoup(html_content, "html.parser")
            for tag in soup.find_all("a", href=True):
                link = urljoin(page_url, tag["href"]).split("#")[0]
                if link not in visited and _same_domain(link) and link not in to_visit:
                    to_visit.append(link)

            # Save + insert artifact
            art_id = generate_id("tra")
            cache_path = None
            inline_content = None
            if should_cache(html_content):
                meta = save_to_cache(art_id, html_content, "text/html")
                cache_path = meta["cache_path"]
            else:
                inline_content = html_content

            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                _insert_artifact_and_link(
                    tx, art_id, ts, "webpage", page_url, "html",
                    cache_path, inline_content, sys_id,
                )
                tx.commit()

            artifacts.append({
                "id": art_id,
                "type": "webpage",
                "url": page_url,
                "format": "html",
                "cache_path": cache_path,
                "system_id": sys_id,
            })

        # Update system status after all pages ingested
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            _update_system_status_if_confirmed(tx, sys_id)
            tx.commit()

        driver.close()
        print(json.dumps({
            "success": True,
            "artifacts_count": len(artifacts),
            "artifacts": artifacts,
        }))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_list_artifacts(args):
    """List artifacts linked to a system via sourced-from."""
    sys_id = escape_string(args.system)
    type_filter = args.type

    try:
        driver = get_driver()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if type_filter:
                esc_type = escape_string(type_filter)
                results = list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sys_id}";
                        $art isa tech-recon-artifact, has artifact-type "{esc_type}";
                        (artifact: $art, source: $sys) isa sourced-from;
                    fetch {{
                        "id": $art.id,
                        "type": $art.artifact-type,
                        "url": $art.tech-recon-url,
                        "format": $art.format,
                        "cache_path": $art.cache-path
                    }};
                ''').resolve())
            else:
                results = list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sys_id}";
                        $art isa tech-recon-artifact;
                        (artifact: $art, source: $sys) isa sourced-from;
                    fetch {{
                        "id": $art.id,
                        "type": $art.artifact-type,
                        "url": $art.tech-recon-url,
                        "format": $art.format,
                        "cache_path": $art.cache-path
                    }};
                ''').resolve())
        driver.close()

        artifacts = []
        for r in results:
            artifacts.append({
                "id": r.get("id"),
                "type": r.get("type"),
                "url": r.get("url"),
                "format": r.get("format"),
                "cache_path": r.get("cache_path"),
            })

        print(json.dumps({"success": True, "artifacts": artifacts}))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_show_artifact(args):
    """Show full artifact details and optionally a content preview."""
    art_id = escape_string(args.id)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $art isa tech-recon-artifact, has id "{art_id}";
                fetch {{
                    "id": $art.id,
                    "type": $art.artifact-type,
                    "url": $art.tech-recon-url,
                    "format": $art.format,
                    "cache_path": $art.cache-path,
                    "content": $art.content
                }};
            ''').resolve())

        if not results:
            print(json.dumps({"success": False, "error": f"Artifact {args.id} not found"}))
            sys.exit(1)

        art = results[0]
        artifact_data = {
            "id": art.get("id"),
            "type": art.get("type"),
            "url": art.get("url"),
            "format": art.get("format"),
            "cache_path": art.get("cache_path"),
        }

        # Include inline content (stored directly in TypeDB, not on disk)
        if art.get("content"):
            artifact_data["content"] = art.get("content")

        print(json.dumps({"success": True, "artifact": artifact_data}))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_cache_stats(args):
    """Show cache directory size by content type."""
    try:
        raw = get_cache_stats()
        formatted = {}
        for type_name, ts in raw.get("by_type", {}).items():
            formatted[type_name] = {
                "count": ts["count"],
                "size_mb": round(ts["size"] / (1024 * 1024), 3),
            }
        print(json.dumps({
            "success": True,
            "stats": formatted,
            "total_files": raw.get("total_files", 0),
            "total_size_mb": round(raw.get("total_size", 0) / (1024 * 1024), 3),
            "cache_dir": raw.get("cache_dir", ""),
        }))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


# =============================================================================
# SENSEMAKING COMMANDS (NOTES)
# =============================================================================


def cmd_write_note(args):
    """Write a note and attach it to a subject entity (system or investigation)."""
    subject_id = escape_string(args.subject_id)
    topic = escape_string(args.topic)
    fmt = escape_string(args.format)
    content = escape_string(args.content)
    note_id = generate_id("trn")
    ts = get_timestamp()

    driver = get_driver()
    try:
        # Verify subject exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(f'''
                match $e isa identifiable-entity, has id "{subject_id}";
                fetch {{ "id": $e.id }};
            ''').resolve())
        if not check:
            print(json.dumps({"success": False, "error": f"Subject {args.subject_id} not found"}))
            sys.exit(1)

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # If --replace, delete existing notes with same topic on same subject
            if getattr(args, 'replace', False):
                old_ids = [r["id"] for r in tx.query(f'''
                    match $n isa note, has topic "{topic}";
                          (note: $n, subject: $e) isa aboutness;
                          $e isa identifiable-entity, has id "{subject_id}";
                    fetch {{ "id": $n.id }};
                ''').resolve()]
                for oid in old_ids:
                    tx.query(f'match $n isa note, has id "{escape_string(oid)}"; delete $n;').resolve()

            # Insert note
            iter_num = getattr(args, 'iteration', 1) or 1
            insert_q = f'''
                insert $n isa tech-recon-note,
                    has id "{note_id}",
                    has name "{topic}",
                    has topic "{topic}",
                    has format "{fmt}",
                    has content "{content}",
                    has iteration-number {iter_num},
                    has created-at {ts};
            '''
            tx.query(insert_q).resolve()

            # Add tags if provided
            if args.tags:
                for raw_tag in args.tags.split(","):
                    tag = escape_string(raw_tag.strip())
                    if tag:
                        tx.query(f'''
                            match $n isa tech-recon-note, has id "{note_id}";
                            insert $n has tech-recon-tag "{tag}";
                        ''').resolve()

            # Link note to subject via aboutness
            link_q = f'''
                match
                    $e isa identifiable-entity, has id "{subject_id}";
                    $n isa tech-recon-note, has id "{note_id}";
                insert
                    (note: $n, subject: $e) isa aboutness;
            '''
            tx.query(link_q).resolve()
            tx.commit()

        print(json.dumps({
            "success": True,
            "note": {
                "id": note_id,
                "topic": args.topic,
                "format": args.format,
                "subject_id": args.subject_id,
            },
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_list_notes(args):
    """List all notes attached to a subject entity."""
    subject_id = escape_string(args.subject_id)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Build optional filters
            topic_filter = ""
            if args.topic:
                topic_filter = f', has topic "{escape_string(args.topic)}"'
            fmt_filter = ""
            if args.format:
                fmt_filter = f', has format "{escape_string(args.format)}"'

            results = list(tx.query(f'''
                match
                    $e isa identifiable-entity, has id "{subject_id}";
                    $n isa tech-recon-note{topic_filter}{fmt_filter};
                    (note: $n, subject: $e) isa aboutness;
                    $n has topic $topic;
                    $n has format $fmt;
                    $n has content $content;
                    $n has id $nid;
                    $n has created-at $created_at;
                fetch {{
                    "id": $nid,
                    "topic": $topic,
                    "format": $fmt,
                    "content": $content,
                    "created_at": $created_at
                }};
            ''').resolve())

            # Fetch tags and iteration per note
            notes = []
            for r in results:
                note_id_val = r.get("id")
                content_val = r.get("content") or ""
                tag_results = list(tx.query(f'''
                    match $n isa tech-recon-note, has id "{escape_string(note_id_val)}", has tech-recon-tag $tag;
                    fetch {{ "tag": $tag }};
                ''').resolve())
                tags = [t.get("tag") for t in tag_results if t.get("tag")]
                # Fetch iteration-number (optional — legacy notes may not have it)
                iter_results = list(tx.query(f'''
                    match $n isa tech-recon-note, has id "{escape_string(note_id_val)}", has iteration-number $iter;
                    fetch {{ "iter": $iter }};
                ''').resolve())
                iteration_number = iter_results[0].get("iter") if iter_results else 1
                notes.append({
                    "id": note_id_val,
                    "topic": r.get("topic"),
                    "format": r.get("format"),
                    "tags": tags,
                    "iteration_number": iteration_number or 1,
                    "created_at": str(r.get("created_at", "")),
                    "content_preview": content_val[:200],
                })

        print(json.dumps({"success": True, "notes": notes}))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_show_note(args):
    """Show full details of a note including all tags."""
    note_id = escape_string(args.id)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $n isa tech-recon-note, has id "{note_id}";
                fetch {{
                    "id": $n.id,
                    "topic": $n.topic,
                    "format": $n.format,
                    "content": $n.content,
                    "created_at": $n.created-at
                }};
            ''').resolve())

            if not results:
                print(json.dumps({"success": False, "error": f"Note {args.id} not found"}))
                sys.exit(1)

            note = results[0]

            # Fetch tags
            tag_results = list(tx.query(f'''
                match $n isa tech-recon-note, has id "{note_id}", has tech-recon-tag $tag;
                fetch {{ "tag": $tag }};
            ''').resolve())
            tags = [t.get("tag") for t in tag_results if t.get("tag")]

        print(json.dumps({
            "success": True,
            "note": {
                "id": note.get("id"),
                "topic": note.get("topic"),
                "format": note.get("format"),
                "content": note.get("content"),
                "tags": tags,
                "created_at": str(note.get("created_at", "")),
            },
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


# =============================================================================
# ANALYSIS COMMANDS
# =============================================================================


def cmd_add_analysis(args):
    """Add an Observable Plot analysis to an investigation."""
    inv_id = escape_string(args.investigation)
    ana_id = generate_id("tra")
    ts = get_timestamp()
    title = escape_string(args.title)
    plot_code = escape_string(args.plot_code)
    tql_query = escape_string(args.query)
    analysis_type = escape_string(args.analysis_type)
    description = escape_string(args.description) if args.description else ""

    driver = get_driver()
    try:
        # Verify investigation exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $inv.id }};
            ''').resolve())
        if not check:
            print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
            sys.exit(1)

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Insert analysis artifact
            insert_q = f'''
                insert $a isa tech-recon-analysis,
                    has id "{ana_id}",
                    has name "{title}",
                    has tech-recon-title "{title}",
                    has analysis-type "{analysis_type}",
                    has plot-code "{plot_code}",
                    has tql-query "{tql_query}",
                    has format "javascript",
                    has created-at {ts};
            '''
            if description:
                insert_q = f'''
                    insert $a isa tech-recon-analysis,
                        has id "{ana_id}",
                        has name "{title}",
                        has tech-recon-title "{title}",
                        has analysis-type "{analysis_type}",
                        has plot-code "{plot_code}",
                        has tql-query "{tql_query}",
                        has format "javascript",
                        has content "{description}",
                        has created-at {ts};
                '''
            tx.query(insert_q).resolve()

            # Link analysis to investigation
            link_q = f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $a isa tech-recon-analysis, has id "{ana_id}";
                insert
                    (analysis: $a, investigation: $inv) isa analysis-of;
            '''
            tx.query(link_q).resolve()
            tx.commit()

        print(json.dumps({
            "success": True,
            "analysis": {
                "id": ana_id,
                "title": args.title,
                "type": args.analysis_type,
                "investigation_id": args.investigation,
            },
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_list_analyses(args):
    """List all analyses linked to an investigation."""
    inv_id = escape_string(args.investigation)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $a isa tech-recon-analysis;
                    (analysis: $a, investigation: $inv) isa analysis-of;
                fetch {{
                    "id": $a.id,
                    "title": $a.tech-recon-title,
                    "type": $a.analysis-type,
                    "content": $a.content
                }};
            ''').resolve())

        analyses = []
        for r in results:
            desc = r.get("content") or ""
            analyses.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "type": r.get("type"),
                "description_preview": desc[:200] if desc else None,
            })

        print(json.dumps({"success": True, "analyses": analyses}))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_show_analysis(args):
    """Show full details of an analysis including plot code and query."""
    ana_id = escape_string(args.id)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $a isa tech-recon-analysis, has id "{ana_id}";
                fetch {{
                    "id": $a.id,
                    "title": $a.tech-recon-title,
                    "type": $a.analysis-type,
                    "plot_code": $a.plot-code,
                    "query": $a.tql-query,
                    "description": $a.content,
                    "pipeline_script": $a.pipeline-script,
                    "pipeline_config": $a.pipeline-config
                }};
            ''').resolve())

        if not results:
            print(json.dumps({"success": False, "error": f"Analysis {args.id} not found"}))
            sys.exit(1)

        a = results[0]
        pipeline_script = a.get("pipeline_script")
        print(json.dumps({
            "success": True,
            "analysis": {
                "id": a.get("id"),
                "title": a.get("title"),
                "type": a.get("type"),
                "plot_code": a.get("plot_code"),
                "query": a.get("query"),
                "description": a.get("description"),
                "pipeline_script": pipeline_script,
                "pipeline_script_preview": (pipeline_script[:500] + "...") if pipeline_script and len(pipeline_script) > 500 else pipeline_script,
                "pipeline_script_chars": len(pipeline_script) if pipeline_script else 0,
                "pipeline_config": a.get("pipeline_config"),
            },
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_run_analysis(args):
    """Execute a stored analysis: fetch its plot code and run its TypeQL query."""
    ana_id = escape_string(args.id)
    driver = get_driver()
    try:
        # Step 1: Get the analysis plot code and stored query
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $a isa tech-recon-analysis, has id "{ana_id}";
                fetch {{
                    "plot_code": $a.plot-code,
                    "query": $a.tql-query
                }};
            ''').resolve())

        if not results:
            print(json.dumps({"success": False, "error": f"Analysis {args.id} not found"}))
            sys.exit(1)

        plot_code = results[0].get("plot_code")
        tql_query = results[0].get("query")

        # Step 2: Execute the stored TypeQL query (must be a fetch query)
        if "fetch" not in tql_query.lower():
            print(json.dumps({"success": False, "error": "Stored query must be a fetch query. Non-fetch queries return TypeDB concept objects that are not JSON-serializable."}))
            sys.exit(1)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            data_results = list(tx.query(tql_query).resolve())

        print(json.dumps({
            "success": True,
            "analysis_id": args.id,
            "plot_code": plot_code,
            "data": data_results,
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def load_pipeline_module(source_code: str, module_name: str = "techrecon_pipeline"):
    """Dynamically load a Hamilton pipeline module from source code string.

    Uses importlib.util.spec_from_file_location via a named temp file because
    Hamilton's introspection calls inspect.getsource() which requires a real file path.
    """
    import importlib.util
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", prefix=f"{module_name}_", delete=False) as f:
        f.write(source_code)
        tmp_path = f.name
    spec = importlib.util.spec_from_file_location(module_name, tmp_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    os.unlink(tmp_path)
    return mod


def cmd_add_pipeline(args):
    """Add a Hamilton pipeline analysis to an investigation (stores script + config)."""
    inv_id = escape_string(args.investigation)
    title = escape_string(args.title)
    analysis_type = escape_string(args.analysis_type)

    # Load pipeline script source
    if args.pipeline_script.startswith("@"):
        script_path = args.pipeline_script[1:]
        with open(script_path) as f:
            pipeline_script = f.read()
    else:
        pipeline_script = args.pipeline_script

    # Load pipeline config
    if args.pipeline_config.startswith("@"):
        config_path = args.pipeline_config[1:]
        with open(config_path) as f:
            pipeline_config = f.read()
    else:
        pipeline_config = args.pipeline_config

    # Validate config is valid JSON
    try:
        json.loads(pipeline_config)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"pipeline-config is not valid JSON: {e}"}))
        sys.exit(1)

    ana_id = generate_id("tra")
    now = get_timestamp()

    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Verify investigation exists
            inv_check = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{ "id": $inv.id }};
            ''').resolve())
            if not inv_check:
                print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
                sys.exit(1)

            escaped_script = escape_string(pipeline_script)
            escaped_config = escape_string(pipeline_config)
            escaped_title = title

            tx.query(f'''
                insert $a isa tech-recon-analysis,
                    has id "{ana_id}",
                    has tech-recon-title "{escaped_title}",
                    has analysis-type "{analysis_type}",
                    has pipeline-script "{escaped_script}",
                    has pipeline-config "{escaped_config}",
                    has created-at {now};
            ''').resolve()

            tx.query(f'''
                match
                    $a isa tech-recon-analysis, has id "{ana_id}";
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                insert (analysis: $a, investigation: $inv) isa analysis-of;
            ''').resolve()

            tx.commit()

        print(json.dumps({
            "success": True,
            "analysis_id": ana_id,
            "investigation_id": args.investigation,
            "title": args.title,
            "analysis_type": args.analysis_type,
            "pipeline_script_chars": len(pipeline_script),
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


# Mapping from Hamilton terminal node name → TypeDB attribute name + update action
_PIPELINE_OUTPUT_ATTRS = {
    "plot_code": "plot-code",
    "table_data": "content",   # serialized as JSON string
    "prose_text": "content",
    "artifact_path": "cache-path",
}


def cmd_run_pipeline(args):
    """Execute a stored Hamilton pipeline and write outputs back to TypeDB."""
    ana_id = escape_string(args.id)
    driver = get_driver()
    try:
        # Step 1: Fetch pipeline-script + pipeline-config from TypeDB
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $a isa tech-recon-analysis, has id "{ana_id}";
                fetch {{
                    "pipeline_script": $a.pipeline-script,
                    "pipeline_config": $a.pipeline-config
                }};
            ''').resolve())

        if not results:
            print(json.dumps({"success": False, "error": f"Analysis {args.id} not found"}))
            sys.exit(1)

        pipeline_script = results[0].get("pipeline_script")
        pipeline_config_str = results[0].get("pipeline_config")

        if not pipeline_script:
            print(json.dumps({"success": False, "error": "Analysis has no pipeline-script stored"}))
            sys.exit(1)
        if not pipeline_config_str:
            print(json.dumps({"success": False, "error": "Analysis has no pipeline-config stored"}))
            sys.exit(1)

        config = json.loads(pipeline_config_str)
        outputs = config.get("outputs", [])
        if not outputs:
            print(json.dumps({"success": False, "error": "pipeline-config has no 'outputs' list"}))
            sys.exit(1)

        # Step 2: Resolve inputs — merge explicit inputs with env_inputs
        inputs = dict(config.get("inputs", {}))
        for param_name, env_var in config.get("env_inputs", {}).items():
            val = os.environ.get(env_var)
            if val is None:
                print(json.dumps({"success": False, "error": f"Required env var {env_var} (for '{param_name}') is not set"}))
                sys.exit(1)
            inputs[param_name] = val

        # Step 3: Dynamically load the Hamilton module
        print("Loading pipeline module...", file=sys.stderr)
        try:
            from hamilton import driver as h_driver  # noqa: PLC0415
        except ImportError:
            print(json.dumps({"success": False, "error": "sf-hamilton not installed. Run: uv add sf-hamilton"}))
            sys.exit(1)

        mod = load_pipeline_module(pipeline_script, module_name=f"pipeline_{ana_id}")

        # Step 4: Build Hamilton driver and execute
        hamilton_cfg = config.get("hamilton", {})
        builder = h_driver.Builder().with_modules(mod)
        if hamilton_cfg.get("with_cache"):
            builder = builder.with_cache()
        dr = builder.build()

        print(f"Executing Hamilton pipeline outputs: {outputs}", file=sys.stderr)
        results_map = dr.execute(outputs, inputs=inputs)

        # Step 5: Write each output back to TypeDB
        written = {}
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            for output_name, value in results_map.items():
                attr_name = _PIPELINE_OUTPUT_ATTRS.get(output_name)
                if not attr_name:
                    print(f"Warning: unknown terminal node '{output_name}', skipping", file=sys.stderr)
                    continue

                # Serialize non-string outputs
                if output_name == "table_data":
                    value = json.dumps(value)
                elif not isinstance(value, str):
                    value = str(value)

                escaped_val = escape_string(value)

                # Delete existing attribute value, then insert new one
                tx.query(f'''
                    match $a isa tech-recon-analysis, has id "{ana_id}", has {attr_name} $old;
                    delete has $old of $a;
                ''').resolve()
                tx.query(f'''
                    match $a isa tech-recon-analysis, has id "{ana_id}";
                    insert $a has {attr_name} "{escaped_val}";
                ''').resolve()
                written[output_name] = len(value)

            tx.commit()

        print(json.dumps({
            "success": True,
            "analysis_id": args.id,
            "outputs_written": written,
        }))

    except SystemExit:
        raise
    except Exception as e:
        import traceback
        print(json.dumps({"success": False, "error": str(e), "traceback": traceback.format_exc()}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_plan_analyses(args):
    """Return investigation context for Claude to propose a visualization plan."""
    inv_id = escape_string(args.investigation)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Fetch investigation details
            inv_results = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{
                    "id": $inv.id,
                    "name": $inv.name,
                    "goal": $inv.goal-description,
                    "criteria": $inv.success-criteria
                }};
            ''').resolve())

            if not inv_results:
                print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
                sys.exit(1)

            inv = inv_results[0]

            # Fetch all systems for the investigation
            sys_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system;
                    (system: $sys, investigation: $inv) isa investigated-in;
                fetch {{
                    "id": $sys.id,
                    "name": $sys.name,
                    "status": $sys.tech-recon-status
                }};
            ''').resolve())

            systems = [
                {"id": r.get("id"), "name": r.get("name"), "status": r.get("status")}
                for r in sys_results
            ]

            # Fetch notes for each system
            notes_by_system = {}
            for sys_item in systems:
                sid = escape_string(sys_item["id"])
                note_results = list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sid}";
                        $n isa tech-recon-note;
                        (note: $n, subject: $sys) isa aboutness;
                        $n has topic $topic;
                        $n has format $fmt;
                        $n has content $content;
                    fetch {{
                        "topic": $topic,
                        "format": $fmt,
                        "content": $content
                    }};
                ''').resolve())
                if note_results:
                    notes_by_system[sys_item["id"]] = [
                        {
                            "topic": r.get("topic"),
                            "format": r.get("format"),
                            "content_preview": (r.get("content") or "")[:200],
                        }
                        for r in note_results
                    ]

            # Fetch existing analyses
            ana_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $a isa tech-recon-analysis;
                    (analysis: $a, investigation: $inv) isa analysis-of;
                fetch {{
                    "id": $a.id,
                    "title": $a.tech-recon-title,
                    "type": $a.analysis-type
                }};
            ''').resolve())

            existing_analyses = [
                {"id": r.get("id"), "title": r.get("title"), "type": r.get("type")}
                for r in ana_results
            ]

        print(json.dumps({
            "success": True,
            "investigation": {
                "id": inv.get("id"),
                "name": inv.get("name"),
                "goal": inv.get("goal"),
                "criteria": inv.get("criteria"),
            },
            "systems": systems,
            "notes_by_system": notes_by_system,
            "existing_analyses": existing_analyses,
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_compile_report(args):
    """Return full note content + investigation context for synthesis report writing."""
    inv_id = escape_string(args.investigation)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Check for existing synthesis-report
            existing_report = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $n isa tech-recon-note, has topic "synthesis-report";
                    (note: $n, subject: $inv) isa aboutness;
                fetch {{ "id": $n.id, "content": $n.content }};
            ''').resolve())

            if existing_report and not getattr(args, 'force', False):
                r = existing_report[0]
                print(json.dumps({
                    "already_exists": True,
                    "note_id": r.get("id"),
                    "content_preview": (r.get("content") or "")[:500],
                    "message": "Synthesis report already exists. Use --force to regenerate.",
                }))
                return

            # Fetch investigation
            inv_results = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{
                    "id": $inv.id,
                    "name": $inv.name,
                    "goal": $inv.goal-description,
                    "criteria": $inv.success-criteria
                }};
            ''').resolve())

            if not inv_results:
                print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
                sys.exit(1)

            inv = inv_results[0]

            # Fetch all systems
            sys_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system;
                    (system: $sys, investigation: $inv) isa investigated-in;
                fetch {{
                    "id": $sys.id,
                    "name": $sys.name,
                    "status": $sys.tech-recon-status
                }};
            ''').resolve())

            systems = [
                {"id": r.get("id"), "name": r.get("name"), "status": r.get("status")}
                for r in sys_results
            ]

            # Fetch full notes for each system (no preview truncation)
            notes_by_system = {}
            artifacts_by_system = {}
            for sys_item in systems:
                sid = escape_string(sys_item["id"])

                note_results = list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sid}";
                        $n isa tech-recon-note;
                        (note: $n, subject: $sys) isa aboutness;
                        $n has id $nid;
                        $n has topic $topic;
                        $n has format $fmt;
                        $n has content $content;
                    fetch {{
                        "id": $nid,
                        "topic": $topic,
                        "format": $fmt,
                        "content": $content
                    }};
                ''').resolve())
                if note_results:
                    notes_by_system[sys_item["id"]] = [
                        {
                            "id": r.get("id"),
                            "topic": r.get("topic"),
                            "format": r.get("format"),
                            "content": r.get("content") or "",
                        }
                        for r in note_results
                        if r.get("topic") != "fragment"  # exclude fragments from report context
                    ]

                art_results = list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sid}";
                        $art isa tech-recon-artifact;
                        (artifact: $art, source: $sys) isa sourced-from;
                        $art has id $aid;
                        $art has artifact-type $atype;
                        $art has tech-recon-url $aurl;
                    fetch {{
                        "id": $aid,
                        "type": $atype,
                        "url": $aurl
                    }};
                ''').resolve())
                if art_results:
                    artifacts_by_system[sys_item["id"]] = [
                        {"id": r.get("id"), "type": r.get("type"), "url": r.get("url")}
                        for r in art_results
                    ]

            # Fetch investigation-level notes
            inv_note_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $n isa tech-recon-note;
                    (note: $n, subject: $inv) isa aboutness;
                    $n has id $nid;
                    $n has topic $topic;
                    $n has content $content;
                fetch {{
                    "id": $nid,
                    "topic": $topic,
                    "content": $content
                }};
            ''').resolve())

            inv_notes = [
                {"id": r.get("id"), "topic": r.get("topic"), "content": r.get("content") or ""}
                for r in inv_note_results
                if r.get("topic") not in ("synthesis-report", "completion-assessment")
            ]

        print(json.dumps({
            "success": True,
            "investigation": {
                "id": inv.get("id"),
                "name": inv.get("name"),
                "goal": inv.get("goal"),
                "criteria": inv.get("criteria"),
            },
            "systems": systems,
            "notes_by_system": notes_by_system,
            "artifacts_by_system": artifacts_by_system,
            "investigation_notes": inv_notes,
            "instruction": (
                "Using the above context, write a synthesis report as a tech-recon-note "
                "with topic='synthesis-report', format='markdown', subject-id=investigation-id. "
                "Required structure:\n"
                "## Executive Summary\n"
                "## Criterion N: [criterion text]  <- one section per criterion with evidence + note IDs cited\n"
                "## System Comparison  <- prose narrative\n"
                "## Key Findings  <- 3-7 bullets\n"
                "## Gaps & Uncertainties\n\n"
                "Cite notes inline as [note:trn-abc123 -- SystemName/topic]. "
                "Run: write-note --subject-id INVESTIGATION_ID --topic synthesis-report "
                "--format markdown --content \"...\""
            ),
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


def cmd_evaluate_completion(args):
    """Return coverage stats for Claude to evaluate and write a completion assessment."""
    inv_id = escape_string(args.investigation)
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Fetch investigation
            inv_results = list(tx.query(f'''
                match $inv isa tech-recon-investigation, has id "{inv_id}";
                fetch {{
                    "id": $inv.id,
                    "name": $inv.name,
                    "goal": $inv.goal-description,
                    "criteria": $inv.success-criteria
                }};
            ''').resolve())

            if not inv_results:
                print(json.dumps({"success": False, "error": f"Investigation {args.investigation} not found"}))
                sys.exit(1)

            inv = inv_results[0]
            criteria_raw = inv.get("criteria") or ""
            # Parse criteria: split on semicolons or newlines
            import re as _re
            criteria_list = [c.strip() for c in _re.split(r'[;\n]+', criteria_raw) if c.strip()]

            # Check for existing completion assessment
            completion_exists = bool(list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $n isa tech-recon-note, has topic "completion-assessment";
                    (note: $n, subject: $inv) isa aboutness;
                fetch {{ "id": $n.id }};
            ''').resolve()))

            # Fetch all systems
            sys_results = list(tx.query(f'''
                match
                    $inv isa tech-recon-investigation, has id "{inv_id}";
                    $sys isa tech-recon-system;
                    (system: $sys, investigation: $inv) isa investigated-in;
                fetch {{
                    "id": $sys.id,
                    "name": $sys.name,
                    "status": $sys.tech-recon-status
                }};
            ''').resolve())

            systems = [
                {"id": r.get("id"), "name": r.get("name"), "status": r.get("status")}
                for r in sys_results
            ]

            # Per-system coverage stats
            coverage = []
            for sys_item in systems:
                sid = escape_string(sys_item["id"])

                artifact_count = len(list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sid}";
                        $art isa tech-recon-artifact;
                        (artifact: $art, source: $sys) isa sourced-from;
                    fetch {{ "id": $art.id }};
                ''').resolve()))

                note_results = list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sid}";
                        $n isa tech-recon-note;
                        (note: $n, subject: $sys) isa aboutness;
                        $n has topic $topic;
                    fetch {{ "topic": $topic }};
                ''').resolve())

                topics = list({r.get("topic") for r in note_results if r.get("topic")})
                has_assessment = "assessment" in topics
                has_repo_clone = bool(list(tx.query(f'''
                    match
                        $sys isa tech-recon-system, has id "{sid}";
                        $art isa tech-recon-artifact, has artifact-type "repo-clone";
                        (artifact: $art, source: $sys) isa sourced-from;
                    fetch {{ "id": $art.id }};
                ''').resolve()))

                is_shallow = (artifact_count < 3) or (not has_repo_clone)

                coverage.append({
                    "system_id": sys_item["id"],
                    "system_name": sys_item["name"],
                    "artifact_count": artifact_count,
                    "note_count": len(note_results),
                    "topics_covered": topics,
                    "has_assessment": has_assessment,
                    "has_repo_clone": has_repo_clone,
                    "is_shallow": is_shallow,
                })

        shallow_systems = [c["system_name"] for c in coverage if c["is_shallow"]]
        missing_assessment = [c["system_name"] for c in coverage if not c["has_assessment"]]

        print(json.dumps({
            "success": True,
            "investigation": {
                "id": inv.get("id"),
                "name": inv.get("name"),
                "goal": inv.get("goal"),
            },
            "criteria_list": criteria_list,
            "system_coverage": coverage,
            "completion_assessment_exists": completion_exists,
            "shallow_systems": shallow_systems,
            "systems_missing_assessment": missing_assessment,
            "instruction": (
                "Using the above coverage data, write a completion assessment as a tech-recon-note "
                "with topic='completion-assessment', format='markdown', subject-id=investigation-id.\n\n"
                "Required structure:\n"
                "| Criterion | Status (YES/PARTIAL/NO) | Strongest evidence | Gaps |\n"
                "|-----------|------------------------|-------------------|------|\n"
                "(one row per criterion)\n\n"
                "## Systems Needing More Work\n"
                "## Missing Topics\n"
                "## Recommended Next Steps\n\n"
                "YES/PARTIAL/NO definitions:\n"
                "- YES: >= 2 systems have assessment notes explicitly addressing this criterion\n"
                "- PARTIAL: evidence from only 1 system, contradictory, or inferred\n"
                "- NO: no assessment note directly addresses this criterion\n\n"
                "Run: write-note --subject-id INVESTIGATION_ID --topic completion-assessment "
                "--format markdown --content \"...\""
            ),
        }))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        driver.close()


# =============================================================================
# ARGUMENT PARSER
# =============================================================================


def build_parser():
    parser = argparse.ArgumentParser(
        description="Tech Recon CLI - Systematically investigate external software systems.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")
    subparsers.required = True

    # -- start-investigation --
    p = subparsers.add_parser("start-investigation", help="Start a new investigation")
    p.add_argument("--name", required=True, help="Investigation name")
    p.add_argument("--goal", required=True, help="Investigation goal description")
    p.add_argument("--success-criteria", required=True, help="Success criteria")
    p.add_argument("--systems", help="Comma-separated list of initial system names")
    p.set_defaults(func=cmd_start_investigation)

    # -- list-investigations --
    p = subparsers.add_parser("list-investigations", help="List all investigations")
    p.set_defaults(func=cmd_list_investigations)

    # -- show-investigation --
    p = subparsers.add_parser("show-investigation", help="Show investigation details")
    p.add_argument("--id", required=True, help="Investigation ID")
    p.set_defaults(func=cmd_show_investigation)

    # -- update-investigation --
    p = subparsers.add_parser("update-investigation", help="Update investigation status/goal/criteria")
    p.add_argument("--id", required=True, help="Investigation ID")
    p.add_argument(
        "--status",
        choices=["scoping", "ingesting", "sensemaking", "viz-planning", "analysis", "synthesis", "evaluating", "done"],
        help="New status",
    )
    p.add_argument("--goal", help="New goal description")
    p.add_argument("--success-criteria", help="New success criteria")
    p.set_defaults(func=cmd_update_investigation)

    # -- advance-iteration --
    p = subparsers.add_parser("advance-iteration", help="Increment investigation iteration counter")
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.set_defaults(func=cmd_advance_iteration)

    # -- delete-note --
    p = subparsers.add_parser("delete-note", help="Delete a note by ID")
    p.add_argument("--id", required=True, help="Note ID")
    p.set_defaults(func=cmd_delete_note)

    # -- delete-system --
    p = subparsers.add_parser("delete-system", help="Delete a system and all its data (dry-run by default)")
    p.add_argument("--id", required=True, help="System ID")
    p.add_argument("--force", action="store_true", help="Required to actually delete")
    p.set_defaults(func=cmd_delete_system)

    # -- delete-investigation --
    p = subparsers.add_parser("delete-investigation", help="Delete an investigation and all its data (dry-run by default)")
    p.add_argument("--id", required=True, help="Investigation ID")
    p.add_argument("--force", action="store_true", help="Required to actually delete")
    p.set_defaults(func=cmd_delete_investigation)

    # -- add-system --
    p = subparsers.add_parser("add-system", help="Add a system to an investigation")
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.add_argument("--name", required=True, help="System name")
    p.add_argument("--url", required=True, help="System homepage URL")
    p.add_argument("--github-url", help="GitHub repository URL")
    p.add_argument("--language", help="Primary programming language")
    p.add_argument("--license", help="Software license")
    p.add_argument("--star-count", type=int, help="GitHub star count")
    p.add_argument("--status", default="confirmed", help="System status (default: confirmed)")
    p.set_defaults(func=cmd_add_system)

    # -- approve-system --
    p = subparsers.add_parser("approve-system", help="Approve a candidate system")
    p.add_argument("--id", required=True, help="System ID")
    p.set_defaults(func=cmd_approve_system)

    # -- list-systems --
    p = subparsers.add_parser("list-systems", help="List systems for an investigation")
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.add_argument(
        "--status",
        choices=["candidate", "confirmed", "ingested", "analyzed", "excluded", "all"],
        default="all",
        help="Filter by status (default: all)",
    )
    p.set_defaults(func=cmd_list_systems)

    # -- show-system --
    p = subparsers.add_parser("show-system", help="Show full system details")
    p.add_argument("--id", required=True, help="System ID")
    p.set_defaults(func=cmd_show_system)

    # -- discover-systems --
    p = subparsers.add_parser(
        "discover-systems",
        help="Return investigation goal for Claude-driven system discovery",
    )
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.set_defaults(func=cmd_discover_systems)

    # -- ingest-page --
    p = subparsers.add_parser("ingest-page", help="Fetch a web page and record it as an artifact")
    p.add_argument("--url", required=True, help="URL of the page to fetch")
    p.add_argument("--system", required=True, help="System ID to link artifact to")
    p.set_defaults(func=cmd_ingest_page)

    # -- ingest-repo --
    p = subparsers.add_parser(
        "ingest-repo",
        help="Fetch a GitHub repo README + file tree and record as artifacts",
    )
    p.add_argument("--url", required=True, help="GitHub repo URL (e.g. https://github.com/org/repo)")
    p.add_argument("--system", required=True, help="System ID to link artifacts to")
    p.add_argument("--clone", action=argparse.BooleanOptionalAction, default=True,
                   help="Git clone the repo into ~/.alhazen/cache/repos/{owner}/{repo} (default: on). Use --no-clone to skip.")
    p.set_defaults(func=cmd_ingest_repo)

    # -- ingest-pdf --
    p = subparsers.add_parser("ingest-pdf", help="Fetch a PDF and record it as an artifact")
    p.add_argument("--url", required=True, help="URL of the PDF to fetch")
    p.add_argument("--system", required=True, help="System ID to link artifact to")
    p.set_defaults(func=cmd_ingest_pdf)

    # -- ingest-docs --
    p = subparsers.add_parser(
        "ingest-docs",
        help="Fetch a documentation site (multiple pages) and record as artifacts",
    )
    p.add_argument("--url", required=True, help="Starting URL of the docs site")
    p.add_argument("--system", required=True, help="System ID to link artifacts to")
    p.add_argument(
        "--max-pages", type=int, default=10,
        help="Maximum number of pages to fetch (default: 10)",
    )
    p.set_defaults(func=cmd_ingest_docs)

    # -- list-artifacts --
    p = subparsers.add_parser("list-artifacts", help="List artifacts linked to a system")
    p.add_argument("--system", required=True, help="System ID")
    p.add_argument(
        "--type",
        choices=["webpage", "github-repo", "pdf", "source-file", "file-tree"],
        help="Filter by artifact type",
    )
    p.set_defaults(func=cmd_list_artifacts)

    # -- show-artifact --
    p = subparsers.add_parser("show-artifact", help="Show full artifact details with content preview")
    p.add_argument("--id", required=True, help="Artifact ID")
    p.set_defaults(func=cmd_show_artifact)

    # -- cache-stats --
    p = subparsers.add_parser("cache-stats", help="Show cache directory size by content type")
    p.set_defaults(func=cmd_cache_stats)

    # -- write-note --
    p = subparsers.add_parser("write-note", help="Write a note and attach it to a system or investigation")
    p.add_argument("--subject-id", required=True, help="ID of the system or investigation to attach note to")
    p.add_argument("--topic", required=True, help="Note topic / heading")
    p.add_argument("--format", required=True, choices=["markdown", "yaml", "json"], help="Note format")
    p.add_argument("--content", required=True, help="Note content")
    p.add_argument("--tags", help="Comma-separated list of tags")
    p.add_argument("--iteration", type=int, default=1, help="Iteration number for this note (default: 1)")
    p.add_argument("--replace", action="store_true", help="Replace existing notes with same topic on same subject")
    p.set_defaults(func=cmd_write_note)

    # -- list-notes --
    p = subparsers.add_parser("list-notes", help="List notes attached to a subject entity")
    p.add_argument("--subject-id", required=True, help="System or investigation ID")
    p.add_argument("--topic", help="Filter by topic")
    p.add_argument("--format", choices=["markdown", "yaml", "json"], help="Filter by format")
    p.set_defaults(func=cmd_list_notes)

    # -- show-note --
    p = subparsers.add_parser("show-note", help="Show full note details including all tags")
    p.add_argument("--id", required=True, help="Note ID")
    p.set_defaults(func=cmd_show_note)

    # -- add-analysis --
    p = subparsers.add_parser("add-analysis", help="Add an Observable Plot analysis to an investigation")
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.add_argument("--title", required=True, help="Analysis title")
    p.add_argument("--description", help="Analysis description (optional)")
    p.add_argument("--plot-code", required=True, help="Observable Plot JavaScript code")
    p.add_argument("--query", required=True, help="TypeQL fetch query that produces the data")
    p.add_argument(
        "--analysis-type",
        default="plot",
        choices=["plot", "table", "prose"],
        help="Analysis type (default: plot)",
    )
    p.set_defaults(func=cmd_add_analysis)

    # -- list-analyses --
    p = subparsers.add_parser("list-analyses", help="List analyses linked to an investigation")
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.set_defaults(func=cmd_list_analyses)

    # -- show-analysis --
    p = subparsers.add_parser("show-analysis", help="Show full analysis details including plot code and query")
    p.add_argument("--id", required=True, help="Analysis ID")
    p.set_defaults(func=cmd_show_analysis)

    # -- run-analysis --
    p = subparsers.add_parser(
        "run-analysis",
        help="Execute a stored analysis: run its TypeQL query and return data + plot code",
    )
    p.add_argument("--id", required=True, help="Analysis ID")
    p.set_defaults(func=cmd_run_analysis)

    # -- add-pipeline --
    p = subparsers.add_parser(
        "add-pipeline",
        help="Add a Hamilton pipeline analysis to an investigation (stores script + config)",
    )
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.add_argument("--title", required=True, help="Analysis title")
    p.add_argument(
        "--pipeline-script",
        required=True,
        help="Hamilton module source code, or @path/to/file.py to read from file",
    )
    p.add_argument(
        "--pipeline-config",
        required=True,
        help='Pipeline config JSON (outputs/inputs/env_inputs), or @path/to/config.json',
    )
    p.add_argument(
        "--analysis-type",
        default="pipeline-plot",
        choices=["pipeline-plot", "pipeline-table", "pipeline-prose", "pipeline-artifact"],
        help="Analysis type (default: pipeline-plot)",
    )
    p.set_defaults(func=cmd_add_pipeline)

    # -- run-pipeline --
    p = subparsers.add_parser(
        "run-pipeline",
        help="Execute a stored Hamilton pipeline and write outputs back to TypeDB",
    )
    p.add_argument("--id", required=True, help="Analysis ID")
    p.set_defaults(func=cmd_run_pipeline)

    # -- plan-analyses --
    p = subparsers.add_parser(
        "plan-analyses",
        help="Return investigation context (systems, notes, existing analyses) for visualization planning",
    )
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.set_defaults(func=cmd_plan_analyses)

    # -- explore-repo --
    p = subparsers.add_parser(
        "explore-repo",
        help="Return clone path + file list for Explore subagent dispatch",
    )
    p.add_argument("--system", required=True, help="System ID with a repo-clone artifact")
    p.add_argument("--investigation", help="Investigation ID (optional, adds goal/criteria to output)")
    p.set_defaults(func=cmd_explore_repo)

    # -- extract-fragments --
    p = subparsers.add_parser(
        "extract-fragments",
        help="Extract code/heading fragments from a repo-clone or HTML artifact",
    )
    p.add_argument("--artifact", required=True, help="Artifact ID (repo-clone or webpage)")
    p.add_argument("--max-fragments", type=int, default=30, help="Max fragments to extract (default: 30)")
    p.set_defaults(func=cmd_extract_fragments)

    # -- compile-report --
    p = subparsers.add_parser(
        "compile-report",
        help="Return full note content + context for synthesis report writing",
    )
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.add_argument("--force", action="store_true", default=False,
                   help="Regenerate even if synthesis-report note already exists")
    p.set_defaults(func=cmd_compile_report)

    # -- evaluate-completion --
    p = subparsers.add_parser(
        "evaluate-completion",
        help="Return coverage stats for completion assessment writing",
    )
    p.add_argument("--investigation", required=True, help="Investigation ID")
    p.set_defaults(func=cmd_evaluate_completion)

    return parser


# =============================================================================
# MAIN
# =============================================================================


def main():
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
