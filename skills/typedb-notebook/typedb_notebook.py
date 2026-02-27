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
import shutil
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )


# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


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
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
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
        query += f", has publication-year {args.year}"
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Add to collection if specified
        if args.collection:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                add_query = f'match $c isa collection, has id "{args.collection}"; $p isa scilit-paper, has id "{pid}"; insert (collection: $c, member: $p) isa collection-membership;'
                tx.query(add_query).resolve()
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
        query += f", has confidence {args.confidence}"
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Create aboutness relation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            rel_query = f'match $s isa identifiable-entity, has id "{args.subject}"; $n isa note, has id "{nid}"; insert (note: $n, subject: $s) isa aboutness;'
            tx.query(rel_query).resolve()
            tx.commit()

        # Add tags if specified
        if args.tags:
            for tag in args.tags:
                tag_id = generate_id("tag")
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    try:
                        tx.query(f'insert $t isa tag, has id "{tag_id}", has name "{tag}";').resolve()
                        tx.commit()
                    except Exception:
                        tx.rollback()  # Tag might already exist

                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(
                        f'match $n isa note, has id "{nid}"; $t isa tag, has name "{tag}"; insert (tagged-entity: $n, tag: $t) isa tagging;'
                    ).resolve()
                    tx.commit()

    print(json.dumps({"success": True, "note_id": nid, "subject": args.subject}))


def query_collection(args):
    """Get collection info and members."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get collection
            result = list(tx.query(
                f'match $c isa collection, has id "{args.id}"; '
                f'fetch {{ "id": $c.id, "name": $c.name, "description": $c.description }};'
            ).resolve())
            if not result:
                print(json.dumps({"success": False, "error": "Collection not found"}))
                return

            # Get members
            members = list(tx.query(
                f'match $c isa collection, has id "{args.id}"; '
                f'(collection: $c, member: $m) isa collection-membership; '
                f'fetch {{ "id": $m.id, "name": $m.name }};'
            ).resolve())

        print(
            json.dumps(
                {
                    "success": True,
                    "collection": {k: v for k, v in result[0].items() if v is not None},
                    "members": [{k: v for k, v in m.items() if v is not None} for m in members],
                    "member_count": len(members),
                },
                indent=2,
            )
        )


def query_notes(args):
    """Find notes about an entity."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = (
                f'match $s isa identifiable-entity, has id "{args.subject}"; '
                f'(note: $n, subject: $s) isa aboutness; '
                f'fetch {{ "id": $n.id, "name": $n.name, "content": $n.content, "confidence": $n.confidence }};'
            )
            results = [{k: v for k, v in r.items() if v is not None}
                       for r in tx.query(query).resolve()]

        print(
            json.dumps(
                {
                    "success": True,
                    "subject": args.subject,
                    "notes": results,
                    "count": len(results),
                },
                indent=2,
            )
        )


def tag_entity(args):
    """Tag an entity."""
    with get_driver() as driver:
        # Create tag if not exists
        tag_id = generate_id("tag")
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            try:
                tx.query(f'insert $t isa tag, has id "{tag_id}", has name "{args.tag}";').resolve()
                tx.commit()
            except Exception:
                tx.rollback()  # Tag might already exist

        # Create tagging relation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $e isa identifiable-entity, has id "{args.entity}"; $t isa tag, has name "{args.tag}"; insert (tagged-entity: $e, tag: $t) isa tagging;'
            ).resolve()
            tx.commit()

    print(json.dumps({"success": True, "entity": args.entity, "tag": args.tag}))


def search_tag(args):
    """Search entities by tag."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = (
                f'match $t isa tag, has name "{args.tag}"; '
                f'(tagged-entity: $e, tag: $t) isa tagging; '
                f'fetch {{ "id": $e.id, "name": $e.name }};'
            )
            results = [{k: v for k, v in r.items() if v is not None}
                       for r in tx.query(query).resolve()]

        print(
            json.dumps(
                {
                    "success": True,
                    "tag": args.tag,
                    "entities": results,
                    "count": len(results),
                },
                indent=2,
            )
        )


def export_db(args):
    """Export the full TypeDB database using the TypeDB Python driver API."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        return

    database = args.database or TYPEDB_DATABASE

    # Build timestamped folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{database}_export_{timestamp}"

    # Determine cache directory
    cache_dir_env = os.getenv("ALHAZEN_CACHE_DIR")
    if cache_dir_env:
        cache_dir = Path(cache_dir_env).expanduser()
    else:
        cache_dir = Path.home() / ".alhazen" / "cache"
    export_dir = cache_dir / "typedb" / folder_name
    export_dir.mkdir(parents=True, exist_ok=True)

    schema_file = f"{database}_schema.typeql"
    data_file = f"{database}_data.typedb"
    local_schema = export_dir / schema_file
    local_data = export_dir / data_file

    print(f"Exporting database '{database}' via Python driver...", file=sys.stderr)

    with get_driver() as driver:
        db = driver.databases.get(database)
        db.export_to_file(str(local_schema), str(local_data))

    # Create zip archive
    zip_path = export_dir.parent / f"{folder_name}.zip"
    print(f"Creating zip archive...", file=sys.stderr)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath in export_dir.iterdir():
            zf.write(filepath, f"{folder_name}/{filepath.name}")

    # Get file sizes
    schema_size = local_schema.stat().st_size
    data_size = local_data.stat().st_size
    zip_size = zip_path.stat().st_size

    # Remove unzipped folder (keep only the zip)
    shutil.rmtree(export_dir)

    print(json.dumps({
        "success": True,
        "database": database,
        "timestamp": timestamp,
        "zip_path": str(zip_path),
        "zip_size": zip_size,
        "contents": {
            "schema": {"file": schema_file, "size": schema_size},
            "data": {"file": data_file, "size": data_size},
        },
    }, indent=2))


def import_db(args):
    """Import a TypeDB database from a previously exported zip using the Python driver API."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        return

    zip_path = Path(args.zip).expanduser()
    if not zip_path.exists():
        print(json.dumps({"success": False, "error": f"File not found: {zip_path}"}))
        return

    database = args.database

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        # Find the schema and data files
        schema_file = None
        data_file = None
        for f in tmpdir.rglob("*"):
            if f.suffix == ".typeql":
                schema_file = f
            elif f.suffix == ".typedb":
                data_file = f

        if not schema_file or not data_file:
            print(json.dumps({
                "success": False,
                "error": "Zip must contain one .typeql (schema) and one .typedb (data) file"
            }))
            return

        print(f"Importing database '{database}' via Python driver...", file=sys.stderr)

        schema_text = schema_file.read_text()

        with get_driver() as driver:
            driver.databases.import_from_file(database, schema_text, str(data_file))

    print(json.dumps({
        "success": True,
        "database": database,
        "source": str(zip_path),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="TypeDB Notebook CLI for Alhazen's knowledge graph"
    )
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

    # export-db
    p = subparsers.add_parser("export-db", help="Export database to timestamped zip")
    p.add_argument("--database", help=f"Database name (default: {TYPEDB_DATABASE})")

    # import-db
    p = subparsers.add_parser("import-db", help="Import database from exported zip")
    p.add_argument("--zip", required=True, help="Path to the export zip file")
    p.add_argument("--database", required=True, help="Target database name (must not exist)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    commands = {
        "insert-collection": insert_collection,
        "insert-paper": insert_paper,
        "insert-note": insert_note,
        "query-collection": query_collection,
        "query-notes": query_notes,
        "tag": tag_entity,
        "search-tag": search_tag,
        "export-db": export_db,
        "import-db": import_db,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
