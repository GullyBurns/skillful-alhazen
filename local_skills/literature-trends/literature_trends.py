#!/usr/bin/env python3
"""
Literature Trends CLI - Abductive argumentation analysis for scientific literature.

Trace the evolution of explanatory hypotheses across time windows within a
keyword-tagged paper cluster.

Usage:
    literature_trends.py create-thread --name "..." --keyword "..." --source-collection "col-id"
    literature_trends.py record-hypothesis --thread "sltrend-thread-id" --window "2016-2018" --content "..."
    literature_trends.py record-genealogy --predecessor "note-id" --successor "note-id" --type "extends"
    literature_trends.py show-thread --thread "sltrend-thread-id"

Environment:
    TYPEDB_HOST         TypeDB host (default: localhost)
    TYPEDB_PORT         TypeDB port (default: 1729)
    TYPEDB_DATABASE     Database name (default: alhazen_notebook)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print("Warning: typedb-driver not installed. Run: uv sync --all-extras", file=sys.stderr)

try:
    from skillful_alhazen.utils.skill_helpers import escape_string, generate_id, get_timestamp
except ImportError:
    def escape_string(s):
        if s is None:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")

    def generate_id(prefix):
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def get_timestamp():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# =============================================================================
# CONFIGURATION
# =============================================================================

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

GENEALOGY_TYPES = {"refines", "extends", "challenges", "supersedes"}


# =============================================================================
# TYPEDB HELPERS
# =============================================================================

def get_driver():
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


# =============================================================================
# COMMANDS
# =============================================================================

def cmd_create_thread(args):
    """Create a sltrend-thread entity linked to a keyword and source collection."""
    thread_id = generate_id("sltrend-thread")
    timestamp = get_timestamp()
    name = escape_string(args.name)
    keyword = escape_string(args.keyword)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            q = (
                f'insert $t isa sltrend-thread, '
                f'has id "{thread_id}", '
                f'has name "{name}", '
                f'has sltrend-keyword "{keyword}", '
                f'has created-at {timestamp};'
            )
            tx.query(q).resolve()
            tx.commit()

        # Link to source collection via alh-note-threading (thread as a meta-note about the collection)
        if args.source_collection:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                link_q = (
                    f'match $t isa sltrend-thread, has id "{thread_id}"; '
                    f'$c isa alh-collection, has id "{escape_string(args.source_collection)}"; '
                    f'insert (collection: $t, member: $c) isa alh-collection-membership, '
                    f'has created-at {timestamp};'
                )
                try:
                    tx.query(link_q).resolve()
                    tx.commit()
                except Exception as e:
                    print(f"Warning: could not link to source collection: {e}", file=sys.stderr)

    print(json.dumps({
        "success": True,
        "thread_id": thread_id,
        "name": args.name,
        "keyword": args.keyword,
        "source_collection": args.source_collection,
    }, indent=2))


def cmd_record_hypothesis(args):
    """Store a sltrend-hypothesis-note and add it to the thread."""
    note_id = generate_id("sltrend-hyp-note")
    timestamp = get_timestamp()
    content = escape_string(args.content)
    window = escape_string(args.window)
    thread_id = escape_string(args.thread)
    title = escape_string(args.title or f"Hypothesis: {args.window}")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            q = (
                f'insert $n isa sltrend-hypothesis-note, '
                f'has id "{note_id}", '
                f'has name "{title}", '
                f'has content "{content}", '
                f'has sltrend-window "{window}", '
                f'has created-at {timestamp};'
            )
            if args.role:
                q = q.rstrip(";") + f', has sltrend-abductive-role "{escape_string(args.role)}";'
            tx.query(q).resolve()
            tx.commit()

        # Link to thread via alh-collection-membership
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            link_q = (
                f'match $t isa sltrend-thread, has id "{thread_id}"; '
                f'$n isa sltrend-hypothesis-note, has id "{note_id}"; '
                f'insert (collection: $t, member: $n) isa alh-collection-membership, '
                f'has created-at {timestamp};'
            )
            tx.query(link_q).resolve()
            tx.commit()

        # Link to subject collection via aboutness if provided
        if args.subject:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                about_q = (
                    f'match $n isa sltrend-hypothesis-note, has id "{note_id}"; '
                    f'$s isa alh-collection, has id "{escape_string(args.subject)}"; '
                    f'insert (note: $n, subject: $s) isa alh-aboutness, '
                    f'has created-at {timestamp};'
                )
                try:
                    tx.query(about_q).resolve()
                    tx.commit()
                except Exception as e:
                    print(f"Warning: could not link to subject: {e}", file=sys.stderr)

    print(json.dumps({
        "success": True,
        "note_id": note_id,
        "thread": args.thread,
        "window": args.window,
    }, indent=2))


def cmd_record_genealogy(args):
    """Insert a sltrend-hypothesis-genealogy edge between two sltrend-hypothesis-note IDs."""
    timestamp = get_timestamp()
    pred_id = escape_string(args.predecessor)
    succ_id = escape_string(args.successor)
    gtype = escape_string(args.type)

    if args.type not in GENEALOGY_TYPES:
        print(json.dumps({
            "success": False,
            "error": f"Invalid genealogy type '{args.type}'. Must be one of: {sorted(GENEALOGY_TYPES)}",
        }))
        sys.exit(1)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            q = (
                f'match $p isa sltrend-hypothesis-note, has id "{pred_id}"; '
                f'$s isa sltrend-hypothesis-note, has id "{succ_id}"; '
                f'insert (predecessor: $p, successor: $s) isa sltrend-hypothesis-genealogy, '
                f'has sltrend-genealogy-type "{gtype}"'
            )
            if args.description:
                q += f', has description "{escape_string(args.description)}"'
            q += ";"
            tx.query(q).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "predecessor": args.predecessor,
        "successor": args.successor,
        "type": args.type,
    }, indent=2))


def cmd_show_thread(args):
    """Fetch the full genealogy chain for a trend thread, ordered by sltrend-window."""
    thread_id = escape_string(args.thread)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Fetch thread metadata
            thread_result = list(tx.query(
                f'match $t isa sltrend-thread, has id "{thread_id}"; '
                f'fetch {{ "id": $t.id, "name": $t.name, "keyword": $t.sltrend-keyword }};'
            ).resolve())

            if not thread_result:
                print(json.dumps({"success": False, "error": f"Thread not found: {thread_id}"}))
                sys.exit(1)

            thread = thread_result[0]

            # Fetch all hypothesis notes in this thread
            notes_result = list(tx.query(
                f'match $t isa sltrend-thread, has id "{thread_id}"; '
                f'(collection: $t, member: $n) isa alh-collection-membership; '
                f'$n isa sltrend-hypothesis-note, has sltrend-window $w; '
                f'fetch {{ "id": $n.id, "name": $n.name, "window": $w, '
                f'"content": $n.content, "role": $n.sltrend-abductive-role }};'
            ).resolve())

            notes = [{k: v for k, v in r.items() if v is not None} for r in notes_result]
            notes.sort(key=lambda n: n.get("window", ""))

            # Fetch genealogy edges between these notes
            note_ids = [n["id"] for n in notes]
            genealogy_edges = []
            for nid in note_ids:
                edges = list(tx.query(
                    f'match $p isa sltrend-hypothesis-note, has id "{nid}"; '
                    f'(predecessor: $p, successor: $s) isa sltrend-hypothesis-genealogy, '
                    f'has sltrend-genealogy-type $gtype; '
                    f'$s has id $sid; '
                    f'fetch {{ "predecessor": $p.id, "successor": $sid, "type": $gtype }};'
                ).resolve())
                genealogy_edges.extend(edges)

    print(json.dumps({
        "success": True,
        "thread": thread,
        "hypotheses": notes,
        "genealogy": genealogy_edges,
        "count": len(notes),
    }, indent=2))


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Literature Trends CLI - abductive argumentation for scientific literature"
    )
    subparsers = parser.add_subparsers(dest="command")

    # create-thread
    p = subparsers.add_parser("create-thread", help="Create a trend analysis thread")
    p.add_argument("--name", required=True, help="Human-readable name for this trend thread")
    p.add_argument("--keyword", "-k", required=True, help="Keyword tag that defines this thread's papers")
    p.add_argument("--source-collection", "-c", dest="source_collection",
                   help="Collection ID of the source paper collection")

    # record-hypothesis
    p = subparsers.add_parser("record-hypothesis", help="Record a hypothesis note for a time window")
    p.add_argument("--thread", required=True, help="Trend thread ID")
    p.add_argument("--window", "-w", required=True, help="Time window string (e.g. '2016-2018')")
    p.add_argument("--content", required=True, help="Markdown content for the hypothesis note")
    p.add_argument("--title", help="Note title (defaults to 'Hypothesis: <window>')")
    p.add_argument("--role", help="Abductive role (phenomenon|hypothesis|evidence|gap)")
    p.add_argument("--subject", help="Collection/entity ID to link via aboutness")

    # record-genealogy
    p = subparsers.add_parser("record-genealogy", help="Link two hypothesis notes in a genealogy edge")
    p.add_argument("--predecessor", required=True, help="Earlier hypothesis note ID")
    p.add_argument("--successor", required=True, help="Later hypothesis note ID")
    p.add_argument("--type", required=True,
                   choices=sorted(GENEALOGY_TYPES),
                   help="Genealogy type: refines|extends|challenges|supersedes")
    p.add_argument("--description", help="Human-readable description of the relationship")

    # show-thread
    p = subparsers.add_parser("show-thread", help="Show the full genealogy chain for a thread")
    p.add_argument("--thread", required=True, help="Trend thread ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed. Run: uv sync --all-extras"}))
        sys.exit(1)

    commands = {
        "create-thread": cmd_create_thread,
        "record-hypothesis": cmd_record_hypothesis,
        "record-genealogy": cmd_record_genealogy,
        "show-thread": cmd_show_thread,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
