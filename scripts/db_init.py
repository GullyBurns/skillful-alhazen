#!/usr/bin/env python3
"""
TypeDB 3.x database initialization script.

Thin wrapper around skills/alhazen-core/alhazen_core.py — shares the same
TypeDB connection and schema loading logic. Kept for backward compatibility
with Makefile targets and docker-compose init services.

Usage:
    uv run python scripts/db_init.py [--wait-only]
    uv run python scripts/db_init.py schema1.tql schema2.tql ...
    uv run python scripts/db_init.py --host localhost --port 1729 --database alhazen_notebook

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    TYPEDB_USERNAME   TypeDB username (default: admin)
    TYPEDB_PASSWORD   TypeDB password (default: password)
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Import shared TypeDB logic from alhazen-core
_core_dir = Path(__file__).parent.parent / "skills" / "alhazen-core"
if not _core_dir.exists():
    # Fallback: check local_skills (after make build-skills)
    _core_dir = Path(__file__).parent.parent / "local_skills" / "alhazen-core"
sys.path.insert(0, str(_core_dir))

import alhazen_core as core  # noqa: E402


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

    # Override core module's globals with our args
    core.TYPEDB_HOST = args.host
    core.TYPEDB_PORT = args.port
    core.TYPEDB_DATABASE = args.database
    core.TYPEDB_USERNAME = args.username
    core.TYPEDB_PASSWORD = args.password

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

    # Use alhazen_core's shared driver and schema loading
    with core._get_driver() as driver:
        # Create database if needed
        core._create_database(driver)

        # Load each schema file
        for schema_path in args.schemas:
            schema_path = Path(schema_path)
            if not schema_path.exists():
                print(f"Warning: schema not found: {schema_path}", flush=True)
                continue

            print(f"Loading schema: {schema_path.name} ...", end=" ", flush=True)
            try:
                core._load_extra_schema(driver, schema_path)
                print("OK", flush=True)
            except Exception as e:
                print(f"FAILED: {e}", flush=True)
                raise

    print(f"\nDatabase '{args.database}' initialized successfully.", flush=True)


if __name__ == "__main__":
    main()
