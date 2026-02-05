#!/usr/bin/env python3
"""
TypeDB Notebook CLI - Command-line interface for Alhazen's Notebook knowledge graph.

Usage:
    python scripts/typedb_notebook.py <command> [options]

Commands:
    insert-collection   Create a new collection
    insert-paper        Add a paper to the knowledge graph
    insert-note         Create a note about an entity
    query-collection    Get collection info and members
    query-notes         Find notes about an entity
    tag                 Tag an entity
    search-tag          Search entities by tag

Examples:
    # Create a collection
    python scripts/typedb_notebook.py insert-collection --name "CRISPR Papers" --description "Papers about CRISPR"

    # Add a paper
    python scripts/typedb_notebook.py insert-paper --name "Gene Editing Study" --abstract "We demonstrate..." --doi "10.1234/example"

    # Add a note about a paper
    python scripts/typedb_notebook.py insert-note --subject paper-abc123 --content "Key finding: 95% efficiency"

    # Query notes about an entity
    python scripts/typedb_notebook.py query-notes --subject paper-abc123

Environment:
    TYPEDB_HOST     TypeDB server host (default: localhost)
    TYPEDB_PORT     TypeDB server port (default: 1729)
    TYPEDB_DATABASE Database name (default: alhazen)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from typedb.driver import TypeDB, SessionType, TransactionType
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print("Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=2.25.0,<3.0.0'", file=sys.stderr)


# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen")


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def insert_collection(args):
    """Create a new collection."""
    cid = args.id or generate_id("collection")

    query = f'insert $c isa collection, has id "{cid}", has name "{escape_string(args.name)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    if args.query:
        query += f', has logical-query "{escape_string(args.query)}"'
    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "collection_id": cid, "name": args.name}))


def insert_paper(args):
    """Add a paper to the knowledge graph."""
    pid = args.id or generate_id("paper")

    query = f'insert $p isa scilit-paper, has id "{pid}", has name "{escape_string(args.name)}"'
    if args.abstract:
        query += f', has abstract-text "{escape_string(args.abstract)}"'
    if args.doi:
        query += f', has doi "{args.doi}"'
    if args.pmid:
        query += f', has pmid "{args.pmid}"'
    if args.year:
        query += f', has publication-year {args.year}'
    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Add to collection if specified
            if args.collection:
                with session.transaction(TransactionType.WRITE) as tx:
                    add_query = f'match $c isa collection, has id "{args.collection}"; $p isa scilit-paper, has id "{pid}"; insert (collection: $c, member: $p) isa collection-membership;'
                    tx.query.insert(add_query)
                    tx.commit()

    print(json.dumps({"success": True, "paper_id": pid, "name": args.name}))


def insert_note(args):
    """Create a note about an entity."""
    nid = args.id or generate_id("note")

    # Insert the note
    query = f'insert $n isa note, has id "{nid}", has content "{escape_string(args.content)}"'
    if args.name:
        query += f', has name "{escape_string(args.name)}"'
    if args.confidence:
        query += f', has confidence {args.confidence}'
    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Create aboutness relation
            with session.transaction(TransactionType.WRITE) as tx:
                rel_query = f'match $s isa information-content-entity, has id "{args.subject}"; $n isa note, has id "{nid}"; insert (note: $n, subject: $s) isa aboutness;'
                tx.query.insert(rel_query)
                tx.commit()

            # Add tags if specified
            if args.tags:
                for tag in args.tags:
                    with session.transaction(TransactionType.WRITE) as tx:
                        # Create tag if not exists, then tag the note
                        tag_id = generate_id("tag")
                        try:
                            tx.query.insert(f'insert $t isa tag, has id "{tag_id}", has name "{tag}";')
                            tx.commit()
                        except:
                            pass  # Tag might already exist

                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.insert(f'match $n isa note, has id "{nid}"; $t isa tag, has name "{tag}"; insert (tagged-entity: $n, tag: $t) isa tagging;')
                        tx.commit()

    print(json.dumps({"success": True, "note_id": nid, "subject": args.subject}))


def query_collection(args):
    """Get collection info and members."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get collection
                result = list(tx.query.fetch(f'match $c isa collection, has id "{args.id}"; fetch $c: id, name, description;'))
                if not result:
                    print(json.dumps({"success": False, "error": "Collection not found"}))
                    return

                # Get members
                members = list(tx.query.fetch(f'match $c isa collection, has id "{args.id}"; (collection: $c, member: $m) isa collection-membership; fetch $m: id, name;'))

                print(json.dumps({
                    "success": True,
                    "collection": result[0],
                    "members": members,
                    "member_count": len(members)
                }, indent=2))


def query_notes(args):
    """Find notes about an entity."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'match $s isa information-content-entity, has id "{args.subject}"; (note: $n, subject: $s) isa aboutness; fetch $n: id, name, content, confidence;'
                results = list(tx.query.fetch(query))

                print(json.dumps({
                    "success": True,
                    "subject": args.subject,
                    "notes": results,
                    "count": len(results)
                }, indent=2))


def tag_entity(args):
    """Tag an entity."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Create tag if not exists
            tag_id = generate_id("tag")
            with session.transaction(TransactionType.WRITE) as tx:
                try:
                    tx.query.insert(f'insert $t isa tag, has id "{tag_id}", has name "{args.tag}";')
                    tx.commit()
                except:
                    pass

            # Create tagging relation
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'match $e isa information-content-entity, has id "{args.entity}"; $t isa tag, has name "{args.tag}"; insert (tagged-entity: $e, tag: $t) isa tagging;')
                tx.commit()

    print(json.dumps({"success": True, "entity": args.entity, "tag": args.tag}))


def search_tag(args):
    """Search entities by tag."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'match $t isa tag, has name "{args.tag}"; (tagged-entity: $e, tag: $t) isa tagging; fetch $e: id, name;'
                results = list(tx.query.fetch(query))

                print(json.dumps({
                    "success": True,
                    "tag": args.tag,
                    "entities": results,
                    "count": len(results)
                }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="TypeDB Notebook CLI for Alhazen's knowledge graph")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # insert-collection
    p = subparsers.add_parser("insert-collection", help="Create a new collection")
    p.add_argument("--name", required=True, help="Collection name")
    p.add_argument("--description", help="Collection description")
    p.add_argument("--query", help="Logical query defining membership")
    p.add_argument("--id", help="Specific ID (auto-generated if not provided)")

    # insert-paper
    p = subparsers.add_parser("insert-paper", help="Add a paper")
    p.add_argument("--name", required=True, help="Paper title")
    p.add_argument("--abstract", help="Paper abstract")
    p.add_argument("--doi", help="DOI")
    p.add_argument("--pmid", help="PubMed ID")
    p.add_argument("--year", type=int, help="Publication year")
    p.add_argument("--collection", help="Collection ID to add to")
    p.add_argument("--id", help="Specific ID")

    # insert-note
    p = subparsers.add_parser("insert-note", help="Create a note about an entity")
    p.add_argument("--subject", required=True, help="ID of entity this note is about")
    p.add_argument("--content", required=True, help="Note content")
    p.add_argument("--name", help="Note name/title")
    p.add_argument("--confidence", type=float, help="Confidence score (0.0-1.0)")
    p.add_argument("--tags", nargs="+", help="Tags to apply")
    p.add_argument("--id", help="Specific ID")

    # query-collection
    p = subparsers.add_parser("query-collection", help="Get collection info")
    p.add_argument("--id", required=True, help="Collection ID")

    # query-notes
    p = subparsers.add_parser("query-notes", help="Find notes about an entity")
    p.add_argument("--subject", required=True, help="Entity ID")

    # tag
    p = subparsers.add_parser("tag", help="Tag an entity")
    p.add_argument("--entity", required=True, help="Entity ID")
    p.add_argument("--tag", required=True, help="Tag name")

    # search-tag
    p = subparsers.add_parser("search-tag", help="Search by tag")
    p.add_argument("--tag", required=True, help="Tag to search for")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "insert-collection": insert_collection,
        "insert-paper": insert_paper,
        "insert-note": insert_note,
        "query-collection": query_collection,
        "query-notes": query_notes,
        "tag": tag_entity,
        "search-tag": search_tag,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
