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
                    has status "scoping",
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
                        has status "confirmed",
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
                    "status": $inv.status,
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
                    "status": $inv.status,
                    "goal": $inv.goal-description,
                    "criteria": $inv.success-criteria
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
                            has status $old_status;
                    delete has $old_status of $inv;
                    insert $inv has status "{new_status}";
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
                optional_attrs += f', has language "{escape_string(args.language)}"'
            if args.license:
                optional_attrs += f', has license "{escape_string(args.license)}"'
            if args.star_count is not None:
                optional_attrs += f", has star-count {args.star_count}"

            sq = f'''
                insert $sys isa tech-recon-system,
                    has id "{sys_id}",
                    has name "{name}",
                    has url "{url}",
                    has status "{status}",
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
                        has status $old_status;
                delete has $old_status of $sys;
                insert $sys has status "confirmed";
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
                        "url": $sys.url,
                        "status": $sys.status,
                        "language": $sys.language,
                        "license": $sys.license,
                        "star_count": $sys.star-count
                    }};
                ''').resolve())
            else:
                esc_status = escape_string(status_filter)
                results = list(tx.query(f'''
                    match
                        $inv isa tech-recon-investigation, has id "{inv_id}";
                        $sys isa tech-recon-system, has status "{esc_status}";
                        (system: $sys, investigation: $inv) isa investigated-in;
                    fetch {{
                        "id": $sys.id,
                        "name": $sys.name,
                        "url": $sys.url,
                        "status": $sys.status,
                        "language": $sys.language,
                        "license": $sys.license,
                        "star_count": $sys.star-count
                    }};
                ''').resolve())

        driver.close()

        systems = []
        for r in results:
            systems.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "url": r.get("url"),
                "status": r.get("status"),
                "language": r.get("language"),
                "license": r.get("license"),
                "star_count": r.get("star_count"),
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
                    "url": $sys.url,
                    "status": $sys.status,
                    "github_url": $sys.github-url,
                    "language": $sys.language,
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
            has url "{esc_url}",
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
        match $sys isa tech-recon-system, has id "{escape_string(sys_id)}", has status "confirmed";
        fetch {{ "id": $sys.id }};
    ''').resolve())
    if check:
        tx.query(f'''
            match
                $sys isa tech-recon-system, has id "{escape_string(sys_id)}",
                    has status $old_status;
            delete has $old_status of $sys;
            insert $sys has status "ingested";
        ''').resolve()


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

        print(json.dumps({"success": True, "artifacts": artifacts}))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


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
                        "url": $art.url,
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
                        "url": $art.url,
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
                    "url": $art.url,
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

        # Load content preview
        content_preview = None
        cp = art.get("cache_path")
        if cp:
            try:
                text = load_from_cache_text(cp)
                content_preview = text[:500]
            except Exception as load_err:
                content_preview = f"[Error loading cache: {load_err}]"
        elif art.get("content"):
            content_preview = art.get("content")[:500]

        if content_preview is not None:
            artifact_data["content_preview"] = content_preview

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
        choices=["scoping", "ingesting", "sensemaking", "viz-planning", "analysis", "done"],
        help="New status",
    )
    p.add_argument("--goal", help="New goal description")
    p.add_argument("--success-criteria", help="New success criteria")
    p.set_defaults(func=cmd_update_investigation)

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
