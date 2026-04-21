#!/usr/bin/env python3
"""
Bioskills Index CLI - Permanent, updatable EDAM-annotated index of bioskills.

A bioskill is any implementation layer giving AI agents access to biological
tools: SKILL.md-pattern skills, MCP servers, Nextflow workflows, Python wrappers.

Skill types are grounded in the EDAM ontology (edamontology.org). Import EDAM
Operation and Topic terms first, then annotate bioskills with them. TypeDB
inference rules transitively propagate annotations up the hierarchy.

Usage:
    python bioskills_index.py <command> [options]

Commands (ontology):
    import-edam      Import EDAM Operation/Topic terms from TSV into TypeDB
    add-operation    Add a custom extension operation (subtypes an EDAM term)
    add-topic        Add a custom extension topic
    show-operation   Show an operation term + subtypes + implementing skills
    list-operations  Browse the bio-operation hierarchy

Commands (index):
    create-index        Create a new bioskill-index collection
    list-indices        List all bioskill-index collections
    add-skill           Add a bioskill entry with optional EDAM annotations
    annotate-skill      Add EDAM op/topic/data I/O and computational profile to a skill
    show-skill          Show skill details (annotations, snippets, notes)
    list-skills         List skills with optional filters (op, topic, cluster, type)
    add-snippet         Add a code snippet to a bioskill
    generate-pseudocode Generate plain-English pseudocode for a skill via Claude

Commands (embedding + search):
    embed-and-project  Batch embed skills, project to UMAP, run HDBSCAN
    search             Cosine similarity search across embedded skills
    compose            Task description -> ordered skill playlist

Commands (discovery):
    update           Discover new skills from configured sources, re-embed

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    TYPEDB_USERNAME   TypeDB username (default: admin)
    TYPEDB_PASSWORD   TypeDB password (default: password)
    VOYAGE_API_KEY    Voyage AI API key (required for embed-and-project, search)
    ALHAZEN_CACHE_DIR Cache directory (default: ~/.alhazen/cache)
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import urllib.request

# ---------------------------------------------------------------------------
# Local helpers (self-contained for standalone deployment)
# ---------------------------------------------------------------------------
_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SKILL_DIR, "..", ".."))
sys.path.insert(0, _PROJECT_ROOT)

try:
    from src.skillful_alhazen.utils.skill_helpers import escape_string, generate_id, get_timestamp
    _HELPERS_FROM_PROJECT = True
except ImportError:
    _HELPERS_FROM_PROJECT = False
    sys.path.insert(0, _SKILL_DIR)
    from _helpers import escape_string, generate_id, get_timestamp

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------
try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print("Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
          file=sys.stderr)

try:
    import voyageai
    VOYAGE_AVAILABLE = True
except ImportError:
    VOYAGE_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from umap import UMAP
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False

try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = os.getenv("TYPEDB_PORT", "1729")
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

EMBEDDINGS_CACHE_PATH = os.path.expanduser(
    os.path.join(os.getenv("ALHAZEN_CACHE_DIR", "~/.alhazen/cache"), "json", "bioskills_embeddings.json")
)

# ---------------------------------------------------------------------------
# TypeDB driver
# ---------------------------------------------------------------------------

def get_driver():
    """Get a TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


# ---------------------------------------------------------------------------
# Embedding cache
# ---------------------------------------------------------------------------

def load_embeddings_cache() -> dict:
    if os.path.exists(EMBEDDINGS_CACHE_PATH):
        with open(EMBEDDINGS_CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_embeddings_cache(cache: dict):
    os.makedirs(os.path.dirname(EMBEDDINGS_CACHE_PATH), exist_ok=True)
    with open(EMBEDDINGS_CACHE_PATH, "w") as f:
        json.dump(cache, f)


# ---------------------------------------------------------------------------
# EDAM TRANSITIVE TRAVERSAL (replaces TypeDB inference rules in 3.x)
# ---------------------------------------------------------------------------

def _get_operation_subtypes(edam_id: str, driver=None) -> list[str]:
    """BFS over bio-subtype to get all TypeDB IDs of operations that are
    subtypes (direct or indirect) of the operation with the given edam-id.
    Returns a list of internal TypeDB `id` values (not edam-ids)."""
    if driver is None:
        driver = get_driver()
    eid = escape_string(edam_id)
    visited_ids: set[str] = set()
    frontier: list[str] = []

    # Find root operation by edam-id
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = f'match $op isa bio-operation, has edam-id "{eid}"; fetch {{ "id": $op.id }};'
        results = list(tx.query(q).resolve())
        if not results:
            return []
        root_id = results[0].get("id", "")
        if not root_id:
            return []
        visited_ids.add(root_id)
        frontier.append(root_id)

    # BFS - expand children
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        while frontier:
            next_frontier = []
            for parent_id in frontier:
                pid = escape_string(parent_id)
                q = f'''
                    match
                        $parent isa bio-operation, has id "{pid}";
                        $child isa bio-operation;
                        (bio-child: $child, bio-parent: $parent) isa bio-subtype;
                    fetch {{ "id": $child.id }};
                '''
                children = list(tx.query(q).resolve())
                for c in children:
                    cid = c.get("id", "")
                    if cid and cid not in visited_ids:
                        visited_ids.add(cid)
                        next_frontier.append(cid)
            frontier = next_frontier

    return list(visited_ids)


def _get_topic_subtypes(edam_id: str, driver=None) -> list[str]:
    """BFS over bio-subtype for bio-topic terms. Returns TypeDB `id` values."""
    if driver is None:
        driver = get_driver()
    eid = escape_string(edam_id)
    visited_ids: set[str] = set()
    frontier: list[str] = []

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = f'match $t isa bio-topic, has edam-id "{eid}"; fetch {{ "id": $t.id }};'
        results = list(tx.query(q).resolve())
        if not results:
            return []
        root_id = results[0].get("id", "")
        if not root_id:
            return []
        visited_ids.add(root_id)
        frontier.append(root_id)

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        while frontier:
            next_frontier = []
            for parent_id in frontier:
                pid = escape_string(parent_id)
                q = f'''
                    match
                        $parent isa bio-topic, has id "{pid}";
                        $child isa bio-topic;
                        (bio-child: $child, bio-parent: $parent) isa bio-subtype;
                    fetch {{ "id": $child.id }};
                '''
                children = list(tx.query(q).resolve())
                for c in children:
                    cid = c.get("id", "")
                    if cid and cid not in visited_ids:
                        visited_ids.add(cid)
                        next_frontier.append(cid)
            frontier = next_frontier

    return list(visited_ids)


# ---------------------------------------------------------------------------
# EDAM IMPORT
# ---------------------------------------------------------------------------

EDAM_TSV_URL = "https://edamontology.org/EDAM.tsv"


def cmd_import_edam(args):
    """Download EDAM TSV and import operation/topic terms into TypeDB."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    namespace = args.namespace  # "operation", "topic", "data", or "format"
    entity_type_map = {
        "operation": "bio-operation",
        "topic": "bio-topic",
        "data": "bio-data",
        "format": "bio-data",  # EDAM format shares bio-data entity for now
    }
    entity_type = entity_type_map.get(namespace, "bio-operation")

    # Download TSV
    if args.tsv:
        with open(args.tsv, newline="", encoding="utf-8") as f:
            content = f.read()
    else:
        print(f"Downloading EDAM TSV from {EDAM_TSV_URL}...", file=sys.stderr)
        with urllib.request.urlopen(EDAM_TSV_URL) as resp:
            content = resp.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    rows = list(reader)

    # EDAM TSV columns (from BioPortal export):
    # "Class ID"  -> full URI, e.g. http://edamontology.org/operation_2403
    # "Preferred Label" -> term name
    # "Synonyms"  -> pipe-separated exact synonyms
    # "Definitions" -> definition text
    # "Obsolete"  -> "TRUE" or "FALSE"
    # "Parents"   -> pipe-separated parent URIs

    # Filter to requested namespace by matching URI pattern
    uri_pattern = f"/{namespace}_"
    target_rows = []
    for row in rows:
        uri = row.get("Class ID", "").strip()
        if uri_pattern in uri:
            target_rows.append(row)

    # Filter deprecated unless --include-deprecated
    if not args.include_deprecated:
        target_rows = [r for r in target_rows if r.get("Obsolete", "").strip().upper() != "TRUE"]

    print(f"Importing {len(target_rows)} {namespace} terms...", file=sys.stderr)

    driver = get_driver()
    inserted = 0
    skipped = 0
    relations_inserted = 0

    # Insert entities in batches of 50
    BATCH = 50
    for i in range(0, len(target_rows), BATCH):
        batch = target_rows[i:i + BATCH]
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            for row in batch:
                uri = (row.get("Class ID") or "").strip()
                edam_id = uri.split("/")[-1] if "/" in uri else ""
                name = (row.get("Preferred Label") or "").strip()
                defn = escape_string((row.get("Definitions") or "").strip())
                edam_uri = uri
                synonyms = escape_string((row.get("Synonyms") or "").strip().split("|")[0].strip())

                if not edam_id or not name:
                    skipped += 1
                    continue

                prefix_map = {"operation": "bop", "topic": "btp", "data": "bdt", "format": "bdt"}
                term_id = generate_id(prefix_map.get(namespace, "bop"))
                ts = get_timestamp()
                esc_name = escape_string(name)
                esc_edam_id = escape_string(edam_id)
                esc_uri = escape_string(edam_uri)

                q = f'''
                    insert ${entity_type.replace("-", "_")} isa {entity_type},
                        has id "{term_id}",
                        has name "{esc_name}",
                        has edam-id "{esc_edam_id}",
                        has edam-uri "{esc_uri}",
                        has edam-source "edam",
                        has edam-namespace "{namespace}",
                        has created-at {ts}
                '''
                if defn:
                    q += f', has edam-definition "{defn}"'
                if synonyms:
                    q += f', has edam-exact-synonym "{synonyms}"'
                q += ";"
                tx.query(q).resolve()
                inserted += 1

            tx.commit()
        print(f"  Inserted batch {i // BATCH + 1} ({min(i + BATCH, len(target_rows))}/{len(target_rows)})",
              file=sys.stderr)

    # Insert bio-subtype hierarchy relations
    # Parse "Parents" column (pipe-separated URIs -> extract edam_id from URI)
    print("Inserting hierarchy relations...", file=sys.stderr)
    hierarchy_pairs = []
    for row in target_rows:
        uri = (row.get("Class ID") or "").strip()
        edam_id = uri.split("/")[-1] if "/" in uri else ""
        parents_raw = (row.get("Parents") or "").strip()
        if not parents_raw or not edam_id:
            continue
        for parent_uri in parents_raw.split("|"):
            parent_uri = parent_uri.strip()
            parent_edam_id = parent_uri.split("/")[-1] if "/" in parent_uri else ""
            if parent_edam_id and parent_edam_id != edam_id and f"{namespace}_" in parent_edam_id:
                hierarchy_pairs.append((edam_id, parent_edam_id))

    for i in range(0, len(hierarchy_pairs), BATCH):
        batch = hierarchy_pairs[i:i + BATCH]
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            batch_relations = 0
            for child_edam_id, parent_edam_id in batch:
                ce = escape_string(child_edam_id)
                pe = escape_string(parent_edam_id)
                q = f'''
                    match
                        $child isa {entity_type}, has edam-id "{ce}";
                        $parent isa {entity_type}, has edam-id "{pe}";
                    insert
                        (bio-child: $child, bio-parent: $parent) isa bio-subtype;
                '''
                try:
                    tx.query(q).resolve()
                    batch_relations += 1
                except Exception:
                    pass  # parent may not exist (cross-namespace) — skip
            tx.commit()
            relations_inserted += batch_relations

    print(json.dumps({
        "success": True,
        "namespace": namespace,
        "inserted": inserted,
        "skipped": skipped,
        "hierarchy_relations": relations_inserted,
    }))


# ---------------------------------------------------------------------------
# CUSTOM EXTENSION TERMS
# ---------------------------------------------------------------------------

def cmd_add_operation(args):
    """Add a custom extension bio-operation that subtypes an existing term."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    term_id = generate_id("bop")
    ts = get_timestamp()
    name = escape_string(args.name)
    defn = escape_string(args.definition or "")
    source = escape_string(args.source or "bioskills-index")

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        q = f'''
            insert $op isa bio-operation,
                has id "{term_id}",
                has bsi-term-id "{term_id}",
                has name "{name}",
                has edam-source "{source}",
                has edam-namespace "operation",
                has created-at {ts}
        '''
        if defn:
            q += f', has edam-definition "{defn}"'
        q += ";"
        tx.query(q).resolve()

        # Link to parent term
        if args.parent_edam:
            pe = escape_string(args.parent_edam)
            pq = f'''
                match
                    $child isa bio-operation, has id "{term_id}";
                    $parent isa bio-operation, has edam-id "{pe}";
                insert
                    (bio-child: $child, bio-parent: $parent) isa bio-subtype;
            '''
            tx.query(pq).resolve()
        elif args.parent_bsi:
            pb = escape_string(args.parent_bsi)
            pq = f'''
                match
                    $child isa bio-operation, has id "{term_id}";
                    $parent isa bio-operation, has bsi-term-id "{pb}";
                insert
                    (bio-child: $child, bio-parent: $parent) isa bio-subtype;
            '''
            tx.query(pq).resolve()

        tx.commit()

    print(json.dumps({"success": True, "id": term_id, "name": args.name, "type": "bio-operation"}))


def cmd_add_topic(args):
    """Add a custom extension bio-topic that subtypes an existing term."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    term_id = generate_id("btp")
    ts = get_timestamp()
    name = escape_string(args.name)
    defn = escape_string(args.definition or "")
    source = escape_string(args.source or "bioskills-index")

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        q = f'''
            insert $t isa bio-topic,
                has id "{term_id}",
                has bsi-term-id "{term_id}",
                has name "{name}",
                has edam-source "{source}",
                has edam-namespace "topic",
                has created-at {ts}
        '''
        if defn:
            q += f', has edam-definition "{defn}"'
        q += ";"
        tx.query(q).resolve()

        if args.parent_edam:
            pe = escape_string(args.parent_edam)
            pq = f'''
                match
                    $child isa bio-topic, has id "{term_id}";
                    $parent isa bio-topic, has edam-id "{pe}";
                insert
                    (bio-child: $child, bio-parent: $parent) isa bio-subtype;
            '''
            tx.query(pq).resolve()
        elif args.parent_bsi:
            pb = escape_string(args.parent_bsi)
            pq = f'''
                match
                    $child isa bio-topic, has id "{term_id}";
                    $parent isa bio-topic, has bsi-term-id "{pb}";
                insert
                    (bio-child: $child, bio-parent: $parent) isa bio-subtype;
            '''
            tx.query(pq).resolve()

        tx.commit()

    print(json.dumps({"success": True, "id": term_id, "name": args.name, "type": "bio-topic"}))


def cmd_show_operation(args):
    """Show an operation term with its children and implementing skills."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        # Find the term
        if args.edam_id:
            eid = escape_string(args.edam_id)
            match_clause = f'$op isa bio-operation, has edam-id "{eid}";'
        elif args.bsi_term_id:
            bid = escape_string(args.bsi_term_id)
            match_clause = f'$op isa bio-operation, has bsi-term-id "{bid}";'
        else:
            tid = escape_string(args.id)
            match_clause = f'$op isa bio-operation, has id "{tid}";'

        q = f'''
            match {match_clause}
            fetch {{
                "id": $op.id,
                "name": $op.name,
                "edam_id": $op.edam-id,
                "edam_source": $op.edam-source,
                "definition": $op.edam-definition
            }};
        '''
        results = list(tx.query(q).resolve())
        if not results:
            print(json.dumps({"success": False, "error": "operation not found"}))
            return
        op = results[0]

        # Count direct implementing skills
        op_id = escape_string(op.get("id", ""))
        count_q = f'''
            match
                $s isa bioskill;
                $op isa bio-operation, has id "{op_id}";
                (bsi-skill: $s, bsi-bio-op: $op) isa bsi-implements;
            fetch {{ "id": $s.id }};
        '''
        skill_count = len(list(tx.query(count_q).resolve()))

    print(json.dumps({
        "success": True,
        "operation": op,
        "implementing_skill_count": skill_count,
    }))


def cmd_list_operations(args):
    """List bio-operation terms, optionally filtered by parent or source."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        filters = ""
        if args.source:
            src = escape_string(args.source)
            filters += f'$op has edam-source "{src}"; '
        if args.parent:
            pe = escape_string(args.parent)
            filters += f'$parent isa bio-operation, has edam-id "{pe}"; (bio-child: $op, bio-parent: $parent) isa bio-subtype; '

        q = f'''
            match
                $op isa bio-operation;
                {filters}
            fetch {{
                "id": $op.id,
                "name": $op.name,
                "edam_id": $op.edam-id,
                "edam_source": $op.edam-source
            }};
        '''
        results = list(tx.query(q).resolve())

    limit = args.limit or 100
    print(json.dumps({
        "success": True,
        "count": len(results),
        "operations": results[:limit],
    }))


# ---------------------------------------------------------------------------
# INDEX COMMANDS
# ---------------------------------------------------------------------------

def cmd_create_index(args):
    """Create a new bioskill-index collection."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    idx_id = generate_id("bsi")
    ts = get_timestamp()
    name = escape_string(args.name)
    desc = escape_string(args.description or "")

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        q = f'''
            insert $idx isa bioskill-index,
                has id "{idx_id}",
                has name "{name}",
                has bsi-index-version 1,
                has bsi-skill-count 0,
                has bsi-status "active",
                has created-at {ts}
        '''
        if desc:
            q += f', has description "{desc}"'
        q += ";"
        tx.query(q).resolve()
        tx.commit()

    print(json.dumps({"success": True, "id": idx_id, "name": args.name}))


def cmd_list_indices(args):
    """List all bioskill-index collections."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = '''
            match $idx isa bioskill-index;
            fetch {
                "id": $idx.id,
                "name": $idx.name,
                "version": $idx.bsi-index-version,
                "skill_count": $idx.bsi-skill-count,
                "status": $idx.bsi-status,
                "created_at": $idx.created-at
            };
        '''
        results = list(tx.query(q).resolve())

    print(json.dumps({"success": True, "count": len(results), "indices": results}))


# ---------------------------------------------------------------------------
# SKILL COMMANDS
# ---------------------------------------------------------------------------

def cmd_add_skill(args):
    """Add a bioskill entry with optional EDAM operation/topic annotations."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    skill_id = generate_id("bsk")
    ts = get_timestamp()
    name = escape_string(args.name)
    desc = escape_string(args.description or "")
    bsi_type = escape_string(args.type or "skill")
    source_repo = escape_string(args.source_repo or "")
    source_file = escape_string(args.source_file or "")
    github_url = escape_string(args.github_url or "")
    tool_access = escape_string(args.tool_access or "")

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        q = f'''
            insert $s isa bioskill,
                has id "{skill_id}",
                has name "{name}",
                has bsi-type "{bsi_type}",
                has bsi-status "active",
                has created-at {ts}
        '''
        if desc:
            q += f', has description "{desc}"'
        if source_repo:
            q += f', has bsi-source-repo "{source_repo}"'
        if source_file:
            q += f', has bsi-source-file "{source_file}"'
        if github_url:
            q += f', has bsi-github-url "{github_url}"'
        if tool_access:
            q += f', has bsi-tool-access "{tool_access}"'
        q += ";"
        tx.query(q).resolve()

        # Link to index
        if args.index:
            idx = escape_string(args.index)
            lq = f'''
                match
                    $s isa bioskill, has id "{skill_id}";
                    $idx isa bioskill-index, has id "{idx}";
                insert
                    (bsi-skill: $s, bsi-index: $idx) isa bsi-indexed-in;
            '''
            tx.query(lq).resolve()

        tx.commit()

    # Add EDAM annotations in a separate transaction
    ops = [o.strip() for o in (args.ops or "").split(",") if o.strip()]
    topics = [t.strip() for t in (args.topics or "").split(",") if t.strip()]
    if ops or topics:
        _annotate_skill(skill_id, ops, topics)

    print(json.dumps({"success": True, "id": skill_id, "name": args.name}))


def _annotate_skill(skill_id: str, ops: list, topics: list,
                    inputs: list = None, outputs: list = None):
    """Add EDAM operation, topic, and data I/O annotations to a bioskill."""
    driver = get_driver()
    sid = escape_string(skill_id)
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        for op in ops:
            op_esc = escape_string(op)
            for match_field in ["edam-id", "id", "bsi-term-id"]:
                q = f'''
                    match
                        $s isa bioskill, has id "{sid}";
                        $op isa bio-operation, has {match_field} "{op_esc}";
                    insert
                        (bsi-skill: $s, bsi-bio-op: $op) isa bsi-implements;
                '''
                try:
                    tx.query(q).resolve()
                    break
                except Exception:
                    continue

        for topic in topics:
            t_esc = escape_string(topic)
            for match_field in ["edam-id", "id", "bsi-term-id"]:
                q = f'''
                    match
                        $s isa bioskill, has id "{sid}";
                        $t isa bio-topic, has {match_field} "{t_esc}";
                    insert
                        (bsi-skill: $s, bsi-bio-topic: $t) isa bsi-covers-topic;
                '''
                try:
                    tx.query(q).resolve()
                    break
                except Exception:
                    continue

        for data_id in (inputs or []):
            d_esc = escape_string(data_id)
            for match_field in ["edam-id", "id", "bsi-data-id"]:
                q = f'''
                    match
                        $s isa bioskill, has id "{sid}";
                        $d isa bio-data, has {match_field} "{d_esc}";
                    insert
                        (bsi-skill: $s, bsi-bio-data: $d) isa bsi-accepts-input;
                '''
                try:
                    tx.query(q).resolve()
                    break
                except Exception:
                    continue

        for data_id in (outputs or []):
            d_esc = escape_string(data_id)
            for match_field in ["edam-id", "id", "bsi-data-id"]:
                q = f'''
                    match
                        $s isa bioskill, has id "{sid}";
                        $d isa bio-data, has {match_field} "{d_esc}";
                    insert
                        (bsi-skill: $s, bsi-bio-data: $d) isa bsi-produces-output;
                '''
                try:
                    tx.query(q).resolve()
                    break
                except Exception:
                    continue

        tx.commit()


def _set_skill_profile(skill_id: str, requires_gpu: bool | None,
                       runtime_class: str | None, memory_class: str | None,
                       language: str | None):
    """Set computational profile attributes on a bioskill."""
    driver = get_driver()
    sid = escape_string(skill_id)
    attrs = {}
    if requires_gpu is not None:
        attrs["bsi-requires-gpu"] = "true" if requires_gpu else "false"
    if runtime_class:
        attrs["bsi-runtime-class"] = f'"{escape_string(runtime_class)}"'
    if memory_class:
        attrs["bsi-memory-class"] = f'"{escape_string(memory_class)}"'
    if language:
        attrs["bsi-language"] = f'"{escape_string(language)}"'

    if not attrs:
        return

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        for attr, val in attrs.items():
            # Delete old value if present
            del_q = f'match $s isa bioskill, has id "{sid}", has {attr} $v; delete has $v of $s;'
            try:
                tx.query(del_q).resolve()
            except Exception:
                pass
            ins_q = f'match $s isa bioskill, has id "{sid}"; insert $s has {attr} {val};'
            tx.query(ins_q).resolve()
        tx.commit()


def cmd_annotate_skill(args):
    """Add EDAM operation/topic/data I/O annotations and computational profile to a skill."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    ops = [o.strip() for o in (args.op or "").split(",") if o.strip()]
    topics = [t.strip() for t in (args.topic or "").split(",") if t.strip()]
    inputs = [i.strip() for i in (args.input or "").split(",") if i.strip()]
    outputs = [o.strip() for o in (args.output or "").split(",") if o.strip()]
    _annotate_skill(args.skill, ops, topics, inputs, outputs)

    # Handle computational profile
    requires_gpu = None
    if args.gpu:
        requires_gpu = True
    elif args.no_gpu:
        requires_gpu = False
    _set_skill_profile(
        args.skill,
        requires_gpu=requires_gpu,
        runtime_class=getattr(args, "runtime_class", None),
        memory_class=getattr(args, "memory_class", None),
        language=getattr(args, "language", None),
    )

    print(json.dumps({
        "success": True,
        "skill_id": args.skill,
        "ops_added": len(ops),
        "topics_added": len(topics),
        "inputs_added": len(inputs),
        "outputs_added": len(outputs),
    }))


def cmd_show_skill(args):
    """Show a bioskill with its EDAM annotations, snippets, and note count."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    sid = escape_string(args.id)
    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = f'''
            match $s isa bioskill, has id "{sid}";
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "description": $s.description,
                "type": $s.bsi-type,
                "status": $s.bsi-status,
                "source_repo": $s.bsi-source-repo,
                "source_file": $s.bsi-source-file,
                "github_url": $s.bsi-github-url,
                "tool_access": $s.bsi-tool-access,
                "umap_x": $s.bsi-umap-x,
                "umap_y": $s.bsi-umap-y,
                "cluster_id": $s.bsi-cluster-id,
                "cluster_label": $s.bsi-cluster-label,
                "requires_gpu": $s.bsi-requires-gpu,
                "runtime_class": $s.bsi-runtime-class,
                "memory_class": $s.bsi-memory-class,
                "language": $s.bsi-language
            }};
        '''
        skills = list(tx.query(q).resolve())
        if not skills:
            print(json.dumps({"success": False, "error": "skill not found"}))
            return
        skill = skills[0]

        # Fetch direct EDAM operation annotations
        ops_q = f'''
            match
                $s isa bioskill, has id "{sid}";
                $op isa bio-operation;
                (bsi-skill: $s, bsi-bio-op: $op) isa bsi-implements;
            fetch {{ "op_name": $op.name, "op_edam_id": $op.edam-id, "op_source": $op.edam-source }};
        '''
        ops = list(tx.query(ops_q).resolve())

        # Fetch topic annotations
        topics_q = f'''
            match
                $s isa bioskill, has id "{sid}";
                $t isa bio-topic;
                (bsi-skill: $s, bsi-bio-topic: $t) isa bsi-covers-topic;
            fetch {{ "topic_name": $t.name, "topic_edam_id": $t.edam-id }};
        '''
        topics = list(tx.query(topics_q).resolve())

        # Fetch input data types
        inputs_q = f'''
            match
                $s isa bioskill, has id "{sid}";
                $d isa bio-data;
                (bsi-skill: $s, bsi-bio-data: $d) isa bsi-accepts-input;
            fetch {{ "data_name": $d.name, "data_edam_id": $d.edam-id }};
        '''
        inputs = list(tx.query(inputs_q).resolve())

        # Fetch output data types
        outputs_q = f'''
            match
                $s isa bioskill, has id "{sid}";
                $d isa bio-data;
                (bsi-skill: $s, bsi-bio-data: $d) isa bsi-produces-output;
            fetch {{ "data_name": $d.name, "data_edam_id": $d.edam-id }};
        '''
        outputs = list(tx.query(outputs_q).resolve())

        # Fetch snippets (content included for dashboard rendering)
        snip_q = f'''
            match
                $s isa bioskill, has id "{sid}";
                $snip isa bioskill-snippet;
                (bsi-parent-skill: $s, bsi-snippet: $snip) isa bsi-snippet-of;
            fetch {{ "snippet_id": $snip.id, "snippet_name": $snip.name, "snippet_content": $snip.content, "snippet_type": $snip.bsi-snippet-type, "snippet_lang": $snip.bsi-snippet-language }};
        '''
        snippets = list(tx.query(snip_q).resolve())

    print(json.dumps({
        "success": True,
        "skill": skill,
        "operations": ops,
        "topics": topics,
        "inputs": inputs,
        "outputs": outputs,
        "snippets": snippets,
    }))


def cmd_list_skills(args):
    """List bioskills with optional filters. EDAM op/topic filters use BFS traversal."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    driver = get_driver()

    # Collect op IDs via BFS transitive traversal (replaces TypeDB inference rules)
    op_type_ids: list[str] | None = None
    if args.op:
        op_type_ids = _get_operation_subtypes(args.op, driver)
        if not op_type_ids:
            # Try as a bsi-term-id
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                tid = escape_string(args.op)
                q = f'match $op isa bio-operation, has bsi-term-id "{tid}"; fetch {{ "id": $op.id }};'
                results = list(tx.query(q).resolve())
                if results:
                    op_type_ids = [results[0].get("id", "")]

    topic_type_ids: list[str] | None = None
    if args.topic:
        topic_type_ids = _get_topic_subtypes(args.topic, driver)

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        filters = ""
        if args.index:
            idx = escape_string(args.index)
            filters += f'$idx isa bioskill-index, has id "{idx}"; (bsi-skill: $s, bsi-index: $idx) isa bsi-indexed-in; '
        if args.type:
            t = escape_string(args.type)
            filters += f'$s has bsi-type "{t}"; '
        if args.cluster is not None:
            filters += f'$s has bsi-cluster-id {args.cluster}; '

        # If EDAM op filter: query once per op type ID (union via Python set)
        if op_type_ids is not None:
            all_skill_ids: set[str] = set()
            for op_id in op_type_ids:
                oid = escape_string(op_id)
                q = f'''
                    match
                        $s isa bioskill;
                        {filters}
                        $op isa bio-operation, has id "{oid}";
                        (bsi-skill: $s, bsi-bio-op: $op) isa bsi-implements;
                    fetch {{ "id": $s.id }};
                '''
                r = list(tx.query(q).resolve())
                all_skill_ids.update(r2.get("id", "") for r2 in r)

            if not all_skill_ids:
                limit = args.limit or 100
                print(json.dumps({"success": True, "count": 0, "op_subtypes_searched": len(op_type_ids), "skills": []}))
                return

            # Fetch details for matching skill IDs
            results = []
            for sid in list(all_skill_ids)[:args.limit or 100]:
                s_esc = escape_string(sid)
                q = f'''
                    match $s isa bioskill, has id "{s_esc}";
                    fetch {{
                        "id": $s.id, "name": $s.name, "type": $s.bsi-type,
                        "status": $s.bsi-status, "source_repo": $s.bsi-source-repo,
                        "cluster_label": $s.bsi-cluster-label,
                        "cluster_id": $s.bsi-cluster-id,
                        "umap_x": $s.bsi-umap-x, "umap_y": $s.bsi-umap-y
                    }};
                '''
                r = list(tx.query(q).resolve())
                if r:
                    results.append(r[0])

            limit = args.limit or 100
            print(json.dumps({
                "success": True,
                "count": len(all_skill_ids),
                "op_subtypes_searched": len(op_type_ids),
                "skills": results[:limit],
            }))
            return

        # Standard filter (no EDAM op traversal needed)
        if topic_type_ids is not None:
            topic_id_list = topic_type_ids[:50]  # safety limit
            topic_filter_parts = []
            for i, tid in enumerate(topic_id_list):
                t_esc = escape_string(tid)
                topic_filter_parts.append(f'$bt{i} isa bio-topic, has id "{t_esc}"; (bsi-skill: $s, bsi-bio-topic: $bt{i}) isa bsi-covers-topic;')
            filters += " OR ".join(topic_filter_parts)  # TypeDB OR not supported — use Python union instead

        q = f'''
            match
                $s isa bioskill;
                {filters}
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "type": $s.bsi-type,
                "status": $s.bsi-status,
                "source_repo": $s.bsi-source-repo,
                "cluster_label": $s.bsi-cluster-label,
                "cluster_id": $s.bsi-cluster-id,
                "umap_x": $s.bsi-umap-x, "umap_y": $s.bsi-umap-y
            }};
        '''
        results = list(tx.query(q).resolve())

    limit = args.limit or 100
    print(json.dumps({
        "success": True,
        "count": len(results),
        "skills": results[:limit],
    }))


def cmd_add_snippet(args):
    """Add a code snippet to a bioskill."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    snip_id = generate_id("bsn")
    ts = get_timestamp()
    skill_id = escape_string(args.skill)
    name = escape_string(args.name or snip_id)
    content = escape_string(args.content)
    snip_type = escape_string(args.type or "example")
    language = escape_string(args.language or "python")

    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        q = f'''
            insert $snip isa bioskill-snippet,
                has id "{snip_id}",
                has name "{name}",
                has content "{content}",
                has bsi-snippet-type "{snip_type}",
                has bsi-snippet-language "{language}",
                has created-at {ts};
        '''
        tx.query(q).resolve()

        lq = f'''
            match
                $s isa bioskill, has id "{skill_id}";
                $snip isa bioskill-snippet, has id "{snip_id}";
            insert
                (bsi-parent-skill: $s, bsi-snippet: $snip) isa bsi-snippet-of;
        '''
        tx.query(lq).resolve()
        tx.commit()

    print(json.dumps({"success": True, "id": snip_id, "skill_id": args.skill}))


# ---------------------------------------------------------------------------
# EMBEDDING + SEARCH COMMANDS (stubs — full impl requires VOYAGE_API_KEY)
# ---------------------------------------------------------------------------

def cmd_embed_and_project(args):
    """Batch embed all skills in an index, project to UMAP, cluster with HDBSCAN."""
    if not VOYAGE_AVAILABLE:
        print(json.dumps({"success": False, "error": "voyageai not installed. pip install voyageai"}))
        return
    if not UMAP_AVAILABLE:
        print(json.dumps({"success": False, "error": "umap-learn not installed. pip install umap-learn"}))
        return
    if not HDBSCAN_AVAILABLE:
        print(json.dumps({"success": False, "error": "hdbscan not installed. pip install hdbscan"}))
        return

    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        print(json.dumps({"success": False, "error": "VOYAGE_API_KEY not set. Get one at https://dash.voyageai.com/"}))
        return

    # 1. Fetch all skills from the index
    driver = get_driver()
    idx = escape_string(args.index)
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = f'''
            match
                $s isa bioskill;
                $idx isa bioskill-index, has id "{idx}";
                (bsi-skill: $s, bsi-index: $idx) isa bsi-indexed-in;
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "description": $s.description,
                "type": $s.bsi-type,
                "tool_access": $s.bsi-tool-access
            }};
        '''
        skills = list(tx.query(q).resolve())

    if not skills:
        print(json.dumps({"success": False, "error": "No skills found in this index"}))
        return

    # 2. Load embedding cache; determine which skills need re-embedding
    cache = load_embeddings_cache()
    texts = []
    ids_to_embed = []
    for skill in skills:
        sid = skill.get("id", "")
        name = skill.get("name", "")
        desc = skill.get("description", "") or ""
        skill_type = skill.get("type", "")
        tool = skill.get("tool_access", "") or ""
        embed_text = f"{name}: {desc}. Type: {skill_type}. Tool: {tool}"
        text_hash = hashlib.sha256(embed_text.encode()).hexdigest()[:16]
        cached = cache.get(sid, {})
        if not args.force and cached.get("hash") == text_hash:
            continue
        ids_to_embed.append((sid, embed_text, text_hash))

    print(f"Embedding {len(ids_to_embed)} skills (skipping {len(skills) - len(ids_to_embed)} unchanged)...",
          file=sys.stderr)

    if ids_to_embed:
        # 3. Batch embed with voyage-4-large
        client = voyageai.Client(api_key=api_key)
        BATCH_SIZE = 128
        for i in range(0, len(ids_to_embed), BATCH_SIZE):
            batch = ids_to_embed[i:i + BATCH_SIZE]
            batch_texts = [b[1] for b in batch]
            result = client.embed(batch_texts, model="voyage-large-2", input_type="document")
            for j, (sid, _, text_hash) in enumerate(batch):
                cache[sid] = {
                    "embedding": result.embeddings[j],
                    "hash": text_hash,
                }
            print(f"  Embedded batch {i // BATCH_SIZE + 1}", file=sys.stderr)
        save_embeddings_cache(cache)

    # 4. UMAP projection (uses all skills in cache that are in this index)
    skill_ids = [s.get("id", "") for s in skills]
    embeddings_matrix = [cache[sid]["embedding"] for sid in skill_ids if sid in cache]
    skill_ids_for_umap = [sid for sid in skill_ids if sid in cache]

    if len(embeddings_matrix) < 5:
        print(json.dumps({"success": False, "error": "Need at least 5 embedded skills for UMAP projection"}))
        return

    print("Running UMAP...", file=sys.stderr)
    reducer = UMAP(n_components=2, n_neighbors=min(15, len(embeddings_matrix) - 1),
                   min_dist=0.1, metric="cosine", random_state=42)
    coords = reducer.fit_transform(np.array(embeddings_matrix))

    # 5. HDBSCAN clustering
    print("Running HDBSCAN...", file=sys.stderr)
    min_cluster_size = max(3, len(skill_ids_for_umap) // 20)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=3)
    labels = clusterer.fit_predict(coords)

    # 6. Update cache with UMAP coords + cluster IDs
    for i, sid in enumerate(skill_ids_for_umap):
        cache[sid]["umap_x"] = float(coords[i][0])
        cache[sid]["umap_y"] = float(coords[i][1])
        cache[sid]["cluster_id"] = int(labels[i])
    save_embeddings_cache(cache)

    # 6b. Compute cluster labels from dominant EDAM topic per cluster
    driver = get_driver()
    cluster_labels: dict[int, str] = {}
    unique_clusters = sorted(set(int(l) for l in labels) - {-1})
    for cid in unique_clusters:
        member_ids = [skill_ids_for_umap[i] for i, l in enumerate(labels) if int(l) == cid]
        # Query dominant EDAM topic across all members
        topic_counts: dict[str, int] = {}
        for sid in member_ids:
            s_esc = escape_string(sid)
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                q = f'''
                    match
                        $s isa bioskill, has id "{s_esc}";
                        (bsi-skill: $s, bsi-bio-topic: $t) isa bsi-covers-topic;
                        $t has name $tn;
                    fetch {{ "topic": $tn }};
                '''
                try:
                    results = list(tx.query(q).resolve())
                    for r in results:
                        tn = r.get("topic", "")
                        if tn:
                            topic_counts[tn] = topic_counts.get(tn, 0) + 1
                except Exception:
                    pass
        if topic_counts:
            dominant = max(topic_counts, key=lambda k: topic_counts[k])
            cluster_labels[cid] = dominant
        else:
            cluster_labels[cid] = f"Cluster {cid}"
    for i, sid in enumerate(skill_ids_for_umap):
        cid = int(labels[i])
        cache[sid]["cluster_label"] = cluster_labels.get(cid, "")
    save_embeddings_cache(cache)

    # 7. Update TypeDB coords in batches of 50
    BATCH = 50
    updated = 0
    for i in range(0, len(skill_ids_for_umap), BATCH):
        batch_ids = skill_ids_for_umap[i:i + BATCH]
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            for sid in batch_ids:
                c = cache[sid]
                x, y, cid = c["umap_x"], c["umap_y"], c["cluster_id"]
                clabel = escape_string(c.get("cluster_label", ""))
                s_esc = escape_string(sid)
                # Delete old coords (TypeDB 3.x delete-has pattern)
                for attr in ["bsi-umap-x", "bsi-umap-y", "bsi-cluster-id", "bsi-cluster-label"]:
                    del_q = f'match $s isa bioskill, has id "{s_esc}", has {attr} $v; delete has $v of $s;'
                    try:
                        tx.query(del_q).resolve()
                    except Exception:
                        pass
                ins_q = f'''
                    match $s isa bioskill, has id "{s_esc}";
                    insert $s has bsi-umap-x {x}, has bsi-umap-y {y},
                               has bsi-cluster-id {cid}, has bsi-cluster-label "{clabel}";
                '''
                tx.query(ins_q).resolve()
                updated += 1
            tx.commit()

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    print(json.dumps({
        "success": True,
        "embedded": len(ids_to_embed),
        "projected": len(skill_ids_for_umap),
        "clusters": n_clusters,
        "updated_in_typedb": updated,
    }))


def cmd_search(args):
    """Cosine similarity search across embedded bioskills."""
    if not VOYAGE_AVAILABLE:
        print(json.dumps({"success": False, "error": "voyageai not installed"}))
        return

    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        print(json.dumps({"success": False, "error": "VOYAGE_API_KEY not set"}))
        return

    cache = load_embeddings_cache()
    if not cache:
        print(json.dumps({"success": False, "error": "No embeddings found. Run embed-and-project first."}))
        return

    # Embed the query
    client = voyageai.Client(api_key=api_key)
    result = client.embed([args.query], model="voyage-large-2", input_type="query")
    query_vec = np.array(result.embeddings[0])

    # Filter to skills in this index if specified
    skill_ids_in_scope = set(cache.keys())
    if args.index:
        driver = get_driver()
        idx = escape_string(args.index)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            q = f'''
                match
                    $s isa bioskill;
                    $idx isa bioskill-index, has id "{idx}";
                    (bsi-skill: $s, bsi-index: $idx) isa bsi-indexed-in;
                fetch {{ "id": $s.id }};
            '''
            results = list(tx.query(q).resolve())
        skill_ids_in_scope = {r.get("id", "") for r in results}

    # Compute cosine similarities
    scores = []
    for sid, entry in cache.items():
        if sid not in skill_ids_in_scope:
            continue
        emb = np.array(entry["embedding"])
        score = float(np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(emb) + 1e-10))
        scores.append((sid, score))

    scores.sort(key=lambda x: -x[1])
    top_k = args.top_k or 10

    # Fetch skill names from TypeDB
    driver = get_driver()
    top_ids = [s[0] for s in scores[:top_k]]
    skill_details = {}
    if top_ids:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for sid in top_ids:
                s_esc = escape_string(sid)
                q = f'''
                    match $s isa bioskill, has id "{s_esc}";
                    fetch {{ "id": $s.id, "name": $s.name, "type": $s.bsi-type, "source_repo": $s.bsi-source-repo }};
                '''
                r = list(tx.query(q).resolve())
                if r:
                    skill_details[sid] = r[0]

    ranked = []
    for sid, score in scores[:top_k]:
        entry = {"id": sid, "score": round(score, 4)}
        entry.update(skill_details.get(sid, {}))
        ranked.append(entry)

    print(json.dumps({"success": True, "query": args.query, "results": ranked}))


def cmd_compose(args):
    """Task description -> ordered skill playlist with EDAM coverage summary."""
    if not VOYAGE_AVAILABLE:
        print(json.dumps({"success": False, "error": "voyageai not installed"}))
        return

    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        print(json.dumps({"success": False, "error": "VOYAGE_API_KEY not set"}))
        return

    cache = load_embeddings_cache()
    if not cache:
        print(json.dumps({"success": False, "error": "No embeddings. Run embed-and-project first."}))
        return

    client = voyageai.Client(api_key=api_key)
    result = client.embed([args.task], model="voyage-large-2", input_type="query")
    query_vec = np.array(result.embeddings[0])

    # Score all skills
    skill_ids_in_scope = set(cache.keys())
    if args.index:
        driver = get_driver()
        idx = escape_string(args.index)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            q = f'''
                match
                    $s isa bioskill;
                    $idx isa bioskill-index, has id "{idx}";
                    (bsi-skill: $s, bsi-index: $idx) isa bsi-indexed-in;
                fetch {{ "id": $s.id }};
            '''
            results = list(tx.query(q).resolve())
        skill_ids_in_scope = {r.get("id", "") for r in results}

    scores = []
    for sid, entry in cache.items():
        if sid not in skill_ids_in_scope:
            continue
        emb = np.array(entry["embedding"])
        score = float(np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(emb) + 1e-10))
        cluster_id = entry.get("cluster_id", -1)
        scores.append((sid, score, cluster_id))

    scores.sort(key=lambda x: -x[1])

    # Apply cluster diversity filter
    max_skills = args.max_skills or 10
    min_clusters = args.min_clusters or 3
    seen_clusters = set()
    playlist = []
    remaining = []

    for sid, score, cid in scores:
        if len(playlist) >= max_skills:
            break
        if cid == -1 or cid not in seen_clusters:
            playlist.append((sid, score, cid))
            seen_clusters.add(cid)
        else:
            remaining.append((sid, score, cid))

    # Fill remaining slots if under max_skills
    for sid, score, cid in remaining:
        if len(playlist) >= max_skills:
            break
        playlist.append((sid, score, cid))

    # Fetch skill details
    driver = get_driver()
    playlist_out = []
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        for rank, (sid, score, cid) in enumerate(playlist, 1):
            s_esc = escape_string(sid)
            q = f'''
                match $s isa bioskill, has id "{s_esc}";
                fetch {{ "id": $s.id, "name": $s.name, "type": $s.bsi-type, "cluster_label": $s.bsi-cluster-label }};
            '''
            r = list(tx.query(q).resolve())
            entry = {"rank": rank, "score": round(score, 4), "cluster_id": cid}
            if r:
                entry.update(r[0])
            playlist_out.append(entry)

    print(json.dumps({
        "success": True,
        "task": args.task,
        "clusters_covered": len(seen_clusters),
        "playlist": playlist_out,
    }))


# ---------------------------------------------------------------------------
# UPDATE COMMAND (discovery)
# ---------------------------------------------------------------------------

def cmd_update(args):
    """Discover new skills from configured sources and add to the index."""
    import yaml
    sources_file = args.sources_file or os.path.join(_SKILL_DIR, "discovery-sources.yaml")
    if not os.path.exists(sources_file):
        print(json.dumps({"success": False, "error": f"Sources file not found: {sources_file}"}))
        return

    with open(sources_file) as f:
        config = yaml.safe_load(f)

    sources = config.get("sources", [])
    total_added = 0
    results = []

    for source in sources:
        src_type = source.get("type")
        print(f"Processing source: {src_type} ...", file=sys.stderr)

        if src_type == "typedb-investigation":
            added = _discover_typedb_investigation(source, args.index, args.dry_run)
        elif src_type == "github-search":
            added = _discover_github_search(source, args.index, args.dry_run)
        elif src_type == "github-repo":
            added = _discover_github_repo(source, args.index, args.dry_run)
        elif src_type == "bio-tools":
            added = _discover_bio_tools(source, args.index, args.dry_run)
        elif src_type == "nf-core":
            added = _discover_nf_core(source, args.index, args.dry_run)
        elif src_type == "awesome-list":
            added = _discover_awesome_list(source, args.index, args.dry_run)
        else:
            added = 0
            print(f"  Unknown source type: {src_type}", file=sys.stderr)

        results.append({"source": src_type, "added": added})
        total_added += added

    print(json.dumps({"success": True, "total_added": total_added, "by_source": results}))


def _discover_typedb_investigation(source: dict, index_id: str, dry_run: bool) -> int:
    """Seed from a tech-recon investigation (tri-f6b3c79c27ab)."""
    inv_id = escape_string(source["id"])
    driver = get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = f'''
            match
                $sys isa tech-recon-system;
                $inv isa tech-recon-investigation, has id "{inv_id}";
                (system: $sys, investigation: $inv) isa investigated-in;
            fetch {{
                "id": $sys.id,
                "name": $sys.name,
                "description": $sys.description,
                "url": $sys.tech-recon-url,
                "github_url": $sys.github-url
            }};
        '''
        systems = list(tx.query(q).resolve())

    if dry_run:
        print(f"  [dry-run] Would import {len(systems)} systems from investigation {source['id']}", file=sys.stderr)
        return 0

    # Deduplicate by name
    existing_names = _get_existing_skill_names(index_id)
    added = 0
    for system in systems:
        name = system.get("name", "")
        if name in existing_names:
            continue
        github_url = system.get("github_url", "") or ""
        url = system.get("url", "") or ""
        desc = system.get("description", "") or ""
        # Create add_skill args-like object
        class FakeArgs:
            pass
        a = FakeArgs()
        a.name = name
        a.description = desc
        a.type = "skill"
        a.source_repo = github_url or url
        a.source_file = ""
        a.github_url = github_url
        a.tool_access = ""
        a.index = index_id
        a.ops = ""
        a.topics = ""
        cmd_add_skill(a)
        added += 1
        existing_names.add(name)

    return added


def _get_existing_skill_names(index_id: str) -> set:
    """Return set of skill names already in the index."""
    driver = get_driver()
    idx = escape_string(index_id)
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = f'''
            match
                $s isa bioskill;
                $idx isa bioskill-index, has id "{idx}";
                (bsi-skill: $s, bsi-index: $idx) isa bsi-indexed-in;
            fetch {{ "name": $s.name }};
        '''
        results = list(tx.query(q).resolve())
    return {r.get("name", "") for r in results}


def _discover_github_search(source: dict, index_id: str, dry_run: bool) -> int:
    """Discover repos via GitHub search API."""
    import urllib.parse
    query = source.get("query", "")
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    encoded = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&per_page=30"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  GitHub search error: {e}", file=sys.stderr)
        return 0

    items = data.get("items", [])
    if dry_run:
        print(f"  [dry-run] Would import {len(items)} repos for query: {query}", file=sys.stderr)
        return 0

    existing_names = _get_existing_skill_names(index_id)
    added = 0
    for item in items:
        name = item.get("full_name", "")
        if name in existing_names:
            continue

        class FakeArgs:
            pass
        a = FakeArgs()
        a.name = name
        a.description = item.get("description", "") or ""
        a.type = "skill"
        a.source_repo = item.get("html_url", "")
        a.source_file = ""
        a.github_url = item.get("html_url", "")
        a.tool_access = ""
        a.index = index_id
        a.ops = ""
        a.topics = ""
        cmd_add_skill(a)
        added += 1
        existing_names.add(name)

    return added


def _discover_github_repo(source: dict, index_id: str, dry_run: bool) -> int:
    """Discover skills from a specific GitHub repo (treat repo itself as a skill)."""
    url = source.get("url", "")
    name = url.rstrip("/").split("/")[-2] + "/" + url.rstrip("/").split("/")[-1]
    existing = _get_existing_skill_names(index_id)
    if name in existing:
        return 0
    if dry_run:
        print(f"  [dry-run] Would add repo: {name}", file=sys.stderr)
        return 0

    class FakeArgs:
        pass
    a = FakeArgs()
    a.name = name
    a.description = ""
    a.type = "skill"
    a.source_repo = url
    a.source_file = ""
    a.github_url = url
    a.tool_access = ""
    a.index = index_id
    a.ops = ""
    a.topics = ""
    cmd_add_skill(a)
    return 1


def _discover_bio_tools(source: dict, index_id: str, dry_run: bool) -> int:
    """Discover tools from the bio.tools registry API (with EDAM annotations)."""
    base_url = source.get("base_url", "https://bio.tools/api/tool")
    filter_param = source.get("filter", "")
    url = f"{base_url}?format=json&{filter_param}&page_size=50"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  bio.tools API error: {e}", file=sys.stderr)
        return 0

    tools = data.get("list", [])
    existing = _get_existing_skill_names(index_id)
    if dry_run:
        print(f"  [dry-run] Would import {len(tools)} tools from bio.tools", file=sys.stderr)
        return 0

    added = 0
    for tool in tools:
        name = tool.get("name", "")
        if name in existing:
            continue

        # Extract EDAM operation IDs
        op_ids = []
        for func in tool.get("function", []):
            for op in func.get("operation", []):
                uri = op.get("uri", "")
                if uri:
                    edam_id = uri.split("/")[-1]
                    op_ids.append(edam_id)

        topic_ids = []
        for t in tool.get("topic", []):
            uri = t.get("uri", "")
            if uri:
                edam_id = uri.split("/")[-1]
                topic_ids.append(edam_id)

        class FakeArgs:
            pass
        a = FakeArgs()
        a.name = name
        a.description = tool.get("description", "") or ""
        a.type = "python-api"
        a.source_repo = tool.get("homepage", "") or ""
        a.source_file = ""
        a.github_url = ""
        a.tool_access = name.lower()
        a.index = index_id
        a.ops = ",".join(op_ids)
        a.topics = ",".join(topic_ids)
        cmd_add_skill(a)
        added += 1
        existing.add(name)

    return added


def _discover_nf_core(source: dict, index_id: str, dry_run: bool) -> int:
    """Discover nf-core pipelines."""
    base_url = source.get("base_url", "https://nf-co.re/pipelines.json")
    try:
        with urllib.request.urlopen(base_url, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  nf-core API error: {e}", file=sys.stderr)
        return 0

    pipelines = data if isinstance(data, list) else data.get("remote_workflows", [])
    existing = _get_existing_skill_names(index_id)
    if dry_run:
        print(f"  [dry-run] Would import {len(pipelines)} nf-core pipelines", file=sys.stderr)
        return 0

    added = 0
    for p in pipelines:
        name = f"nf-core/{p.get('name', '')}"
        if name in existing:
            continue

        class FakeArgs:
            pass
        a = FakeArgs()
        a.name = name
        a.description = p.get("description", "") or ""
        a.type = "workflow"
        a.source_repo = f"https://github.com/nf-core/{p.get('name', '')}"
        a.source_file = ""
        a.github_url = f"https://github.com/nf-core/{p.get('name', '')}"
        a.tool_access = "nextflow"
        a.index = index_id
        a.ops = ""
        a.topics = ""
        cmd_add_skill(a)
        added += 1
        existing.add(name)

    return added


def _discover_awesome_list(source: dict, index_id: str, dry_run: bool) -> int:
    """Discover skills from an awesome-list GitHub repo."""
    # Minimal implementation — fetch README, extract GitHub links
    url = source.get("url", "")
    section = source.get("section", "")
    github_api_url = url.replace("https://github.com/", "https://raw.githubusercontent.com/") + "/main/README.md"
    try:
        with urllib.request.urlopen(github_api_url, timeout=10) as resp:
            content = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  awesome-list fetch error: {e}", file=sys.stderr)
        return 0

    import re
    links = re.findall(r"\[([^\]]+)\]\((https://github\.com/[^\)]+)\)", content)
    if dry_run:
        print(f"  [dry-run] Would inspect {len(links)} links from awesome list", file=sys.stderr)
        return 0

    # Just record the awesome-list itself as a source skill for now
    return 0


# ---------------------------------------------------------------------------
# GENERATE PSEUDOCODE
# ---------------------------------------------------------------------------

def cmd_generate_pseudocode(args):
    """Generate a plain-English algorithmic pseudocode snippet for a bioskill via Claude."""
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not available"}))
        return

    try:
        import anthropic
    except ImportError:
        print(json.dumps({"success": False, "error": "anthropic package not installed. pip install anthropic"}))
        return

    sid = escape_string(args.skill)
    driver = get_driver()

    # Fetch skill details
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        q = f'''
            match $s isa bioskill, has id "{sid}";
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "description": $s.description,
                "type": $s.bsi-type,
                "source_repo": $s.bsi-source-repo,
                "source_file": $s.bsi-source-file,
                "tool_access": $s.bsi-tool-access
            }};
        '''
        results = list(tx.query(q).resolve())
        if not results:
            print(json.dumps({"success": False, "error": "skill not found"}))
            return
        skill = results[0]

    name = skill.get("name", "")
    description = skill.get("description", "") or ""
    bsi_type = skill.get("type", "skill") or "skill"
    source_repo = skill.get("source_repo", "") or ""
    source_file = skill.get("source_file", "") or ""
    tool_access = skill.get("tool_access", "") or ""

    # Try to fetch source content from GitHub
    source_content = ""
    if source_repo and source_file:
        # Convert GitHub URL to raw content URL
        raw_url = ""
        if "github.com" in source_repo:
            repo_path = source_repo.rstrip("/").replace("https://github.com/", "")
            raw_url = f"https://raw.githubusercontent.com/{repo_path}/main/{source_file.lstrip('/')}"
        if raw_url:
            try:
                req = urllib.request.Request(raw_url, headers={"User-Agent": "bioskills-index/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    source_content = resp.read().decode("utf-8", errors="replace")[:8000]
                print(f"Fetched source: {source_file} ({len(source_content)} chars)", file=sys.stderr)
            except Exception as e:
                print(f"Could not fetch source: {e}", file=sys.stderr)

    # Build prompt
    context_parts = [f"Name: {name}", f"Type: {bsi_type}"]
    if description:
        context_parts.append(f"Description: {description}")
    if tool_access:
        context_parts.append(f"Underlying library/tool: {tool_access}")
    if source_repo:
        context_parts.append(f"Source repo: {source_repo}")
    if source_file:
        context_parts.append(f"Source file: {source_file}")

    prompt = "Write a 5-10 line plain-English pseudocode summary of the following bioskill's core algorithm or workflow. Focus on WHAT it does and HOW, not on implementation details. Use numbered steps. Be concrete and specific.\n\n"
    prompt += "\n".join(context_parts)
    if source_content:
        prompt += f"\n\nSource file content:\n```\n{source_content}\n```"
    prompt += "\n\nReturn ONLY the pseudocode steps, no preamble or explanation."

    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    print("Calling Claude to generate pseudocode...", file=sys.stderr)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    pseudocode = message.content[0].text.strip()

    # Insert as a snippet
    snip_id = generate_id("bsn")
    ts = get_timestamp()
    snip_name = escape_string(f"Pseudocode: {name}")
    snip_content = escape_string(pseudocode)

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        q = f'''
            insert $snip isa bioskill-snippet,
                has id "{snip_id}",
                has name "{snip_name}",
                has content "{snip_content}",
                has bsi-snippet-type "pseudocode",
                has bsi-snippet-language "text",
                has created-at {ts};
        '''
        tx.query(q).resolve()
        lq = f'''
            match
                $s isa bioskill, has id "{sid}";
                $snip isa bioskill-snippet, has id "{snip_id}";
            insert
                (bsi-parent-skill: $s, bsi-snippet: $snip) isa bsi-snippet-of;
        '''
        tx.query(lq).resolve()
        tx.commit()

    print(json.dumps({
        "success": True,
        "snippet_id": snip_id,
        "skill_id": args.skill,
        "pseudocode": pseudocode,
    }))


# ---------------------------------------------------------------------------
# ARGUMENT PARSER
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Bioskills Index CLI — EDAM-annotated index of bioskills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- EDAM import ---
    p = sub.add_parser("import-edam", help="Import EDAM terms from TSV into TypeDB")
    p.add_argument("--tsv", help="Path to local EDAM.tsv file (downloads if not specified)")
    p.add_argument("--namespace", required=True, choices=["operation", "topic", "data", "format"],
                   help="EDAM namespace to import")
    p.add_argument("--include-deprecated", action="store_true", help="Include deprecated terms")
    p.set_defaults(func=cmd_import_edam)

    # --- Custom terms ---
    p = sub.add_parser("add-operation", help="Add a custom extension bio-operation")
    p.add_argument("--name", required=True)
    p.add_argument("--definition", help="Term definition")
    p.add_argument("--parent-edam", help="Parent EDAM operation ID (e.g. operation_2403)")
    p.add_argument("--parent-bsi", help="Parent custom term bsi-term-id")
    p.add_argument("--source", default="bioskills-index", help="Source namespace")
    p.set_defaults(func=cmd_add_operation)

    p = sub.add_parser("add-topic", help="Add a custom extension bio-topic")
    p.add_argument("--name", required=True)
    p.add_argument("--definition")
    p.add_argument("--parent-edam", help="Parent EDAM topic ID")
    p.add_argument("--parent-bsi", help="Parent custom bsi-term-id")
    p.add_argument("--source", default="bioskills-index")
    p.set_defaults(func=cmd_add_topic)

    p = sub.add_parser("show-operation", help="Show an operation term")
    p.add_argument("--id", help="Internal TypeDB id")
    p.add_argument("--edam-id", help="EDAM ID (e.g. operation_2403)")
    p.add_argument("--bsi-term-id", help="Custom term bsi-term-id")
    p.set_defaults(func=cmd_show_operation)

    p = sub.add_parser("list-operations", help="Browse bio-operation hierarchy")
    p.add_argument("--parent", help="Filter to children of this EDAM ID")
    p.add_argument("--source", help="Filter by source (edam | bioskills-index | user)")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_list_operations)

    # --- Index commands ---
    p = sub.add_parser("create-index", help="Create a new bioskill-index collection")
    p.add_argument("--name", required=True)
    p.add_argument("--description")
    p.set_defaults(func=cmd_create_index)

    p = sub.add_parser("list-indices", help="List all bioskill-index collections")
    p.set_defaults(func=cmd_list_indices)

    # --- Skill commands ---
    p = sub.add_parser("add-skill", help="Add a bioskill entry")
    p.add_argument("--index", help="Index ID to enroll skill in")
    p.add_argument("--name", required=True)
    p.add_argument("--description")
    p.add_argument("--type", default="skill", choices=["skill", "mcp-server", "workflow", "python-api"])
    p.add_argument("--source-repo", help="GitHub URL of source repo")
    p.add_argument("--source-file", help="Path within repo")
    p.add_argument("--github-url")
    p.add_argument("--tool-access", help="Underlying library (e.g. biopython)")
    p.add_argument("--ops", help="Comma-separated EDAM operation IDs to annotate")
    p.add_argument("--topics", help="Comma-separated EDAM topic IDs to annotate")
    p.set_defaults(func=cmd_add_skill)

    p = sub.add_parser("annotate-skill", help="Add EDAM annotations and computational profile to a skill")
    p.add_argument("--skill", required=True, help="Skill ID")
    p.add_argument("--op", help="Comma-separated EDAM operation IDs")
    p.add_argument("--topic", help="Comma-separated EDAM topic IDs")
    p.add_argument("--input", help="Comma-separated EDAM data IDs for accepted inputs")
    p.add_argument("--output", help="Comma-separated EDAM data IDs for produced outputs")
    p.add_argument("--gpu", dest="gpu", action="store_true", default=False, help="Requires GPU")
    p.add_argument("--no-gpu", dest="no_gpu", action="store_true", default=False, help="Does not require GPU")
    p.add_argument("--runtime-class", choices=["instant", "seconds", "minutes", "hours", "days"],
                   help="Runtime class")
    p.add_argument("--memory-class", choices=["lightweight", "moderate", "heavy"],
                   help="Memory class")
    p.add_argument("--language", help="Primary implementation language (Python, R, Nextflow, etc.)")
    p.set_defaults(func=cmd_annotate_skill)

    p = sub.add_parser("show-skill", help="Show skill details")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_show_skill)

    p = sub.add_parser("list-skills", help="List skills with optional filters")
    p.add_argument("--index", help="Filter by index ID")
    p.add_argument("--op", help="Filter by EDAM operation ID (uses inference)")
    p.add_argument("--topic", help="Filter by EDAM topic ID (uses inference)")
    p.add_argument("--cluster", type=int, help="Filter by cluster ID")
    p.add_argument("--type", help="Filter by bsi-type")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_list_skills)

    p = sub.add_parser("add-snippet", help="Add a code snippet to a bioskill")
    p.add_argument("--skill", required=True, help="Skill ID")
    p.add_argument("--name", help="Snippet name")
    p.add_argument("--content", required=True, help="Snippet code/text")
    p.add_argument("--type", default="example",
                   choices=["function", "prompt", "example", "config", "pseudocode"])
    p.add_argument("--language", default="python",
                   choices=["python", "bash", "yaml", "markdown", "typescript", "text"])
    p.set_defaults(func=cmd_add_snippet)

    p = sub.add_parser("generate-pseudocode", help="Generate plain-English pseudocode for a skill via Claude")
    p.add_argument("--skill", required=True, help="Skill ID")
    p.set_defaults(func=cmd_generate_pseudocode)

    # --- Embedding + search ---
    p = sub.add_parser("embed-and-project", help="Batch embed -> UMAP -> HDBSCAN")
    p.add_argument("--index", required=True)
    p.add_argument("--force", action="store_true", help="Re-embed all skills even if unchanged")
    p.set_defaults(func=cmd_embed_and_project)

    p = sub.add_parser("search", help="Cosine similarity search")
    p.add_argument("--index", help="Limit search to this index")
    p.add_argument("--query", required=True)
    p.add_argument("--top-k", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("compose", help="Task description -> ordered skill playlist")
    p.add_argument("--index", help="Limit to this index")
    p.add_argument("--task", required=True)
    p.add_argument("--max-skills", type=int, default=10)
    p.add_argument("--min-clusters", type=int, default=3)
    p.set_defaults(func=cmd_compose)

    # --- Discovery ---
    p = sub.add_parser("update", help="Discover new skills from configured sources")
    p.add_argument("--index", required=True)
    p.add_argument("--sources-file", help="Path to discovery-sources.yaml")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_update)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
