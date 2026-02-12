#!/usr/bin/env python3
"""
Schema Migration: Separate Things from ICEs

Migrates the TypeDB database from the old schema (where everything inherits from
information-content-entity) to the new schema with identifiable-entity as the shared
root and separate thing/ICE hierarchies.

Key changes:
- research-item removed; subtypes now sub thing
- collection now sub identifiable-entity (was sub information-content-entity)
- your-skill now sub thing (was sub entity), gains id @key
- abstract-text and publication-date moved from research-item to per-type ownership

Strategy: Export all data via TypeDB queries, transform, reload with new schema.
The binary export format requires matching schema, so we extract data as structured
dicts and regenerate insert statements.

Usage:
    # Export current data, transform, and prepare for reimport
    uv run python local_resources/typedb/migrate_schema_v2.py export --output exports/migration_data.json

    # After loading new schema, import transformed data
    uv run python local_resources/typedb/migrate_schema_v2.py import --input exports/migration_data.json

    # Or do it all in one shot (drops and recreates database)
    uv run python local_resources/typedb/migrate_schema_v2.py migrate
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

try:
    from typedb.driver import SessionType, TransactionType, TypeDB
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print("Error: typedb-driver not installed", file=sys.stderr)
    sys.exit(1)


# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")

# Path to schema files (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
CORE_SCHEMA = PROJECT_ROOT / "local_resources" / "typedb" / "alhazen_notebook.tql"
NAMESPACE_DIR = PROJECT_ROOT / "local_resources" / "typedb" / "namespaces"


def get_driver():
    return TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")


def slugify(s):
    """Convert a string to a URL-safe slug."""
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s)
    return s


def escape_string(s):
    """Escape special characters for TypeQL strings."""
    if s is None:
        return ""
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def extract_value(attr_data):
    """Extract value from TypeDB fetch result attribute."""
    if isinstance(attr_data, list):
        if len(attr_data) == 0:
            return None
        if len(attr_data) == 1:
            return attr_data[0].get("value")
        # Multiple values (e.g., keywords)
        return [item.get("value") for item in attr_data]
    if isinstance(attr_data, dict):
        return attr_data.get("value")
    return attr_data


def parse_entity(result, var_name="$e"):
    """Parse a TypeDB fetch result into a flat dict."""
    entity_data = result.get(var_name, {})
    parsed = {}
    for attr_name, attr_value in entity_data.items():
        if attr_name == "type":
            parsed["_type"] = attr_value.get("label") if isinstance(attr_value, dict) else attr_value
        else:
            val = extract_value(attr_value)
            if val is not None:
                parsed[attr_name] = val
    return parsed


# ============================================================================
# Export Phase: Read all data from old schema
# ============================================================================

def export_entities(driver, database):
    """Export all entities with their attributes."""
    entities = {}

    # Export all identifiable entities (everything that has an id)
    # We query by the old root type: information-content-entity
    # Plus separate queries for types that don't inherit from ICE (your-skill, agent, etc.)

    entity_queries = [
        # All ICE subtypes (collection, research-item subtypes, artifact, fragment, note, etc.)
        ('match $e isa information-content-entity, has id $id; '
         'fetch $e: id, name, description, iri, content, content-hash, format, token-count, '
         'cache-path, mime-type, file-size, created-at, updated-at, provenance, source-uri, license;',
         "$e"),

        # your-skill (sub entity, no id @key in old schema)
        ('match $e isa your-skill; '
         'fetch $e: skill-name, skill-level, last-updated, description;',
         "$e"),

        # agent
        ('match $e isa agent, has id $id; '
         'fetch $e: id, name, iri, agent-type, model-name;',
         "$e"),

        # organization
        ('match $e isa organization, has id $id; '
         'fetch $e: id, name, iri;',
         "$e"),

        # vocabulary, vocabulary-type, vocabulary-property, tag
        ('match $e isa vocabulary, has id $id; fetch $e: id, name, iri, description;', "$e"),
        ('match $e isa vocabulary-type, has id $id; fetch $e: id, name, schema-org-uri, wikidata-qid, description;', "$e"),
        ('match $e isa tag, has id $id; fetch $e: id, name, description;', "$e"),
    ]

    with driver.session(database, SessionType.DATA) as session:
        # First, get detailed type info for each entity via get queries
        # We need the actual concrete type, not just ICE
        print("Exporting entity types...", file=sys.stderr)

        # Get all entities with their concrete types using get query
        with session.transaction(TransactionType.READ) as tx:
            # Get type labels for all entities with id
            results = list(tx.query.get(
                'match $e isa entity, has id $id; get $e, $id;'
            ))
            for r in results:
                entity = r.get("e")
                id_attr = r.get("id")
                if entity and id_attr:
                    eid = id_attr.get_value() if hasattr(id_attr, 'get_value') else str(id_attr)
                    etype = entity.get_type().get_label().name if hasattr(entity.get_type().get_label(), 'name') else str(entity.get_type().get_label())
                    entities[eid] = {"_type": etype, "id": eid}

        print(f"  Found {len(entities)} entities with IDs", file=sys.stderr)

        # Now fetch detailed attributes for each entity type group
        # Collections
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa collection, has id $id; '
                'fetch $e: id, name, description, logical-query, is-extensional, created-at, source-uri;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # Things (research-items) - get all attributes including namespace-specific ones
        # scilit-paper
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa scilit-paper, has id $id; '
                'fetch $e: id, name, description, abstract-text, publication-date, source-uri, '
                'doi, pmid, pmcid, arxiv-id, journal-name, journal-volume, journal-issue, '
                'page-range, publication-year, keyword, created-at, content;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # jobhunt-position
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa jobhunt-position, has id $id; '
                'fetch $e: id, name, description, source-uri, job-url, short-name, salary-range, '
                'location, remote-policy, team-size, deadline, priority-level, created-at;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # jobhunt-company
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa jobhunt-company, has id $id; '
                'fetch $e: id, name, description, source-uri, company-url, linkedin-url, location, created-at;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # jobhunt-learning-resource
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa jobhunt-learning-resource, has id $id; '
                'fetch $e: id, name, description, source-uri, resource-type, resource-url, '
                'estimated-hours, completion-status, created-at;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # your-skill (no id in old schema - needs special handling)
        print("Exporting your-skill entities...", file=sys.stderr)
        your_skills = []
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa your-skill; '
                'fetch $e: skill-name, skill-level, last-updated, description;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                parsed["_type"] = "your-skill"
                # Generate an id from skill-name
                skill_name = parsed.get("skill-name", "unknown")
                parsed["id"] = f"skill-{slugify(skill_name)}"
                your_skills.append(parsed)

        print(f"  Found {len(your_skills)} your-skill entities", file=sys.stderr)

        # Artifacts (all subtypes)
        artifact_types = [
            "artifact", "jobhunt-job-description", "jobhunt-resume",
            "jobhunt-cover-letter", "jobhunt-company-page",
            "scilit-jats-fulltext", "scilit-pdf-fulltext",
            "scilit-citation-record", "scilit-supplementary",
            "scilit-structured-data",
        ]
        for atype in artifact_types:
            with session.transaction(TransactionType.READ) as tx:
                try:
                    results = list(tx.query.fetch(
                        f'match $e isa {atype}, has id $id; '
                        f'fetch $e: id, name, description, content, content-hash, format, '
                        f'source-uri, cache-path, mime-type, file-size, created-at;'
                    ))
                    for r in results:
                        parsed = parse_entity(r, "$e")
                        eid = parsed.get("id")
                        if eid and eid in entities:
                            entities[eid].update(parsed)
                except Exception:
                    pass  # Type may not have instances

        # Fragments (all subtypes)
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa fragment, has id $id; '
                'fetch $e: id, name, description, content, format, offset, length, created-at;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # Notes (all subtypes)
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa note, has id $id; '
                'fetch $e: id, name, description, content, format, confidence, created-at;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # Jobhunt-specific notes with extra attributes
        note_types_with_extras = {
            "jobhunt-application-note": "application-status, applied-date, response-date",
            "jobhunt-interview-note": "interview-date",
            "jobhunt-fit-analysis-note": "fit-score, fit-summary",
            "jobhunt-interaction-note": "interaction-type, interaction-date",
        }
        for ntype, extra_attrs in note_types_with_extras.items():
            with session.transaction(TransactionType.READ) as tx:
                try:
                    results = list(tx.query.fetch(
                        f'match $e isa {ntype}, has id $id; '
                        f'fetch $e: id, {extra_attrs};'
                    ))
                    for r in results:
                        parsed = parse_entity(r, "$e")
                        eid = parsed.get("id")
                        if eid and eid in entities:
                            entities[eid].update(parsed)
                except Exception:
                    pass

        # Jobhunt fragments with extra attributes
        with session.transaction(TransactionType.READ) as tx:
            try:
                results = list(tx.query.fetch(
                    'match $e isa jobhunt-requirement, has id $id; '
                    'fetch $e: id, skill-name, skill-level, your-level;'
                ))
                for r in results:
                    parsed = parse_entity(r, "$e")
                    eid = parsed.get("id")
                    if eid and eid in entities:
                        entities[eid].update(parsed)
            except Exception:
                pass

        # Tags
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa tag, has id $id; fetch $e: id, name, description;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

        # Agents
        with session.transaction(TransactionType.READ) as tx:
            results = list(tx.query.fetch(
                'match $e isa agent, has id $id; fetch $e: id, name, iri, agent-type, model-name;'
            ))
            for r in results:
                parsed = parse_entity(r, "$e")
                eid = parsed.get("id")
                if eid and eid in entities:
                    entities[eid].update(parsed)

    return entities, your_skills


def export_relations(driver, database):
    """Export all relations."""
    relations = []

    relation_queries = [
        # collection-membership
        ('match (collection: $c, member: $m) isa collection-membership, has created-at $ca; '
         '$c has id $cid; $m has id $mid; get $cid, $mid, $ca;',
         "collection-membership", ["cid", "mid", "ca"],
         lambda r: {
             "type": "collection-membership",
             "roles": {"collection": val(r, "cid"), "member": val(r, "mid")},
             "attrs": {"created-at": val(r, "ca")},
         }),

        # representation
        ('match (artifact: $a, referent: $t) isa representation; '
         '$a has id $aid; $t has id $tid; get $aid, $tid;',
         "representation", ["aid", "tid"],
         lambda r: {
             "type": "representation",
             "roles": {"artifact": val(r, "aid"), "referent": val(r, "tid")},
         }),

        # fragmentation
        ('match (whole: $w, part: $p) isa fragmentation; '
         '$w has id $wid; $p has id $pid; get $wid, $pid;',
         "fragmentation", ["wid", "pid"],
         lambda r: {
             "type": "fragmentation",
             "roles": {"whole": val(r, "wid"), "part": val(r, "pid")},
         }),

        # aboutness
        ('match (note: $n, subject: $s) isa aboutness; '
         '$n has id $nid; $s has id $sid; get $nid, $sid;',
         "aboutness", ["nid", "sid"],
         lambda r: {
             "type": "aboutness",
             "roles": {"note": val(r, "nid"), "subject": val(r, "sid")},
         }),

        # tagging
        ('match (tagged-entity: $e, tag: $t) isa tagging; '
         '$e has id $eid; $t has id $tid; get $eid, $tid;',
         "tagging", ["eid", "tid"],
         lambda r: {
             "type": "tagging",
             "roles": {"tagged-entity": val(r, "eid"), "tag": val(r, "tid")},
         }),

        # authorship (author + work)
        ('match (author: $a, work: $w) isa authorship; '
         '$a has id $aid; $w has id $wid; get $aid, $wid;',
         "authorship", ["aid", "wid"],
         lambda r: {
             "type": "authorship",
             "roles": {"author": val(r, "aid"), "work": val(r, "wid")},
         }),

        # citation-reference
        ('match (citing-item: $c, cited-item: $d) isa citation-reference; '
         '$c has id $cid; $d has id $did; get $cid, $did;',
         "citation-reference", ["cid", "did"],
         lambda r: {
             "type": "citation-reference",
             "roles": {"citing-item": val(r, "cid"), "cited-item": val(r, "did")},
         }),

        # position-at-company
        ('match (position: $p, employer: $e) isa position-at-company; '
         '$p has id $pid; $e has id $eid; get $pid, $eid;',
         "position-at-company", ["pid", "eid"],
         lambda r: {
             "type": "position-at-company",
             "roles": {"position": val(r, "pid"), "employer": val(r, "eid")},
         }),

        # requirement-for
        ('match (requirement: $r, position: $p) isa requirement-for; '
         '$r has id $rid; $p has id $pid; get $rid, $pid;',
         "requirement-for", ["rid", "pid"],
         lambda r: {
             "type": "requirement-for",
             "roles": {"requirement": val(r, "rid"), "position": val(r, "pid")},
         }),

        # addresses-requirement
        ('match (resource: $r, requirement: $q) isa addresses-requirement; '
         '$r has id $rid; $q has id $qid; get $rid, $qid;',
         "addresses-requirement", ["rid", "qid"],
         lambda r: {
             "type": "addresses-requirement",
             "roles": {"resource": val(r, "rid"), "requirement": val(r, "qid")},
         }),

        # note-threading
        ('match (parent-note: $p, child-note: $c) isa note-threading; '
         '$p has id $pid; $c has id $cid; get $pid, $cid;',
         "note-threading", ["pid", "cid"],
         lambda r: {
             "type": "note-threading",
             "roles": {"parent-note": val(r, "pid"), "child-note": val(r, "cid")},
         }),
    ]

    with driver.session(database, SessionType.DATA) as session:
        for query, rel_type, var_names, transform in relation_queries:
            print(f"  Exporting {rel_type}...", file=sys.stderr)
            with session.transaction(TransactionType.READ) as tx:
                try:
                    results = list(tx.query.get(query))
                    for r in results:
                        try:
                            relations.append(transform(r))
                        except Exception as e:
                            print(f"    Warning: Failed to parse {rel_type}: {e}", file=sys.stderr)
                except Exception as e:
                    print(f"    Warning: Query failed for {rel_type}: {e}", file=sys.stderr)

    return relations


def val(result, var_name):
    """Extract a value from a TypeDB get query result."""
    v = result.get(var_name)
    if v is None:
        return None
    if hasattr(v, 'get_value'):
        return v.get_value()
    return str(v)


# ============================================================================
# Transform Phase
# ============================================================================

def transform_data(entities, your_skills, relations):
    """Transform exported data for the new schema.

    Key transformations:
    - your-skill entities get id @key values
    - No type renames needed (subtypes keep their names, just change parent in schema)
    - Relations referencing your-skill by skill-name need to be updated
    """
    log = []

    # Transform your-skill: add id attribute
    for skill in your_skills:
        skill_name = skill.get("skill-name", "unknown")
        new_id = f"skill-{slugify(skill_name)}"
        skill["id"] = new_id
        log.append(f"your-skill '{skill_name}' -> id '{new_id}'")

    # No entity type renames needed - the concrete types (scilit-paper, jobhunt-position, etc.)
    # keep the same names. Only their parent type changes in the schema (research-item -> thing).

    log.append(f"Total entities: {len(entities)}")
    log.append(f"Total your-skills: {len(your_skills)}")
    log.append(f"Total relations: {len(relations)}")

    return entities, your_skills, relations, log


# ============================================================================
# Import Phase: Write data into new schema
# ============================================================================

def format_attr(attr_name, value):
    """Format an attribute for TypeQL insert."""
    if value is None:
        return None

    # Skip internal metadata
    if attr_name.startswith("_"):
        return None

    # Datetime attributes
    datetime_attrs = {
        "created-at", "updated-at", "publication-date", "valid-from",
        "valid-until", "applied-date", "interview-date", "deadline",
        "response-date", "last-updated", "interaction-date",
        "operation-timestamp",
    }

    # Long attributes
    long_attrs = {
        "token-count", "file-size", "offset", "length",
        "publication-year", "estimated-hours",
    }

    # Double attributes
    double_attrs = {"confidence", "fit-score"}

    # Boolean attributes
    bool_attrs = {"is-extensional"}

    if attr_name in datetime_attrs:
        # TypeDB requires ISO format with T separator
        dt_str = str(value).replace(" ", "T")
        if "." in dt_str:
            dt_str = dt_str[:dt_str.index(".")]
        return f"has {attr_name} {dt_str}"
    elif attr_name in long_attrs:
        return f"has {attr_name} {value}"
    elif attr_name in double_attrs:
        return f"has {attr_name} {value}"
    elif attr_name in bool_attrs:
        return f"has {attr_name} {str(value).lower()}"
    else:
        # String attribute
        if isinstance(value, list):
            # Multi-valued (e.g., keywords)
            parts = []
            for v in value:
                parts.append(f'has {attr_name} "{escape_string(str(v))}"')
            return ", ".join(parts)
        return f'has {attr_name} "{escape_string(str(value))}"'


def import_entities(driver, database, entities, your_skills):
    """Import entities into the new schema."""
    imported = 0
    errors = 0

    with driver.session(database, SessionType.DATA) as session:
        # Import regular entities (those with id)
        for eid, entity in entities.items():
            etype = entity.get("_type", "entity")
            attrs = []
            for attr_name, attr_value in entity.items():
                formatted = format_attr(attr_name, attr_value)
                if formatted:
                    attrs.append(formatted)

            if not attrs:
                continue

            query = f'insert $e isa {etype}, {", ".join(attrs)};'

            with session.transaction(TransactionType.WRITE) as tx:
                try:
                    tx.query.insert(query)
                    tx.commit()
                    imported += 1
                except Exception as e:
                    errors += 1
                    print(f"  Error inserting {etype} '{eid}': {e}", file=sys.stderr)
                    # Try without problematic attributes
                    # (e.g., attributes that moved between types)

        # Import your-skill entities (now with id)
        for skill in your_skills:
            attrs = []
            for attr_name, attr_value in skill.items():
                formatted = format_attr(attr_name, attr_value)
                if formatted:
                    attrs.append(formatted)

            if not attrs:
                continue

            query = f'insert $e isa your-skill, {", ".join(attrs)};'

            with session.transaction(TransactionType.WRITE) as tx:
                try:
                    tx.query.insert(query)
                    tx.commit()
                    imported += 1
                except Exception as e:
                    errors += 1
                    print(f"  Error inserting your-skill: {e}", file=sys.stderr)

    return imported, errors


def import_relations(driver, database, relations):
    """Import relations into the new schema."""
    imported = 0
    errors = 0

    with driver.session(database, SessionType.DATA) as session:
        for rel in relations:
            rel_type = rel["type"]
            roles = rel.get("roles", {})
            attrs = rel.get("attrs", {})

            # Build match clause
            match_parts = []
            role_parts = []
            var_counter = 0

            for role_name, entity_id in roles.items():
                if entity_id is None:
                    continue
                var = f"$v{var_counter}"
                var_counter += 1
                # Use identifiable-entity as the broadest match type
                # (covers thing, collection, ICE subtypes, agent, tag)
                match_parts.append(f'{var} has id "{entity_id}"')
                role_parts.append(f"{role_name}: {var}")

            if len(role_parts) < 2:
                continue

            # Build insert clause
            attr_parts = []
            for attr_name, attr_value in attrs.items():
                formatted = format_attr(attr_name, attr_value)
                if formatted:
                    attr_parts.append(formatted)

            insert_rel = f'({", ".join(role_parts)}) isa {rel_type}'
            if attr_parts:
                insert_rel += f', {", ".join(attr_parts)}'
            insert_rel += ";"

            query = f'match {"; ".join(match_parts)}; insert {insert_rel}'

            with session.transaction(TransactionType.WRITE) as tx:
                try:
                    tx.query.insert(query)
                    tx.commit()
                    imported += 1
                except Exception as e:
                    errors += 1
                    print(f"  Error inserting {rel_type}: {e}", file=sys.stderr)

    return imported, errors


# ============================================================================
# Commands
# ============================================================================

def cmd_export(args):
    """Export current data to JSON."""
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print("Connecting to TypeDB...", file=sys.stderr)
    with get_driver() as driver:
        print("Exporting entities...", file=sys.stderr)
        entities, your_skills = export_entities(driver, TYPEDB_DATABASE)

        print("Exporting relations...", file=sys.stderr)
        relations = export_relations(driver, TYPEDB_DATABASE)

    # Serialize (convert datetime objects to strings)
    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "database": TYPEDB_DATABASE,
        "entities": entities,
        "your_skills": your_skills,
        "relations": relations,
    }

    with open(output, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print(json.dumps({
        "success": True,
        "output": str(output),
        "entity_count": len(entities),
        "your_skill_count": len(your_skills),
        "relation_count": len(relations),
    }, indent=2))


def cmd_import(args):
    """Import transformed data into new schema."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(json.dumps({"success": False, "error": f"File not found: {input_path}"}))
        return

    with open(input_path) as f:
        data = json.load(f)

    entities = data["entities"]
    your_skills = data["your_skills"]
    relations = data["relations"]

    # Transform
    entities, your_skills, relations, log = transform_data(entities, your_skills, relations)
    for entry in log:
        print(f"  {entry}", file=sys.stderr)

    print("Connecting to TypeDB...", file=sys.stderr)
    with get_driver() as driver:
        print("Importing entities...", file=sys.stderr)
        e_imported, e_errors = import_entities(driver, TYPEDB_DATABASE, entities, your_skills)

        print("Importing relations...", file=sys.stderr)
        r_imported, r_errors = import_relations(driver, TYPEDB_DATABASE, relations)

    print(json.dumps({
        "success": True,
        "entities_imported": e_imported,
        "entity_errors": e_errors,
        "relations_imported": r_imported,
        "relation_errors": r_errors,
    }, indent=2))


def cmd_migrate(args):
    """Full migration: export, drop, recreate, import."""
    # Step 1: Export
    export_path = Path(args.export_path or "exports/migration_data.json")
    export_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60, file=sys.stderr)
    print("STEP 1: Exporting data from current database", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    with get_driver() as driver:
        entities, your_skills = export_entities(driver, TYPEDB_DATABASE)
        relations = export_relations(driver, TYPEDB_DATABASE)

    # Save export for safety
    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "database": TYPEDB_DATABASE,
        "entities": entities,
        "your_skills": your_skills,
        "relations": relations,
    }
    with open(export_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print(f"  Exported {len(entities)} entities, {len(your_skills)} skills, {len(relations)} relations",
          file=sys.stderr)
    print(f"  Saved to {export_path}", file=sys.stderr)

    # Step 2: Transform
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("STEP 2: Transforming data for new schema", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    entities, your_skills, relations, log = transform_data(entities, your_skills, relations)
    for entry in log:
        print(f"  {entry}", file=sys.stderr)

    # Step 3: Drop and recreate database
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("STEP 3: Dropping and recreating database with new schema", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    with get_driver() as driver:
        if driver.databases.contains(TYPEDB_DATABASE):
            print(f"  Dropping database '{TYPEDB_DATABASE}'...", file=sys.stderr)
            driver.databases.get(TYPEDB_DATABASE).delete()
        print(f"  Creating database '{TYPEDB_DATABASE}'...", file=sys.stderr)
        driver.databases.create(TYPEDB_DATABASE)

        # Load schemas
        print("  Loading core schema...", file=sys.stderr)
        with open(CORE_SCHEMA) as f:
            schema = f.read()
        with driver.session(TYPEDB_DATABASE, SessionType.SCHEMA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.define(schema)
                tx.commit()

        for schema_file in sorted(NAMESPACE_DIR.glob("*.tql")):
            print(f"  Loading {schema_file.name}...", file=sys.stderr)
            with open(schema_file) as f:
                ns_schema = f.read()
            with driver.session(TYPEDB_DATABASE, SessionType.SCHEMA) as session:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.define(ns_schema)
                    tx.commit()

    # Step 4: Import
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("STEP 4: Importing transformed data", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    with get_driver() as driver:
        e_imported, e_errors = import_entities(driver, TYPEDB_DATABASE, entities, your_skills)
        print(f"  Entities: {e_imported} imported, {e_errors} errors", file=sys.stderr)

        r_imported, r_errors = import_relations(driver, TYPEDB_DATABASE, relations)
        print(f"  Relations: {r_imported} imported, {r_errors} errors", file=sys.stderr)

    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("MIGRATION COMPLETE", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    print(json.dumps({
        "success": True,
        "export_path": str(export_path),
        "entities_exported": len(data["entities"]),
        "your_skills_exported": len(data["your_skills"]),
        "relations_exported": len(data["relations"]),
        "entities_imported": e_imported,
        "entity_errors": e_errors,
        "relations_imported": r_imported,
        "relation_errors": r_errors,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Migrate TypeDB schema: separate Things from ICEs"
    )
    subparsers = parser.add_subparsers(dest="command", help="Migration command")

    # export
    p = subparsers.add_parser("export", help="Export current data to JSON")
    p.add_argument("--output", default="exports/migration_data.json", help="Output JSON file")

    # import
    p = subparsers.add_parser("import", help="Import transformed data into new schema")
    p.add_argument("--input", required=True, help="Input JSON file from export step")

    # migrate (all-in-one)
    p = subparsers.add_parser("migrate", help="Full migration: export, transform, reload")
    p.add_argument("--export-path", default="exports/migration_data.json",
                   help="Path to save export backup")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "export":
        cmd_export(args)
    elif args.command == "import":
        cmd_import(args)
    elif args.command == "migrate":
        cmd_migrate(args)


if __name__ == "__main__":
    main()
