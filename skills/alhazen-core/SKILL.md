---
name: alhazen-core
description: REQUIRED FIRST — starts TypeDB + dashboard via Docker, loads the Alhazen base schema. Must install before any other Alhazen skill.
---

# Alhazen Core

**Install and initialize this skill before any other Alhazen skill.**

Starts the shared infrastructure via Docker Compose: TypeDB (knowledge graph database) + Dashboard (web UI for visualizing skill data). Loads `alhazen_notebook.tql` (the base schema that all domain skills extend).

**When to use:** First-time setup, infrastructure health checks, wiring skill dashboards, resetting the database.

## Prerequisites

- Docker must be running
- `uv` must be installed

## Quick Start

```bash
# Initialize TypeDB + dashboard (idempotent — safe to re-run)
uv run --project <skill-path> python <skill-path>/alhazen_core.py init

# Check status
uv run --project <skill-path> python <skill-path>/alhazen_core.py status
```

After init:
- TypeDB is available at `localhost:1729`
- Dashboard is available at `http://localhost:3001`

## Dashboard Workflow

The dashboard starts empty (just a hub page). After installing skills that have dashboards, wire them in and rebuild:

```bash
# 1. Wire a skill's dashboard into the container
uv run --project <skill-path> python <skill-path>/alhazen_core.py wire-dashboard \
    --skill-name jobhunt \
    --dashboard-dir /path/to/jobhunt/dashboard \
    --display-name "Jobhunt" \
    --icon Briefcase \
    --color indigo

# 2. Repeat for each skill with a dashboard...

# 3. Rebuild once (takes 30-60s)
uv run --project <skill-path> python <skill-path>/alhazen_core.py rebuild-dashboard

# 4. Check what's wired
uv run --project <skill-path> python <skill-path>/alhazen_core.py dashboard-status
```

When the user says "rebuild the dashboard", run steps 1-3 for each installed skill that has a `dashboard/` directory.

## Commands

| Command | Description |
|---------|-------------|
| `init` | Start TypeDB + dashboard, create database, load base schema |
| `load-schema FILE.tql` | Load additional schema into existing database |
| `wire-dashboard --skill-name X --dashboard-dir Y` | Copy skill's dashboard files into container |
| `rebuild-dashboard` | Rebuild Next.js inside dashboard container |
| `dashboard-status` | Show which skills are wired into the dashboard |
| `status` | Check TypeDB + dashboard container state |
| `reset --yes` | Drop and recreate the database (destroys data) |

**Read `USAGE.md` for troubleshooting and advanced usage.**
