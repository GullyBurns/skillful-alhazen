#!/usr/bin/env python3
"""
Agentic Memory CLI - TypeDB-backed two-tier memory architecture.

Manages persons (nbmem-operator-users + application-users) with personal context,
nbmem-memory-claim-notes (crystallized semantic propositions), and session episodes.

Usage:
    python skills/agentic-memory/agentic_memory.py <command> [options]

Person / Context commands:
    create-operator        Create an nbmem-operator-user with personal context
    update-context-domain  Update one personal context domain for a person
    get-context            Get formatted personal context for a person (JSON)
    link-project           Link a person to a collection (nbmem-project-involvement)
    link-tool              Link a person to a alh-domain-thing (nbmem-tool-familiarity)
    link-person            Create a nbmem-relationship-context between two persons
    list-persons           List all person entities

Memory Claim Note commands:
    consolidate            Create a nbmem-memory-claim-note about an entity
    recall                 Get nbmem-memory-claim-notes about an entity
    recall-person          Get all nbmem-memory-claim-notes about a person
    invalidate             Invalidate a nbmem-memory-claim-note (set valid-until to now)
    list-claims            List nbmem-memory-claim-notes with optional filters

Episode commands:
    create-episode         Create an episode entity
    link-episode           Link an episode to graph entities via alh-episode-mention
    show-episode           Show episode details with linked entities
    list-episodes          List recent episodes

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
    _SKILL_DIR = os.path.dirname(os.path.realpath(__file__))
    _PROJECT_ROOT = os.path.abspath(os.path.join(_SKILL_DIR, "..", ".."))
    sys.path.insert(0, _PROJECT_ROOT)
    from src.skillful_alhazen.utils.skill_helpers import escape_string, generate_id, get_timestamp
    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False
    import uuid
    from datetime import datetime, timezone

    def escape_string(s: str) -> str:
        if s is None:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")

    def generate_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def get_timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# TypeDB connection
# ---------------------------------------------------------------------------

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


# ---------------------------------------------------------------------------
# Person / Context commands
# ---------------------------------------------------------------------------

def create_operator(args):
    """Create an nbmem-operator-user with initial personal context."""
    eid = generate_id("op")
    ts = get_timestamp()
    name_esc = escape_string(args.name)
    given = escape_string(args.given_name or "")
    family = escape_string(args.family_name or "")
    identity = escape_string(args.identity or "")
    role = escape_string(args.role or "")

    query = f'''
    insert $p isa nbmem-operator-user,
        has id "{eid}",
        has name "{name_esc}",
        has created-at {ts};
    '''
    if given:
        query = query.rstrip().rstrip(";") + f',\n        has alh-given-name "{given}";'
    if family:
        query = query.rstrip().rstrip(";") + f',\n        has alh-family-name "{family}";'
    if identity:
        query = query.rstrip().rstrip(";") + f',\n        has nbmem-identity-summary "{identity}";'
    if role:
        query = query.rstrip().rstrip(";") + f',\n        has nbmem-role-description "{role}";'
    if not query.rstrip().endswith(";"):
        query = query.rstrip() + ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "id": eid, "name": args.name}))


def update_context_domain(args):
    """Update one personal context domain attribute for a person."""
    domain_map = {
        "identity": "nbmem-identity-summary",
        "role": "nbmem-role-description",
        "style": "nbmem-communication-style",
        "goals": "nbmem-goals-summary",
        "preferences": "nbmem-preferences-summary",
        "expertise": "nbmem-domain-expertise",
    }
    attr = domain_map.get(args.domain)
    if not attr:
        print(json.dumps({"success": False, "error": f"Unknown domain '{args.domain}'. Choose: {list(domain_map)}"}))
        return

    content_esc = escape_string(args.content)
    pid = escape_string(args.person)
    ts = get_timestamp()

    # Delete old value then insert new one
    # Use nbmem-operator-user as the match type so TypeDB inference resolves nbmem-operator-user-specific attrs
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            check_q = f'''
            match $p isa nbmem-operator-user, has id "{pid}", has {attr} $v;
            delete has $v of $p;
            '''
            try:
                tx.query(check_q).resolve()
                tx.commit()
            except Exception:
                pass  # No existing value -- that is fine

        # Remove old updated-at before inserting new one (cardinality 0..1)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            try:
                tx.query(f'''
                match $p isa nbmem-operator-user, has id "{pid}", has updated-at $v;
                delete has $v of $p;
                ''').resolve()
                tx.commit()
            except Exception:
                pass

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match $p isa nbmem-operator-user, has id "{pid}";
            insert $p has {attr} "{content_esc}", has updated-at {ts};
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "person": pid, "domain": args.domain}))


def get_context(args):
    """Retrieve formatted personal context for a person."""
    pid = escape_string(args.person)

    domain_attrs = [
        ("identity", "nbmem-identity-summary"),
        ("role", "nbmem-role-description"),
        ("style", "nbmem-communication-style"),
        ("goals", "nbmem-goals-summary"),
        ("preferences", "nbmem-preferences-summary"),
        ("expertise", "nbmem-domain-expertise"),
    ]

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get basic person info
            person_q = f'''
            match $p isa nbmem-operator-user, has id "{pid}";
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "alh-given-name": $p.alh-given-name,
                "alh-family-name": $p.alh-family-name,
                "nbmem-identity-summary": $p.nbmem-identity-summary,
                "nbmem-role-description": $p.nbmem-role-description,
                "nbmem-communication-style": $p.nbmem-communication-style,
                "nbmem-goals-summary": $p.nbmem-goals-summary,
                "nbmem-preferences-summary": $p.nbmem-preferences-summary,
                "nbmem-domain-expertise": $p.nbmem-domain-expertise
            }};
            '''
            persons = list(tx.query(person_q).resolve())
            if not persons:
                print(json.dumps({"success": False, "error": f"Person not found: {pid}"}))
                return

            ctx = persons[0]

            # Get linked projects (nbmem-project-involvement)
            proj_q = f'''
            match
                $p isa alh-identifiable-entity, has id "{pid}";
                (participant: $p, project: $c) isa nbmem-project-involvement;
                $c has id $cid, has name $cname;
            fetch {{
                "id": $cid,
                "name": $cname
            }};
            '''
            try:
                projects = list(tx.query(proj_q).resolve())
            except Exception:
                projects = []

            # Get linked tools (nbmem-tool-familiarity)
            tool_q = f'''
            match
                $p isa alh-identifiable-entity, has id "{pid}";
                (practitioner: $p, tool: $t) isa nbmem-tool-familiarity;
                $t has id $tid, has name $tname;
            fetch {{
                "id": $tid,
                "name": $tname
            }};
            '''
            try:
                tools = list(tx.query(tool_q).resolve())
            except Exception:
                tools = []

    result = {
        "success": True,
        "context": dict(ctx),
        "projects": projects,
        "tools": tools,
    }
    print(json.dumps(result, default=str))


def link_project(args):
    """Create a nbmem-project-involvement relation between a person and a collection."""
    pid = escape_string(args.person)
    cid = escape_string(args.collection)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match
                $p isa nbmem-operator-user, has id "{pid}";
                $c isa alh-collection, has id "{cid}";
            insert (participant: $p, project: $c) isa nbmem-project-involvement;
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "person": pid, "collection": cid}))


def link_tool(args):
    """Create a nbmem-tool-familiarity relation between a person and a alh-domain-thing."""
    pid = escape_string(args.person)
    tid = escape_string(args.entity)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match
                $p isa nbmem-operator-user, has id "{pid}";
                $t isa alh-domain-thing, has id "{tid}";
            insert (practitioner: $p, tool: $t) isa nbmem-tool-familiarity;
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "person": pid, "tool": tid}))


def link_person(args):
    """Create a nbmem-relationship-context between two persons."""
    from_id = escape_string(args.from_person)
    to_id = escape_string(args.to_person)
    desc = escape_string(args.context or "")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            q = f'''
            match
                $a isa alh-identifiable-entity, has id "{from_id}";
                $b isa alh-identifiable-entity, has id "{to_id}";
            insert (from-person: $a, to-person: $b) isa nbmem-relationship-context
            '''
            if desc:
                q += f', has description "{desc}"'
            q += ";"
            tx.query(q).resolve()
            tx.commit()

    print(json.dumps({"success": True, "from": from_id, "to": to_id}))


def list_persons(args):
    """List all person entities."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query('''
            match $p isa alh-person;
            fetch {
                "id": $p.id,
                "name": $p.name,
                "alh-given-name": $p.alh-given-name,
                "alh-family-name": $p.alh-family-name
            };
            ''').resolve())

    print(json.dumps({"success": True, "persons": results}, default=str))


# ---------------------------------------------------------------------------
# Memory Claim Note commands
# ---------------------------------------------------------------------------

def consolidate(args):
    """Create a nbmem-memory-claim-note about an entity."""
    nid = generate_id("mcn")
    ts = get_timestamp()
    content_esc = escape_string(args.content)
    subject_id = escape_string(args.subject)
    fact_type = escape_string(args.fact_type or "knowledge")
    confidence = float(args.confidence) if args.confidence else 0.8

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Insert the nbmem-memory-claim-note
            q = f'''
            insert $n isa nbmem-memory-claim-note,
                has id "{nid}",
                has content "{content_esc}",
                has alh-fact-type "{fact_type}",
                has confidence {confidence},
                has created-at {ts};
            '''
            if args.valid_until:
                q = q.rstrip().rstrip(";") + f',\n                has valid-until {args.valid_until};'
            if not q.rstrip().endswith(";"):
                q = q.rstrip() + ";"
            tx.query(q).resolve()
            tx.commit()

        # Link to subject via alh-aboutness
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match
                $n isa alh-note, has id "{nid}";
                $e isa alh-identifiable-entity, has id "{subject_id}";
            insert (note: $n, subject: $e) isa alh-aboutness;
            ''').resolve()
            tx.commit()

        # Link provenance: derive from source episode or note if given
        if args.source_episode or args.source_note:
            src_id = escape_string(args.source_episode or args.source_note)
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''
                match
                    $n isa alh-note, has id "{nid}";
                    $src isa alh-identifiable-entity, has id "{src_id}";
                insert (derived: $n, source: $src) isa nbmem-fact-evidence;
                ''').resolve()
                tx.commit()

    print(json.dumps({"success": True, "id": nid, "fact_type": fact_type}))


def recall(args):
    """Get nbmem-memory-claim-notes about an entity."""
    subject_id = escape_string(args.subject)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
            match
                $n isa nbmem-memory-claim-note;
                $e isa alh-identifiable-entity, has id "{subject_id}";
                (note: $n, subject: $e) isa alh-aboutness;
            fetch {{
                "id": $n.id,
                "content": $n.content,
                "alh-fact-type": $n.alh-fact-type,
                "confidence": $n.confidence,
                "created-at": $n.created-at
            }};
            ''').resolve())

    print(json.dumps({"success": True, "claims": results}, default=str))


def recall_person(args):
    """Get all nbmem-memory-claim-notes about a person."""
    args.subject = args.person
    recall(args)


def invalidate(args):
    """Set valid-until to now for a nbmem-memory-claim-note."""
    nid = escape_string(args.claim_id)
    ts = get_timestamp()

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match $n isa nbmem-memory-claim-note, has id "{nid}";
            insert $n has valid-until {ts};
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "id": nid, "invalidated_at": ts}))


def list_claims(args):
    """List nbmem-memory-claim-notes with optional filters."""
    filters = ""
    if args.fact_type:
        ft = escape_string(args.fact_type)
        filters += f'\n                $n has alh-fact-type "{ft}";'
    if args.person:
        pid = escape_string(args.person)
        filters += f'''
                $e isa alh-identifiable-entity, has id "{pid}";
                (note: $n, subject: $e) isa alh-aboutness;'''

    limit = int(args.limit) if args.limit else 50

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
            match
                $n isa nbmem-memory-claim-note;{filters}
            fetch {{
                "id": $n.id,
                "content": $n.content,
                "alh-fact-type": $n.alh-fact-type,
                "confidence": $n.confidence,
                "created-at": $n.created-at
            }};
            ''').resolve())

    print(json.dumps({"success": True, "claims": results[:limit]}, default=str))


# ---------------------------------------------------------------------------
# Episode commands
# ---------------------------------------------------------------------------

def create_episode(args):
    """Create an episode entity."""
    eid = generate_id("ep")
    ts = get_timestamp()
    skill = escape_string(args.skill or "unknown")
    summary = escape_string(args.summary)
    session_id = escape_string(args.session_id or eid)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            insert $e isa alh-episode,
                has id "{eid}",
                has content "{summary}",
                has alh-source-skill "{skill}",
                has alh-session-id "{session_id}",
                has created-at {ts};
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "id": eid, "session_id": session_id}))


def link_episode(args):
    """Add alh-episode-mention relations linking an episode to graph entities."""
    ep_id = escape_string(args.episode)
    entity_ids = [e.strip() for e in args.entities.split(",") if e.strip()]
    op_type = getattr(args, "operation_type", None)
    rationale_text = getattr(args, "rationale", None)

    results = []
    with get_driver() as driver:
        for eid in entity_ids:
            eid_esc = escape_string(eid)
            try:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    insert_clause = "(session: $ep, subject: $e) isa alh-episode-mention"
                    if op_type:
                        insert_clause += f', has alh-operation-type "{escape_string(op_type)}"'
                    if rationale_text:
                        insert_clause += f', has nbmem-rationale "{escape_string(rationale_text)}"'
                    insert_clause += ";"
                    tx.query(f'''
                    match
                        $ep isa alh-episode, has id "{ep_id}";
                        $e isa alh-identifiable-entity, has id "{eid_esc}";
                    insert {insert_clause}
                    ''').resolve()
                    tx.commit()
                results.append({"entity": eid, "success": True})
            except Exception as exc:
                results.append({"entity": eid, "success": False, "error": str(exc)})

    print(json.dumps({"success": True, "episode": ep_id, "links": results}))


def show_episode(args):
    """Show episode details with linked entities."""
    ep_id = escape_string(args.episode_id)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            eps = list(tx.query(f'''
            match $ep isa alh-episode, has id "{ep_id}";
            fetch {{
                "id": $ep.id,
                "content": $ep.content,
                "alh-source-skill": $ep.alh-source-skill,
                "alh-session-id": $ep.alh-session-id,
                "created-at": $ep.created-at
            }};
            ''').resolve())

            if not eps:
                print(json.dumps({"success": False, "error": f"Episode not found: {ep_id}"}))
                return

            entities = list(tx.query(f'''
            match
                $ep isa alh-episode, has id "{ep_id}";
                (session: $ep, subject: $e) isa alh-episode-mention;
                $e has id $eid, has name $ename;
            fetch {{
                "id": $eid,
                "name": $ename
            }};
            ''').resolve())

            # Second query: get entities with alh-operation-type metadata
            try:
                entities_with_ops = list(tx.query(f'''
                match
                    $ep isa alh-episode, has id "{ep_id}";
                    $r (session: $ep, subject: $e) isa alh-episode-mention, has alh-operation-type $ot;
                    $e has id $eid, has name $ename;
                fetch {{
                    "id": $eid,
                    "name": $ename,
                    "alh-operation-type": $ot
                }};
                ''').resolve())
            except Exception:
                entities_with_ops = []

            # Merge: prefer entries with operation metadata
            if entities_with_ops:
                ops_by_id = {str(e.get("id", "")): e for e in entities_with_ops}
                merged = []
                seen = set()
                for e in entities:
                    eid_val = str(e.get("id", ""))
                    if eid_val in ops_by_id:
                        merged.append(ops_by_id[eid_val])
                    else:
                        merged.append(e)
                    seen.add(eid_val)
                # Add any ops entries not in base set
                for eid_val, e in ops_by_id.items():
                    if eid_val not in seen:
                        merged.append(e)
                entities = merged

    print(json.dumps({
        "success": True,
        "episode": eps[0],
        "entities": entities
    }, default=str))


def list_episodes(args):
    """List recent episodes with optional skill filter."""
    limit = int(args.limit) if args.limit else 20

    skill_filter = ""
    if args.skill:
        sf = escape_string(args.skill)
        skill_filter = f'\n                $ep has alh-source-skill "{sf}";'

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
            match
                $ep isa alh-episode;{skill_filter}
            fetch {{
                "id": $ep.id,
                "content": $ep.content,
                "alh-source-skill": $ep.alh-source-skill,
                "alh-session-id": $ep.alh-session-id,
                "created-at": $ep.created-at
            }};
            ''').resolve())

    # Sort by created-at descending (most recent first), apply limit
    results_sorted = sorted(results, key=lambda r: str(r.get("created-at", "")), reverse=True)
    print(json.dumps({"success": True, "episodes": results_sorted[:limit]}, default=str))


# ---------------------------------------------------------------------------
# Schema, search, and entity management commands
# ---------------------------------------------------------------------------


def describe_schema(args):
    """Describe the TypeDB schema with optional skill filter, instance counts, and audit."""
    source = getattr(args, "source", "live") or "live"
    skill_filter = getattr(args, "skill", None)
    full_mode = getattr(args, "full", False)
    audit_mode = getattr(args, "audit", False)

    if audit_mode:
        full_mode = True

    if source == "files":
        result = _describe_schema_from_files(skill_filter, full_mode)
        print(json.dumps({"success": True, **result}, default=str))
        return

    # Live mode: introspect TypeDB
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all entity types
            entity_rows = list(tx.query('''
            match entity $t;
            fetch { "type": $t };
            ''').resolve())
            entity_labels = sorted(set(
                r["type"]["label"] for r in entity_rows
                if isinstance(r.get("type"), dict) and "label" in r["type"]
            ))

            # Build parent map using hierarchy query
            parent_map = {}
            try:
                hier_rows = list(tx.query(
                    'match { $t sub! $supertype; } or '
                    '{ $t sub $supertype; $t is $supertype; }; '
                    'fetch { "type": $t, "super": $supertype };'
                ).resolve())
                for row in hier_rows:
                    t_label = row["type"]["label"] if isinstance(row.get("type"), dict) else str(row.get("type", ""))
                    s_label = row["super"]["label"] if isinstance(row.get("super"), dict) else str(row.get("super", ""))
                    if t_label != s_label:
                        parent_map[t_label] = s_label
            except Exception:
                pass

            entities = {}
            for label in entity_labels:
                if not label or label in ("entity",):
                    continue
                info = {"parent": parent_map.get(label), "owns": [], "plays": [], "subtypes": []}

                # Get owns
                try:
                    owns_rows = list(tx.query(f'''
                    match $t label {label}; $t owns $a;
                    fetch {{ "attr": $a }};
                    ''').resolve())
                    info["owns"] = sorted(set(
                        r["attr"]["label"] for r in owns_rows
                        if isinstance(r.get("attr"), dict)
                    ))
                except Exception:
                    pass

                # Get plays
                try:
                    plays_rows = list(tx.query(f'''
                    match entity $t, label {label}, plays $role;
                    fetch {{ "role": $role }};
                    ''').resolve())
                    info["plays"] = sorted(set(
                        r["role"]["label"] for r in plays_rows
                        if isinstance(r.get("role"), dict)
                    ))
                except Exception:
                    pass

                # Get subtypes
                try:
                    sub_rows = list(tx.query(f'''
                    match entity $t sub {label};
                    fetch {{ "type": $t }};
                    ''').resolve())
                    info["subtypes"] = sorted(set(
                        r["type"]["label"] for r in sub_rows
                        if isinstance(r.get("type"), dict) and r["type"]["label"] != label
                    ))
                except Exception:
                    pass

                # Count instances if full mode
                if full_mode:
                    try:
                        count_rows = list(tx.query(f'''
                        match $x isa {label};
                        fetch {{ "id": $x.id }};
                        ''').resolve())
                        info["instance_count"] = len(count_rows)
                    except Exception:
                        info["instance_count"] = 0

                entities[label] = info

            # Get all relation types
            rel_rows = list(tx.query('''
            match relation $t;
            fetch { "type": $t };
            ''').resolve())
            rel_labels = sorted(set(
                r["type"]["label"] for r in rel_rows
                if isinstance(r.get("type"), dict) and "label" in r["type"]
            ))

            relations = {}
            for label in rel_labels:
                if not label or label in ("relation",):
                    continue
                rinfo = {"roles": [], "owns": []}

                try:
                    role_rows = list(tx.query(f'''
                    match relation $t, label {label}, relates $role;
                    fetch {{ "role": $role }};
                    ''').resolve())
                    rinfo["roles"] = sorted(set(
                        r["role"]["label"] for r in role_rows
                        if isinstance(r.get("role"), dict)
                    ))
                except Exception:
                    pass

                try:
                    owns_rows = list(tx.query(f'''
                    match $t label {label}; $t owns $a;
                    fetch {{ "attr": $a }};
                    ''').resolve())
                    rinfo["owns"] = sorted(set(
                        r["attr"]["label"] for r in owns_rows
                        if isinstance(r.get("attr"), dict)
                    ))
                except Exception:
                    pass

                relations[label] = rinfo

    # Apply skill filter if provided
    if skill_filter:
        prefix = skill_filter
        core_types = {
            "alh-identifiable-entity", "alh-domain-thing", "alh-collection",
            "alh-information-content-entity", "alh-artifact", "alh-fragment", "alh-note",
            "alh-episode", "alh-user-question", "alh-information-resource",
            "alh-agent", "alh-person", "alh-author", "alh-organization", "alh-interaction",
            "alh-tag", "alh-vocabulary", "alh-vocabulary-type", "alh-vocabulary-property",
            "nbmem-operator-user", "nbmem-application-user", "nbmem-memory-claim-note",
        }
        core_rels = {
            "alh-aboutness", "alh-representation", "alh-collection-membership",
            "alh-collection-nesting", "alh-fragmentation", "alh-authorship",
            "alh-affiliation", "alh-citation-reference", "alh-derivation",
            "alh-works-at", "alh-interaction-participation", "alh-evidence-chain",
            "alh-provenance-record", "alh-classification", "alh-tagging",
            "alh-episode-mention", "alh-note-threading", "alh-semantic-triple",
            "alh-property-assertion", "alh-quotation",
            "nbmem-project-involvement", "nbmem-tool-familiarity",
            "nbmem-relationship-context", "nbmem-fact-evidence", "nbmem-entity-alias",
        }
        entities = {k: v for k, v in entities.items()
                    if k.startswith(prefix + "-") or k == prefix or k in core_types}
        relations = {k: v for k, v in relations.items()
                    if k.startswith(prefix + "-") or k == prefix or k in core_rels}

    result = {"source": "live", "entities": entities, "relations": relations}

    # Add embedding index
    result["embedding_index"] = _get_embedding_index()

    # Add namespace audit if requested
    if audit_mode:
        result["namespace_audit"] = _run_namespace_audit(entities, relations)

    print(json.dumps({"success": True, **result}, default=str))


def _describe_schema_from_files(skill_filter, full_mode):
    """Describe schema by parsing .tql files directly."""
    try:
        from src.skillful_alhazen.utils.schema_diff import parse_tql
    except ImportError:
        return {"error": "schema_diff module not available"}

    tql_files = []
    base_schema = os.path.join(_PROJECT_ROOT, "local_resources", "typedb", "alhazen_notebook.tql")
    if os.path.exists(base_schema):
        tql_files.append(("core", base_schema))

    # Discover skill schemas
    local_skills_dir = os.path.join(_PROJECT_ROOT, "local_skills")
    if os.path.isdir(local_skills_dir):
        for skill_name in sorted(os.listdir(local_skills_dir)):
            schema_path = os.path.join(local_skills_dir, skill_name, "schema.tql")
            if os.path.exists(schema_path):
                if skill_filter and skill_name != skill_filter:
                    continue
                tql_files.append((skill_name, schema_path))

    entities = {}
    relations = {}
    for source_name, path in tql_files:
        try:
            parsed = parse_tql(path)
            for type_name, type_info in parsed.items():
                kind = getattr(type_info, "kind", str(type(type_info).__name__))
                entry = {
                    "source": source_name,
                    "parent": getattr(type_info, "parent", None),
                    "owns": sorted(getattr(type_info, "owns", [])),
                    "plays": sorted(getattr(type_info, "plays", [])),
                }
                if "entity" in str(kind).lower() or "Entity" in str(kind):
                    entities[type_name] = entry
                elif "relation" in str(kind).lower() or "Relation" in str(kind):
                    relations[type_name] = entry
        except Exception as exc:
            entities[f"_parse_error_{source_name}"] = {"error": str(exc)}

    return {"entities": entities, "relations": relations, "source": "files"}


def _get_embedding_index():
    """Read embedding_registry.json and check Qdrant collection status."""
    registry_path = os.path.join(_SKILL_DIR, "embedding_registry.json")
    if not os.path.exists(registry_path):
        return {"error": "embedding_registry.json not found"}

    try:
        with open(registry_path) as f:
            registry = json.load(f)
    except Exception as exc:
        return {"error": str(exc)}

    collections = registry.get("collections", {})
    result = {}
    for coll_name, coll_info in collections.items():
        entry = dict(coll_info)
        # Try to get point count from Qdrant
        try:
            import urllib.request
            qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            qdrant_port = os.getenv("QDRANT_PORT", "6333")
            url = f"http://{qdrant_host}:{qdrant_port}/collections/{coll_name}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                if data.get("result"):
                    entry["point_count"] = data["result"].get("points_count", 0)
                    entry["status"] = data["result"].get("status", "unknown")
        except Exception:
            entry["status"] = "unreachable"
        result[coll_name] = entry

    return result


def _run_namespace_audit(entities, relations):
    """Audit entity namespaces against skill registry."""
    CORE_TYPES = {
        "alh-identifiable-entity", "alh-domain-thing", "alh-collection",
        "alh-information-content-entity", "alh-artifact", "alh-fragment", "alh-note",
        "nbmem-memory-claim-note", "alh-episode", "alh-agent", "alh-ai-agent", "alh-person",
        "nbmem-operator-user", "alh-author", "alh-organization", "alh-interaction",
    }
    KNOWN_PREFIXES = [
        "trec",    # was tech-recon
        "jhunt",   # was jobhunt
        "sltrend", # was trend
        "scilit", "dm", "slog", "nbmem", "alh",
    ]

    # Group entities by namespace prefix
    namespaces = {}
    for etype in entities:
        if etype in CORE_TYPES:
            ns = "core"
        else:
            ns = "unknown"
            for prefix in KNOWN_PREFIXES:
                if etype.startswith(prefix + "-") or etype == prefix:
                    ns = prefix
                    break
        namespaces.setdefault(ns, []).append(etype)

    # Read skills-registry.yaml for skill-to-namespace mapping
    registry_path = os.path.join(_PROJECT_ROOT, "skills-registry.yaml")
    skill_ns_map = {}
    if os.path.exists(registry_path):
        try:
            import yaml
            with open(registry_path) as f:
                reg = yaml.safe_load(f)
            schema_map = reg.get("schema_map", {}).get("namespaces", {})
            for ns_prefix, info in schema_map.items():
                skill_ns_map[ns_prefix] = info.get("skill", "unknown")
        except Exception:
            pass

    audit = {}
    for ns, types in namespaces.items():
        skill = skill_ns_map.get(ns, "core" if ns == "core" else "unmapped")
        instances = sum(entities.get(t, {}).get("instance_count", 0) for t in types)
        audit[ns] = {
            "skill": skill,
            "types": sorted(types),
            "type_count": len(types),
            "instances": instances,
            "status": "mapped" if skill != "unmapped" else "unmapped",
        }

    return audit


def query_typeql(args):
    """Execute a raw TypeQL query and return results."""
    typeql = args.typeql
    mode = getattr(args, "mode", "read") or "read"
    limit = int(getattr(args, "limit", 50) or 50)

    tx_type = TransactionType.WRITE if mode == "write" else TransactionType.READ

    try:
        with get_driver() as driver:
            with driver.transaction(TYPEDB_DATABASE, tx_type) as tx:
                results = list(tx.query(typeql).resolve())
                if mode == "write":
                    tx.commit()
        # Apply limit
        results = results[:limit]
        print(json.dumps({"success": True, "results": results, "count": len(results)}, default=str))
    except Exception as exc:
        print(json.dumps({
            "success": False,
            "error": str(exc),
            "query": typeql,
            "mode": mode,
        }))


def search_semantic(args):
    """Search Qdrant vector collections using semantic similarity."""
    query_text = args.query
    collection = getattr(args, "collection", None)
    limit = int(getattr(args, "limit", 10) or 10)
    threshold = float(getattr(args, "threshold", 0.0) or 0.0)

    # Load embedding registry
    registry_path = os.path.join(_SKILL_DIR, "embedding_registry.json")
    if not os.path.exists(registry_path):
        print(json.dumps({"success": False, "error": "embedding_registry.json not found"}))
        return

    with open(registry_path) as f:
        registry = json.load(f)

    collections_info = registry.get("collections", {})

    # Determine which collections to search
    if collection:
        if collection not in collections_info:
            print(json.dumps({"success": False, "error": f"Unknown collection: {collection}. Available: {list(collections_info.keys())}"}))
            return
        search_collections = [collection]
    else:
        search_collections = list(collections_info.keys())

    # Embed query
    try:
        from src.skillful_alhazen.utils.embeddings import embed_texts
        query_vector = embed_texts([query_text])[0]
    except ImportError:
        print(json.dumps({"success": False, "error": "embeddings module not available. Install voyage-ai and set VOYAGE_API_KEY."}))
        return
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"Embedding failed: {exc}"}))
        return

    # Search Qdrant
    try:
        from qdrant_client import QdrantClient
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=10)
    except ImportError:
        print(json.dumps({"success": False, "error": "qdrant-client not installed"}))
        return
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"Qdrant connection failed: {exc}"}))
        return

    all_results = []
    for coll_name in search_collections:
        try:
            hits = client.search(
                collection_name=coll_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=threshold if threshold > 0 else None,
            )
            coll_info = collections_info.get(coll_name, {})
            for hit in hits:
                entry = {
                    "score": hit.score,
                    "collection": coll_name,
                    "entity_type": coll_info.get("entity_type", "unknown"),
                    "id": str(hit.id),
                }
                if hit.payload:
                    entry["payload"] = hit.payload
                all_results.append(entry)
        except Exception as exc:
            all_results.append({
                "collection": coll_name,
                "error": str(exc),
            })

    # Sort all results by score descending, apply limit
    scored = [r for r in all_results if "score" in r]
    errors = [r for r in all_results if "error" in r]
    scored.sort(key=lambda r: r["score"], reverse=True)
    scored = scored[:limit]

    print(json.dumps({
        "success": True,
        "query": query_text,
        "results": scored,
        "errors": errors if errors else None,
        "count": len(scored),
    }, default=str))


def merge_entities(args):
    """Create an nbmem-entity-alias relation between canonical and alias entity."""
    canonical_id = escape_string(args.canonical)
    alias_id = escape_string(args.alias)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            q = f'''
            match
                $c isa alh-identifiable-entity, has id "{canonical_id}";
                $a isa alh-identifiable-entity, has id "{alias_id}";
            insert (primary-entity: $c, aliased-entity: $a) isa nbmem-entity-alias'''
            # Add optional metadata
            desc = getattr(args, "description", None)
            conf = getattr(args, "confidence", None)
            if desc:
                q += f', has description "{escape_string(desc)}"'
            if conf is not None:
                q += f", has confidence {float(conf)}"
            q += ";"
            tx.query(q).resolve()
            tx.commit()

    print(json.dumps({"success": True, "canonical": canonical_id, "alias": alias_id}))


def unmerge_entities(args):
    """Remove an nbmem-entity-alias relation between canonical and alias entity."""
    canonical_id = escape_string(args.canonical)
    alias_id = escape_string(args.alias)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match
                $c isa alh-identifiable-entity, has id "{canonical_id}";
                $a isa alh-identifiable-entity, has id "{alias_id}";
                $r isa nbmem-entity-alias (primary-entity: $c, aliased-entity: $a);
            delete $r;
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "canonical": canonical_id, "alias": alias_id, "action": "unmerged"}))


def list_aliases(args):
    """List nbmem-entity-alias relations, optionally filtered by entity ID."""
    entity_id = getattr(args, "id", None)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if entity_id:
                eid = escape_string(entity_id)
                # Check both directions: entity is canonical or aliased
                results = []
                for direction_q in [
                    f'''match
                        $e isa alh-identifiable-entity, has id "{eid}";
                        (primary-entity: $e, aliased-entity: $other) isa nbmem-entity-alias;
                    fetch {{ "other-id": $other.id, "other-name": $other.name }};''',
                    f'''match
                        $e isa alh-identifiable-entity, has id "{eid}";
                        (primary-entity: $other, aliased-entity: $e) isa nbmem-entity-alias;
                    fetch {{ "other-id": $other.id, "other-name": $other.name }};''',
                ]:
                    try:
                        results.extend(list(tx.query(direction_q).resolve()))
                    except Exception:
                        pass
            else:
                results = list(tx.query('''
                match
                    (primary-entity: $c, aliased-entity: $a) isa nbmem-entity-alias;
                fetch {
                    "canonical-id": $c.id,
                    "canonical-name": $c.name,
                    "alias-id": $a.id,
                    "alias-name": $a.name
                };
                ''').resolve())

    print(json.dumps({"success": True, "aliases": results}, default=str))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Agentic Memory CLI")
    subparsers = parser.add_subparsers(dest="command")

    # --- Person / Context ---
    p = subparsers.add_parser("create-operator", help="Create an nbmem-operator-user")
    p.add_argument("--name", required=True)
    p.add_argument("--given-name")
    p.add_argument("--family-name")
    p.add_argument("--identity", help="Identity summary prose")
    p.add_argument("--role", help="Role description prose")

    p = subparsers.add_parser("update-context-domain", help="Update a personal context domain")
    p.add_argument("--person", required=True, help="Person ID")
    p.add_argument("--domain", required=True,
                   choices=["identity", "role", "style", "goals", "preferences", "expertise"])
    p.add_argument("--content", required=True)

    p = subparsers.add_parser("get-context", help="Get personal context for a person")
    p.add_argument("--person", required=True)

    p = subparsers.add_parser("link-project", help="Link person to a collection")
    p.add_argument("--person", required=True)
    p.add_argument("--collection", required=True)

    p = subparsers.add_parser("link-tool", help="Link person to a alh-domain-thing")
    p.add_argument("--person", required=True)
    p.add_argument("--entity", required=True, help="Domain-thing ID")

    p = subparsers.add_parser("link-person", help="Create nbmem-relationship-context between two persons")
    p.add_argument("--from-person", required=True)
    p.add_argument("--to-person", required=True)
    p.add_argument("--context", help="Description of the relationship")

    p = subparsers.add_parser("list-persons", help="List all person entities")

    # --- Memory Claim Notes ---
    p = subparsers.add_parser("consolidate", help="Create a nbmem-memory-claim-note")
    p.add_argument("--content", required=True)
    p.add_argument("--subject", required=True, help="Entity ID this claim is about")
    p.add_argument("--fact-type", default="knowledge",
                   help="Type: knowledge | decision | goal | preference | schema-gap | ...")
    p.add_argument("--confidence", type=float, default=0.8)
    p.add_argument("--valid-until", help="ISO datetime when claim expires")
    p.add_argument("--source-episode", help="Episode ID this was derived from")
    p.add_argument("--source-note", help="Note ID this was derived from")

    p = subparsers.add_parser("recall", help="Get nbmem-memory-claim-notes about an entity")
    p.add_argument("--subject", required=True)

    p = subparsers.add_parser("recall-person", help="Get all nbmem-memory-claim-notes about a person")
    p.add_argument("--person", required=True)

    p = subparsers.add_parser("invalidate", help="Invalidate a nbmem-memory-claim-note")
    p.add_argument("claim_id", help="Memory-claim-note ID")

    p = subparsers.add_parser("list-claims", help="List nbmem-memory-claim-notes")
    p.add_argument("--fact-type")
    p.add_argument("--person")
    p.add_argument("--limit", type=int, default=50)

    # --- Episodes ---
    p = subparsers.add_parser("create-episode", help="Create an episode entity")
    p.add_argument("--skill", help="Source skill name")
    p.add_argument("--summary", required=True, help="Narrative of what happened")
    p.add_argument("--session-id", help="Session ID to link to skilllog-session")

    p = subparsers.add_parser("link-episode", help="Link episode to graph entities")
    p.add_argument("--episode", required=True)
    p.add_argument("--entities", required=True, help="Comma-separated entity IDs")
    p.add_argument("--operation-type", help="Operation type (e.g. created, updated, analyzed)")
    p.add_argument("--rationale", help="Why this operation was performed")

    p = subparsers.add_parser("show-episode", help="Show episode details")
    p.add_argument("episode_id", help="Episode ID")

    p = subparsers.add_parser("list-episodes", help="List recent episodes")
    p.add_argument("--skill")
    p.add_argument("--limit", type=int, default=20)

    # --- Schema, search, and entity management ---
    p = subparsers.add_parser("describe-schema", help="Describe TypeDB schema")
    p.add_argument("--skill", help="Filter by skill namespace prefix")
    p.add_argument("--full", action="store_true", help="Include instance counts")
    p.add_argument("--audit", action="store_true", help="Run namespace audit (implies --full)")
    p.add_argument("--source", choices=["live", "files"], default="live",
                   help="Schema source: live TypeDB or .tql files")

    p = subparsers.add_parser("query", help="Execute a raw TypeQL query")
    p.add_argument("--typeql", required=True, help="TypeQL query string")
    p.add_argument("--mode", choices=["read", "write"], default="read")
    p.add_argument("--limit", type=int, default=50)

    p = subparsers.add_parser("search", help="Semantic search across Qdrant collections")
    p.add_argument("--query", required=True, help="Search query text")
    p.add_argument("--collection", help="Qdrant collection name (default: search all)")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--threshold", type=float, default=0.0, help="Minimum similarity score")

    p = subparsers.add_parser("merge-entities", help="Create nbmem-entity-alias relation")
    p.add_argument("--canonical", required=True, help="Canonical entity ID")
    p.add_argument("--alias", required=True, help="Alias entity ID")
    p.add_argument("--description", help="Description of the alias relationship")
    p.add_argument("--confidence", type=float, help="Confidence score")

    p = subparsers.add_parser("unmerge-entities", help="Remove nbmem-entity-alias relation")
    p.add_argument("--canonical", required=True, help="Canonical entity ID")
    p.add_argument("--alias", required=True, help="Alias entity ID")

    p = subparsers.add_parser("list-aliases", help="List nbmem-entity-alias relations")
    p.add_argument("--id", help="Entity ID to find aliases for")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    commands = {
        "create-operator": create_operator,
        "update-context-domain": update_context_domain,
        "get-context": get_context,
        "link-project": link_project,
        "link-tool": link_tool,
        "link-person": link_person,
        "list-persons": list_persons,
        "consolidate": consolidate,
        "recall": recall,
        "recall-person": recall_person,
        "invalidate": invalidate,
        "list-claims": list_claims,
        "create-episode": create_episode,
        "link-episode": link_episode,
        "show-episode": show_episode,
        "list-episodes": list_episodes,
        "describe-schema": describe_schema,
        "query": query_typeql,
        "search": search_semantic,
        "merge-entities": merge_entities,
        "unmerge-entities": unmerge_entities,
        "list-aliases": list_aliases,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
