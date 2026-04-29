#!/usr/bin/env python3
"""Export all entity and relation data from TypeDB as schema-free JSON.

Exports every entity with all its attributes, and every relation with
its role players (identified by id). The output can be re-imported into
a database with a different schema as long as entity types and attribute
names are compatible.

Usage:
    uv run python scripts/export_all_data.py export --output exports/full_export.json
    uv run python scripts/export_all_data.py import --input exports/full_export.json
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


from typedb.driver import Credentials, DriverOptions, TypeDB, TransactionType


def get_driver():
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def escape(s):
    """Escape a string for TypeQL insertion."""
    if s is None:
        return None
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


# -------------------------------------------------------------------------
# EXPORT
# -------------------------------------------------------------------------

def discover_entity_types(tx):
    """Find all concrete entity types that have instances."""
    results = list(tx.query(
        'match $e isa! $t, has id $id; fetch { "type": $t };'
    ).resolve())
    types = defaultdict(int)
    for r in results:
        label = r.get("type", {}).get("label", "unknown")
        types[label] += 1
    return dict(types)


def discover_attributes_for_type(tx, entity_type, sample_size=5):
    """Sample a few entities of a type to discover which attributes they have."""
    # Fetch a sample entity with all attributes via a broad match
    results = list(tx.query(f'''
        match $e isa {entity_type}, has $a;
        fetch {{ "attr_type": $a }};
    ''').resolve())

    # Collect unique attribute type labels
    attr_types = set()
    for r in results:
        at = r.get("attr_type", {})
        if isinstance(at, dict) and "type" in at:
            attr_types.add(at["type"]["label"])
        elif isinstance(at, dict) and "label" in at:
            attr_types.add(at["label"])
    return list(attr_types)


def export_entities_of_type(tx, entity_type):
    """Export all entities of a given type with all their attributes."""
    # First get all IDs
    id_results = list(tx.query(f'''
        match $e isa! {entity_type}, has id $id;
        fetch {{ "id": $id }};
    ''').resolve())

    entities = []
    for id_row in id_results:
        eid = id_row["id"]
        # Fetch all attributes for this entity
        attr_results = list(tx.query(f'''
            match $e isa {entity_type}, has id "{escape(eid)}", has $a;
            fetch {{ "attr": $a }};
        ''').resolve())

        attrs = {}
        for ar in attr_results:
            a = ar.get("attr", {})
            if isinstance(a, dict):
                atype = a.get("type", {}).get("label", "unknown") if "type" in a else "unknown"
                aval = a.get("value")
                if aval is not None:
                    # Handle multiple values for same attribute
                    if atype in attrs:
                        if isinstance(attrs[atype], list):
                            attrs[atype].append(aval)
                        else:
                            attrs[atype] = [attrs[atype], aval]
                    else:
                        attrs[atype] = aval

        entities.append({"id": eid, "type": entity_type, "attributes": attrs})

    return entities


def export_relations(tx):
    """Export all relations by querying known relation patterns."""
    relations = []

    # Define relation types and their role patterns
    # Each tuple: (relation_type, [(role_name, var_name), ...], [extra_attr_names])
    relation_specs = [
        ("aboutness", [("note", "n"), ("subject", "s")], []),
        ("collection-membership", [("collection", "c"), ("member", "m")], []),
        ("tagging", [("tagged-entity", "e"), ("tag", "t")], []),
        ("representation", [("artifact", "a"), ("referent", "r")], []),
        ("fragmentation", [("whole", "w"), ("part", "p")], []),
        ("authorship", [("author", "a"), ("work", "w")], []),
        ("citation-reference", [("citing-item", "ci"), ("cited-item", "cd")], []),
        ("derivation", [("derivative", "d"), ("derived-from-source", "s")], []),
        ("note-threading", [("parent-note", "p"), ("child-note", "c")], []),
        ("classification", [("classified-entity", "e"), ("type-facet", "t")], []),
        ("evidence-chain", [("claim", "c"), ("evidence", "e")], []),
        ("position-at-company", [("position", "p"), ("employer", "e")], []),
        ("requirement-for", [("requirement", "r"), ("position", "p")], []),
        ("addresses-requirement", [("resource", "r"), ("requirement", "q")], []),
        ("source-provides", [("source", "s"), ("candidate", "c")], []),
        ("opportunity-at-organization", [("opportunity", "o"), ("organization", "g")], []),
        ("works-at", [("employee", "e"), ("employer", "c")], []),
        ("interaction-participation", [("interaction", "i"), ("participant", "p")], ["participant-role"]),
        ("fact-evidence", [("derived", "d"), ("source", "s")], []),
        ("relationship-context", [("from-person", "f"), ("to-person", "t")], []),
        ("affiliation", [("affiliated-agent", "a"), ("organization", "o")], []),
        ("episode-mention", [("session", "s"), ("subject", "e")], []),
    ]

    for rel_type, roles, extra_attrs in relation_specs:
        role_str = ", ".join(f"{rname}: ${var}" for rname, var in roles)
        # Build fetch keys from role player ids
        has_clauses = "; ".join(f"${var} has id ${var}id" for _, var in roles)
        fetch_keys = ", ".join(f'"{rname}": ${var}id' for rname, var in roles)

        # Add extra attribute fetches if any
        extra_has = ""
        extra_fetch = ""
        if extra_attrs:
            extra_has = "; " + "; ".join(
                f"$rel has {attr} ${attr.replace('-', '_')}" for attr in extra_attrs
            )
            extra_fetch = ", " + ", ".join(
                f'"{attr}": ${attr.replace("-", "_")}' for attr in extra_attrs
            )

        query = f'''
            match $rel ({role_str}) isa {rel_type}; {has_clauses}{extra_has};
            fetch {{ {fetch_keys}{extra_fetch} }};
        '''
        try:
            results = list(tx.query(query).resolve())
            if results:
                for r in results:
                    rel_data = {"type": rel_type, "roles": {}}
                    for rname, var in roles:
                        rel_data["roles"][rname] = r.get(rname)
                    for attr in extra_attrs:
                        rel_data[attr] = r.get(attr)
                    relations.append(rel_data)
                print(f"  {rel_type}: {len(results)} relations", file=sys.stderr)
        except Exception as e:
            # Some relation types may not exist in this database
            err = str(e)
            if "not found" not in err.lower() and "INF2" not in err:
                print(f"  {rel_type}: error - {err[:80]}", file=sys.stderr)

    return relations


def cmd_export(args):
    """Export all data to JSON."""
    driver = get_driver()
    data = {"entities": [], "relations": [], "metadata": {}}

    print("Discovering entity types...", file=sys.stderr)
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
    
        type_counts = discover_entity_types(tx)

    print(f"Found {len(type_counts)} entity types with {sum(type_counts.values())} total entities", file=sys.stderr)
    data["metadata"]["type_counts"] = type_counts
    data["metadata"]["database"] = TYPEDB_DATABASE
    data["metadata"]["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    # Export entities type by type

    for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"Exporting {etype} ({count} entities)...", file=sys.stderr)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            entities = export_entities_of_type(tx, etype)
            data["entities"].extend(entities)
        print(f"  Done: {len(entities)} exported", file=sys.stderr)

    # Export relations
    print("Exporting relations...", file=sys.stderr)
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        data["relations"] = export_relations(tx)

    print(f"\nTotal: {len(data['entities'])} entities, {len(data['relations'])} relations", file=sys.stderr)

    # Write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported to {args.output}", file=sys.stderr)

    driver.close()


# -------------------------------------------------------------------------
# IMPORT
# -------------------------------------------------------------------------

def cmd_import(args):
    """Import data from JSON into a clean database."""


    with open(args.input) as f:
        data = json.load(f)

    driver = get_driver()
    entities = data["entities"]
    relations = data["relations"]

    print(f"Importing {len(entities)} entities and {len(relations)} relations", file=sys.stderr)

    # Group entities by type for batch insertion
    by_type = defaultdict(list)
    for e in entities:
        by_type[e["type"]].append(e)

    # Insert entities in batches
    batch_size = args.batch_size
    total_inserted = 0
    total_failed = 0

    for etype, type_entities in sorted(by_type.items(), key=lambda x: -len(x[1])):
        print(f"Inserting {etype} ({len(type_entities)} entities)...", file=sys.stderr)
        type_inserted = 0
        type_failed = 0

        for i in range(0, len(type_entities), batch_size):
            batch = type_entities[i:i + batch_size]
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                for entity in batch:
                    attrs = entity["attributes"]
                    eid = escape(entity["id"])

                    # Build has clauses
                    has_parts = [f'has id "{eid}"']
                    for attr_name, attr_val in attrs.items():
                        if attr_name == "id":
                            continue  # already added
                        vals = attr_val if isinstance(attr_val, list) else [attr_val]
                        for v in vals:
                            if v is None:
                                continue
                            if isinstance(v, str):
                                has_parts.append(f'has {attr_name} "{escape(v)}"')
                            elif isinstance(v, bool):
                                has_parts.append(f'has {attr_name} {"true" if v else "false"}')
                            elif isinstance(v, (int, float)):
                                has_parts.append(f'has {attr_name} {v}')
                            else:
                                # datetime or other - try as string
                                has_parts.append(f'has {attr_name} "{escape(str(v))}"')

                    query = f'insert $e isa {etype}, {", ".join(has_parts)};'
                    try:
                        tx.query(query).resolve()
                        type_inserted += 1
                    except Exception as e:
                        type_failed += 1
                        if type_failed <= 3:
                            print(f"  FAIL [{etype}] {eid}: {str(e)[:100]}", file=sys.stderr)

                try:
                    tx.commit()
                except Exception as e:
                    print(f"  BATCH COMMIT FAIL [{etype}]: {str(e)[:100]}", file=sys.stderr)
                    # Retry one by one
                    for entity in batch:
                        try:
                            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx2:
                                attrs = entity["attributes"]
                                eid = escape(entity["id"])
                                has_parts = [f'has id "{eid}"']
                                for attr_name, attr_val in attrs.items():
                                    if attr_name == "id":
                                        continue
                                    vals = attr_val if isinstance(attr_val, list) else [attr_val]
                                    for v in vals:
                                        if v is None:
                                            continue
                                        if isinstance(v, str):
                                            has_parts.append(f'has {attr_name} "{escape(v)}"')
                                        elif isinstance(v, bool):
                                            has_parts.append(f'has {attr_name} {"true" if v else "false"}')
                                        elif isinstance(v, (int, float)):
                                            has_parts.append(f'has {attr_name} {v}')
                                        else:
                                            has_parts.append(f'has {attr_name} "{escape(str(v))}"')
                                query = f'insert $e isa {etype}, {", ".join(has_parts)};'
                                tx2.query(query).resolve()
                                tx2.commit()
                        except:
                            pass

        total_inserted += type_inserted
        total_failed += type_failed
        if type_failed > 0:
            print(f"  {type_inserted} inserted, {type_failed} failed", file=sys.stderr)

    print(f"\nEntities: {total_inserted} inserted, {total_failed} failed", file=sys.stderr)

    # Insert relations
    print(f"Inserting {len(relations)} relations...", file=sys.stderr)
    rel_inserted = 0
    rel_failed = 0

    for i in range(0, len(relations), batch_size):
        batch = relations[i:i + batch_size]
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            for rel in batch:
                rel_type = rel["type"]
                roles = rel["roles"]

                # Build match clause for role players
                match_parts = []
                role_parts = []
                for j, (role_name, player_id) in enumerate(roles.items()):
                    if player_id is None:
                        continue
                    var = f"$r{j}"
                    match_parts.append(f'{var} has id "{escape(player_id)}"')
                    role_parts.append(f"{role_name}: {var}")

                if not role_parts:
                    continue

                # Build extra attribute has clauses
                extra_has = ""
                for k, v in rel.items():
                    if k in ("type", "roles") or v is None:
                        continue
                    if isinstance(v, str):
                        extra_has += f', has {k} "{escape(v)}"'
                    elif isinstance(v, (int, float)):
                        extra_has += f', has {k} {v}'

                query = f'''
                    match {"; ".join(match_parts)};
                    insert ({", ".join(role_parts)}) isa {rel_type}{extra_has};
                '''
                try:
                    tx.query(query).resolve()
                    rel_inserted += 1
                except Exception as e:
                    rel_failed += 1
                    if rel_failed <= 5:
                        print(f"  REL FAIL [{rel_type}]: {str(e)[:100]}", file=sys.stderr)

            try:
                tx.commit()
            except Exception as e:
                print(f"  REL BATCH COMMIT FAIL: {str(e)[:100]}", file=sys.stderr)

    print(f"Relations: {rel_inserted} inserted, {rel_failed} failed", file=sys.stderr)
    print(f"\nDone. Total: {total_inserted} entities + {rel_inserted} relations", file=sys.stderr)

    driver.close()


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export/import all TypeDB data as schema-free JSON")
    sub = parser.add_subparsers(dest="command")

    p_export = sub.add_parser("export", help="Export all data to JSON")
    p_export.add_argument("--output", required=True, help="Output JSON file path")

    p_import = sub.add_parser("import", help="Import data from JSON")
    p_import.add_argument("--input", required=True, help="Input JSON file path")
    p_import.add_argument("--batch-size", type=int, default=100, help="Batch size for inserts")

    args = parser.parse_args()
    if args.command == "export":
        cmd_export(args)
    elif args.command == "import":
        cmd_import(args)
    else:
        parser.print_help()
