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

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    TYPEDB_USERNAME   TypeDB username (default: admin)
    TYPEDB_PASSWORD   TypeDB password (default: password)
"""

import argparse
import json
import os
import sys

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

    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False
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
    try:
        driver = get_driver()

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

        driver.close()

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

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


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
    status = escape_string(args.status or "confirmed")

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
                "status": args.status or "confirmed",
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
    try:
        driver = get_driver()
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

        driver.close()

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

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def cmd_discover_systems(args):
    """Return investigation goal/criteria and existing systems for Claude-driven discovery."""
    inv_id = escape_string(args.investigation)
    try:
        driver = get_driver()
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

        driver.close()

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
