#!/usr/bin/env python3
"""
Alhazen Core — TypeDB infrastructure setup for Alhazen skills.

Starts the TypeDB Docker container, creates the database, and loads the base schema.
Run this once before installing any other Alhazen skill.

Usage:
    python alhazen_core.py init                        # Start TypeDB + dashboard, create DB, load base schema
    python alhazen_core.py load-schema FILE.tql         # Load additional schema into existing DB
    python alhazen_core.py wire-dashboard ...           # Copy a skill's dashboard files into the dashboard container
    python alhazen_core.py rebuild-dashboard            # Rebuild Next.js inside the dashboard container
    python alhazen_core.py dashboard-status             # Show which skills are wired into the dashboard
    python alhazen_core.py status                       # Check TypeDB container and database state
    python alhazen_core.py reset                        # Drop and recreate the database (WARNING: destroys data)

Environment:
    TYPEDB_HOST         TypeDB host (default: localhost)
    TYPEDB_PORT         TypeDB port (default: 1729)
    TYPEDB_DATABASE     Database name (default: alhazen_notebook)
    TYPEDB_USERNAME     TypeDB username (default: admin)
    TYPEDB_PASSWORD     TypeDB password (default: password)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

TYPEDB_IMAGE = "typedb/typedb:3.8.0"
TYPEDB_CONTAINER = "alhazen-typedb"
DASHBOARD_CONTAINER = "alhazen-dashboard"
COMPOSE_FILE = Path(__file__).parent / "docker-compose.alhazen.yml"
COMPOSE_PROJECT = "alhazen"

SCHEMA_FILE = Path(__file__).parent / "alhazen_notebook.tql"


def _docker(*args, check=True, capture=True):
    """Run a docker command, return CompletedProcess."""
    cmd = ["docker"] + list(args)
    return subprocess.run(cmd, capture_output=capture, text=True, check=check)


def _is_docker_running():
    try:
        _docker("info")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _container_status():
    """Return container status string or '' if not found."""
    try:
        r = _docker("inspect", "--format", "{{.State.Status}}", TYPEDB_CONTAINER)
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _compose(*args, check=True, capture=True):
    """Run a docker compose command using our compose file."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", COMPOSE_PROJECT] + list(args)
    return subprocess.run(cmd, capture_output=capture, text=True, check=check)


def _start_services():
    """Start TypeDB + dashboard via docker compose. Returns True on success."""
    # Check if TypeDB is already running (fast path)
    status = _container_status()
    if status == "running":
        return True

    # Start services via compose (builds dashboard image on first run)
    try:
        _compose("up", "-d", "--build")
    except subprocess.CalledProcessError as e:
        print(f"docker compose up failed: {e.stderr}", file=sys.stderr)
        return False

    # Wait for TypeDB to become ready (up to 90s — first build takes time)
    for _ in range(90):
        time.sleep(1)
        try:
            from typedb.driver import Credentials, DriverOptions, TypeDB
            driver = TypeDB.driver(
                f"{TYPEDB_HOST}:{TYPEDB_PORT}",
                Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
                DriverOptions(is_tls_enabled=False),
            )
            driver.close()
            return True
        except Exception:
            pass
    return False


def _dashboard_container_status():
    """Return dashboard container status or '' if not found."""
    try:
        r = _docker("inspect", "--format", "{{.State.Status}}", DASHBOARD_CONTAINER)
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _get_driver():
    try:
        from typedb.driver import Credentials, DriverOptions, TypeDB
        return TypeDB.driver(
            f"{TYPEDB_HOST}:{TYPEDB_PORT}",
            Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
            DriverOptions(is_tls_enabled=False),
        )
    except ImportError:
        print(
            json.dumps({"success": False, "error": "typedb-driver not installed. Run: uv sync"}),
            file=sys.stderr,
        )
        sys.exit(1)


def _database_exists(driver):
    try:
        return driver.databases.contains(TYPEDB_DATABASE)
    except Exception:
        return False


def _create_database(driver):
    """Create the database if it doesn't exist."""
    if not _database_exists(driver):
        driver.databases.create(TYPEDB_DATABASE)
        return True
    return False


def _load_schema(driver):
    """Load alhazen_notebook.tql into the database."""
    from typedb.driver import TransactionType
    schema_text = SCHEMA_FILE.read_text(encoding="utf-8")
    with driver.transaction(TYPEDB_DATABASE, TransactionType.SCHEMA) as tx:
        tx.query(schema_text).resolve()
        tx.commit()


def _load_extra_schema(driver, schema_path):
    """Load an additional schema file into the database."""
    from typedb.driver import TransactionType
    schema_text = schema_path.read_text(encoding="utf-8")
    with driver.transaction(TYPEDB_DATABASE, TransactionType.SCHEMA) as tx:
        tx.query(schema_text).resolve()
        tx.commit()


def cmd_init(args):
    """Start TypeDB, create database, load base schema."""
    result = {"step": "", "success": False}

    # Step 1: Docker
    result["step"] = "docker"
    if not _is_docker_running():
        print(json.dumps({"success": False, "error": "Docker is not running. Start Docker Desktop (macOS) or `sudo systemctl start docker` (Linux)."}))
        sys.exit(1)

    # Step 2: Start TypeDB + dashboard via docker compose
    result["step"] = "services"
    if not _start_services():
        print(json.dumps({"success": False, "error": f"Services failed to start within 90s. Check: docker logs {TYPEDB_CONTAINER}"}))
        sys.exit(1)

    # Step 3: Database
    result["step"] = "database"
    with _get_driver() as driver:
        created = _create_database(driver)

        # Step 4: Base schema
        result["step"] = "schema"
        try:
            _load_schema(driver)
            schema_result = "loaded"
        except Exception as e:
            # Schema may already be loaded — that's fine
            schema_result = f"already-loaded (or error: {e})"

        # Step 5: Load extra schemas passed via --extra-schema
        extra_results = []
        for extra in (args.extra_schema or []):
            extra_path = Path(extra)
            if not extra_path.exists():
                extra_results.append({"file": str(extra_path), "result": "not-found"})
                continue
            try:
                _load_extra_schema(driver, extra_path)
                extra_results.append({"file": str(extra_path), "result": "loaded"})
            except Exception as e:
                extra_results.append({"file": str(extra_path), "result": f"already-loaded (or error: {e})"})

    output = {
        "success": True,
        "typedb": "running",
        "database": TYPEDB_DATABASE,
        "database_created": created,
        "schema": schema_result,
        "message": "Alhazen core ready.",
    }
    if extra_results:
        output["extra_schemas"] = extra_results
    print(json.dumps(output))


def cmd_status(args):
    """Check TypeDB container and database state."""
    docker_ok = _is_docker_running()
    container_status = _container_status() if docker_ok else "docker-not-running"

    typedb_reachable = False
    db_exists = False
    if container_status == "running":
        try:
            with _get_driver() as driver:
                typedb_reachable = True
                db_exists = _database_exists(driver)
        except Exception:
            pass

    dashboard_status = _dashboard_container_status() if docker_ok else "docker-not-running"

    print(json.dumps({
        "success": True,
        "docker": "running" if docker_ok else "not-running",
        "typedb_container": container_status,
        "typedb_reachable": typedb_reachable,
        "database": TYPEDB_DATABASE,
        "database_exists": db_exists,
        "dashboard_container": dashboard_status,
        "dashboard_url": "http://localhost:3001" if dashboard_status == "running" else None,
    }))


def cmd_load_schema(args):
    """Load an additional schema file into the existing database."""
    schema_path = Path(args.schema_file)
    if not schema_path.exists():
        print(json.dumps({"success": False, "error": f"Schema file not found: {schema_path}"}))
        sys.exit(1)

    with _get_driver() as driver:
        if not _database_exists(driver):
            print(json.dumps({"success": False, "error": f"Database '{TYPEDB_DATABASE}' does not exist. Run 'init' first."}))
            sys.exit(1)

        try:
            _load_extra_schema(driver, schema_path)
            result = "loaded"
        except Exception as e:
            result = f"already-loaded (or error: {e})"

    print(json.dumps({
        "success": True,
        "database": TYPEDB_DATABASE,
        "schema_file": str(schema_path),
        "schema": result,
    }))


def cmd_wire_dashboard(args):
    """Copy a skill's dashboard files into the dashboard container."""
    skill_name = args.skill_name
    dashboard_dir = Path(args.dashboard_dir)

    if not dashboard_dir.exists():
        print(json.dumps({"success": False, "error": f"Dashboard directory not found: {dashboard_dir}"}))
        sys.exit(1)

    if _dashboard_container_status() != "running":
        print(json.dumps({"success": False, "error": "Dashboard container is not running. Run 'init' first."}))
        sys.exit(1)

    wired = []

    # Copy dashboard slots into the container
    slots = [
        ("components", f"src/components/{skill_name}"),
        ("pages", f"src/app/({skill_name})"),
        ("routes", f"src/app/api/{skill_name}"),
    ]
    for slot, dest in slots:
        src = dashboard_dir / slot
        if src.exists():
            # Ensure dest directory exists in container
            _docker("exec", DASHBOARD_CONTAINER, "mkdir", "-p", f"/app/{dest}")
            _docker("cp", f"{src}/.", f"{DASHBOARD_CONTAINER}:/app/{dest}")
            wired.append(slot)

    # Copy lib.ts
    lib = dashboard_dir / "lib.ts"
    if lib.exists():
        _docker("exec", DASHBOARD_CONTAINER, "mkdir", "-p", "/app/src/lib")
        _docker("cp", str(lib), f"{DASHBOARD_CONTAINER}:/app/src/lib/{skill_name}.ts")
        wired.append("lib.ts")

    # Copy Python scripts so API routes can call them
    skill_root = dashboard_dir.parent
    py_dir = f"/app/.claude/skills/{skill_name}"
    _docker("exec", DASHBOARD_CONTAINER, "mkdir", "-p", py_dir)
    for py_file in skill_root.glob("*.py"):
        _docker("cp", str(py_file), f"{DASHBOARD_CONTAINER}:{py_dir}/")
    wired.append("python-scripts")

    # Update skills-config.json in the container
    _update_skills_config_in_container(skill_name, args)

    print(json.dumps({
        "success": True,
        "skill": skill_name,
        "wired": wired,
        "message": f"Skill '{skill_name}' wired into dashboard. Run 'rebuild-dashboard' to apply.",
    }))


def _update_skills_config_in_container(skill_name, args):
    """Merge this skill's metadata into skills-config.json inside the container."""
    # Read current config from container
    try:
        r = _docker("exec", DASHBOARD_CONTAINER, "cat", "/app/public/skills-config.json")
        configs = json.loads(r.stdout)
    except Exception:
        configs = []

    # Remove existing entry for this skill (if re-wiring)
    configs = [c for c in configs if c.get("slug") != skill_name]

    # Add new entry
    entry = {
        "slug": skill_name,
        "enabled": True,
        "name": getattr(args, "display_name", None) or skill_name.replace("-", " ").title(),
        "description": getattr(args, "description", None) or f"{skill_name} skill dashboard",
        "url_path": f"/{skill_name}",
        "icon": getattr(args, "icon", None) or "Box",
        "color": getattr(args, "color", None) or "blue",
    }
    configs.append(entry)

    # Write back to container
    config_json = json.dumps(configs, indent=2)
    _docker(
        "exec", DASHBOARD_CONTAINER,
        "sh", "-c", f"echo '{config_json}' > /app/public/skills-config.json",
    )


def cmd_rebuild_dashboard(args):
    """Rebuild Next.js inside the dashboard container and restart."""
    if _dashboard_container_status() != "running":
        print(json.dumps({"success": False, "error": "Dashboard container is not running. Run 'init' first."}))
        sys.exit(1)

    print(json.dumps({"step": "rebuilding", "message": "Running npm run build inside dashboard container..."}))
    try:
        _docker("exec", DASHBOARD_CONTAINER, "npx", "next", "build", check=True, capture=False)
    except subprocess.CalledProcessError:
        print(json.dumps({"success": False, "error": "Next.js build failed. Check container logs."}))
        sys.exit(1)

    # Restart the container to pick up the new build
    _docker("restart", DASHBOARD_CONTAINER)

    print(json.dumps({
        "success": True,
        "message": "Dashboard rebuilt and restarted. Open http://localhost:3001",
    }))


def cmd_dashboard_status(args):
    """Show which skills are wired into the dashboard."""
    status = _dashboard_container_status()
    if status != "running":
        print(json.dumps({"success": True, "dashboard": status or "not-created", "skills": []}))
        return

    # Read skills-config.json from container
    try:
        r = _docker("exec", DASHBOARD_CONTAINER, "cat", "/app/public/skills-config.json")
        configs = json.loads(r.stdout)
    except Exception:
        configs = []

    # Check which skill directories exist in the container
    try:
        r = _docker("exec", DASHBOARD_CONTAINER, "ls", "/app/.claude/skills/")
        skill_dirs = r.stdout.strip().split() if r.stdout.strip() else []
    except Exception:
        skill_dirs = []

    print(json.dumps({
        "success": True,
        "dashboard": "running",
        "url": "http://localhost:3001",
        "wired_skills": [c.get("slug") for c in configs],
        "python_scripts": skill_dirs,
    }))


def cmd_reset(args):
    """Drop and recreate the database. WARNING: destroys all data."""
    if not args.yes:
        print(json.dumps({"success": False, "error": "Pass --yes to confirm database reset. This destroys ALL data."}))
        sys.exit(1)

    with _get_driver() as driver:
        if _database_exists(driver):
            driver.databases.get(TYPEDB_DATABASE).delete()
        driver.databases.create(TYPEDB_DATABASE)
        _load_schema(driver)

    print(json.dumps({
        "success": True,
        "database": TYPEDB_DATABASE,
        "schema": "loaded",
        "message": "Database reset. Re-run each skill's init-schema command to reload domain schemas.",
    }))


def main():
    parser = argparse.ArgumentParser(description="Alhazen Core — TypeDB infrastructure setup")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Start TypeDB + dashboard, create database, load base schema")
    init_p.add_argument("--extra-schema", nargs="*", help="Additional .tql schema files to load after base schema")

    load_p = sub.add_parser("load-schema", help="Load a schema file into the existing database")
    load_p.add_argument("schema_file", help="Path to the .tql schema file")

    wire_p = sub.add_parser("wire-dashboard", help="Copy a skill's dashboard files into the dashboard container")
    wire_p.add_argument("--skill-name", required=True, help="Skill name (e.g., jobhunt)")
    wire_p.add_argument("--dashboard-dir", required=True, help="Path to skill's dashboard/ directory")
    wire_p.add_argument("--display-name", help="Display name for the skill in the hub")
    wire_p.add_argument("--description", help="Short description for the hub card")
    wire_p.add_argument("--icon", help="Lucide icon name (default: Box)")
    wire_p.add_argument("--color", help="Theme color (default: blue)")

    sub.add_parser("rebuild-dashboard", help="Rebuild Next.js inside the dashboard container")
    sub.add_parser("dashboard-status", help="Show which skills are wired into the dashboard")
    sub.add_parser("status", help="Check TypeDB container and database state")

    reset_p = sub.add_parser("reset", help="Drop and recreate the database (destroys data)")
    reset_p.add_argument("--yes", action="store_true", help="Confirm destructive reset")

    args = parser.parse_args()
    dispatch = {
        "init": cmd_init,
        "load-schema": cmd_load_schema,
        "wire-dashboard": cmd_wire_dashboard,
        "rebuild-dashboard": cmd_rebuild_dashboard,
        "dashboard-status": cmd_dashboard_status,
        "status": cmd_status,
        "reset": cmd_reset,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
