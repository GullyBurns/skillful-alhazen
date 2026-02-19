#!/usr/bin/env python3
"""
Tech Recon CLI - Systematically investigate external software systems.

This script handles INGESTION and QUERIES. Claude handles SENSEMAKING via the SKILL.md.

Usage:
    python .claude/skills/techrecon/techrecon.py <command> [options]

Commands:
    # Investigation Management
    start-investigation   Start a new investigation
    list-investigations   List investigations
    update-investigation  Update investigation status

    # Entity Creation
    add-system            Add a software system
    add-component         Add a component/module
    add-concept           Add a key concept
    add-data-model        Add a data model/schema

    # Ingestion
    ingest-repo           Ingest a GitHub repository (README + file tree)
    ingest-doc            Ingest a documentation page
    ingest-source         Ingest a source code file
    ingest-schema         Ingest a schema/model file
    ingest-model-card     Ingest a HuggingFace model card

    # Linking
    link-component        Link component to system
    link-concept          Link concept to component
    link-data-model       Link data model to system
    link-dependency       Link system dependency

    # Queries
    list-systems          List all systems
    show-system           Show system details
    show-architecture     Show system architecture (components + relations)
    list-artifacts        List artifacts
    show-artifact         Show artifact content
    show-component        Show component details
    show-concept          Show concept details
    show-data-model       Show data model details

    # Notes and Fragments
    add-note              Add a note about any entity
    add-fragment          Add a fragment extracted from an artifact

    # Tagging
    tag                   Tag an entity
    search-tag            Search by tag

    # Cache
    cache-stats           Show cache statistics

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    ALHAZEN_CACHE_DIR File cache directory (default: ~/.alhazen/cache)
    GITHUB_TOKEN      GitHub API token (optional, for higher rate limits)
"""

import argparse
import base64
import json
import os
import sys
import uuid
from datetime import datetime, timezone
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
    from typedb.driver import SessionType, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=2.25.0,<3.0.0'",
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
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


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
    """Safely extract attribute value from TypeDB fetch result."""
    attr_list = entity.get(attr_name, [])
    if attr_list and len(attr_list) > 0:
        return attr_list[0].get("value", default)
    return default


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


def store_artifact(session, artifact_id, artifact_type, name, content, source_uri,
                   mime_type="text/plain", extra_attrs=None):
    """Store an artifact with inline or cached content.

    Returns dict with storage info.
    """
    timestamp = get_timestamp()

    with session.transaction(TransactionType.WRITE) as tx:
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
        tx.query.insert(query)
        tx.commit()

    return {"storage": storage, "content_length": len(content)}


def link_artifact_to_entity(session, artifact_id, artifact_type, entity_id, entity_type):
    """Link an artifact to an entity via representation relation."""
    with session.transaction(TransactionType.WRITE) as tx:
        query = f'''match
            $a isa {artifact_type}, has id "{artifact_id}";
            $e isa {entity_type}, has id "{entity_id}";
        insert (artifact: $a, referent: $e) isa representation;'''
        tx.query.insert(query)
        tx.commit()


def add_to_collection(session, entity_id, collection_id):
    """Add an entity to a collection via collection-membership."""
    timestamp = get_timestamp()
    with session.transaction(TransactionType.WRITE) as tx:
        query = f'''match
            $c isa techrecon-investigation, has id "{collection_id}";
            $e isa entity, has id "{entity_id}";
        insert (collection: $c, member: $e) isa collection-membership,
            has created-at {timestamp};'''
        tx.query.insert(query)
        tx.commit()


def apply_tags(session, entity_id, entity_type, tags):
    """Apply tags to an entity."""
    if not tags:
        return
    for tag_name in tags:
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
                $e isa {entity_type}, has id "{entity_id}";
                $t isa tag, has name "{tag_name}";
            insert (tagged-entity: $e, tag: $t) isa tagging;''')
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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # If a system is specified, add it to the investigation
            if args.system:
                add_to_collection(session, args.system, inv_id)

    print(json.dumps({
        "success": True,
        "investigation_id": inv_id,
        "name": args.name,
        "goal": args.goal,
        "status": "active",
    }, indent=2))


def cmd_list_investigations(args):
    """List investigations."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = "match $i isa techrecon-investigation"
                if args.status:
                    query += f', has techrecon-investigation-status "{args.status}"'
                query += """;
                fetch $i: id, name, techrecon-investigation-status, techrecon-investigation-goal, created-at;"""
                results = list(tx.query.fetch(query))

    investigations = []
    for r in results:
        investigations.append({
            "id": get_attr(r["i"], "id"),
            "name": get_attr(r["i"], "name"),
            "status": get_attr(r["i"], "techrecon-investigation-status"),
            "goal": get_attr(r["i"], "techrecon-investigation-goal"),
            "created_at": get_attr(r["i"], "created-at"),
        })

    print(json.dumps({"success": True, "investigations": investigations, "count": len(investigations)}, indent=2))


def cmd_update_investigation(args):
    """Update investigation status."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Delete old status and insert new
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.delete(f'''match
                    $i isa techrecon-investigation, has id "{args.id}",
                        has techrecon-investigation-status $s;
                delete $i has $s;''')
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'''match
                    $i isa techrecon-investigation, has id "{args.id}";
                insert $i has techrecon-investigation-status "{args.status}";''')
                tx.commit()

    print(json.dumps({"success": True, "investigation_id": args.id, "status": args.status}))


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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Add to investigation if specified
            if args.investigation:
                add_to_collection(session, system_id, args.investigation)

            apply_tags(session, system_id, "techrecon-system", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to system if specified
            if args.system:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(f'''match
                        $s isa techrecon-system, has id "{args.system}";
                        $c isa techrecon-component, has id "{comp_id}";
                    insert (system: $s, component: $c) isa techrecon-has-component;''')
                    tx.commit()

            # Add to investigation if specified
            if args.investigation:
                add_to_collection(session, comp_id, args.investigation)

            apply_tags(session, comp_id, "techrecon-component", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            if args.investigation:
                add_to_collection(session, concept_id, args.investigation)

            apply_tags(session, concept_id, "techrecon-concept", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to system if specified
            if args.system:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(f'''match
                        $s isa techrecon-system, has id "{args.system}";
                        $m isa techrecon-data-model, has id "{model_id}";
                    insert (system: $s, data-model: $m) isa techrecon-has-data-model;''')
                    tx.commit()

            if args.investigation:
                add_to_collection(session, model_id, args.investigation)

            apply_tags(session, model_id, "techrecon-data-model", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
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
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(sys_query)
                    tx.commit()

            # Store README artifact
            readme_artifact_id = None
            if readme_content:
                readme_artifact_id = generate_id("artifact")
                store_artifact(
                    session,
                    readme_artifact_id,
                    "techrecon-readme",
                    f"README: {owner}/{repo}",
                    readme_content,
                    f"{args.url}/blob/main/README.md",
                    mime_type="text/markdown",
                )
                link_artifact_to_entity(session, readme_artifact_id, "techrecon-readme", system_id, "techrecon-system")

            # Store file tree artifact
            tree_artifact_id = None
            if file_tree:
                tree_artifact_id = generate_id("artifact")
                tree_json = json.dumps(file_tree, indent=2)
                store_artifact(
                    session,
                    tree_artifact_id,
                    "techrecon-file-tree",
                    f"File Tree: {owner}/{repo}",
                    tree_json,
                    f"{args.url}/tree/main",
                    mime_type="application/json",
                )
                link_artifact_to_entity(session, tree_artifact_id, "techrecon-file-tree", system_id, "techrecon-system")

            # Add to investigation
            if args.investigation:
                add_to_collection(session, system_id, args.investigation)
                if readme_artifact_id:
                    add_to_collection(session, readme_artifact_id, args.investigation)
                if tree_artifact_id:
                    add_to_collection(session, tree_artifact_id, args.investigation)

            apply_tags(session, system_id, "techrecon-system", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            name = title if title else f"Doc page: {args.url[:60]}"
            store_artifact(
                session, artifact_id, "techrecon-doc-page",
                name, content, args.url, mime_type="text/html",
            )

            # Link to system
            if args.system:
                link_artifact_to_entity(session, artifact_id, "techrecon-doc-page", args.system, "techrecon-system")

            if args.investigation:
                add_to_collection(session, artifact_id, args.investigation)

            apply_tags(session, artifact_id, "techrecon-doc-page", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            store_artifact(
                session, artifact_id, "techrecon-source-file",
                f"Source: {file_path}", content, args.url,
                mime_type="text/plain", extra_attrs=extra_attrs,
            )

            if args.system:
                link_artifact_to_entity(session, artifact_id, "techrecon-source-file", args.system, "techrecon-system")

            if args.investigation:
                add_to_collection(session, artifact_id, args.investigation)

            apply_tags(session, artifact_id, "techrecon-source-file", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            store_artifact(
                session, artifact_id, "techrecon-schema-file",
                f"Schema: {name}", content, source_uri,
                mime_type="text/plain", extra_attrs=extra_attrs,
            )

            if args.system:
                link_artifact_to_entity(session, artifact_id, "techrecon-schema-file", args.system, "techrecon-system")

            if args.investigation:
                add_to_collection(session, artifact_id, args.investigation)

            apply_tags(session, artifact_id, "techrecon-schema-file", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            store_artifact(
                session, artifact_id, "techrecon-model-card",
                f"Model Card: {model_id}", card_content,
                f"https://huggingface.co/{model_id}",
                mime_type="text/markdown", extra_attrs=extra_attrs,
            )

            if args.system:
                link_artifact_to_entity(session, artifact_id, "techrecon-model-card", args.system, "techrecon-system")

            if args.investigation:
                add_to_collection(session, artifact_id, args.investigation)

            apply_tags(session, artifact_id, "techrecon-model-card", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'''match
                    $s isa techrecon-system, has id "{args.system}";
                    $c isa techrecon-component, has id "{args.component}";
                insert (system: $s, component: $c) isa techrecon-has-component;''')
                tx.commit()

    print(json.dumps({"success": True, "system": args.system, "component": args.component}))


def cmd_link_concept(args):
    """Link a concept to a component."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $comp isa techrecon-component, has id "{args.component}";
                    $con isa techrecon-concept, has id "{args.concept}";
                insert (component: $comp, concept: $con) isa techrecon-uses-concept'''
                if args.confidence:
                    query += f", has confidence {args.confidence}"
                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "component": args.component, "concept": args.concept}))


def cmd_link_data_model(args):
    """Link a data model to a system."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'''match
                    $s isa techrecon-system, has id "{args.system}";
                    $m isa techrecon-data-model, has id "{args.data_model}";
                insert (system: $s, data-model: $m) isa techrecon-has-data-model;''')
                tx.commit()

    print(json.dumps({"success": True, "system": args.system, "data_model": args.data_model}))


def cmd_link_dependency(args):
    """Link a system dependency."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $s isa techrecon-system, has id "{args.system}";
                    $d isa techrecon-system, has id "{args.dependency}";
                insert (dependent: $s, dependency: $d) isa techrecon-system-dependency'''
                if args.version:
                    query += f', has techrecon-version "{escape_string(args.version)}"'
                query += ";"
                tx.query.insert(query)
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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match $s isa techrecon-system;
                fetch $s: id, name, techrecon-repo-url, techrecon-language,
                    techrecon-stars, techrecon-maturity, created-at;"""
                results = list(tx.query.fetch(query))

    systems = []
    for r in results:
        systems.append({
            "id": get_attr(r["s"], "id"),
            "name": get_attr(r["s"], "name"),
            "repo_url": get_attr(r["s"], "techrecon-repo-url"),
            "language": get_attr(r["s"], "techrecon-language"),
            "stars": get_attr(r["s"], "techrecon-stars"),
            "maturity": get_attr(r["s"], "techrecon-maturity"),
            "created_at": get_attr(r["s"], "created-at"),
        })

    print(json.dumps({"success": True, "systems": systems, "count": len(systems)}, indent=2))


def cmd_show_system(args):
    """Show full system details."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # System details
                sys_query = f'''match $s isa techrecon-system, has id "{args.id}";
                fetch $s: id, name, description, techrecon-repo-url, techrecon-doc-url,
                    techrecon-language, techrecon-version, techrecon-stars, techrecon-last-commit,
                    techrecon-license-type, techrecon-maturity, techrecon-package-name, created-at;'''
                sys_result = list(tx.query.fetch(sys_query))

                if not sys_result:
                    print(json.dumps({"success": False, "error": "System not found"}))
                    return

                # Components
                comp_query = f'''match
                    $s isa techrecon-system, has id "{args.id}";
                    (system: $s, component: $c) isa techrecon-has-component;
                fetch $c: id, name, techrecon-component-type, techrecon-component-role;'''
                comp_result = list(tx.query.fetch(comp_query))

                # Data models
                model_query = f'''match
                    $s isa techrecon-system, has id "{args.id}";
                    (system: $s, data-model: $m) isa techrecon-has-data-model;
                fetch $m: id, name, techrecon-model-format;'''
                model_result = list(tx.query.fetch(model_query))

                # Dependencies
                dep_query = f'''match
                    $s isa techrecon-system, has id "{args.id}";
                    (dependent: $s, dependency: $d) isa techrecon-system-dependency;
                fetch $d: id, name;'''
                dep_result = list(tx.query.fetch(dep_query))

                # Artifacts
                artifact_query = f'''match
                    $s isa techrecon-system, has id "{args.id}";
                    (artifact: $a, referent: $s) isa representation;
                fetch $a: id, name, source-uri, mime-type;'''
                artifact_result = list(tx.query.fetch(artifact_query))

                # Notes
                notes_query = f'''match
                    $s isa techrecon-system, has id "{args.id}";
                    (note: $n, subject: $s) isa aboutness;
                fetch $n: id, name, content;'''
                notes_result = list(tx.query.fetch(notes_query))

                # Tags
                tags_query = f'''match
                    $s isa techrecon-system, has id "{args.id}";
                    (tagged-entity: $s, tag: $t) isa tagging;
                fetch $t: name;'''
                tags_result = list(tx.query.fetch(tags_query))

    s = sys_result[0]["s"]
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
        },
        "components": [{
            "id": get_attr(c["c"], "id"),
            "name": get_attr(c["c"], "name"),
            "type": get_attr(c["c"], "techrecon-component-type"),
            "role": get_attr(c["c"], "techrecon-component-role"),
        } for c in comp_result],
        "data_models": [{
            "id": get_attr(m["m"], "id"),
            "name": get_attr(m["m"], "name"),
            "format": get_attr(m["m"], "techrecon-model-format"),
        } for m in model_result],
        "dependencies": [{
            "id": get_attr(d["d"], "id"),
            "name": get_attr(d["d"], "name"),
        } for d in dep_result],
        "artifacts": [{
            "id": get_attr(a["a"], "id"),
            "name": get_attr(a["a"], "name"),
            "source_uri": get_attr(a["a"], "source-uri"),
            "mime_type": get_attr(a["a"], "mime-type"),
        } for a in artifact_result],
        "notes": [{
            "id": get_attr(n["n"], "id"),
            "name": get_attr(n["n"], "name"),
            "content": get_attr(n["n"], "content"),
        } for n in notes_result],
        "tags": [get_attr(t["t"], "name") for t in tags_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_architecture(args):
    """Show system architecture: components and their relationships."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get system
                sys_query = f'''match $s isa techrecon-system, has id "{args.id}";
                fetch $s: id, name;'''
                sys_result = list(tx.query.fetch(sys_query))

                if not sys_result:
                    print(json.dumps({"success": False, "error": "System not found"}))
                    return

                # Get all components
                comp_query = f'''match
                    $s isa techrecon-system, has id "{args.id}";
                    (system: $s, component: $c) isa techrecon-has-component;
                fetch $c: id, name, techrecon-component-type, techrecon-component-role, techrecon-file-path;'''
                comp_result = list(tx.query.fetch(comp_query))

                # Get component-concept links
                concept_links = []
                for c in comp_result:
                    cid = get_attr(c["c"], "id")
                    cq = f'''match
                        $c isa techrecon-component, has id "{cid}";
                        (component: $c, concept: $con) isa techrecon-uses-concept;
                    fetch $con: id, name, techrecon-concept-category;'''
                    for r in tx.query.fetch(cq):
                        concept_links.append({
                            "component_id": cid,
                            "concept_id": get_attr(r["con"], "id"),
                            "concept_name": get_attr(r["con"], "name"),
                            "concept_category": get_attr(r["con"], "techrecon-concept-category"),
                        })

                # Get component dependencies
                comp_deps = []
                for c in comp_result:
                    cid = get_attr(c["c"], "id")
                    dq = f'''match
                        $c isa techrecon-component, has id "{cid}";
                        (dependent-component: $c, dependency-component: $d) isa techrecon-component-dependency;
                    fetch $d: id, name;'''
                    for r in tx.query.fetch(dq):
                        comp_deps.append({
                            "from": cid,
                            "to": get_attr(r["d"], "id"),
                            "to_name": get_attr(r["d"], "name"),
                        })

    output = {
        "success": True,
        "system": {
            "id": get_attr(sys_result[0]["s"], "id"),
            "name": get_attr(sys_result[0]["s"], "name"),
        },
        "components": [{
            "id": get_attr(c["c"], "id"),
            "name": get_attr(c["c"], "name"),
            "type": get_attr(c["c"], "techrecon-component-type"),
            "role": get_attr(c["c"], "techrecon-component-role"),
            "file_path": get_attr(c["c"], "techrecon-file-path"),
        } for c in comp_result],
        "concept_links": concept_links,
        "component_dependencies": comp_deps,
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_list_artifacts(args):
    """List artifacts with optional filters."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
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
                        query += f''';\n                        $s isa techrecon-system, has id "{args.system}";
                        (artifact: $a, referent: $s) isa representation'''

                    query += ";\nfetch $a: id, name, source-uri, mime-type, created-at;"

                    for r in tx.query.fetch(query):
                        artifact_id = get_attr(r["a"], "id")

                        # Check analysis status
                        status = "raw"
                        if args.status and args.status != "all":
                            notes_q = f'''match
                                $a isa artifact, has id "{artifact_id}";
                                (artifact: $a, referent: $e) isa representation;
                                (note: $n, subject: $e) isa aboutness;
                            fetch $n: id;'''
                            try:
                                notes = list(tx.query.fetch(notes_q))
                                status = "analyzed" if len(notes) > 0 else "raw"
                            except Exception:
                                status = "raw"

                            if args.status != status:
                                continue

                        results.append({
                            "id": artifact_id,
                            "name": get_attr(r["a"], "name"),
                            "type": atype,
                            "source_uri": get_attr(r["a"], "source-uri"),
                            "mime_type": get_attr(r["a"], "mime-type"),
                            "created_at": get_attr(r["a"], "created-at"),
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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match $a isa artifact, has id "{args.id}";
                fetch $a: id, name, content, cache-path, mime-type, file-size, source-uri, created-at;'''
                result = list(tx.query.fetch(query))

                if not result:
                    print(json.dumps({"success": False, "error": "Artifact not found"}))
                    return

                # Get linked entity
                entity_query = f'''match
                    $a isa artifact, has id "{args.id}";
                    (artifact: $a, referent: $e) isa representation;
                fetch $e: id, name;'''
                try:
                    entity_result = list(tx.query.fetch(entity_query))
                except Exception:
                    entity_result = []

    art = result[0]["a"]

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
        ent = entity_result[0]["e"]
        output["linked_entity"] = {
            "id": get_attr(ent, "id"),
            "name": get_attr(ent, "name"),
        }

    print(json.dumps(output, indent=2))


def cmd_show_component(args):
    """Show component details."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                comp_query = f'''match $c isa techrecon-component, has id "{args.id}";
                fetch $c: id, name, description, techrecon-component-type,
                    techrecon-component-role, techrecon-file-path;'''
                comp_result = list(tx.query.fetch(comp_query))

                if not comp_result:
                    print(json.dumps({"success": False, "error": "Component not found"}))
                    return

                # Get parent system
                sys_query = f'''match
                    $c isa techrecon-component, has id "{args.id}";
                    (system: $s, component: $c) isa techrecon-has-component;
                fetch $s: id, name;'''
                sys_result = list(tx.query.fetch(sys_query))

                # Get concepts
                con_query = f'''match
                    $c isa techrecon-component, has id "{args.id}";
                    (component: $c, concept: $con) isa techrecon-uses-concept;
                fetch $con: id, name, techrecon-concept-category;'''
                con_result = list(tx.query.fetch(con_query))

                # Get notes
                notes_query = f'''match
                    $c isa techrecon-component, has id "{args.id}";
                    (note: $n, subject: $c) isa aboutness;
                fetch $n: id, name, content;'''
                notes_result = list(tx.query.fetch(notes_query))

    c = comp_result[0]["c"]
    output = {
        "success": True,
        "component": {
            "id": get_attr(c, "id"),
            "name": get_attr(c, "name"),
            "description": get_attr(c, "description"),
            "type": get_attr(c, "techrecon-component-type"),
            "role": get_attr(c, "techrecon-component-role"),
            "file_path": get_attr(c, "techrecon-file-path"),
        },
        "system": {
            "id": get_attr(sys_result[0]["s"], "id"),
            "name": get_attr(sys_result[0]["s"], "name"),
        } if sys_result else None,
        "concepts": [{
            "id": get_attr(r["con"], "id"),
            "name": get_attr(r["con"], "name"),
            "category": get_attr(r["con"], "techrecon-concept-category"),
        } for r in con_result],
        "notes": [{
            "id": get_attr(n["n"], "id"),
            "name": get_attr(n["n"], "name"),
            "content": get_attr(n["n"], "content"),
        } for n in notes_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_concept(args):
    """Show concept details."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                con_query = f'''match $c isa techrecon-concept, has id "{args.id}";
                fetch $c: id, name, description, techrecon-concept-category;'''
                con_result = list(tx.query.fetch(con_query))

                if not con_result:
                    print(json.dumps({"success": False, "error": "Concept not found"}))
                    return

                # Get components using this concept
                comp_query = f'''match
                    $con isa techrecon-concept, has id "{args.id}";
                    (component: $c, concept: $con) isa techrecon-uses-concept;
                fetch $c: id, name;'''
                comp_result = list(tx.query.fetch(comp_query))

                # Get notes
                notes_query = f'''match
                    $con isa techrecon-concept, has id "{args.id}";
                    (note: $n, subject: $con) isa aboutness;
                fetch $n: id, name, content;'''
                notes_result = list(tx.query.fetch(notes_query))

    c = con_result[0]["c"]
    output = {
        "success": True,
        "concept": {
            "id": get_attr(c, "id"),
            "name": get_attr(c, "name"),
            "description": get_attr(c, "description"),
            "category": get_attr(c, "techrecon-concept-category"),
        },
        "used_by_components": [{
            "id": get_attr(r["c"], "id"),
            "name": get_attr(r["c"], "name"),
        } for r in comp_result],
        "notes": [{
            "id": get_attr(n["n"], "id"),
            "name": get_attr(n["n"], "name"),
            "content": get_attr(n["n"], "content"),
        } for n in notes_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_data_model(args):
    """Show data model details."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                model_query = f'''match $m isa techrecon-data-model, has id "{args.id}";
                fetch $m: id, name, description, techrecon-model-format, techrecon-doc-url;'''
                model_result = list(tx.query.fetch(model_query))

                if not model_result:
                    print(json.dumps({"success": False, "error": "Data model not found"}))
                    return

                # Get systems using this model
                sys_query = f'''match
                    $m isa techrecon-data-model, has id "{args.id}";
                    (system: $s, data-model: $m) isa techrecon-has-data-model;
                fetch $s: id, name;'''
                sys_result = list(tx.query.fetch(sys_query))

                # Get notes
                notes_query = f'''match
                    $m isa techrecon-data-model, has id "{args.id}";
                    (note: $n, subject: $m) isa aboutness;
                fetch $n: id, name, content;'''
                notes_result = list(tx.query.fetch(notes_query))

    m = model_result[0]["m"]
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
            "id": get_attr(s["s"], "id"),
            "name": get_attr(s["s"], "name"),
        } for s in sys_result],
        "notes": [{
            "id": get_attr(n["n"], "id"),
            "name": get_attr(n["n"], "name"),
            "content": get_attr(n["n"], "content"),
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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to subject
            with session.transaction(TransactionType.WRITE) as tx:
                about_query = f'''match
                    $n isa note, has id "{note_id}";
                    $s isa entity, has id "{args.about}";
                insert (note: $n, subject: $s) isa aboutness;'''
                tx.query.insert(about_query)
                tx.commit()

            # Add to investigation
            if args.investigation:
                add_to_collection(session, note_id, args.investigation)

            apply_tags(session, note_id, "note", args.tags)

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
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to source artifact via fragmentation
            if args.source:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(f'''match
                        $a isa artifact, has id "{args.source}";
                        $f isa fragment, has id "{frag_id}";
                    insert (whole: $a, part: $f) isa fragmentation;''')
                    tx.commit()

            # Tag fragment with the subject entity's ID for traceability
            if args.about:
                apply_tags(session, frag_id, "fragment", [f"about:{args.about}"])

            if args.investigation:
                add_to_collection(session, frag_id, args.investigation)

            apply_tags(session, frag_id, "fragment", args.tags)

    print(json.dumps({
        "success": True,
        "fragment_id": frag_id,
        "type": args.type,
        "source": args.source,
        "about": args.about,
    }))


# =============================================================================
# TAGGING
# =============================================================================


def cmd_tag(args):
    """Tag an entity."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            apply_tags(session, args.entity, "entity", [args.tag])

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

    entities = []
    for r in results:
        entities.append({
            "id": get_attr(r["e"], "id"),
            "name": get_attr(r["e"], "name"),
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
                   choices=["architecture", "design-pattern", "integration", "comparison", "data-model", "assessment", "general"],
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
    p.add_argument("--about", help="Entity ID this fragment is about")
    p.add_argument("--language", help="Programming language (for code-snippet)")
    p.add_argument("--format", choices=["JSON-Schema", "RDF-OWL", "TypeDB", "SQL", "Protobuf", "GraphQL", "custom"],
                   help="Schema format (for schema-excerpt)")
    p.add_argument("--investigation", help="Investigation ID")
    p.add_argument("--tags", nargs="+", help="Tags")
    p.add_argument("--id", help="Specific ID")

    # --- Tagging ---

    p = subparsers.add_parser("tag", help="Tag an entity")
    p.add_argument("--entity", required=True, help="Entity ID")
    p.add_argument("--tag", required=True, help="Tag name")

    p = subparsers.add_parser("search-tag", help="Search by tag")
    p.add_argument("--tag", required=True, help="Tag to search for")

    # --- Cache ---

    subparsers.add_parser("cache-stats", help="Show cache statistics")

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
        "update-investigation": cmd_update_investigation,
        # Entity creation
        "add-system": cmd_add_system,
        "add-component": cmd_add_component,
        "add-concept": cmd_add_concept,
        "add-data-model": cmd_add_data_model,
        # Ingestion
        "ingest-repo": cmd_ingest_repo,
        "ingest-doc": cmd_ingest_doc,
        "ingest-source": cmd_ingest_source,
        "ingest-schema": cmd_ingest_schema,
        "ingest-model-card": cmd_ingest_model_card,
        # Linking
        "link-component": cmd_link_component,
        "link-concept": cmd_link_concept,
        "link-data-model": cmd_link_data_model,
        "link-dependency": cmd_link_dependency,
        # Queries
        "list-systems": cmd_list_systems,
        "show-system": cmd_show_system,
        "show-architecture": cmd_show_architecture,
        "list-artifacts": cmd_list_artifacts,
        "show-artifact": cmd_show_artifact,
        "show-component": cmd_show_component,
        "show-concept": cmd_show_concept,
        "show-data-model": cmd_show_data_model,
        # Notes and fragments
        "add-note": cmd_add_note,
        "add-fragment": cmd_add_fragment,
        # Tagging
        "tag": cmd_tag,
        "search-tag": cmd_search_tag,
        # Cache
        "cache-stats": cmd_cache_stats,
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
