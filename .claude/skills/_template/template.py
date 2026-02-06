#!/usr/bin/env python3
"""
[DOMAIN NAME] CLI - [Brief description].

This script handles INGESTION and QUERIES. Claude handles SENSEMAKING via the SKILL.md.

Usage:
    python .claude/skills/DOMAIN/DOMAIN.py <command> [options]

Commands:
    # Ingestion
    ingest              Fetch content from URL and store as artifact
    add-entity          Add an entity manually

    # Artifacts (for Claude's sensemaking)
    list-artifacts      List artifacts by analysis status
    show-artifact       Get artifact content for Claude to read

    # Queries
    list-entities       List all entities
    show-entity         Get entity details

    # Updates
    update-status       Update entity status
    add-note            Create a note about any entity
    tag                 Tag an entity
    search-tag          Search by tag

Environment:
    TYPEDB_HOST     TypeDB server host (default: localhost)
    TYPEDB_PORT     TypeDB server port (default: 1729)
    TYPEDB_DATABASE Database name (default: alhazen_notebook)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

# Optional: for URL fetching
try:
    import requests
    from bs4 import BeautifulSoup

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# TypeDB driver
try:
    from typedb.driver import SessionType, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=2.25.0,<3.0.0'",
        file=sys.stderr,
    )


# =============================================================================
# CONFIGURATION
# =============================================================================

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")

# TODO: Update these constants for your domain
DOMAIN_PREFIX = "domain"  # e.g., "jobhunt", "scilit"
ENTITY_TYPE = f"{DOMAIN_PREFIX}-entity"
ARTIFACT_TYPE = f"{DOMAIN_PREFIX}-artifact"


# =============================================================================
# UTILITIES
# =============================================================================


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def get_attr(entity: dict, attr_name: str, default=None):
    """Safely extract attribute value from TypeDB fetch result.

    TypeDB fetch returns attributes as arrays, e.g.:
    {'id': [{'value': 'abc', 'type': {...}}], 'name': [...]}

    This helper extracts the first value or returns default.
    """
    attr_list = entity.get(attr_name, [])
    if attr_list and len(attr_list) > 0:
        return attr_list[0].get("value", default)
    return default


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def fetch_url_content(url: str) -> tuple[str, str]:
    """
    Fetch URL and return (title, text_content).

    Returns basic parsed content - Claude will do the intelligent extraction.
    """
    if not REQUESTS_AVAILABLE:
        return "", ""

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        title = soup.title.string if soup.title else ""

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        # Limit content size
        if len(text) > 50000:
            text = text[:50000] + "\n... [truncated]"

        return title, text

    except Exception as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return "", ""


# =============================================================================
# INGESTION COMMANDS
# =============================================================================


def cmd_ingest(args):
    """
    Fetch content from URL and store as artifact.

    This implements the INGESTION phase of the curation pattern:
    - Fetches URL content (raw, unedited)
    - Stores as artifact with provenance
    - Creates placeholder entity
    - Claude does the SENSEMAKING separately
    """
    if not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests/beautifulsoup4 not installed"}))
        return

    url = args.url
    title, content = fetch_url_content(url)

    if not content:
        print(json.dumps({"success": False, "error": "Could not fetch URL content"}))
        return

    # Generate IDs
    entity_id = generate_id("entity")
    artifact_id = generate_id("artifact")
    timestamp = get_timestamp()

    placeholder_name = title if title else f"Content from {url[:50]}"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Create entity placeholder
            with session.transaction(TransactionType.WRITE) as tx:
                entity_query = f'''insert $e isa {ENTITY_TYPE},
                    has id "{entity_id}",
                    has name "{escape_string(placeholder_name)}",
                    has created-at {timestamp};'''
                tx.query.insert(entity_query)
                tx.commit()

            # Create artifact with raw content
            with session.transaction(TransactionType.WRITE) as tx:
                artifact_query = f'''insert $a isa {ARTIFACT_TYPE},
                    has id "{artifact_id}",
                    has name "Content: {escape_string(placeholder_name)}",
                    has content "{escape_string(content)}",
                    has source-uri "{escape_string(url)}",
                    has created-at {timestamp};'''
                tx.query.insert(artifact_query)
                tx.commit()

            # Link artifact to entity
            with session.transaction(TransactionType.WRITE) as tx:
                rep_query = f'''match
                    $a isa {ARTIFACT_TYPE}, has id "{artifact_id}";
                    $e isa {ENTITY_TYPE}, has id "{entity_id}";
                insert (artifact: $a, referent: $e) isa representation;'''
                tx.query.insert(rep_query)
                tx.commit()

            # Add tags if specified
            if args.tags:
                for tag_name in args.tags:
                    tag_id = generate_id("tag")
                    with session.transaction(TransactionType.READ) as tx:
                        tag_check = f'match $t isa tag, has name "{tag_name}"; fetch $t: id;'
                        existing_tag = list(tx.query.fetch(tag_check))

                    if not existing_tag:
                        with session.transaction(TransactionType.WRITE) as tx:
                            tx.query.insert(
                                f'insert $t isa tag, has id "{tag_id}", has name "{tag_name}";'
                            )
                            tx.commit()

                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.insert(f'''match
                            $e isa {ENTITY_TYPE}, has id "{entity_id}";
                            $t isa tag, has name "{tag_name}";
                        insert (tagged-entity: $e, tag: $t) isa tagging;''')
                        tx.commit()

    print(
        json.dumps(
            {
                "success": True,
                "entity_id": entity_id,
                "artifact_id": artifact_id,
                "url": url,
                "content_length": len(content),
                "status": "raw",
                "message": "Content ingested. Artifact stored - ask Claude to 'analyze this' for sensemaking.",
            },
            indent=2,
        )
    )


def cmd_add_entity(args):
    """Add an entity manually."""
    entity_id = args.id or generate_id("entity")
    timestamp = get_timestamp()

    query = f'''insert $e isa {ENTITY_TYPE},
        has id "{entity_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "entity_id": entity_id, "name": args.name}))


# =============================================================================
# ARTIFACT COMMANDS
# =============================================================================


def cmd_list_artifacts(args):
    """List artifacts, optionally filtered by analysis status."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f"""match
                    $a isa {ARTIFACT_TYPE};
                fetch $a: id, name, source-uri, created-at;"""
                artifacts = list(tx.query.fetch(query))

                results = []
                for art in artifacts:
                    artifact_id = get_attr(art["a"], "id")

                    # Check for notes (simple heuristic for "analyzed")
                    notes_query = f'''match
                        $a isa {ARTIFACT_TYPE}, has id "{artifact_id}";
                        (artifact: $a, referent: $e) isa representation;
                        (note: $n, subject: $e) isa aboutness;
                    fetch $n: id;'''

                    try:
                        notes = list(tx.query.fetch(notes_query))
                        has_notes = len(notes) > 0
                    except Exception:
                        has_notes = False

                    status = "analyzed" if has_notes else "raw"

                    if args.status and args.status != "all":
                        if args.status != status:
                            continue

                    results.append(
                        {
                            "id": artifact_id,
                            "name": get_attr(art["a"], "name"),
                            "source_url": get_attr(art["a"], "source-uri"),
                            "created_at": get_attr(art["a"], "created-at"),
                            "status": status,
                        }
                    )

    print(
        json.dumps(
            {
                "success": True,
                "artifacts": results,
                "count": len(results),
                "filter": args.status or "all",
            },
            indent=2,
        )
    )


def cmd_show_artifact(args):
    """Get artifact content for Claude to read during sensemaking."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match
                    $a isa {ARTIFACT_TYPE}, has id "{args.id}";
                fetch $a: id, name, content, source-uri, created-at;'''
                result = list(tx.query.fetch(query))

                if not result:
                    print(json.dumps({"success": False, "error": "Artifact not found"}))
                    return

                # Get linked entity
                entity_query = f'''match
                    $a isa {ARTIFACT_TYPE}, has id "{args.id}";
                    (artifact: $a, referent: $e) isa representation;
                fetch $e: id, name;'''
                entity_result = list(tx.query.fetch(entity_query))

    art = result[0]["a"]
    output = {
        "success": True,
        "artifact": {
            "id": get_attr(art, "id"),
            "name": get_attr(art, "name"),
            "source_url": get_attr(art, "source-uri"),
            "created_at": get_attr(art, "created-at"),
            "content": get_attr(art, "content"),
        },
        "entity": None,
    }

    if entity_result:
        ent = entity_result[0]["e"]
        output["entity"] = {
            "id": get_attr(ent, "id"),
            "name": get_attr(ent, "name"),
        }

    print(json.dumps(output, indent=2))


# =============================================================================
# QUERY COMMANDS
# =============================================================================


def cmd_list_entities(args):
    """List all entities."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f"""match
                    $e isa {ENTITY_TYPE};
                fetch $e: id, name, created-at;"""
                results = list(tx.query.fetch(query))

    entities = []
    for r in results:
        entities.append(
            {
                "id": get_attr(r["e"], "id"),
                "name": get_attr(r["e"], "name"),
                "created_at": get_attr(r["e"], "created-at"),
            }
        )

    print(json.dumps({"success": True, "entities": entities, "count": len(entities)}, indent=2))


def cmd_show_entity(args):
    """Get entity details."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match
                    $e isa {ENTITY_TYPE}, has id "{args.id}";
                fetch $e: id, name, description, created-at;'''
                result = list(tx.query.fetch(query))

                if not result:
                    print(json.dumps({"success": False, "error": "Entity not found"}))
                    return

                # Get notes
                notes_query = f'''match
                    $e isa {ENTITY_TYPE}, has id "{args.id}";
                    (note: $n, subject: $e) isa aboutness;
                fetch $n: id, name, content;'''
                notes_result = list(tx.query.fetch(notes_query))

                # Get tags
                tags_query = f'''match
                    $e isa {ENTITY_TYPE}, has id "{args.id}";
                    (tagged-entity: $e, tag: $t) isa tagging;
                fetch $t: name;'''
                tags_result = list(tx.query.fetch(tags_query))

    output = {
        "success": True,
        "entity": result[0]["e"],
        "notes": [n["n"] for n in notes_result],
        "tags": [get_attr(t["t"], "name") for t in tags_result],
    }

    print(json.dumps(output, indent=2, default=str))


# =============================================================================
# UPDATE COMMANDS
# =============================================================================


def cmd_add_note(args):
    """Create a note about an entity."""
    note_id = args.id or generate_id("note")
    timestamp = get_timestamp()

    query = f'''insert $n isa note,
        has id "{note_id}",
        has content "{escape_string(args.content)}",
        has created-at {timestamp}'''

    if args.name:
        query += f', has name "{escape_string(args.name)}"'
    if args.confidence:
        query += f", has confidence {args.confidence}"

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                about_query = f'''match
                    $n isa note, has id "{note_id}";
                    $s isa entity, has id "{args.about}";
                insert (note: $n, subject: $s) isa aboutness;'''
                tx.query.insert(about_query)
                tx.commit()

            if args.tags:
                for tag_name in args.tags:
                    tag_id = generate_id("tag")
                    with session.transaction(TransactionType.READ) as tx:
                        tag_check = f'match $t isa tag, has name "{tag_name}"; fetch $t: id;'
                        existing_tag = list(tx.query.fetch(tag_check))

                    if not existing_tag:
                        with session.transaction(TransactionType.WRITE) as tx:
                            tx.query.insert(
                                f'insert $t isa tag, has id "{tag_id}", has name "{tag_name}";'
                            )
                            tx.commit()

                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.insert(f'''match
                            $n isa note, has id "{note_id}";
                            $t isa tag, has name "{tag_name}";
                        insert (tagged-entity: $n, tag: $t) isa tagging;''')
                        tx.commit()

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about}))


def cmd_tag(args):
    """Tag an entity."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            tag_id = generate_id("tag")
            with session.transaction(TransactionType.READ) as tx:
                tag_check = f'match $t isa tag, has name "{args.tag}"; fetch $t: id;'
                existing_tag = list(tx.query.fetch(tag_check))

            if not existing_tag:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(f'insert $t isa tag, has id "{tag_id}", has name "{args.tag}";')
                    tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'''match
                    $e isa entity, has id "{args.entity}";
                    $t isa tag, has name "{args.tag}";
                insert (tagged-entity: $e, tag: $t) isa tagging;''')
                tx.commit()

    print(json.dumps({"success": True, "entity": args.entity, "tag": args.tag}))


def cmd_search_tag(args):
    """Search entities by tag."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match
                    $t isa tag, has name "{args.tag}";
                    (tagged-entity: $e, tag: $t) isa tagging;
                fetch $e: id, name;'''
                results = list(tx.query.fetch(query))

    print(
        json.dumps(
            {
                "success": True,
                "tag": args.tag,
                "entities": [r["e"] for r in results],
                "count": len(results),
            },
            indent=2,
            default=str,
        )
    )


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="[DOMAIN] CLI - [Brief description]"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ingest
    p = subparsers.add_parser("ingest", help="Fetch content from URL and store as artifact")
    p.add_argument("--url", required=True, help="Source URL")
    p.add_argument("--tags", nargs="+", help="Tags to apply")

    # add-entity
    p = subparsers.add_parser("add-entity", help="Add an entity manually")
    p.add_argument("--name", required=True, help="Entity name")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # list-artifacts
    p = subparsers.add_parser("list-artifacts", help="List artifacts by status")
    p.add_argument(
        "--status",
        choices=["raw", "analyzed", "all"],
        help="Filter: raw, analyzed, or all",
    )

    # show-artifact
    p = subparsers.add_parser("show-artifact", help="Get artifact content")
    p.add_argument("--id", required=True, help="Artifact ID")

    # list-entities
    subparsers.add_parser("list-entities", help="List all entities")

    # show-entity
    p = subparsers.add_parser("show-entity", help="Get entity details")
    p.add_argument("--id", required=True, help="Entity ID")

    # add-note
    p = subparsers.add_parser("add-note", help="Create a note")
    p.add_argument("--about", required=True, help="Entity ID this note is about")
    p.add_argument("--content", required=True, help="Note content")
    p.add_argument("--name", help="Note title")
    p.add_argument("--confidence", type=float, help="Confidence score (0.0-1.0)")
    p.add_argument("--tags", nargs="+", help="Tags to apply")
    p.add_argument("--id", help="Specific ID")

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
        "ingest": cmd_ingest,
        "add-entity": cmd_add_entity,
        "list-artifacts": cmd_list_artifacts,
        "show-artifact": cmd_show_artifact,
        "list-entities": cmd_list_entities,
        "show-entity": cmd_show_entity,
        "add-note": cmd_add_note,
        "tag": cmd_tag,
        "search-tag": cmd_search_tag,
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
