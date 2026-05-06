#!/usr/bin/env python3
"""
Retire (remove) a namespace's types and data from TypeDB.

Given a namespace prefix, finds all entity, relation, and attribute types
that start with that prefix, deletes their instances, and undefines the types.

Usage:
    uv run python scripts/db_retire_namespace.py --namespace apt
    uv run python scripts/db_retire_namespace.py --namespace apt --dry-run
    uv run python scripts/db_retire_namespace.py --namespace scilit --host localhost --port 1729

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

BATCH_SIZE = 500  # Max instances to delete per transaction


def get_connection_params(args):
    """Resolve connection parameters from args + env vars."""
    return {
        "host": args.host or os.environ.get("TYPEDB_HOST", "localhost"),
        "port": int(args.port or os.environ.get("TYPEDB_PORT", "1729")),
        "database": args.database or os.environ.get("TYPEDB_DATABASE", "alhazen_notebook"),
        "username": args.username or os.environ.get("TYPEDB_USERNAME", "admin"),
        "password": args.password or os.environ.get("TYPEDB_PASSWORD", "password"),
    }


def connect(params):
    """Create a TypeDB driver connection."""
    from typedb.driver import Credentials, DriverOptions, TypeDB

    return TypeDB.driver(
        f"{params['host']}:{params['port']}",
        Credentials(params["username"], params["password"]),
        DriverOptions(is_tls_enabled=False),
    )


def discover_types(driver, database, prefix):
    """Query TypeDB for all types matching the namespace prefix.

    Returns dict with keys: relations, entities, attributes — each a list of type labels.
    """
    from typedb.driver import TransactionType

    result = {"relations": [], "entities": [], "attributes": []}

    with driver.transaction(database, TransactionType.READ) as tx:
        # Discover relation types
        rows = list(tx.query("match relation $t; fetch { \"label\": $t };").resolve())
        for row in rows:
            label = row.get("label", "")
            if isinstance(label, dict):
                label = label.get("label", label.get("value", ""))
            label = str(label)
            if label.startswith(prefix + "-"):
                result["relations"].append(label)

        # Discover entity types
        rows = list(tx.query("match entity $t; fetch { \"label\": $t };").resolve())
        for row in rows:
            label = row.get("label", "")
            if isinstance(label, dict):
                label = label.get("label", label.get("value", ""))
            label = str(label)
            if label.startswith(prefix + "-"):
                result["entities"].append(label)

        # Discover attribute types
        rows = list(tx.query("match attribute $t; fetch { \"label\": $t };").resolve())
        for row in rows:
            label = row.get("label", "")
            if isinstance(label, dict):
                label = label.get("label", label.get("value", ""))
            label = str(label)
            if label.startswith(prefix + "-"):
                result["attributes"].append(label)

    # Sort each list for deterministic output
    for key in result:
        result[key].sort()

    return result


def count_instances(driver, database, type_label):
    """Count instances of a given type."""
    from typedb.driver import TransactionType

    with driver.transaction(database, TransactionType.READ) as tx:
        rows = list(tx.query(
            f'match $x isa {type_label}; reduce $count = count;'
        ).resolve())
        if rows:
            # reduce returns a single row with the count
            row = rows[0]
            if isinstance(row, dict):
                return row.get("count", row.get("$count", 0))
            return 0
        return 0


def delete_instances_batched(driver, database, type_label):
    """Delete all instances of a type in batches. Returns total deleted."""
    from typedb.driver import TransactionType

    total_deleted = 0
    while True:
        with driver.transaction(database, TransactionType.WRITE) as tx:
            # Match a batch
            rows = list(tx.query(
                f'match $x isa {type_label}; reduce $count = count;'
            ).resolve())
            count = 0
            if rows:
                row = rows[0]
                if isinstance(row, dict):
                    count = row.get("count", row.get("$count", 0))
            if count == 0:
                break

            # Delete a batch
            tx.query(f'match $x isa {type_label}; delete $x;').resolve()
            tx.commit()
            total_deleted += count
            print(f"    Deleted batch ({count} instances)", file=sys.stderr)

        # If we deleted fewer than we might expect in a single pass, we're done
        # (TypeDB deletes all matching in one query, so one pass suffices)
        break

    return total_deleted


def undefine_type(driver, database, type_label):
    """Undefine a type from the schema. Returns True on success."""
    from typedb.driver import TransactionType

    try:
        with driver.transaction(database, TransactionType.SCHEMA) as tx:
            tx.query(f'undefine {type_label};').resolve()
            tx.commit()
        return True
    except Exception as e:
        print(f"    Warning: could not undefine '{type_label}': {e}", file=sys.stderr)
        return False


def check_attribute_orphaned(driver, database, attr_label):
    """Check if any remaining type still owns this attribute.

    Returns True if orphaned (no type owns it), False if still in use.
    """
    from typedb.driver import TransactionType

    try:
        with driver.transaction(database, TransactionType.READ) as tx:
            # Check if any entity or relation type still owns this attribute
            rows = list(tx.query(
                f'match $t owns {attr_label}; fetch {{ "type": $t }};'
            ).resolve())
            return len(rows) == 0
    except Exception:
        # If the query fails, assume orphaned (safe to try undefine)
        return True


def retire_namespace(driver, database, prefix, dry_run=False):
    """Main retirement logic. Returns summary dict."""
    print("Discovering types for the requested namespace...",
          file=sys.stderr)
    types = discover_types(driver, database, prefix)

    total_relations = len(types["relations"])
    total_entities = len(types["entities"])
    total_attributes = len(types["attributes"])
    total_types = total_relations + total_entities + total_attributes

    if total_types == 0:
        print(f"No types found with prefix '{prefix}-'. Nothing to do.", file=sys.stderr)
        return {
            "success": True,
            "namespace": prefix,
            "dry_run": dry_run,
            "types_found": 0,
            "types_removed": 0,
            "instances_deleted": 0,
            "details": {"relations": [], "entities": [], "attributes": []},
        }

    print(f"Found {total_relations} relations, {total_entities} entities, "
          f"{total_attributes} attributes", file=sys.stderr)

    summary = {
        "relations": [],
        "entities": [],
        "attributes": [],
    }
    total_instances_deleted = 0
    total_types_removed = 0

    # --- Phase 1: Relations (must go first to remove role constraints) ---
    if types["relations"]:
        print(f"\n--- Phase 1: Retiring {len(types['relations'])} relation types ---",
              file=sys.stderr)
    for rel in types["relations"]:
        count = count_instances(driver, database, rel)
        entry = {"type": rel, "instances": count, "deleted": False, "undefined": False}
        print(f"  {rel}: {count} instances", file=sys.stderr)

        if not dry_run:
            if count > 0:
                deleted = delete_instances_batched(driver, database, rel)
                entry["instances_deleted"] = deleted
                total_instances_deleted += deleted
                entry["deleted"] = True

            if undefine_type(driver, database, rel):
                entry["undefined"] = True
                total_types_removed += 1

        summary["relations"].append(entry)

    # --- Phase 2: Entities ---
    if types["entities"]:
        print(f"\n--- Phase 2: Retiring {len(types['entities'])} entity types ---",
              file=sys.stderr)
    for ent in types["entities"]:
        count = count_instances(driver, database, ent)
        entry = {"type": ent, "instances": count, "deleted": False, "undefined": False}
        print(f"  {ent}: {count} instances", file=sys.stderr)

        if not dry_run:
            if count > 0:
                deleted = delete_instances_batched(driver, database, ent)
                entry["instances_deleted"] = deleted
                total_instances_deleted += deleted
                entry["deleted"] = True

            if undefine_type(driver, database, ent):
                entry["undefined"] = True
                total_types_removed += 1

        summary["entities"].append(entry)

    # --- Phase 3: Attributes (only if orphaned) ---
    if types["attributes"]:
        print(f"\n--- Phase 3: Checking {len(types['attributes'])} attribute types ---",
              file=sys.stderr)
    for attr in types["attributes"]:
        orphaned = check_attribute_orphaned(driver, database, attr)
        entry = {"type": attr, "orphaned": orphaned, "undefined": False}

        if orphaned:
            print(f"  {attr}: orphaned — will remove", file=sys.stderr)
            if not dry_run:
                if undefine_type(driver, database, attr):
                    entry["undefined"] = True
                    total_types_removed += 1
        else:
            print(f"  {attr}: still owned by other types — skipping", file=sys.stderr)

        summary["attributes"].append(entry)

    result = {
        "success": True,
        "namespace": prefix,
        "dry_run": dry_run,
        "types_found": total_types,
        "types_removed": total_types_removed,
        "instances_deleted": total_instances_deleted,
        "details": summary,
    }

    if dry_run:
        print(f"\n[DRY RUN] Would remove {total_types} types. "
              "Re-run without --dry-run to execute.", file=sys.stderr)
    else:
        print(f"\nRetired {total_types_removed}/{total_types} types, "
              f"deleted {total_instances_deleted} instances.", file=sys.stderr)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Retire a namespace's types and data from TypeDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--namespace", required=True,
                        help="Namespace prefix to remove (e.g., 'apt', 'scilit')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be removed without executing")
    parser.add_argument("--host", default=None,
                        help="TypeDB host (default: $TYPEDB_HOST or localhost)")
    parser.add_argument("--port", default=None,
                        help="TypeDB port (default: $TYPEDB_PORT or 1729)")
    parser.add_argument("--database", default=None,
                        help="Database name (default: $TYPEDB_DATABASE or alhazen_notebook)")
    parser.add_argument("--username", default=None,
                        help="TypeDB username (default: $TYPEDB_USERNAME or admin)")
    parser.add_argument("--password", default=None,
                        help="TypeDB password (default: $TYPEDB_PASSWORD or password)")

    args = parser.parse_args()
    params = get_connection_params(args)

    try:
        from typedb.driver import TypeDB  # noqa: F401
    except ImportError:
        print("Error: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
              file=sys.stderr)
        sys.exit(1)

    driver = connect(params)
    try:
        # Verify database exists
        if not driver.databases.contains(params["database"]):
            print(f"Error: database '{params['database']}' does not exist", file=sys.stderr)
            sys.exit(1)

        result = retire_namespace(driver, params["database"], args.namespace, args.dry_run)
        print(json.dumps(result, indent=2))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
