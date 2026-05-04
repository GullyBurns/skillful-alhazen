#!/usr/bin/env python3
"""
Migrate data from old namespace to new namespace.

Reads entities from alhazen_backup (old type names) and inserts into
alhazen_notebook (new type names) using the rename map.

Usage:
    uv run python scripts/migrate_namespace_rename.py [--dry-run] [--type OLD_TYPE]
"""

import argparse
import json
import os
import sys

from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")
SOURCE_DB = "alhazen_backup"
TARGET_DB = "alhazen_notebook"


def get_driver():
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def escape(s):
    if s is None:
        return ""
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def migrate_entity_type(driver, old_type, new_type, attr_rename, dry_run=False):
    """Migrate all instances of one entity type from source to target."""
    # Get attribute list from source
    with driver.transaction(SOURCE_DB, TransactionType.READ) as tx:
        owns_rows = list(tx.query(
            f'match $t label {old_type}; $t owns $a; fetch {{ "a": $a }};'
        ).resolve())
        attrs = [r["a"]["label"] for r in owns_rows]

    # Count instances
    with driver.transaction(SOURCE_DB, TransactionType.READ) as tx:
        count_rows = list(tx.query(
            f'match $x isa! {old_type}; fetch {{ "id": $x.id }};'
        ).resolve())
    count = len(count_rows)

    if count == 0:
        return {"type": old_type, "new_type": new_type, "count": 0, "migrated": 0}

    # For each instance, read all attributes and insert into target
    migrated = 0
    errors = 0

    # Process in batches — read IDs first, then process each
    ids = [r["id"] for r in count_rows]

    for entity_id in ids:
        eid = escape(str(entity_id))

        # Read all attribute values from source
        attr_values = {}
        with driver.transaction(SOURCE_DB, TransactionType.READ) as tx:
            for attr in attrs:
                try:
                    rows = list(tx.query(
                        f'match $x isa! {old_type}, has id "{eid}", has {attr} $v; '
                        f'fetch {{ "v": $v }};'
                    ).resolve())
                    if rows:
                        # Handle multi-valued attributes
                        vals = [r["v"] for r in rows]
                        attr_values[attr] = vals
                except Exception:
                    pass

        if dry_run:
            migrated += 1
            continue

        # Build insert query
        # Get attribute value types from source schema
        attr_value_types = {}
        with driver.transaction(SOURCE_DB, TransactionType.READ) as tx:
            for attr in attr_values:
                try:
                    rows = list(tx.query(f'match attribute $t, label {attr}; fetch {{ "t": $t }};').resolve())
                    if rows:
                        attr_value_types[attr] = rows[0]["t"].get("valueType", "string")
                except Exception:
                    attr_value_types[attr] = "string"

        new_attr_clauses = []
        for attr, vals in attr_values.items():
            new_attr = attr_rename.get(attr, attr)
            vtype = attr_value_types.get(attr, "string")
            for val in vals:
                if vtype == "datetime":
                    # TypeQL datetime: bare value without quotes, no nanoseconds
                    ts = str(val).replace(" ", "T")
                    if "." in ts:
                        ts = ts.split(".")[0]
                    new_attr_clauses.append(f'has {new_attr} {ts}')
                elif vtype in ("integer", "long", "double"):
                    new_attr_clauses.append(f'has {new_attr} {val}')
                elif vtype == "boolean":
                    new_attr_clauses.append(f'has {new_attr} {str(val).lower()}')
                else:
                    new_attr_clauses.append(f'has {new_attr} "{escape(str(val))}"')

        if not new_attr_clauses:
            continue

        insert_q = f'insert $x isa {new_type}, {", ".join(new_attr_clauses)};'

        try:
            with driver.transaction(TARGET_DB, TransactionType.WRITE) as tx:
                tx.query(insert_q).resolve()
                tx.commit()
            migrated += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Error inserting {old_type} id={eid}: {str(e)[:120]}", file=sys.stderr)

    return {"type": old_type, "new_type": new_type, "count": count, "migrated": migrated, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description="Migrate data with namespace rename")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--type", help="Migrate only this old type name")
    parser.add_argument("--map", default="scripts/rename_map.json", help="Path to rename map")
    args = parser.parse_args()

    rename_map = json.load(open(args.map))

    # Build attribute rename map (subset of full rename map that applies to attributes)
    attr_rename = {old: new for old, new in rename_map.items()}

    driver = get_driver()

    # Get all concrete entity types with data from source
    with driver.transaction(SOURCE_DB, TransactionType.READ) as tx:
        all_ents = list(tx.query('match entity $t; fetch { "type": $t };').resolve())

    concrete_types = []
    for row in all_ents:
        label = row["type"]["label"]
        if args.type and label != args.type:
            continue
        with driver.transaction(SOURCE_DB, TransactionType.READ) as tx:
            try:
                count = len(list(tx.query(
                    f'match $x isa! {label}; fetch {{ "id": $x.id }};'
                ).resolve()))
                if count > 0:
                    concrete_types.append((label, count))
            except Exception:
                pass

    # Sort by count ascending (small types first for quick verification)
    concrete_types.sort(key=lambda x: x[1])

    print(f"Migrating {len(concrete_types)} entity types, {sum(c for _, c in concrete_types)} total instances", file=sys.stderr)

    results = []
    for old_type, count in concrete_types:
        new_type = rename_map.get(old_type, old_type)
        print(f"  {old_type} -> {new_type} ({count})...", end="", file=sys.stderr, flush=True)
        result = migrate_entity_type(driver, old_type, new_type, attr_rename, args.dry_run)
        print(f" {result['migrated']}/{count}", file=sys.stderr)
        results.append(result)

    total_migrated = sum(r["migrated"] for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    print(f"\nDone: {total_migrated} entities migrated, {total_errors} errors", file=sys.stderr)

    print(json.dumps({"results": results, "total_migrated": total_migrated, "total_errors": total_errors}, indent=2))

    driver.close()


if __name__ == "__main__":
    main()
