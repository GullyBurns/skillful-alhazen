#!/usr/bin/env python3
"""
TypeDB 3.x database initialization script.

Creates the database (if it doesn't exist) and loads all schemas using
the TypeDB Python driver. This replaces the console-based approach.

Usage:
    uv run python scripts/db_init.py [--wait-only]
    uv run python scripts/db_init.py --host localhost --port 1729 --database alhazen_notebook

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    TYPEDB_USERNAME   TypeDB username (default: admin)
    TYPEDB_PASSWORD   TypeDB password (default: password)
"""

import argparse
import glob
import os
import sys
import time
from pathlib import Path


def wait_for_typedb(host, port, username, password, timeout=60):
    """Wait until TypeDB is accepting connections."""
    from typedb.driver import Credentials, DriverOptions, TypeDB
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            driver = TypeDB.driver(
                f"{host}:{port}",
                Credentials(username, password),
                DriverOptions(is_tls_enabled=False),
            )
            driver.close()
            print(f"TypeDB is ready at {host}:{port}", flush=True)
            return True
        except Exception:
            print(".", end="", flush=True)
            time.sleep(2)
    print(f"\nTypeDB failed to start within {timeout} seconds", flush=True)
    return False


def init_database(host, port, username, password, database, schema_files):
    """Create database and load schemas."""
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    driver = TypeDB.driver(
        f"{host}:{port}",
        Credentials(username, password),
        DriverOptions(is_tls_enabled=False),
    )

    try:
        # Create database if it doesn't exist
        if not driver.databases.contains(database):
            driver.databases.create(database)
            print(f"Created database: {database}", flush=True)
        else:
            print(f"Database already exists: {database}", flush=True)

        # Load each schema file
        for schema_path in schema_files:
            schema_path = Path(schema_path)
            if not schema_path.exists():
                print(f"Warning: schema not found: {schema_path}", flush=True)
                continue

            print(f"Loading schema: {schema_path.name} ...", end=" ", flush=True)
            with open(schema_path) as f:
                schema = f.read()

            try:
                with driver.transaction(database, TransactionType.SCHEMA) as tx:
                    tx.query(schema).resolve()
                    tx.commit()
                print("OK", flush=True)
            except Exception as e:
                print(f"FAILED: {e}", flush=True)
                raise

    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(description="Initialize TypeDB 3.x database")
    parser.add_argument("--host", default=os.getenv("TYPEDB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("TYPEDB_PORT", "1729")))
    parser.add_argument("--database", default=os.getenv("TYPEDB_DATABASE", "alhazen_notebook"))
    parser.add_argument("--username", default=os.getenv("TYPEDB_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("TYPEDB_PASSWORD", "password"))
    parser.add_argument("--timeout", type=int, default=60,
                        help="Seconds to wait for TypeDB to be ready")
    parser.add_argument("--wait-only", action="store_true",
                        help="Only wait for TypeDB readiness, don't load schemas")
    parser.add_argument("schemas", nargs="*",
                        help="Schema .tql files to load (in order)")
    args = parser.parse_args()

    # Wait for TypeDB to be ready
    print(f"Waiting for TypeDB at {args.host}:{args.port} ...", flush=True)
    if not wait_for_typedb(args.host, args.port, args.username, args.password, args.timeout):
        sys.exit(1)

    if args.wait_only:
        return

    # Load schemas
    if not args.schemas:
        print("No schema files specified. Use: scripts/db_init.py schema1.tql schema2.tql ...", flush=True)
        sys.exit(1)

    init_database(args.host, args.port, args.username, args.password, args.database, args.schemas)
    print(f"\nDatabase '{args.database}' initialized successfully.", flush=True)


if __name__ == "__main__":
    main()
