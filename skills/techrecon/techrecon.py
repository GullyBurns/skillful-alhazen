#!/usr/bin/env python3
"""
Tech Recon CLI - Systematically investigate external software systems.

This script handles INGESTION and QUERIES. Claude handles SENSEMAKING via the SKILL.md.

Usage:
    python .claude/skills/techrecon/techrecon.py <command> [options]

Commands:
    # Investigation Management
    start-investigation   Start a new investigation
    list-investigations   List investigations (with summary counts)
    show-investigation    Show investigation details with all members
    update-investigation  Update investigation status

    # Entity Creation
    add-system            Add a software system
    add-component         Add a component/module
    add-concept           Add a key concept
    add-data-model        Add a data model/schema

    # Ingestion
    ingest-repo           Ingest a GitHub repository (README + file tree)
    clone-repo            Clone a GitHub repo locally for native file exploration
    ingest-doc            Ingest a documentation page
    ingest-source         Ingest a source code file
    ingest-schema         Ingest a schema/model file
    ingest-model-card     Ingest a HuggingFace model card

    # Linking
    link-component        Link component to system
    link-concept          Link concept to component
    link-data-model       Link data model to system
    link-dependency       Link system dependency
    link-paper            Link system to a scilit-paper (cross-skill)

    # Queries
    list-systems          List all systems
    show-system           Show system details
    show-architecture     Show system architecture (components + relations)
    list-artifacts        List artifacts
    show-artifact         Show artifact content
    show-component        Show component details
    show-concept          Show concept details
    show-data-model       Show data model details

    # Workflows
    add-workflow          Document how a system expects to be invoked
    list-workflows        List workflows for a system
    show-workflow         Show workflow details

    # Notes and Fragments
    add-note              Add a note about any entity
    add-fragment          Add a fragment extracted from an artifact

    # Tagging
    tag                   Tag an entity
    search-tag            Search by tag

    # Comparisons
    list-comparisons      List comparison notes (optionally filtered by investigation)
    show-comparison       Show a specific comparison note

    # Benchmarks
    add-benchmark         Add a quantitative performance metric to a system
    show-benchmarks       Show all benchmarks for a system

    # Design Decisions
    add-decision          Add a design decision for a system or component
    show-decisions        Show all design decisions for a system or component

    # Cache
    cache-stats           Show cache statistics

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    TYPEDB_USERNAME   TypeDB username (default: admin)
    TYPEDB_PASSWORD   TypeDB password (default: password)
    ALHAZEN_CACHE_DIR File cache directory (default: ~/.alhazen/cache)
    GITHUB_TOKEN      GitHub API token (optional, for higher rate limits)
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print(
        "Warning: requests not installed. Install with: pip install requests",
        file=sys.stderr,
    )

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

# Cache utilities
try:
    from skillful_alhazen.utils.cache import (
        get_cache_stats,
        load_from_cache_text,
        save_to_cache,
        should_cache,
        format_size,
    )

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

    def should_cache(content):
        return False

    def get_cache_stats():
        return {"error": "Cache module not available"}

    def format_size(size):
        return f"{size} bytes"


# =============================================================================
# CONFIGURATION
# =============================================================================

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


# =============================================================================
# UTILITIES
# =============================================================================


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
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def get_attr(entity: dict, attr_name: str, default=None):
    """Safely extract attribute value from TypeDB 3.x fetch result.

    TypeDB 3.x fetch returns plain Python dicts directly.
    """
    return entity.get(attr_name, default)


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def github_headers() -> dict:
    """Get GitHub API headers with optional auth."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "skillful-alhazen-techrecon",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def parse_github_url(url: str) -> tuple:
    """Parse a GitHub URL into (owner, repo).

    Handles:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        https://github.com/owner/repo/tree/branch/path
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None, None
    owner = parts[0]
    repo = parts[1].replace(".git", "")
    return owner, repo


def fetch_url_content(url: str) -> tuple:
    """Fetch URL and return (title, text_content)."""
    if not REQUESTS_AVAILABLE:
        return "", ""

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Try to parse as HTML
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            title = soup.title.string if soup.title else ""
            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)
            if len(text) > 100000:
                text = text[:100000] + "\n... [truncated]"
            return title, text
        except ImportError:
            # No BeautifulSoup, return raw text
            return "", response.text[:100000]

    except Exception as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return "", ""


def fetch_raw_content(url: str) -> str:
    """Fetch raw content from a URL (no HTML parsing)."""
    if not REQUESTS_AVAILABLE:
        return ""
    try:
        headers = {"User-Agent": "skillful-alhazen-techrecon"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.text
        if len(content) > 200000:
            content = content[:200000] + "\n... [truncated]"
        return content
    except Exception as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return ""


def store_artifact(driver, artifact_id, artifact_type, name, content, source_uri,
                   mime_type="text/plain", extra_attrs=None):
    """Store an artifact with inline or cached content.

    Returns dict with storage info.
    """
    timestamp = get_timestamp()

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        if CACHE_AVAILABLE and should_cache(content):
            cache_result = save_to_cache(
                artifact_id=artifact_id,
                content=content,
                mime_type=mime_type,
            )
            query = f'''insert $a isa {artifact_type},
                has id "{artifact_id}",
                has name "{escape_string(name)}",
                has cache-path "{cache_result['cache_path']}",
                has mime-type "{mime_type}",
                has file-size {cache_result['file_size']},
                has content-hash "{cache_result['content_hash']}",
                has source-uri "{escape_string(source_uri)}",
                has created-at {timestamp}'''
            storage = "cache"
        else:
            query = f'''insert $a isa {artifact_type},
                has id "{artifact_id}",
                has name "{escape_string(name)}",
                has content "{escape_string(content)}",
                has mime-type "{mime_type}",
                has source-uri "{escape_string(source_uri)}",
                has created-at {timestamp}'''
            storage = "inline"

        if extra_attrs:
            for k, v in extra_attrs.items():
                if isinstance(v, str):
                    query += f', has {k} "{escape_string(v)}"'
                elif isinstance(v, (int, float)):
                    query += f", has {k} {v}"

        query += ";"
        tx.query(query).resolve()
        tx.commit()

    return {"storage": storage, "content_length": len(content)}


def link_artifact_to_entity(driver, artifact_id, artifact_type, entity_id, entity_type):
    """Link an artifact to an entity via representation relation."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        query = f'''match
            $a isa {artifact_type}, has id "{artifact_id}";
            $e isa {entity_type}, has id "{entity_id}";
        insert (artifact: $a, referent: $e) isa representation;'''
        tx.query(query).resolve()
        tx.commit()


def add_to_collection(driver, entity_id, collection_id):
    """Add an entity to a collection via collection-membership."""
    timestamp = get_timestamp()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        query = f'''match
            $c isa techrecon-investigation, has id "{collection_id}";
            $e isa identifiable-entity, has id "{entity_id}";
        insert (collection: $c, member: $e) isa collection-membership,
            has created-at {timestamp};'''
        tx.query(query).resolve()
        tx.commit()


def apply_tags(driver, entity_id, entity_type, tags):
    """Apply tags to an entity."""
    if not tags:
        return
    for tag_name in tags:
        tag_id = generate_id("tag")
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            tag_check = f'match $t isa tag, has name "{tag_name}"; fetch {{ "id": $t.id }};'
            existing_tag = list(tx.query(tag_check).resolve())

        if not existing_tag:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'insert $t isa tag, has id "{tag_id}", has name "{tag_name}";'
                ).resolve()
                tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $e isa {entity_type}, has id "{entity_id}";
                $t isa tag, has name "{tag_name}";
            insert (tagged-entity: $e, tag: $t) isa tagging;''').resolve()
            tx.commit()


# =============================================================================
# INVESTIGATION MANAGEMENT
# =============================================================================


def cmd_start_investigation(args):
    """Start a new investigation."""
    inv_id = generate_id("investigation")
    timestamp = get_timestamp()

    query = f'''insert $i isa techrecon-investigation,
        has id "{inv_id}",
        has name "{escape_string(args.name)}",
        has techrecon-investigation-status "active",
        has techrecon-investigation-goal "{escape_string(args.goal)}",
        has created-at {timestamp}'''

    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # If a system is specified, add it to the investigation
        if args.system:
            add_to_collection(driver, args.system, inv_id)

    print(json.dumps({
        "success": True,
        "investigation_id": inv_id,
        "name": args.name,
        "goal": args.goal,
        "status": "active",
    }, indent=2))


def cmd_list_investigations(args):
    """List investigations with summary counts."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = "match $i isa techrecon-investigation"
            if args.status:
                query += f', has techrecon-investigation-status "{args.status}"'
            query += """;
            fetch {
                "id": $i.id,
                "name": $i.name,
                "description": $i.description,
                "techrecon-investigation-status": $i.techrecon-investigation-status,
                "techrecon-investigation-goal": $i.techrecon-investigation-goal,
                "created-at": $i.created-at
            };"""
            results = list(tx.query(query).resolve())

            investigations = []
            for r in results:
                inv_id = r.get("id")

                # Count members by type
                counts = {"systems": 0, "artifacts": 0, "notes": 0, "components": 0, "concepts": 0, "data_models": 0}
                member_types = [
                    ("systems", "techrecon-system"),
                    ("artifacts", "artifact"),
                    ("notes", "note"),
                    ("components", "techrecon-component"),
                    ("concepts", "techrecon-concept"),
                    ("data_models", "techrecon-data-model"),
                ]
                for count_key, type_name in member_types:
                    count_q = f'''match
                        $c isa techrecon-investigation, has id "{inv_id}";
                        (collection: $c, member: $m) isa collection-membership;
                        $m isa {type_name};
                    fetch {{ "id": $m.id }};'''
                    try:
                        counts[count_key] = len(list(tx.query(count_q).resolve()))
                    except Exception:
                        pass

                investigations.append({
                    "id": inv_id,
                    "name": r.get("name"),
                    "description": r.get("description"),
                    "status": r.get("techrecon-investigation-status"),
                    "goal": r.get("techrecon-investigation-goal"),
                    "created_at": r.get("created-at"),
                    "summary": counts,
                })

    print(json.dumps({"success": True, "investigations": investigations, "count": len(investigations)}, indent=2))


def cmd_update_investigation(args):
    """Update investigation status."""
    with get_driver() as driver:
        # Delete old status and insert new
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $i isa techrecon-investigation, has id "{args.id}",
                    has techrecon-investigation-status $s;
            delete has $s of $i;''').resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $i isa techrecon-investigation, has id "{args.id}";
            insert $i has techrecon-investigation-status "{args.status}";''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "investigation_id": args.id, "status": args.status}))


def cmd_show_investigation(args):
    """Show full investigation details with all members."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Investigation metadata
            inv_query = f'''match $i isa techrecon-investigation, has id "{args.id}";
            fetch {{
                "id": $i.id,
                "name": $i.name,
                "description": $i.description,
                "techrecon-investigation-status": $i.techrecon-investigation-status,
                "techrecon-investigation-goal": $i.techrecon-investigation-goal,
                "created-at": $i.created-at
            }};'''
            inv_result = list(tx.query(inv_query).resolve())

            if not inv_result:
                print(json.dumps({"success": False, "error": "Investigation not found"}))
                return

            # Systems
            sys_query = f'''match
                $c isa techrecon-investigation, has id "{args.id}";
                (collection: $c, member: $s) isa collection-membership;
                $s isa techrecon-system;
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "techrecon-repo-url": $s.techrecon-repo-url,
                "techrecon-language": $s.techrecon-language,
                "techrecon-stars": $s.techrecon-stars,
                "techrecon-maturity": $s.techrecon-maturity,
                "description": $s.description,
                "created-at": $s.created-at
            }};'''
            sys_result = list(tx.query(sys_query).resolve())

            # Artifacts
            art_query = f'''match
                $c isa techrecon-investigation, has id "{args.id}";
                (collection: $c, member: $a) isa collection-membership;
                $a isa artifact;
            fetch {{
                "id": $a.id,
                "name": $a.name,
                "source-uri": $a.source-uri,
                "mime-type": $a.mime-type,
                "created-at": $a.created-at
            }};'''
            art_result = list(tx.query(art_query).resolve())

            # Notes by subtype
            note_types = [
                ("architecture", "techrecon-architecture-note"),
                ("design-pattern", "techrecon-design-pattern-note"),
                ("integration", "techrecon-integration-note"),
                ("comparison", "techrecon-comparison-note"),
                ("data-model", "techrecon-data-model-note"),
                ("assessment", "techrecon-assessment-note"),
                ("provenance", "techrecon-provenance-note"),
                ("use-case", "techrecon-use-case-note"),
                ("general", "note"),
            ]
            all_notes = []
            for note_type_label, note_type_name in note_types:
                note_query = f'''match
                    $c isa techrecon-investigation, has id "{args.id}";
                    (collection: $c, member: $n) isa collection-membership;
                    $n isa {note_type_name};
                fetch {{
                    "id": $n.id,
                    "name": $n.name,
                    "content": $n.content,
                    "created-at": $n.created-at
                }};'''
                try:
                    note_results = list(tx.query(note_query).resolve())
                except Exception:
                    note_results = []

                for nr in note_results:
                    note_data = {
                        "id": nr.get("id"),
                        "name": nr.get("name"),
                        "content": nr.get("content"),
                        "type": note_type_label,
                        "created_at": nr.get("created-at"),
                    }
                    # Fetch priority/complexity for integration and assessment notes
                    if note_type_label in ("integration", "assessment"):
                        nid = note_data["id"]
                        extra_q = f'''match $n isa {note_type_name}, has id "{nid}";
                        fetch {{
                            "techrecon-integration-priority": $n.techrecon-integration-priority,
                            "techrecon-complexity-rating": $n.techrecon-complexity-rating
                        }};'''
                        try:
                            extra_r = list(tx.query(extra_q).resolve())
                            if extra_r:
                                note_data["priority"] = extra_r[0].get("techrecon-integration-priority")
                                note_data["complexity"] = extra_r[0].get("techrecon-complexity-rating")
                        except Exception:
                            pass
                    all_notes.append(note_data)

            # Also fetch general notes
            gen_note_query = f'''match
                $c isa techrecon-investigation, has id "{args.id}";
                (collection: $c, member: $n) isa collection-membership;
                $n isa note;
            fetch {{
                "id": $n.id,
                "name": $n.name,
                "content": $n.content,
                "created-at": $n.created-at
            }};'''
            try:
                gen_note_results = list(tx.query(gen_note_query).resolve())
                # Exclude notes already found as subtypes
                seen_ids = {n["id"] for n in all_notes}
                for nr in gen_note_results:
                    nid = nr.get("id")
                    if nid not in seen_ids:
                        all_notes.append({
                            "id": nid,
                            "name": nr.get("name"),
                            "content": nr.get("content"),
                            "type": "general",
                            "created_at": nr.get("created-at"),
                        })
            except Exception:
                pass

            # Components
            comp_query = f'''match
                $c isa techrecon-investigation, has id "{args.id}";
                (collection: $c, member: $m) isa collection-membership;
                $m isa techrecon-component;
            fetch {{
                "id": $m.id,
                "name": $m.name,
                "techrecon-component-type": $m.techrecon-component-type,
                "techrecon-component-role": $m.techrecon-component-role
            }};'''
            comp_result = list(tx.query(comp_query).resolve())

            # Concepts
            con_query = f'''match
                $c isa techrecon-investigation, has id "{args.id}";
                (collection: $c, member: $m) isa collection-membership;
                $m isa techrecon-concept;
            fetch {{
                "id": $m.id,
                "name": $m.name,
                "techrecon-concept-category": $m.techrecon-concept-category,
                "description": $m.description
            }};'''
            con_result = list(tx.query(con_query).resolve())

            # Data models
            dm_query = f'''match
                $c isa techrecon-investigation, has id "{args.id}";
                (collection: $c, member: $m) isa collection-membership;
                $m isa techrecon-data-model;
            fetch {{
                "id": $m.id,
                "name": $m.name,
                "techrecon-model-format": $m.techrecon-model-format,
                "description": $m.description
            }};'''
            dm_result = list(tx.query(dm_query).resolve())

    inv = inv_result[0]
    output = {
        "success": True,
        "investigation": {
            "id": get_attr(inv, "id"),
            "name": get_attr(inv, "name"),
            "description": get_attr(inv, "description"),
            "status": get_attr(inv, "techrecon-investigation-status"),
            "goal": get_attr(inv, "techrecon-investigation-goal"),
            "created_at": get_attr(inv, "created-at"),
        },
        "systems": [{
            "id": s.get("id"),
            "name": s.get("name"),
            "repo_url": s.get("techrecon-repo-url"),
            "language": s.get("techrecon-language"),
            "stars": s.get("techrecon-stars"),
            "maturity": s.get("techrecon-maturity"),
            "description": s.get("description"),
            "created_at": s.get("created-at"),
        } for s in sys_result],
        "artifacts": [{
            "id": a.get("id"),
            "name": a.get("name"),
            "source_uri": a.get("source-uri"),
            "mime_type": a.get("mime-type"),
            "created_at": a.get("created-at"),
        } for a in art_result],
        "notes": all_notes,
        "components": [{
            "id": c.get("id"),
            "name": c.get("name"),
            "type": c.get("techrecon-component-type"),
            "role": c.get("techrecon-component-role"),
        } for c in comp_result],
        "concepts": [{
            "id": c.get("id"),
            "name": c.get("name"),
            "category": c.get("techrecon-concept-category"),
            "description": c.get("description"),
        } for c in con_result],
        "data_models": [{
            "id": d.get("id"),
            "name": d.get("name"),
            "format": d.get("techrecon-model-format"),
            "description": d.get("description"),
        } for d in dm_result],
        "summary": {
            "systems_count": len(sys_result),
            "artifacts_count": len(art_result),
            "notes_count": len(all_notes),
            "components_count": len(comp_result),
            "concepts_count": len(con_result),
            "data_models_count": len(dm_result),
        },
    }

    print(json.dumps(output, indent=2, default=str))


# =============================================================================
# ENTITY CREATION
# =============================================================================


def cmd_add_system(args):
    """Add a software system."""
    system_id = args.id or generate_id("system")
    timestamp = get_timestamp()

    query = f'''insert $s isa techrecon-system,
        has id "{system_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.repo_url:
        query += f', has techrecon-repo-url "{escape_string(args.repo_url)}"'
    if args.doc_url:
        query += f', has techrecon-doc-url "{escape_string(args.doc_url)}"'
    if args.language:
        query += f', has techrecon-language "{escape_string(args.language)}"'
    if args.version:
        query += f', has techrecon-version "{escape_string(args.version)}"'
    if args.maturity:
        query += f', has techrecon-maturity "{args.maturity}"'
    if args.license:
        query += f', has techrecon-license-type "{escape_string(args.license)}"'
    if args.package:
        query += f', has techrecon-package-name "{escape_string(args.package)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Add to investigation if specified
        if args.investigation:
            add_to_collection(driver, system_id, args.investigation)

        apply_tags(driver, system_id, "techrecon-system", args.tags)

    print(json.dumps({"success": True, "system_id": system_id, "name": args.name}, indent=2))


def cmd_add_component(args):
    """Add a component/module."""
    comp_id = args.id or generate_id("component")
    timestamp = get_timestamp()

    query = f'''insert $c isa techrecon-component,
        has id "{comp_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.type:
        query += f', has techrecon-component-type "{args.type}"'
    if args.role:
        query += f', has techrecon-component-role "{escape_string(args.role)}"'
    if args.file_path:
        query += f', has techrecon-file-path "{escape_string(args.file_path)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to system if specified
        if args.system:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $s isa techrecon-system, has id "{args.system}";
                    $c isa techrecon-component, has id "{comp_id}";
                insert (system: $s, component: $c) isa techrecon-has-component;''').resolve()
                tx.commit()

        # Add to investigation if specified
        if args.investigation:
            add_to_collection(driver, comp_id, args.investigation)

        apply_tags(driver, comp_id, "techrecon-component", args.tags)

    print(json.dumps({"success": True, "component_id": comp_id, "name": args.name}, indent=2))


def cmd_add_concept(args):
    """Add a key concept."""
    concept_id = args.id or generate_id("concept")
    timestamp = get_timestamp()

    query = f'''insert $c isa techrecon-concept,
        has id "{concept_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.category:
        query += f', has techrecon-concept-category "{args.category}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if args.investigation:
            add_to_collection(driver, concept_id, args.investigation)

        apply_tags(driver, concept_id, "techrecon-concept", args.tags)

    print(json.dumps({"success": True, "concept_id": concept_id, "name": args.name}, indent=2))


def cmd_add_data_model(args):
    """Add a data model/schema."""
    model_id = args.id or generate_id("datamodel")
    timestamp = get_timestamp()

    query = f'''insert $m isa techrecon-data-model,
        has id "{model_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.format:
        query += f', has techrecon-model-format "{args.format}"'
    if args.doc_url:
        query += f', has techrecon-doc-url "{escape_string(args.doc_url)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to system if specified
        if args.system:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $s isa techrecon-system, has id "{args.system}";
                    $m isa techrecon-data-model, has id "{model_id}";
                insert (system: $s, data-model: $m) isa techrecon-has-data-model;''').resolve()
                tx.commit()

        if args.investigation:
            add_to_collection(driver, model_id, args.investigation)

        apply_tags(driver, model_id, "techrecon-data-model", args.tags)

    print(json.dumps({"success": True, "data_model_id": model_id, "name": args.name}, indent=2))


# =============================================================================
# INGESTION COMMANDS
# =============================================================================


def cmd_ingest_repo(args):
    """Ingest a GitHub repository: fetches README + file tree."""
    if not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests not installed"}))
        return

    owner, repo = parse_github_url(args.url)
    if not owner or not repo:
        print(json.dumps({"success": False, "error": f"Could not parse GitHub URL: {args.url}"}))
        return

    headers = github_headers()
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    # 1. Fetch repo metadata
    print(f"Fetching repo metadata for {owner}/{repo}...", file=sys.stderr)
    try:
        meta_resp = requests.get(api_base, headers=headers, timeout=30)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
    except Exception as e:
        print(json.dumps({"success": False, "error": f"GitHub API error: {e}"}))
        return

    # 2. Fetch README
    print("Fetching README...", file=sys.stderr)
    readme_content = ""
    try:
        readme_resp = requests.get(f"{api_base}/readme", headers=headers, timeout=30)
        if readme_resp.status_code == 200:
            readme_data = readme_resp.json()
            readme_content = base64.b64decode(readme_data.get("content", "")).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Warning: Could not fetch README: {e}", file=sys.stderr)

    # 3. Fetch file tree
    print("Fetching file tree...", file=sys.stderr)
    file_tree = []
    try:
        tree_resp = requests.get(
            f"{api_base}/git/trees/HEAD?recursive=1",
            headers=headers,
            timeout=30,
        )
        if tree_resp.status_code == 200:
            tree_data = tree_resp.json()
            for item in tree_data.get("tree", []):
                file_tree.append({
                    "path": item.get("path"),
                    "type": item.get("type"),  # blob or tree
                    "size": item.get("size"),
                })
    except Exception as e:
        print(f"Warning: Could not fetch file tree: {e}", file=sys.stderr)

    # 4. Create or find system entity
    system_id = args.system
    timestamp = get_timestamp()
    last_commit = meta.get("pushed_at", "").replace("Z", "").split("+")[0]
    if last_commit and "T" not in last_commit:
        last_commit = last_commit.replace(" ", "T")

    with get_driver() as driver:
        # Create system if not specified
        if not system_id:
            system_id = generate_id("system")
            sys_query = f'''insert $s isa techrecon-system,
                has id "{system_id}",
                has name "{escape_string(meta.get('full_name', f'{owner}/{repo}'))}",
                has description "{escape_string((meta.get('description') or '')[:500])}",
                has techrecon-repo-url "{escape_string(args.url)}",
                has techrecon-language "{escape_string(meta.get('language') or 'unknown')}",
                has techrecon-stars {meta.get('stargazers_count', 0)},
                has techrecon-license-type "{escape_string((meta.get('license') or {}).get('spdx_id', 'unknown'))}",
                has techrecon-maturity "stable",
                has created-at {timestamp}'''

            if last_commit:
                sys_query += f', has techrecon-last-commit {last_commit}'

            sys_query += ";"
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(sys_query).resolve()
                tx.commit()

        # Store README artifact
        readme_artifact_id = None
        if readme_content:
            readme_artifact_id = generate_id("artifact")
            store_artifact(
                driver,
                readme_artifact_id,
                "techrecon-readme",
                f"README: {owner}/{repo}",
                readme_content,
                f"{args.url}/blob/main/README.md",
                mime_type="text/markdown",
            )
            link_artifact_to_entity(driver, readme_artifact_id, "techrecon-readme", system_id, "techrecon-system")

        # Store file tree artifact
        tree_artifact_id = None
        if file_tree:
            tree_artifact_id = generate_id("artifact")
            tree_json = json.dumps(file_tree, indent=2)
            store_artifact(
                driver,
                tree_artifact_id,
                "techrecon-file-tree",
                f"File Tree: {owner}/{repo}",
                tree_json,
                f"{args.url}/tree/main",
                mime_type="application/json",
            )
            link_artifact_to_entity(driver, tree_artifact_id, "techrecon-file-tree", system_id, "techrecon-system")

        # Add to investigation
        if args.investigation:
            add_to_collection(driver, system_id, args.investigation)
            if readme_artifact_id:
                add_to_collection(driver, readme_artifact_id, args.investigation)
            if tree_artifact_id:
                add_to_collection(driver, tree_artifact_id, args.investigation)

        apply_tags(driver, system_id, "techrecon-system", args.tags)

    output = {
        "success": True,
        "system_id": system_id,
        "repo": f"{owner}/{repo}",
        "description": meta.get("description", ""),
        "language": meta.get("language", ""),
        "stars": meta.get("stargazers_count", 0),
        "readme_artifact_id": readme_artifact_id,
        "readme_length": len(readme_content) if readme_content else 0,
        "tree_artifact_id": tree_artifact_id,
        "file_count": len(file_tree),
        "message": "Repository ingested. Ask Claude to analyze the README and file tree for sensemaking.",
    }
    print(json.dumps(output, indent=2))


def cmd_clone_repo(args):
    """Clone a GitHub repository locally for native file exploration."""
    owner, repo = parse_github_url(args.url)
    if not owner or not repo:
        print(json.dumps({"success": False, "error": f"Could not parse GitHub URL: {args.url}"}))
        return

    local_path = Path.home() / ".alhazen" / "cache" / "repos" / owner / repo

    with get_driver() as driver:
        # Check if already stored in TypeDB
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing = list(tx.query(f'''match
                $a isa techrecon-local-repo, has cache-path $p;
                $p == "{str(local_path)}";
            fetch {{ "id": $a.id, "name": $a.name }};''').resolve())

        if existing and not args.update:
            print(json.dumps({
                "success": True,
                "local_repo_id": existing[0].get("id"),
                "system_id": args.system,
                "local_path": str(local_path),
                "status": "already_exists",
            }, indent=2))
            return

        # Clone or update on disk
        if local_path.exists():
            if args.update:
                print(f"Updating {owner}/{repo}...", file=sys.stderr)
                result = subprocess.run(
                    ["git", "-C", str(local_path), "pull", "--ff-only"],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    print(f"Warning: git pull failed: {result.stderr}", file=sys.stderr)
                status = "updated"
            else:
                status = "already_exists"
        else:
            print(f"Cloning {args.url}...", file=sys.stderr)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", args.url, str(local_path)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(json.dumps({"success": False, "error": f"git clone failed: {result.stderr}"}))
                return
            status = "cloned"

        # Store techrecon-local-repo artifact
        artifact_id = existing[0].get("id") if existing else generate_id("artifact")
        if not existing:
            timestamp = get_timestamp()
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''insert $a isa techrecon-local-repo,
                    has id "{artifact_id}",
                    has name "local-clone:{escape_string(f"{owner}/{repo}")}",
                    has cache-path "{escape_string(str(local_path))}",
                    has techrecon-repo-url "{escape_string(args.url)}",
                    has source-uri "{escape_string(args.url)}",
                    has mime-type "inode/directory",
                    has created-at {timestamp};''').resolve()
                tx.commit()

        # Create or reuse system
        system_id = args.system
        if not system_id:
            # Check for existing system with this repo URL
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                sys_check = list(tx.query(f'''match
                    $s isa techrecon-system, has techrecon-repo-url $u;
                    $u == "{escape_string(args.url)}";
                fetch {{ "id": $s.id }};''').resolve())
            if sys_check:
                system_id = sys_check[0].get("id")
            else:
                system_id = generate_id("system")
                timestamp = get_timestamp()
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''insert $s isa techrecon-system,
                        has id "{system_id}",
                        has name "{escape_string(f"{owner}/{repo}")}",
                        has techrecon-repo-url "{escape_string(args.url)}",
                        has created-at {timestamp};''').resolve()
                    tx.commit()

        # Link artifact to system
        if not existing:
            link_artifact_to_entity(driver, artifact_id, "techrecon-local-repo", system_id, "techrecon-system")

        if args.investigation:
            add_to_collection(driver, artifact_id, args.investigation)
            add_to_collection(driver, system_id, args.investigation)

    print(json.dumps({
        "success": True,
        "local_repo_id": artifact_id,
        "system_id": system_id,
        "local_path": str(local_path),
        "status": status,
    }, indent=2))


def cmd_ingest_doc(args):
    """Ingest a documentation page."""
    if not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests not installed"}))
        return

    title, content = fetch_url_content(args.url)
    if not content:
        print(json.dumps({"success": False, "error": "Could not fetch URL content"}))
        return

    artifact_id = generate_id("artifact")

    with get_driver() as driver:
        name = title if title else f"Doc page: {args.url[:60]}"
        store_artifact(
            driver, artifact_id, "techrecon-doc-page",
            name, content, args.url, mime_type="text/html",
        )

        # Link to system
        if args.system:
            link_artifact_to_entity(driver, artifact_id, "techrecon-doc-page", args.system, "techrecon-system")

        if args.investigation:
            add_to_collection(driver, artifact_id, args.investigation)

        apply_tags(driver, artifact_id, "techrecon-doc-page", args.tags)

    print(json.dumps({
        "success": True,
        "artifact_id": artifact_id,
        "url": args.url,
        "title": title,
        "content_length": len(content),
        "message": "Doc page ingested. Ask Claude to analyze it for sensemaking.",
    }, indent=2))


def cmd_ingest_source(args):
    """Ingest a source code file."""
    if not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests not installed"}))
        return

    # Determine the raw URL for GitHub files
    url = args.url
    if "github.com" in url and "/blob/" in url:
        # Convert GitHub blob URL to raw URL
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    content = fetch_raw_content(url)
    if not content:
        print(json.dumps({"success": False, "error": "Could not fetch source content"}))
        return

    artifact_id = generate_id("artifact")
    file_path = args.file_path or url.split("/")[-1]
    language = args.language or ""

    extra_attrs = {}
    if file_path:
        extra_attrs["techrecon-file-path"] = file_path
    if language:
        extra_attrs["techrecon-file-language"] = language

    with get_driver() as driver:
        store_artifact(
            driver, artifact_id, "techrecon-source-file",
            f"Source: {file_path}", content, args.url,
            mime_type="text/plain", extra_attrs=extra_attrs,
        )

        if args.system:
            link_artifact_to_entity(driver, artifact_id, "techrecon-source-file", args.system, "techrecon-system")

        if args.investigation:
            add_to_collection(driver, artifact_id, args.investigation)

        apply_tags(driver, artifact_id, "techrecon-source-file", args.tags)

    print(json.dumps({
        "success": True,
        "artifact_id": artifact_id,
        "file_path": file_path,
        "language": language,
        "content_length": len(content),
        "message": "Source file ingested. Ask Claude to analyze it.",
    }, indent=2))


def cmd_ingest_schema(args):
    """Ingest a schema/model file."""
    content = ""
    source_uri = ""

    if args.url:
        if not REQUESTS_AVAILABLE:
            print(json.dumps({"success": False, "error": "requests not installed"}))
            return
        url = args.url
        if "github.com" in url and "/blob/" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        content = fetch_raw_content(url)
        source_uri = args.url
    elif args.file:
        try:
            with open(args.file, "r") as f:
                content = f.read()
            source_uri = f"file://{os.path.abspath(args.file)}"
        except Exception as e:
            print(json.dumps({"success": False, "error": f"Could not read file: {e}"}))
            return

    if not content:
        print(json.dumps({"success": False, "error": "No content to ingest"}))
        return

    artifact_id = generate_id("artifact")
    extra_attrs = {}
    if args.format:
        extra_attrs["techrecon-model-format"] = args.format

    name = os.path.basename(args.file) if args.file else f"Schema from {source_uri[:60]}"

    with get_driver() as driver:
        store_artifact(
            driver, artifact_id, "techrecon-schema-file",
            f"Schema: {name}", content, source_uri,
            mime_type="text/plain", extra_attrs=extra_attrs,
        )

        if args.system:
            link_artifact_to_entity(driver, artifact_id, "techrecon-schema-file", args.system, "techrecon-system")

        if args.investigation:
            add_to_collection(driver, artifact_id, args.investigation)

        apply_tags(driver, artifact_id, "techrecon-schema-file", args.tags)

    print(json.dumps({
        "success": True,
        "artifact_id": artifact_id,
        "name": name,
        "format": args.format or "unknown",
        "content_length": len(content),
        "message": "Schema file ingested. Ask Claude to analyze it.",
    }, indent=2))


def cmd_ingest_model_card(args):
    """Ingest a HuggingFace model card."""
    if not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests not installed"}))
        return

    model_id = args.model_id

    # Fetch model info
    print(f"Fetching model info for {model_id}...", file=sys.stderr)
    try:
        info_resp = requests.get(
            f"https://huggingface.co/api/models/{model_id}",
            timeout=30,
        )
        info_resp.raise_for_status()
        model_info = info_resp.json()
    except Exception as e:
        print(json.dumps({"success": False, "error": f"HuggingFace API error: {e}"}))
        return

    # Fetch model card (README.md)
    print("Fetching model card...", file=sys.stderr)
    card_content = ""
    try:
        card_resp = requests.get(
            f"https://huggingface.co/{model_id}/raw/main/README.md",
            timeout=30,
        )
        if card_resp.status_code == 200:
            card_content = card_resp.text
    except Exception as e:
        print(f"Warning: Could not fetch model card: {e}", file=sys.stderr)

    if not card_content:
        # Fall back to model info as JSON
        card_content = json.dumps(model_info, indent=2)

    artifact_id = generate_id("artifact")
    extra_attrs = {"techrecon-model-id": model_id}

    with get_driver() as driver:
        store_artifact(
            driver, artifact_id, "techrecon-model-card",
            f"Model Card: {model_id}", card_content,
            f"https://huggingface.co/{model_id}",
            mime_type="text/markdown", extra_attrs=extra_attrs,
        )

        if args.system:
            link_artifact_to_entity(driver, artifact_id, "techrecon-model-card", args.system, "techrecon-system")

        if args.investigation:
            add_to_collection(driver, artifact_id, args.investigation)

        apply_tags(driver, artifact_id, "techrecon-model-card", args.tags)

    print(json.dumps({
        "success": True,
        "artifact_id": artifact_id,
        "model_id": model_id,
        "model_name": model_info.get("modelId", model_id),
        "pipeline_tag": model_info.get("pipeline_tag", ""),
        "downloads": model_info.get("downloads", 0),
        "likes": model_info.get("likes", 0),
        "content_length": len(card_content),
        "message": "Model card ingested. Ask Claude to analyze it.",
    }, indent=2))


# =============================================================================
# LINKING COMMANDS
# =============================================================================


def cmd_link_component(args):
    """Link a component to a system."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $s isa techrecon-system, has id "{args.system}";
                $c isa techrecon-component, has id "{args.component}";
            insert (system: $s, component: $c) isa techrecon-has-component;''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "system": args.system, "component": args.component}))


def cmd_link_concept(args):
    """Link a concept to a component."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            query = f'''match
                $comp isa techrecon-component, has id "{args.component}";
                $con isa techrecon-concept, has id "{args.concept}";
            insert (component: $comp, concept: $con) isa techrecon-uses-concept'''
            if args.confidence:
                query += f", has confidence {args.confidence}"
            query += ";"
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "component": args.component, "concept": args.concept}))


def cmd_link_data_model(args):
    """Link a data model to a system."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $s isa techrecon-system, has id "{args.system}";
                $m isa techrecon-data-model, has id "{args.data_model}";
            insert (system: $s, data-model: $m) isa techrecon-has-data-model;''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "system": args.system, "data_model": args.data_model}))


def cmd_link_dependency(args):
    """Link a system dependency."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            query = f'''match
                $s isa techrecon-system, has id "{args.system}";
                $d isa techrecon-system, has id "{args.dependency}";
            insert (dependent: $s, dependency: $d) isa techrecon-system-dependency'''
            if args.version:
                query += f', has techrecon-version "{escape_string(args.version)}"'
            query += ";"
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "system": args.system,
        "dependency": args.dependency,
        "version": args.version,
    }))


# =============================================================================
# QUERY COMMANDS
# =============================================================================


def cmd_list_systems(args):
    """List all systems."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = """match $s isa techrecon-system;
            fetch {
                "id": $s.id,
                "name": $s.name,
                "techrecon-repo-url": $s.techrecon-repo-url,
                "techrecon-language": $s.techrecon-language,
                "techrecon-stars": $s.techrecon-stars,
                "techrecon-maturity": $s.techrecon-maturity,
                "created-at": $s.created-at
            };"""
            results = list(tx.query(query).resolve())

    systems = []
    for r in results:
        systems.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "repo_url": r.get("techrecon-repo-url"),
            "language": r.get("techrecon-language"),
            "stars": r.get("techrecon-stars"),
            "maturity": r.get("techrecon-maturity"),
            "created_at": r.get("created-at"),
        })

    print(json.dumps({"success": True, "systems": systems, "count": len(systems)}, indent=2))


def cmd_list_papers(args):
    """List all scientific papers linked to a system via techrecon-references-paper."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get system details and verify it exists
            sys_result = list(tx.query(
                f'match $s isa techrecon-system, has id "{escape_string(args.system)}"; '
                f'fetch {{ "id": $s.id, "name": $s.name }};'
            ).resolve())

            if not sys_result:
                print(json.dumps({"success": False, "error": f"System not found: {args.system}"}))
                sys.exit(1)

            system_name = sys_result[0].get("name")

            # Fetch all linked papers with citation metadata
            paper_query = f'''match
    $s isa techrecon-system, has id "{escape_string(args.system)}";
    (system: $s, paper: $p) isa techrecon-references-paper;
    $p has id $pid;
fetch {{
    "id": $pid,
    "name": $p.name,
    "doi": $p.doi,
    "publication-year": $p.publication-year,
    "journal-name": $p.journal-name
}};'''
            paper_result = list(tx.query(paper_query).resolve())

    def build_citation(r):
        title = r.get("name") or ""
        year = r.get("publication-year")
        journal = r.get("journal-name") or ""
        parts = [title]
        if year:
            parts.append(f"({year})")
        if journal:
            parts.append(journal)
        return ". ".join(p for p in parts if p) or r.get("id", "unknown")

    papers = [
        {
            "id": r.get("id"),
            "citation": build_citation(r),
            "doi": r.get("doi"),
        }
        for r in paper_result
    ]

    print(json.dumps({
        "success": True,
        "system_id": args.system,
        "system_name": system_name,
        "count": len(papers),
        "papers": papers,
    }, indent=2))


def cmd_link_paper(args):
    """Link a techrecon-system to an existing scilit-paper via techrecon-references-paper."""
    with get_driver() as driver:
        # Verify both entities exist
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            sys_check = list(tx.query(
                f'match $s isa techrecon-system, has id "{escape_string(args.system_id)}"; '
                f'fetch {{ "id": $s.id, "name": $s.name }};'
            ).resolve())
            paper_check = list(tx.query(
                f'match $p isa scilit-paper, has id "{escape_string(args.paper_id)}"; '
                f'fetch {{ "id": $p.id, "name": $p.name }};'
            ).resolve())

        if not sys_check:
            print(json.dumps({"success": False, "error": f"System not found: {args.system_id}"}))
            sys.exit(1)
        if not paper_check:
            print(json.dumps({"success": False, "error": f"Paper not found: {args.paper_id}"}))
            sys.exit(1)

        # Check if link already exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing = list(tx.query(
                f'match $s isa techrecon-system, has id "{escape_string(args.system_id)}"; '
                f'$p isa scilit-paper, has id "{escape_string(args.paper_id)}"; '
                f'(system: $s, paper: $p) isa techrecon-references-paper; '
                f'fetch {{ "system": $s.id }};'
            ).resolve())
        if existing:
            print(json.dumps({
                "success": True, "status": "existing",
                "system_id": args.system_id, "paper_id": args.paper_id,
            }, indent=2))
            return

        # Insert the relation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $s isa techrecon-system, has id "{escape_string(args.system_id)}"; '
                f'$p isa scilit-paper, has id "{escape_string(args.paper_id)}"; '
                f'insert (system: $s, paper: $p) isa techrecon-references-paper;'
            ).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "status": "linked",
        "system_id": args.system_id,
        "system_name": sys_check[0].get("name"),
        "paper_id": args.paper_id,
        "paper_name": paper_check[0].get("name"),
    }, indent=2))


def cmd_search_literature(args):
    """Search scientific literature and link papers to a techrecon-system."""
    skill_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Path resolution ---
    scilit_path = os.path.join(skill_dir, "..", "scientific-literature", "scientific_literature.py")
    if not os.path.exists(scilit_path):
        project_root = os.path.dirname(os.path.dirname(skill_dir))
        scilit_path = os.path.join(project_root, ".claude", "skills", "scientific-literature", "scientific_literature.py")
    if not os.path.exists(scilit_path):
        print(json.dumps({"success": False, "error": "scientific-literature skill not found"}))
        sys.exit(1)

    # --- Verify system exists (own driver context) ---
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            sys_check = list(tx.query(
                f'match $s isa techrecon-system, has id "{escape_string(args.system)}"; '
                f'fetch {{ "id": $s.id, "name": $s.name }};'
            ).resolve())
    if not sys_check:
        print(json.dumps({"success": False, "error": f"System not found: {args.system}"}))
        sys.exit(1)

    # --- Run scilit search (outside driver context) ---
    # project_root is the cwd for subprocess so uv uses the project's venv
    project_root = os.path.normpath(os.path.join(skill_dir, "..", ".."))
    cmd = ["uv", "run", "python", scilit_path, "search",
           "--source", args.source, "--query", args.query,
           "--max-results", str(args.limit)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, timeout=120)

    if proc.returncode != 0:
        print(json.dumps({"success": False, "error": f"scilit search failed: {proc.stderr[-500:]}"}))
        sys.exit(1)

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Failed to parse scilit output: {e}"}))
        sys.exit(1)

    # --- Check scilit success flag ---
    if not data.get("success"):
        print(json.dumps({"success": False, "error": f"scilit search returned failure: {data.get('error', 'unknown')}"}))
        sys.exit(1)

    papers = data.get("papers", [])

    # --- Link papers to system ---
    papers_linked = 0
    papers_already_linked = 0
    result_papers = []

    with get_driver() as driver:
        for paper in papers:
            paper_id = paper.get("id")
            if not paper_id:
                continue
            # Check if link already exists
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                existing = list(tx.query(
                    f'match $s isa techrecon-system, has id "{escape_string(args.system)}"; '
                    f'$p isa scilit-paper, has id "{escape_string(paper_id)}"; '
                    f'(system: $s, paper: $p) isa techrecon-references-paper; '
                    f'fetch {{ "system": $s.id }};'
                ).resolve())
            if existing:
                papers_already_linked += 1
                result_papers.append({"id": paper_id, "title": paper.get("title", ""), "status": "already_linked"})
            else:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(
                        f'match $s isa techrecon-system, has id "{escape_string(args.system)}"; '
                        f'$p isa scilit-paper, has id "{escape_string(paper_id)}"; '
                        f'insert (system: $s, paper: $p) isa techrecon-references-paper;'
                    ).resolve()
                    tx.commit()
                papers_linked += 1
                result_papers.append({"id": paper_id, "title": paper.get("title", ""), "status": "linked"})

        # Add the system (not individual papers) to the investigation — marks that
        # literature was searched for this system in this investigation context.
        if args.investigation:
            add_to_collection(driver, args.system, args.investigation)

    print(json.dumps({
        "success": True,
        "system_id": args.system,
        "query": args.query,
        "source": args.source,
        "papers_found": len(papers),
        "papers_linked": papers_linked,
        "papers_already_linked": papers_already_linked,
        "papers": result_papers,
    }, indent=2))


def cmd_show_system(args):
    """Show full system details."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # System details
            sys_query = f'''match $s isa techrecon-system, has id "{args.id}";
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "description": $s.description,
                "techrecon-repo-url": $s.techrecon-repo-url,
                "techrecon-doc-url": $s.techrecon-doc-url,
                "techrecon-language": $s.techrecon-language,
                "techrecon-version": $s.techrecon-version,
                "techrecon-stars": $s.techrecon-stars,
                "techrecon-last-commit": $s.techrecon-last-commit,
                "techrecon-license-type": $s.techrecon-license-type,
                "techrecon-maturity": $s.techrecon-maturity,
                "techrecon-package-name": $s.techrecon-package-name,
                "techrecon-model-architecture": $s.techrecon-model-architecture,
                "techrecon-training-methodology": $s.techrecon-training-methodology,
                "techrecon-base-model": $s.techrecon-base-model,
                "techrecon-parameter-count": $s.techrecon-parameter-count,
                "created-at": $s.created-at
            }};'''
            sys_result = list(tx.query(sys_query).resolve())

            if not sys_result:
                print(json.dumps({"success": False, "error": "System not found"}))
                return

            # Components
            comp_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                (system: $s, component: $c) isa techrecon-has-component;
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "techrecon-component-type": $c.techrecon-component-type,
                "techrecon-component-role": $c.techrecon-component-role
            }};'''
            comp_result = list(tx.query(comp_query).resolve())

            # Data models
            model_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                (system: $s, data-model: $m) isa techrecon-has-data-model;
            fetch {{
                "id": $m.id,
                "name": $m.name,
                "techrecon-model-format": $m.techrecon-model-format
            }};'''
            model_result = list(tx.query(model_query).resolve())

            # Dependencies
            dep_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                (dependent: $s, dependency: $d) isa techrecon-system-dependency;
            fetch {{
                "id": $d.id,
                "name": $d.name
            }};'''
            dep_result = list(tx.query(dep_query).resolve())

            # Artifacts
            artifact_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                (artifact: $a, referent: $s) isa representation;
            fetch {{
                "id": $a.id,
                "name": $a.name,
                "source-uri": $a.source-uri,
                "mime-type": $a.mime-type
            }};'''
            artifact_result = list(tx.query(artifact_query).resolve())

            # Notes
            notes_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                (note: $n, subject: $s) isa aboutness;
            fetch {{
                "id": $n.id,
                "name": $n.name,
                "content": $n.content
            }};'''
            notes_result = list(tx.query(notes_query).resolve())

            # Tags
            tags_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                (tagged-entity: $s, tag: $t) isa tagging;
            fetch {{
                "name": $t.name
            }};'''
            tags_result = list(tx.query(tags_query).resolve())

            # Linked scilit-papers
            papers_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                $p isa scilit-paper;
                (system: $s, paper: $p) isa techrecon-references-paper;
            fetch {{
                "id": $p.id,
                "name": $p.name
            }};'''
            papers_result = list(tx.query(papers_query).resolve())

    s = sys_result[0]
    output = {
        "success": True,
        "system": {
            "id": get_attr(s, "id"),
            "name": get_attr(s, "name"),
            "description": get_attr(s, "description"),
            "repo_url": get_attr(s, "techrecon-repo-url"),
            "doc_url": get_attr(s, "techrecon-doc-url"),
            "language": get_attr(s, "techrecon-language"),
            "version": get_attr(s, "techrecon-version"),
            "stars": get_attr(s, "techrecon-stars"),
            "last_commit": get_attr(s, "techrecon-last-commit"),
            "license": get_attr(s, "techrecon-license-type"),
            "maturity": get_attr(s, "techrecon-maturity"),
            "package": get_attr(s, "techrecon-package-name"),
            "model_architecture": get_attr(s, "techrecon-model-architecture"),
            "training_methodology": get_attr(s, "techrecon-training-methodology"),
            "base_model": get_attr(s, "techrecon-base-model"),
            "parameter_count": get_attr(s, "techrecon-parameter-count"),
        },
        "components": [{
            "id": c.get("id"),
            "name": c.get("name"),
            "type": c.get("techrecon-component-type"),
            "role": c.get("techrecon-component-role"),
        } for c in comp_result],
        "data_models": [{
            "id": m.get("id"),
            "name": m.get("name"),
            "format": m.get("techrecon-model-format"),
        } for m in model_result],
        "dependencies": [{
            "id": d.get("id"),
            "name": d.get("name"),
        } for d in dep_result],
        "artifacts": [{
            "id": a.get("id"),
            "name": a.get("name"),
            "source_uri": a.get("source-uri"),
            "mime_type": a.get("mime-type"),
        } for a in artifact_result],
        "notes": [{
            "id": n.get("id"),
            "name": n.get("name"),
            "content": n.get("content"),
        } for n in notes_result],
        "tags": [t.get("name") for t in tags_result],
        "papers": [{
            "id": p.get("id"),
            "name": p.get("name"),
        } for p in papers_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_architecture(args):
    """Show system architecture: components and their relationships."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get system
            sys_query = f'''match $s isa techrecon-system, has id "{args.id}";
            fetch {{
                "id": $s.id,
                "name": $s.name
            }};'''
            sys_result = list(tx.query(sys_query).resolve())

            if not sys_result:
                print(json.dumps({"success": False, "error": "System not found"}))
                return

            # Get all components
            comp_query = f'''match
                $s isa techrecon-system, has id "{args.id}";
                (system: $s, component: $c) isa techrecon-has-component;
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "techrecon-component-type": $c.techrecon-component-type,
                "techrecon-component-role": $c.techrecon-component-role,
                "techrecon-file-path": $c.techrecon-file-path
            }};'''
            comp_result = list(tx.query(comp_query).resolve())

            # Get component-concept links
            concept_links = []
            for c in comp_result:
                cid = c.get("id")
                cq = f'''match
                    $c isa techrecon-component, has id "{cid}";
                    (component: $c, concept: $con) isa techrecon-uses-concept;
                fetch {{
                    "id": $con.id,
                    "name": $con.name,
                    "techrecon-concept-category": $con.techrecon-concept-category
                }};'''
                for r in tx.query(cq).resolve():
                    concept_links.append({
                        "component_id": cid,
                        "concept_id": r.get("id"),
                        "concept_name": r.get("name"),
                        "concept_category": r.get("techrecon-concept-category"),
                    })

            # Get component dependencies
            comp_deps = []
            for c in comp_result:
                cid = c.get("id")
                dq = f'''match
                    $c isa techrecon-component, has id "{cid}";
                    (dependent-component: $c, dependency-component: $d) isa techrecon-component-dependency;
                fetch {{
                "id": $d.id,
                "name": $d.name
            }};'''
                for r in tx.query(dq).resolve():
                    comp_deps.append({
                        "from": cid,
                        "to": r.get("id"),
                        "to_name": r.get("name"),
                    })

    output = {
        "success": True,
        "system": {
            "id": sys_result[0].get("id"),
            "name": sys_result[0].get("name"),
        },
        "components": [{
            "id": c.get("id"),
            "name": c.get("name"),
            "type": c.get("techrecon-component-type"),
            "role": c.get("techrecon-component-role"),
            "file_path": c.get("techrecon-file-path"),
        } for c in comp_result],
        "concept_links": concept_links,
        "component_dependencies": comp_deps,
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_list_artifacts(args):
    """List artifacts with optional filters."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Build artifact type filter
            artifact_types = [
                "techrecon-readme", "techrecon-source-file", "techrecon-doc-page",
                "techrecon-schema-file", "techrecon-model-card", "techrecon-file-tree",
            ]

            if args.type:
                type_map = {
                    "readme": "techrecon-readme",
                    "source": "techrecon-source-file",
                    "doc": "techrecon-doc-page",
                    "schema": "techrecon-schema-file",
                    "model-card": "techrecon-model-card",
                    "file-tree": "techrecon-file-tree",
                }
                if args.type in type_map:
                    artifact_types = [type_map[args.type]]

            results = []
            for atype in artifact_types:
                query = f"match $a isa {atype}"

                if args.system:
                    query += f''';\n                    $s isa techrecon-system, has id "{args.system}";
                    (artifact: $a, referent: $s) isa representation'''

                query += """;
            fetch {
                "id": $a.id,
                "name": $a.name,
                "source-uri": $a.source-uri,
                "mime-type": $a.mime-type,
                "created-at": $a.created-at
            };"""

                for r in tx.query(query).resolve():
                    artifact_id = r.get("id")

                    # Check analysis status
                    status = "raw"
                    if args.status and args.status != "all":
                        notes_q = f'''match
                            $a isa artifact, has id "{artifact_id}";
                            (artifact: $a, referent: $e) isa representation;
                            (note: $n, subject: $e) isa aboutness;
                        fetch {{
                            "id": $n.id
                        }};'''
                        try:
                            notes = list(tx.query(notes_q).resolve())
                            status = "analyzed" if len(notes) > 0 else "raw"
                        except Exception:
                            status = "raw"

                        if args.status != status:
                            continue

                    results.append({
                        "id": artifact_id,
                        "name": r.get("name"),
                        "type": atype,
                        "source_uri": r.get("source-uri"),
                        "mime_type": r.get("mime-type"),
                        "created_at": r.get("created-at"),
                        "status": status,
                    })

    print(json.dumps({
        "success": True,
        "artifacts": results,
        "count": len(results),
    }, indent=2))


def cmd_show_artifact(args):
    """Show artifact content."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = f'''match $a isa artifact, has id "{args.id}";
            fetch {{
                "id": $a.id,
                "name": $a.name,
                "content": $a.content,
                "cache-path": $a.cache-path,
                "mime-type": $a.mime-type,
                "file-size": $a.file-size,
                "source-uri": $a.source-uri,
                "created-at": $a.created-at
            }};'''
            result = list(tx.query(query).resolve())

            if not result:
                print(json.dumps({"success": False, "error": "Artifact not found"}))
                return

            # Get linked entity
            entity_query = f'''match
                $a isa artifact, has id "{args.id}";
                (artifact: $a, referent: $e) isa representation;
            fetch {{
                "id": $e.id,
                "name": $e.name
            }};'''
            try:
                entity_result = list(tx.query(entity_query).resolve())
            except Exception:
                entity_result = []

    art = result[0]

    # Get content from cache or inline
    cache_path = get_attr(art, "cache-path")
    if cache_path and CACHE_AVAILABLE:
        try:
            content = load_from_cache_text(cache_path)
            storage = "cache"
        except FileNotFoundError:
            content = f"[ERROR: Cache file not found: {cache_path}]"
            storage = "cache_missing"
    else:
        content = get_attr(art, "content")
        storage = "inline"

    output = {
        "success": True,
        "artifact": {
            "id": get_attr(art, "id"),
            "name": get_attr(art, "name"),
            "source_uri": get_attr(art, "source-uri"),
            "mime_type": get_attr(art, "mime-type"),
            "created_at": get_attr(art, "created-at"),
            "content": content,
            "storage": storage,
            "cache_path": cache_path,
            "file_size": get_attr(art, "file-size"),
        },
        "linked_entity": None,
    }

    if entity_result:
        ent = entity_result[0]
        output["linked_entity"] = {
            "id": get_attr(ent, "id"),
            "name": get_attr(ent, "name"),
        }

    print(json.dumps(output, indent=2))


def cmd_show_component(args):
    """Show component details."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            comp_query = f'''match $c isa techrecon-component, has id "{args.id}";
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "description": $c.description,
                "techrecon-component-type": $c.techrecon-component-type,
                "techrecon-component-role": $c.techrecon-component-role,
                "techrecon-file-path": $c.techrecon-file-path
            }};'''
            comp_result = list(tx.query(comp_query).resolve())

            if not comp_result:
                print(json.dumps({"success": False, "error": "Component not found"}))
                return

            # Get parent system
            sys_query = f'''match
                $c isa techrecon-component, has id "{args.id}";
                (system: $s, component: $c) isa techrecon-has-component;
            fetch {{
                "id": $s.id,
                "name": $s.name
            }};'''
            sys_result = list(tx.query(sys_query).resolve())

            # Get concepts
            con_query = f'''match
                $c isa techrecon-component, has id "{args.id}";
                (component: $c, concept: $con) isa techrecon-uses-concept;
            fetch {{
                "id": $con.id,
                "name": $con.name,
                "techrecon-concept-category": $con.techrecon-concept-category
            }};'''
            con_result = list(tx.query(con_query).resolve())

            # Get notes
            notes_query = f'''match
                $c isa techrecon-component, has id "{args.id}";
                (note: $n, subject: $c) isa aboutness;
            fetch {{
                "id": $n.id,
                "name": $n.name,
                "content": $n.content
            }};'''
            notes_result = list(tx.query(notes_query).resolve())

            # Get snippets linked via techrecon-snippet-for
            snippets_query = f'''match
                $c isa techrecon-component, has id "{args.id}";
                (component: $c, snippet: $s) isa techrecon-snippet-for;
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "content": $s.content,
                "techrecon-file-language": $s.techrecon-file-language
            }};'''
            try:
                snippets_result = list(tx.query(snippets_query).resolve())
            except Exception:
                snippets_result = []

    c = comp_result[0]
    output = {
        "success": True,
        "component": {
            "id": get_attr(c, "id"),
            "name": get_attr(c, "name"),
            "description": get_attr(c, "description"),
            "type": get_attr(c, "techrecon-component-type"),
            "role": get_attr(c, "techrecon-component-role"),
            "file_path": get_attr(c, "techrecon-file-path"),
            "snippets": [{
                "id": s.get("id"),
                "name": s.get("name"),
                "content": s.get("content"),
                "language": s.get("techrecon-file-language"),
            } for s in snippets_result],
        },
        "system": {
            "id": sys_result[0].get("id"),
            "name": sys_result[0].get("name"),
        } if sys_result else None,
        "concepts": [{
            "id": r.get("id"),
            "name": r.get("name"),
            "category": r.get("techrecon-concept-category"),
        } for r in con_result],
        "notes": [{
            "id": n.get("id"),
            "name": n.get("name"),
            "content": n.get("content"),
        } for n in notes_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_concept(args):
    """Show concept details."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            con_query = f'''match $c isa techrecon-concept, has id "{args.id}";
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "description": $c.description,
                "techrecon-concept-category": $c.techrecon-concept-category
            }};'''
            con_result = list(tx.query(con_query).resolve())

            if not con_result:
                print(json.dumps({"success": False, "error": "Concept not found"}))
                return

            # Get components using this concept
            comp_query = f'''match
                $con isa techrecon-concept, has id "{args.id}";
                (component: $c, concept: $con) isa techrecon-uses-concept;
            fetch {{
                "id": $c.id,
                "name": $c.name
            }};'''
            comp_result = list(tx.query(comp_query).resolve())

            # Get notes
            notes_query = f'''match
                $con isa techrecon-concept, has id "{args.id}";
                (note: $n, subject: $con) isa aboutness;
            fetch {{
                "id": $n.id,
                "name": $n.name,
                "content": $n.content
            }};'''
            notes_result = list(tx.query(notes_query).resolve())

    c = con_result[0]
    output = {
        "success": True,
        "concept": {
            "id": get_attr(c, "id"),
            "name": get_attr(c, "name"),
            "description": get_attr(c, "description"),
            "category": get_attr(c, "techrecon-concept-category"),
        },
        "used_by_components": [{
            "id": r.get("id"),
            "name": r.get("name"),
        } for r in comp_result],
        "notes": [{
            "id": n.get("id"),
            "name": n.get("name"),
            "content": n.get("content"),
        } for n in notes_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_data_model(args):
    """Show data model details."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            model_query = f'''match $m isa techrecon-data-model, has id "{args.id}";
            fetch {{
                "id": $m.id,
                "name": $m.name,
                "description": $m.description,
                "techrecon-model-format": $m.techrecon-model-format,
                "techrecon-doc-url": $m.techrecon-doc-url
            }};'''
            model_result = list(tx.query(model_query).resolve())

            if not model_result:
                print(json.dumps({"success": False, "error": "Data model not found"}))
                return

            # Get systems using this model
            sys_query = f'''match
                $m isa techrecon-data-model, has id "{args.id}";
                (system: $s, data-model: $m) isa techrecon-has-data-model;
            fetch {{
                "id": $s.id,
                "name": $s.name
            }};'''
            sys_result = list(tx.query(sys_query).resolve())

            # Get notes
            notes_query = f'''match
                $m isa techrecon-data-model, has id "{args.id}";
                (note: $n, subject: $m) isa aboutness;
            fetch {{
                "id": $n.id,
                "name": $n.name,
                "content": $n.content
            }};'''
            notes_result = list(tx.query(notes_query).resolve())

    m = model_result[0]
    output = {
        "success": True,
        "data_model": {
            "id": get_attr(m, "id"),
            "name": get_attr(m, "name"),
            "description": get_attr(m, "description"),
            "format": get_attr(m, "techrecon-model-format"),
            "doc_url": get_attr(m, "techrecon-doc-url"),
        },
        "systems": [{
            "id": s.get("id"),
            "name": s.get("name"),
        } for s in sys_result],
        "notes": [{
            "id": n.get("id"),
            "name": n.get("name"),
            "content": n.get("content"),
        } for n in notes_result],
    }

    print(json.dumps(output, indent=2, default=str))


# =============================================================================
# NOTES AND FRAGMENTS
# =============================================================================


def cmd_add_note(args):
    """Add a note about any entity."""
    note_id = args.id or generate_id("note")
    timestamp = get_timestamp()

    # Map note type to TypeDB type
    type_map = {
        "architecture": "techrecon-architecture-note",
        "design-pattern": "techrecon-design-pattern-note",
        "integration": "techrecon-integration-note",
        "comparison": "techrecon-comparison-note",
        "data-model": "techrecon-data-model-note",
        "assessment": "techrecon-assessment-note",
        "provenance": "techrecon-provenance-note",
        "use-case": "techrecon-use-case-note",
        "ml-evaluation": "techrecon-ml-evaluation-note",
        "literature-review": "techrecon-literature-review-note",
        "general": "note",
    }

    note_type = type_map.get(args.type, "note")

    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(args.content)}",
        has created-at {timestamp}'''

    if args.name:
        query += f', has name "{escape_string(args.name)}"'
    if args.confidence:
        query += f", has confidence {args.confidence}"

    # Type-specific attributes
    if args.type in ("integration", "assessment"):
        if args.priority:
            query += f', has techrecon-integration-priority "{args.priority}"'
        if args.complexity:
            query += f', has techrecon-complexity-rating "{args.complexity}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to subject
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            about_query = f'''match
                $n isa note, has id "{note_id}";
                $s isa identifiable-entity, has id "{args.about}";
            insert (note: $n, subject: $s) isa aboutness;'''
            tx.query(about_query).resolve()
            tx.commit()

        # Add to investigation
        if args.investigation:
            add_to_collection(driver, note_id, args.investigation)

        apply_tags(driver, note_id, "note", args.tags)

    print(json.dumps({
        "success": True,
        "note_id": note_id,
        "about": args.about,
        "type": args.type,
    }))


def cmd_add_fragment(args):
    """Add a fragment extracted from an artifact."""
    frag_id = args.id or generate_id("fragment")
    timestamp = get_timestamp()

    # Map fragment type to TypeDB type
    type_map = {
        "code-snippet": "techrecon-code-snippet",
        "api-spec": "techrecon-api-spec",
        "schema-excerpt": "techrecon-schema-excerpt",
        "config-excerpt": "techrecon-config-excerpt",
        "general": "fragment",
    }

    frag_type = type_map.get(args.type, "fragment")

    query = f'''insert $f isa {frag_type},
        has id "{frag_id}",
        has content "{escape_string(args.content)}",
        has created-at {timestamp}'''

    if args.name:
        query += f', has name "{escape_string(args.name)}"'

    # Type-specific attributes
    if args.type == "code-snippet" and args.language:
        query += f', has techrecon-file-language "{escape_string(args.language)}"'
    if args.type == "schema-excerpt" and args.format:
        query += f', has techrecon-model-format "{args.format}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to source artifact via fragmentation
        if args.source:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $a isa artifact, has id "{args.source}";
                    $f isa fragment, has id "{frag_id}";
                insert (whole: $a, part: $f) isa fragmentation;''').resolve()
                tx.commit()

        # Tag fragment with the subject entity's ID for traceability
        if args.about:
            apply_tags(driver, frag_id, "fragment", [f"about:{args.about}"])

        # Link to component via techrecon-snippet-for (preferred over tag-based --about)
        if args.component:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $c isa techrecon-component, has id "{args.component}";
                    $f isa fragment, has id "{frag_id}";
                insert (snippet: $f, component: $c) isa techrecon-snippet-for;''').resolve()
                tx.commit()

        if args.investigation:
            add_to_collection(driver, frag_id, args.investigation)

        apply_tags(driver, frag_id, "fragment", args.tags)

    print(json.dumps({
        "success": True,
        "fragment_id": frag_id,
        "type": args.type,
        "source": args.source,
        "about": args.about,
        "component": getattr(args, "component", None),
    }))


# =============================================================================
# WORKFLOW COMMANDS
# =============================================================================


VALID_GRANULARITIES = [
    "single-command",
    "multi-step-sequential",
    "configuration-driven",
    "programmatic-api",
    "interactive-notebook",
]


def cmd_add_workflow(args):
    """Document how a system expects to be invoked."""
    if args.granularity not in VALID_GRANULARITIES:
        print(json.dumps({"success": False, "error": f"Invalid granularity. Choose from: {', '.join(VALID_GRANULARITIES)}"}))
        return

    workflow_id = args.id or generate_id("workflow")
    timestamp = get_timestamp()

    query = f'''insert $w isa techrecon-workflow,
        has id "{workflow_id}",
        has name "{escape_string(args.name)}",
        has description "{escape_string(args.content)}",
        has techrecon-workflow-granularity "{args.granularity}",
        has created-at {timestamp};'''

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to system
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $s isa techrecon-system, has id "{args.system}";
                $w isa techrecon-workflow, has id "{workflow_id}";
            insert (system: $s, workflow: $w) isa techrecon-system-has-workflow;''').resolve()
            tx.commit()

        # Link to components
        if args.components:
            for comp_id in args.components:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $w isa techrecon-workflow, has id "{workflow_id}";
                        $c isa techrecon-component, has id "{comp_id}";
                    insert (workflow: $w, component: $c) isa techrecon-workflow-uses;''').resolve()
                    tx.commit()

        if args.investigation:
            add_to_collection(driver, workflow_id, args.investigation)

        if args.tags:
            apply_tags(driver, workflow_id, "techrecon-workflow", args.tags)

    print(json.dumps({
        "success": True,
        "workflow_id": workflow_id,
        "system_id": args.system,
        "granularity": args.granularity,
    }, indent=2))


def cmd_list_workflows(args):
    """List workflows, optionally filtered by system or granularity."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if args.system:
                query = f'''match
                    $s isa techrecon-system, has id "{args.system}";
                    (system: $s, workflow: $w) isa techrecon-system-has-workflow;
                fetch {{
                    "id": $w.id,
                    "name": $w.name,
                    "created-at": $w.created-at
                }};'''
            elif args.investigation:
                query = f'''match
                    $inv isa techrecon-investigation, has id "{args.investigation}";
                    (collection: $inv, member: $w) isa collection-membership;
                    $w isa techrecon-workflow;
                fetch {{
                    "id": $w.id,
                    "name": $w.name,
                    "created-at": $w.created-at
                }};'''
            else:
                query = '''match $w isa techrecon-workflow;
                fetch {
                    "id": $w.id,
                    "name": $w.name,
                    "created-at": $w.created-at
                };'''
            results = list(tx.query(query).resolve())

            # Fetch category tags for all workflows
            wf_ids = [r.get("id") for r in results if r.get("id")]
            tag_map = {}  # workflow_id -> [category_name, ...]
            if wf_ids:
                tag_query = '''match
                    $w isa techrecon-workflow;
                    $t isa tag, has name $tn;
                    (tagged-entity: $w, tag: $t) isa tagging;
                fetch {
                    "wid": $w.id,
                    "tag": $tn
                };'''
                tag_results = list(tx.query(tag_query).resolve())
                for tr in tag_results:
                    wid = tr.get("wid")
                    tag_name = tr.get("tag")
                    if wid and tag_name:
                        tag_map.setdefault(wid, []).append(tag_name)

            workflows = [{
                "id": r.get("id"),
                "name": r.get("name"),
                "created_at": r.get("created-at"),
                "tags": tag_map.get(r.get("id"), []),
                "category": next(
                    (t.replace("category:", "") for t in tag_map.get(r.get("id"), []) if t.startswith("category:")),
                    None
                ),
            } for r in results]

    print(json.dumps({"success": True, "count": len(workflows), "workflows": workflows}, indent=2, default=str))


def cmd_show_workflow(args):
    """Show workflow details including system and components."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            wf_query = f'''match $w isa techrecon-workflow, has id "{args.id}";
            fetch {{
                "id": $w.id,
                "name": $w.name,
                "description": $w.description,
                "techrecon-workflow-granularity": $w.techrecon-workflow-granularity,
                "created-at": $w.created-at
            }};'''
            wf_result = list(tx.query(wf_query).resolve())

            if not wf_result:
                print(json.dumps({"success": False, "error": "Workflow not found"}))
                return

            sys_query = f'''match
                $w isa techrecon-workflow, has id "{args.id}";
                (system: $s, workflow: $w) isa techrecon-system-has-workflow;
            fetch {{ "id": $s.id, "name": $s.name }};'''
            sys_result = list(tx.query(sys_query).resolve())

            comp_query = f'''match
                $w isa techrecon-workflow, has id "{args.id}";
                (workflow: $w, component: $c) isa techrecon-workflow-uses;
            fetch {{ "id": $c.id, "name": $c.name }};'''
            comp_result = list(tx.query(comp_query).resolve())

    w = wf_result[0]
    print(json.dumps({
        "success": True,
        "workflow": {
            "id": w.get("id"),
            "name": w.get("name"),
            "content": w.get("description"),
            "granularity": w.get("techrecon-workflow-granularity"),
            "created_at": w.get("created-at"),
        },
        "system": {"id": sys_result[0].get("id"), "name": sys_result[0].get("name")} if sys_result else None,
        "components": [{"id": c.get("id"), "name": c.get("name")} for c in comp_result],
    }, indent=2, default=str))


# =============================================================================
# COMPARISON COMMANDS (Gap 4)
# =============================================================================


def cmd_list_comparisons(args):
    """List comparison notes, optionally filtered by investigation."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if args.investigation:
                query = f'''match
                    $c isa techrecon-investigation, has id "{args.investigation}";
                    (collection: $c, member: $n) isa collection-membership;
                    $n isa techrecon-comparison-note;
                fetch {{ "id": $n.id, "name": $n.name, "content": $n.content, "created-at": $n.created-at }};'''
            else:
                query = '''match $n isa techrecon-comparison-note;
                fetch { "id": $n.id, "name": $n.name, "content": $n.content, "created-at": $n.created-at };'''
            results = list(tx.query(query).resolve())
    print(json.dumps({"success": True, "count": len(results), "comparisons": results}))


def cmd_show_comparison(args):
    """Show a specific comparison note."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = f'''match $n isa techrecon-comparison-note, has id "{args.id}";
            fetch {{ "id": $n.id, "name": $n.name, "content": $n.content, "created-at": $n.created-at }};'''
            results = list(tx.query(query).resolve())
    if not results:
        print(json.dumps({"success": False, "error": f"Comparison note {args.id} not found"}))
    else:
        print(json.dumps({"success": True, "comparison": results[0]}))


# =============================================================================
# BENCHMARK COMMANDS (Gap 5)
# =============================================================================


def cmd_add_benchmark(args):
    """Add a quantitative performance benchmark to a system."""
    benchmark_id = generate_id("benchmark")
    timestamp = get_timestamp()

    query = f'''insert $b isa techrecon-benchmark,
        has id "{benchmark_id}",
        has name "{escape_string(args.name)}",
        has techrecon-metric-name "{escape_string(args.metric)}",
        has techrecon-metric-value {args.value},
        has created-at {timestamp}'''
    if args.unit:
        query += f', has techrecon-metric-unit "{escape_string(args.unit)}"'
    if args.context:
        query += f', has techrecon-metric-context "{escape_string(args.context)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $s isa techrecon-system, has id "{args.system}";
                $b isa techrecon-benchmark, has id "{benchmark_id}";
            insert (system: $s, benchmark: $b) isa techrecon-system-has-benchmark;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "benchmark_id": benchmark_id,
        "metric": args.metric,
        "value": args.value,
    }))


def cmd_show_benchmarks(args):
    """Show all benchmarks for a system."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = f'''match
                $s isa techrecon-system, has id "{args.system}";
                (system: $s, benchmark: $b) isa techrecon-system-has-benchmark;
                $b has techrecon-metric-name $mn;
                $b has techrecon-metric-value $mv;
            fetch {{
                "id": $b.id,
                "name": $b.name,
                "metric": $mn,
                "value": $mv,
                "unit": $b.techrecon-metric-unit,
                "context": $b.techrecon-metric-context
            }};'''
            results = list(tx.query(query).resolve())
    print(json.dumps({
        "success": True,
        "system": args.system,
        "count": len(results),
        "benchmarks": results,
    }))


# =============================================================================
# DESIGN DECISION COMMANDS (Gap 2)
# =============================================================================


def cmd_add_decision(args):
    """Add a design decision linked to a system or component."""
    decision_id = generate_id("decision")
    timestamp = get_timestamp()

    query = f'''insert $d isa techrecon-design-decision,
        has id "{decision_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''
    if args.rationale:
        query += f', has techrecon-decision-rationale "{escape_string(args.rationale)}"'
    if args.alternatives:
        query += f', has techrecon-alternative-considered "{escape_string(args.alternatives)}"'
    if args.trade_off:
        query += f', has techrecon-trade-off "{escape_string(args.trade_off)}"'
    if args.status:
        query += f', has techrecon-decision-status "{args.status}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    subject_id = args.system or args.component
    subject_type = "techrecon-system" if args.system else "techrecon-component"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $s isa {subject_type}, has id "{subject_id}";
                $d isa techrecon-design-decision, has id "{decision_id}";
            insert (decision: $d, subject: $s) isa techrecon-decision-applies-to;''').resolve()
            tx.commit()

        if args.investigation:
            add_to_collection(driver, decision_id, args.investigation)

    print(json.dumps({"success": True, "decision_id": decision_id, "name": args.name}))


def cmd_show_decisions(args):
    """Show all design decisions for a system or component."""
    subject_id = args.system or args.component
    subject_type = "techrecon-system" if args.system else "techrecon-component"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = f'''match
                $s isa {subject_type}, has id "{subject_id}";
                (decision: $d, subject: $s) isa techrecon-decision-applies-to;
            fetch {{
                "id": $d.id,
                "name": $d.name,
                "description": $d.description,
                "rationale": $d.techrecon-decision-rationale,
                "alternatives": $d.techrecon-alternative-considered,
                "trade-off": $d.techrecon-trade-off,
                "status": $d.techrecon-decision-status,
                "created-at": $d.created-at
            }};'''
            results = list(tx.query(query).resolve())
    print(json.dumps({
        "success": True,
        "subject": subject_id,
        "count": len(results),
        "decisions": results,
    }))


# =============================================================================
# TAGGING
# =============================================================================


def cmd_tag(args):
    """Tag an entity."""
    with get_driver() as driver:
        apply_tags(driver, args.entity, "identifiable-entity", [args.tag])

    print(json.dumps({"success": True, "entity": args.entity, "tag": args.tag}))


def cmd_search_tag(args):
    """Search entities by tag."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = f'''match
                $t isa tag, has name "{args.tag}";
                (tagged-entity: $e, tag: $t) isa tagging;
            fetch {{
                "id": $e.id,
                "name": $e.name
            }};'''
            results = list(tx.query(query).resolve())

    entities = []
    for r in results:
        entities.append({
            "id": r.get("id"),
            "name": r.get("name"),
        })

    print(json.dumps({
        "success": True,
        "tag": args.tag,
        "entities": entities,
        "count": len(entities),
    }, indent=2, default=str))


# =============================================================================
# CACHE
# =============================================================================


def cmd_cache_stats(args):
    """Show cache statistics."""
    stats = get_cache_stats()

    if "error" in stats:
        print(json.dumps({"success": False, "error": stats["error"]}))
        return

    output = {
        "success": True,
        "cache_dir": stats["cache_dir"],
        "total_files": stats["total_files"],
        "total_size": stats["total_size"],
        "total_size_human": format_size(stats["total_size"]),
        "by_type": {},
    }

    for type_name, type_stats in stats["by_type"].items():
        output["by_type"][type_name] = {
            "count": type_stats["count"],
            "size": type_stats["size"],
            "size_human": format_size(type_stats["size"]),
        }

    print(json.dumps(output, indent=2))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Tech Recon CLI - Systematically investigate external software systems"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- Investigation Management ---

    p = subparsers.add_parser("start-investigation", help="Start a new investigation")
    p.add_argument("--name", required=True, help="Investigation name")
    p.add_argument("--goal", required=True, help="What we want to learn")
    p.add_argument("--description", help="Detailed description")
    p.add_argument("--system", help="System ID to include in investigation")

    p = subparsers.add_parser("list-investigations", help="List investigations")
    p.add_argument("--status", choices=["active", "paused", "completed", "archived"], help="Filter by status")

    p = subparsers.add_parser("show-investigation", help="Show investigation details with all members")
    p.add_argument("--id", required=True, help="Investigation ID")

    p = subparsers.add_parser("update-investigation", help="Update investigation status")
    p.add_argument("--id", required=True, help="Investigation ID")
    p.add_argument("--status", required=True, choices=["active", "paused", "completed", "archived"], help="New status")

    # --- Entity Creation ---

    p = subparsers.add_parser("add-system", help="Add a software system")
    p.add_argument("--name", required=True, help="System name")
    p.add_argument("--repo-url", dest="repo_url", help="Repository URL")
    p.add_argument("--doc-url", dest="doc_url", help="Documentation URL")
    p.add_argument("--language", help="Primary language")
    p.add_argument("--version", help="Version string")
    p.add_argument("--maturity", choices=["experimental", "alpha", "beta", "stable", "mature", "deprecated"], help="Maturity level")
    p.add_argument("--license", help="License type")
    p.add_argument("--package", help="Package name (pip/npm/cargo)")
    p.add_argument("--description", help="Description")
    p.add_argument("--investigation", help="Investigation ID to add to")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    p = subparsers.add_parser("add-component", help="Add a component/module")
    p.add_argument("--name", required=True, help="Component name")
    p.add_argument("--system", help="System ID to link to")
    p.add_argument("--type", choices=["module", "service", "library", "plugin", "API", "CLI", "data-store"], help="Component type")
    p.add_argument("--role", help="Component role/purpose")
    p.add_argument("--file-path", dest="file_path", help="File path in repo")
    p.add_argument("--description", help="Description")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    p = subparsers.add_parser("add-concept", help="Add a key concept")
    p.add_argument("--name", required=True, help="Concept name")
    p.add_argument("--category", choices=["algorithm", "pattern", "protocol", "data-structure", "architecture"], help="Category")
    p.add_argument("--description", help="Description")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    p = subparsers.add_parser("add-data-model", help="Add a data model/schema")
    p.add_argument("--name", required=True, help="Data model name")
    p.add_argument("--system", help="System ID to link to")
    p.add_argument("--format", choices=["JSON-Schema", "RDF-OWL", "TypeDB", "SQL", "Protobuf", "GraphQL", "custom"], help="Model format")
    p.add_argument("--doc-url", dest="doc_url", help="Documentation URL")
    p.add_argument("--description", help="Description")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    # --- Ingestion ---

    p = subparsers.add_parser("ingest-repo", help="Ingest a GitHub repository")
    p.add_argument("--url", required=True, help="GitHub repository URL")
    p.add_argument("--system", help="Existing system ID (creates new if not specified)")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")

    p = subparsers.add_parser("clone-repo", help="Clone a GitHub repo locally for native file exploration")
    p.add_argument("--url", required=True, help="GitHub repository URL")
    p.add_argument("--system", help="Existing system ID (creates new if not specified)")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--update", action="store_true", help="Pull latest if already cloned")

    p = subparsers.add_parser("ingest-doc", help="Ingest a documentation page")
    p.add_argument("--url", required=True, help="Documentation URL")
    p.add_argument("--system", help="System ID to link to")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")

    p = subparsers.add_parser("ingest-source", help="Ingest a source code file")
    p.add_argument("--url", required=True, help="Source file URL (GitHub blob URL OK)")
    p.add_argument("--file-path", dest="file_path", help="File path within repo")
    p.add_argument("--language", help="Programming language")
    p.add_argument("--system", help="System ID to link to")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")

    p = subparsers.add_parser("ingest-schema", help="Ingest a schema/model file")
    p.add_argument("--url", help="Schema URL (GitHub blob URL OK)")
    p.add_argument("--file", help="Local file path")
    p.add_argument("--format", choices=["JSON-Schema", "RDF-OWL", "TypeDB", "SQL", "Protobuf", "GraphQL", "custom"], help="Schema format")
    p.add_argument("--system", help="System ID to link to")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")

    p = subparsers.add_parser("ingest-model-card", help="Ingest a HuggingFace model card")
    p.add_argument("--model-id", dest="model_id", required=True, help="HuggingFace model ID (e.g., bert-base-uncased)")
    p.add_argument("--system", help="System ID to link to")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")

    # --- Linking ---

    p = subparsers.add_parser("link-component", help="Link component to system")
    p.add_argument("--system", required=True, help="System ID")
    p.add_argument("--component", required=True, help="Component ID")

    p = subparsers.add_parser("link-concept", help="Link concept to component")
    p.add_argument("--component", required=True, help="Component ID")
    p.add_argument("--concept", required=True, help="Concept ID")
    p.add_argument("--confidence", type=float, help="Confidence score (0.0-1.0)")

    p = subparsers.add_parser("link-data-model", help="Link data model to system")
    p.add_argument("--system", required=True, help="System ID")
    p.add_argument("--data-model", dest="data_model", required=True, help="Data model ID")

    p = subparsers.add_parser("link-dependency", help="Link system dependency")
    p.add_argument("--system", required=True, help="Dependent system ID")
    p.add_argument("--dependency", required=True, help="Dependency system ID")
    p.add_argument("--version", help="Version constraint")

    p = subparsers.add_parser("link-paper", help="Link a system to a scilit-paper")
    p.add_argument("--system-id", required=True, dest="system_id", help="techrecon-system ID")
    p.add_argument("--paper-id", required=True, dest="paper_id", help="scilit-paper ID")

    p = subparsers.add_parser("search-literature", help="Search scientific literature and link papers to a system")
    p.add_argument("--query", required=True, help="Search query")
    p.add_argument("--system", required=True, help="System ID to link papers to")
    p.add_argument("--source", default="openalex",
                   choices=["pubmed", "openalex", "biorxiv"],
                   help="Literature source (default: openalex)")
    p.add_argument("--limit", type=int, default=10, help="Maximum results (default: 10)")
    p.add_argument("--investigation", help="Investigation ID")

    # --- Queries ---

    subparsers.add_parser("list-systems", help="List all systems")

    p = subparsers.add_parser("show-system", help="Show system details")
    p.add_argument("--id", required=True, help="System ID")

    p = subparsers.add_parser("show-architecture", help="Show system architecture")
    p.add_argument("--id", required=True, help="System ID")

    p = subparsers.add_parser("list-artifacts", help="List artifacts")
    p.add_argument("--status", choices=["raw", "analyzed", "all"], help="Filter by status")
    p.add_argument("--system", help="Filter by system ID")
    p.add_argument("--type", choices=["readme", "source", "doc", "schema", "model-card", "file-tree"], help="Filter by type")

    p = subparsers.add_parser("show-artifact", help="Show artifact content")
    p.add_argument("--id", required=True, help="Artifact ID")

    p = subparsers.add_parser("show-component", help="Show component details")
    p.add_argument("--id", required=True, help="Component ID")

    p = subparsers.add_parser("show-concept", help="Show concept details")
    p.add_argument("--id", required=True, help="Concept ID")

    p = subparsers.add_parser("show-data-model", help="Show data model details")
    p.add_argument("--id", required=True, help="Data model ID")

    # --- Notes and Fragments ---

    p = subparsers.add_parser("add-note", help="Add a note about any entity")
    p.add_argument("--about", required=True, help="Entity ID this note is about")
    p.add_argument("--type", required=True,
                   choices=["architecture", "design-pattern", "integration", "comparison", "data-model", "assessment", "provenance", "use-case", "ml-evaluation", "literature-review", "general"],
                   help="Note type")
    p.add_argument("--content", required=True, help="Note content")
    p.add_argument("--name", help="Note title")
    p.add_argument("--confidence", type=float, help="Confidence score (0.0-1.0)")
    p.add_argument("--priority", choices=["high", "medium", "low", "none"], help="Integration priority (for integration/assessment notes)")
    p.add_argument("--complexity", choices=["trivial", "moderate", "complex", "prohibitive"], help="Complexity rating (for integration/assessment notes)")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    p = subparsers.add_parser("add-fragment", help="Add a fragment extracted from an artifact")
    p.add_argument("--type", required=True,
                   choices=["code-snippet", "api-spec", "schema-excerpt", "config-excerpt", "general"],
                   help="Fragment type")
    p.add_argument("--content", required=True, help="Fragment content")
    p.add_argument("--name", help="Fragment title")
    p.add_argument("--source", help="Source artifact ID")
    p.add_argument("--about", help="Entity ID this fragment is about (tag-based)")
    p.add_argument("--component", help="Component ID to link via techrecon-snippet-for (preferred)")
    p.add_argument("--language", help="Programming language (for code-snippet)")
    p.add_argument("--format", choices=["JSON-Schema", "RDF-OWL", "TypeDB", "SQL", "Protobuf", "GraphQL", "custom"],
                   help="Schema format (for schema-excerpt)")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    # --- Workflows ---

    p = subparsers.add_parser("add-workflow", help="Document how a system expects to be invoked")
    p.add_argument("--system", required=True, help="System ID")
    p.add_argument("--name", required=True, help="Workflow name")
    p.add_argument("--granularity", required=True,
                   choices=VALID_GRANULARITIES,
                   help="Invocation granularity")
    p.add_argument("--content", required=True, help="Free-text markdown: steps, params, examples")
    p.add_argument("--components", nargs="+", help="Component IDs this workflow exercises")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    p = subparsers.add_parser("list-workflows", help="List workflows")
    p.add_argument("--system", help="Filter by system ID")
    p.add_argument("--investigation", help="Filter by investigation ID")
    p.add_argument("--granularity", choices=VALID_GRANULARITIES, help="Filter by granularity")

    p = subparsers.add_parser("show-workflow", help="Show workflow details")
    p.add_argument("--id", required=True, help="Workflow ID")

    # --- Tagging ---

    p = subparsers.add_parser("tag", help="Tag an entity")
    p.add_argument("--entity", required=True, help="Entity ID")
    p.add_argument("--tag", required=True, help="Tag name")

    p = subparsers.add_parser("search-tag", help="Search by tag")
    p.add_argument("--tag", required=True, help="Tag to search for")

    # --- Cache ---

    subparsers.add_parser("cache-stats", help="Show cache statistics")

    # --- Comparison queries ---

    p = subparsers.add_parser("list-comparisons", help="List comparison notes")
    p.add_argument("--investigation", help="Filter by investigation ID")

    p = subparsers.add_parser("show-comparison", help="Show a comparison note")
    p.add_argument("--id", required=True, help="Comparison note ID")

    # --- Benchmarks ---

    p = subparsers.add_parser("add-benchmark", help="Add a quantitative metric to a system")
    p.add_argument("--system", required=True, help="System ID")
    p.add_argument("--name", required=True, help="Benchmark name (e.g. 'Conclusion accuracy')")
    p.add_argument("--metric", required=True, help="Metric name (e.g. 'accuracy')")
    p.add_argument("--value", required=True, type=float, help="Numeric value")
    p.add_argument("--unit", help="Unit (e.g. '%', 'ms', 'USD/run')")
    p.add_argument("--context", help="Context note (e.g. 'on 20-step run')")

    p = subparsers.add_parser("show-benchmarks", help="Show benchmarks for a system")
    p.add_argument("--system", required=True, help="System ID")

    # --- Design decisions ---

    p = subparsers.add_parser("add-decision", help="Add a design decision for a system or component")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--system", help="System ID")
    g.add_argument("--component", help="Component ID")
    p.add_argument("--name", required=True, help="Decision name/title")
    p.add_argument("--rationale", help="Why this decision was made")
    p.add_argument("--alternatives", help="Alternatives that were considered")
    p.add_argument("--trade-off", dest="trade_off", help="Trade-offs accepted")
    p.add_argument("--status", choices=["open", "decided", "revisited"], default="decided", help="Decision status")
    p.add_argument("--description", help="Additional description")
    p.add_argument("--investigation", help="Investigation ID")

    p = subparsers.add_parser("show-decisions", help="Show design decisions for a system or component")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--system", help="System ID")
    g.add_argument("--component", help="Component ID")

    p = subparsers.add_parser("list-papers", help="List scientific papers linked to a system")
    p.add_argument("--system", required=True, help="System ID")

    # --- Parse and dispatch ---

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        # Investigation management
        "start-investigation": cmd_start_investigation,
        "list-investigations": cmd_list_investigations,
        "show-investigation": cmd_show_investigation,
        "update-investigation": cmd_update_investigation,
        # Entity creation
        "add-system": cmd_add_system,
        "add-component": cmd_add_component,
        "add-concept": cmd_add_concept,
        "add-data-model": cmd_add_data_model,
        # Ingestion
        "ingest-repo": cmd_ingest_repo,
        "clone-repo": cmd_clone_repo,
        "ingest-doc": cmd_ingest_doc,
        "ingest-source": cmd_ingest_source,
        "ingest-schema": cmd_ingest_schema,
        "ingest-model-card": cmd_ingest_model_card,
        # Linking
        "link-component": cmd_link_component,
        "link-concept": cmd_link_concept,
        "link-data-model": cmd_link_data_model,
        "link-dependency": cmd_link_dependency,
        "link-paper": cmd_link_paper,
        "search-literature": cmd_search_literature,
        # Queries
        "list-systems": cmd_list_systems,
        "list-papers": cmd_list_papers,
        "show-system": cmd_show_system,
        "show-architecture": cmd_show_architecture,
        "list-artifacts": cmd_list_artifacts,
        "show-artifact": cmd_show_artifact,
        "show-component": cmd_show_component,
        "show-concept": cmd_show_concept,
        "show-data-model": cmd_show_data_model,
        # Workflows
        "add-workflow": cmd_add_workflow,
        "list-workflows": cmd_list_workflows,
        "show-workflow": cmd_show_workflow,
        # Notes and fragments
        "add-note": cmd_add_note,
        "add-fragment": cmd_add_fragment,
        # Tagging
        "tag": cmd_tag,
        "search-tag": cmd_search_tag,
        # Cache
        "cache-stats": cmd_cache_stats,
        # Comparison queries
        "list-comparisons": cmd_list_comparisons,
        "show-comparison": cmd_show_comparison,
        # Benchmarks
        "add-benchmark": cmd_add_benchmark,
        "show-benchmarks": cmd_show_benchmarks,
        # Design decisions
        "add-decision": cmd_add_decision,
        "show-decisions": cmd_show_decisions,
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
