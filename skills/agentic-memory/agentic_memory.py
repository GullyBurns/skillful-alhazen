#!/usr/bin/env python3
"""
Agentic Memory CLI - TypeDB-backed two-tier memory architecture.

Manages persons (operator-users + application-users) with personal context,
memory-claim-notes (crystallized semantic propositions), and session episodes.

Usage:
    python skills/agentic-memory/agentic_memory.py <command> [options]

Person / Context commands:
    create-operator        Create an operator-user with personal context
    update-context-domain  Update one personal context domain for a person
    get-context            Get formatted personal context for a person (JSON)
    link-project           Link a person to a collection (project-involvement)
    link-tool              Link a person to a domain-thing (tool-familiarity)
    link-person            Create a relationship-context between two persons
    list-persons           List all person entities

Memory Claim Note commands:
    consolidate            Create a memory-claim-note about an entity
    recall                 Get memory-claim-notes about an entity
    recall-person          Get all memory-claim-notes about a person
    invalidate             Invalidate a memory-claim-note (set valid-until to now)
    list-claims            List memory-claim-notes with optional filters

Episode commands:
    create-episode         Create an episode entity
    link-episode           Link an episode to graph entities via episode-mention
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
    """Create an operator-user with initial personal context."""
    eid = generate_id("op")
    ts = get_timestamp()
    name_esc = escape_string(args.name)
    given = escape_string(args.given_name or "")
    family = escape_string(args.family_name or "")
    identity = escape_string(args.identity or "")
    role = escape_string(args.role or "")

    query = f'''
    insert $p isa operator-user,
        has id "{eid}",
        has name "{name_esc}",
        has created-at {ts};
    '''
    if given:
        query = query.rstrip().rstrip(";") + f',\n        has given-name "{given}";'
    if family:
        query = query.rstrip().rstrip(";") + f',\n        has family-name "{family}";'
    if identity:
        query = query.rstrip().rstrip(";") + f',\n        has identity-summary "{identity}";'
    if role:
        query = query.rstrip().rstrip(";") + f',\n        has role-description "{role}";'
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
        "identity": "identity-summary",
        "role": "role-description",
        "style": "communication-style",
        "goals": "goals-summary",
        "preferences": "preferences-summary",
        "expertise": "domain-expertise",
    }
    attr = domain_map.get(args.domain)
    if not attr:
        print(json.dumps({"success": False, "error": f"Unknown domain '{args.domain}'. Choose: {list(domain_map)}"}))
        return

    content_esc = escape_string(args.content)
    pid = escape_string(args.person)
    ts = get_timestamp()

    # Delete old value then insert new one
    with get_driver() as driver:
        # First check the old value exists and delete it
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            check_q = f'''
            match $p isa identifiable-entity, has id "{pid}", has {attr} $v;
            delete has $v of $p;
            '''
            try:
                tx.query(check_q).resolve()
                tx.commit()
            except Exception:
                pass  # No existing value -- that is fine

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match $p isa identifiable-entity, has id "{pid}";
            insert $p has {attr} "{content_esc}", has updated-at {ts};
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "person": pid, "domain": args.domain}))


def get_context(args):
    """Retrieve formatted personal context for a person."""
    pid = escape_string(args.person)

    domain_attrs = [
        ("identity", "identity-summary"),
        ("role", "role-description"),
        ("style", "communication-style"),
        ("goals", "goals-summary"),
        ("preferences", "preferences-summary"),
        ("expertise", "domain-expertise"),
    ]

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get basic person info
            person_q = f'''
            match $p isa identifiable-entity, has id "{pid}";
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "given-name": $p.given-name,
                "family-name": $p.family-name,
                "identity-summary": $p.identity-summary,
                "role-description": $p.role-description,
                "communication-style": $p.communication-style,
                "goals-summary": $p.goals-summary,
                "preferences-summary": $p.preferences-summary,
                "domain-expertise": $p.domain-expertise
            }};
            '''
            persons = list(tx.query(person_q).resolve())
            if not persons:
                print(json.dumps({"success": False, "error": f"Person not found: {pid}"}))
                return

            ctx = persons[0]

            # Get linked projects (project-involvement)
            proj_q = f'''
            match
                $p isa identifiable-entity, has id "{pid}";
                (participant: $p, project: $c) isa project-involvement;
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

            # Get linked tools (tool-familiarity)
            tool_q = f'''
            match
                $p isa identifiable-entity, has id "{pid}";
                (practitioner: $p, tool: $t) isa tool-familiarity;
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
    """Create a project-involvement relation between a person and a collection."""
    pid = escape_string(args.person)
    cid = escape_string(args.collection)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match
                $p isa identifiable-entity, has id "{pid}";
                $c isa collection, has id "{cid}";
            insert (participant: $p, project: $c) isa project-involvement;
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "person": pid, "collection": cid}))


def link_tool(args):
    """Create a tool-familiarity relation between a person and a domain-thing."""
    pid = escape_string(args.person)
    tid = escape_string(args.entity)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match
                $p isa identifiable-entity, has id "{pid}";
                $t isa domain-thing, has id "{tid}";
            insert (practitioner: $p, tool: $t) isa tool-familiarity;
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "person": pid, "tool": tid}))


def link_person(args):
    """Create a relationship-context between two persons."""
    from_id = escape_string(args.from_person)
    to_id = escape_string(args.to_person)
    desc = escape_string(args.context or "")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            q = f'''
            match
                $a isa identifiable-entity, has id "{from_id}";
                $b isa identifiable-entity, has id "{to_id}";
            insert (from-person: $a, to-person: $b) isa relationship-context
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
            match $p isa person;
            fetch {
                "id": $p.id,
                "name": $p.name,
                "given-name": $p.given-name,
                "family-name": $p.family-name
            };
            ''').resolve())

    print(json.dumps({"success": True, "persons": results}, default=str))


# ---------------------------------------------------------------------------
# Memory Claim Note commands
# ---------------------------------------------------------------------------

def consolidate(args):
    """Create a memory-claim-note about an entity."""
    nid = generate_id("mcn")
    ts = get_timestamp()
    content_esc = escape_string(args.content)
    subject_id = escape_string(args.subject)
    fact_type = escape_string(args.fact_type or "knowledge")
    confidence = float(args.confidence) if args.confidence else 0.8

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Insert the memory-claim-note
            q = f'''
            insert $n isa memory-claim-note,
                has id "{nid}",
                has content "{content_esc}",
                has fact-type "{fact_type}",
                has confidence {confidence},
                has created-at {ts};
            '''
            if args.valid_until:
                q = q.rstrip().rstrip(";") + f',\n                has valid-until {args.valid_until};'
            if not q.rstrip().endswith(";"):
                q = q.rstrip() + ";"
            tx.query(q).resolve()
            tx.commit()

        # Link to subject via aboutness
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match
                $n isa note, has id "{nid}";
                $e isa identifiable-entity, has id "{subject_id}";
            insert (note: $n, subject: $e) isa aboutness;
            ''').resolve()
            tx.commit()

        # Link provenance: derive from source episode or note if given
        if args.source_episode or args.source_note:
            src_id = escape_string(args.source_episode or args.source_note)
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''
                match
                    $n isa note, has id "{nid}";
                    $src isa identifiable-entity, has id "{src_id}";
                insert (derived: $n, source: $src) isa fact-evidence;
                ''').resolve()
                tx.commit()

    print(json.dumps({"success": True, "id": nid, "fact_type": fact_type}))


def recall(args):
    """Get memory-claim-notes about an entity."""
    subject_id = escape_string(args.subject)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
            match
                $n isa memory-claim-note;
                $e isa identifiable-entity, has id "{subject_id}";
                (note: $n, subject: $e) isa aboutness;
            fetch {{
                "id": $n.id,
                "content": $n.content,
                "fact-type": $n.fact-type,
                "confidence": $n.confidence,
                "created-at": $n.created-at,
                "valid-until": $n.valid-until
            }};
            ''').resolve())

    print(json.dumps({"success": True, "claims": results}, default=str))


def recall_person(args):
    """Get all memory-claim-notes about a person."""
    args.subject = args.person
    recall(args)


def invalidate(args):
    """Set valid-until to now for a memory-claim-note."""
    nid = escape_string(args.claim_id)
    ts = get_timestamp()

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
            match $n isa identifiable-entity, has id "{nid}";
            insert $n has valid-until {ts};
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "id": nid, "invalidated_at": ts}))


def list_claims(args):
    """List memory-claim-notes with optional filters."""
    filters = ""
    if args.fact_type:
        ft = escape_string(args.fact_type)
        filters += f'\n                $n has fact-type "{ft}";'
    if args.person:
        pid = escape_string(args.person)
        filters += f'''
                $e isa identifiable-entity, has id "{pid}";
                (note: $n, subject: $e) isa aboutness;'''

    limit = int(args.limit) if args.limit else 50

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
            match
                $n isa memory-claim-note;{filters}
            fetch {{
                "id": $n.id,
                "content": $n.content,
                "fact-type": $n.fact-type,
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
            insert $e isa episode,
                has id "{eid}",
                has content "{summary}",
                has source-skill "{skill}",
                has session-id "{session_id}",
                has created-at {ts};
            ''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "id": eid, "session_id": session_id}))


def link_episode(args):
    """Add episode-mention relations linking an episode to graph entities."""
    ep_id = escape_string(args.episode)
    entity_ids = [e.strip() for e in args.entities.split(",") if e.strip()]

    results = []
    with get_driver() as driver:
        for eid in entity_ids:
            eid_esc = escape_string(eid)
            try:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''
                    match
                        $ep isa episode, has id "{ep_id}";
                        $e isa identifiable-entity, has id "{eid_esc}";
                    insert (session: $ep, subject: $e) isa episode-mention;
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
            match $ep isa episode, has id "{ep_id}";
            fetch {{
                "id": $ep.id,
                "content": $ep.content,
                "source-skill": $ep.source-skill,
                "session-id": $ep.session-id,
                "created-at": $ep.created-at
            }};
            ''').resolve())

            if not eps:
                print(json.dumps({"success": False, "error": f"Episode not found: {ep_id}"}))
                return

            entities = list(tx.query(f'''
            match
                $ep isa episode, has id "{ep_id}";
                (session: $ep, subject: $e) isa episode-mention;
                $e has id $eid, has name $ename;
            fetch {{
                "id": $eid,
                "name": $ename
            }};
            ''').resolve())

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
        skill_filter = f'\n                $ep has source-skill "{sf}";'

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
            match
                $ep isa episode;{skill_filter}
            fetch {{
                "id": $ep.id,
                "content": $ep.content,
                "source-skill": $ep.source-skill,
                "session-id": $ep.session-id,
                "created-at": $ep.created-at
            }};
            ''').resolve())

    # Sort by created-at descending (most recent first), apply limit
    results_sorted = sorted(results, key=lambda r: str(r.get("created-at", "")), reverse=True)
    print(json.dumps({"success": True, "episodes": results_sorted[:limit]}, default=str))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Agentic Memory CLI")
    subparsers = parser.add_subparsers(dest="command")

    # --- Person / Context ---
    p = subparsers.add_parser("create-operator", help="Create an operator-user")
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

    p = subparsers.add_parser("link-tool", help="Link person to a domain-thing")
    p.add_argument("--person", required=True)
    p.add_argument("--entity", required=True, help="Domain-thing ID")

    p = subparsers.add_parser("link-person", help="Create relationship-context between two persons")
    p.add_argument("--from-person", required=True)
    p.add_argument("--to-person", required=True)
    p.add_argument("--context", help="Description of the relationship")

    p = subparsers.add_parser("list-persons", help="List all person entities")

    # --- Memory Claim Notes ---
    p = subparsers.add_parser("consolidate", help="Create a memory-claim-note")
    p.add_argument("--content", required=True)
    p.add_argument("--subject", required=True, help="Entity ID this claim is about")
    p.add_argument("--fact-type", default="knowledge",
                   help="Type: knowledge | decision | goal | preference | schema-gap | ...")
    p.add_argument("--confidence", type=float, default=0.8)
    p.add_argument("--valid-until", help="ISO datetime when claim expires")
    p.add_argument("--source-episode", help="Episode ID this was derived from")
    p.add_argument("--source-note", help="Note ID this was derived from")

    p = subparsers.add_parser("recall", help="Get memory-claim-notes about an entity")
    p.add_argument("--subject", required=True)

    p = subparsers.add_parser("recall-person", help="Get all memory-claim-notes about a person")
    p.add_argument("--person", required=True)

    p = subparsers.add_parser("invalidate", help="Invalidate a memory-claim-note")
    p.add_argument("claim_id", help="Memory-claim-note ID")

    p = subparsers.add_parser("list-claims", help="List memory-claim-notes")
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

    p = subparsers.add_parser("show-episode", help="Show episode details")
    p.add_argument("episode_id", help="Episode ID")

    p = subparsers.add_parser("list-episodes", help="List recent episodes")
    p.add_argument("--skill")
    p.add_argument("--limit", type=int, default=20)

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
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
