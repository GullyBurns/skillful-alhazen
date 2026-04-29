# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Skillful-Alhazen is a TypeDB-powered scientific knowledge notebook. It helps researchers build knowledge graphs from papers and notes using AI-powered analysis. Named after Ibn al-Haytham (965-1039 AD), an early pioneer of the scientific method.

Forked from the CZI [alhazen](https://github.com/chanzuckerberg/alhazen) project.

## Agent OS — Coordinator Role

Claude Code acts as the **coordinator agent** for the Alhazen notebook OS. The OS has 6 layers, all backed by TypeDB as the single source of truth:

| Layer | Purpose | Implementation |
|-------|---------|----------------|
| **Identity** | Who the operator is, rules enforced every session | `operator-user` entity (10 context domains) via `agentic_memory.py` |
| **Context** | Structured knowledge about the operator's situation | TypeDB relations + context files in workspace |
| **Skills** | Domain-specific reusable instruction sets | `skills/` directories, `skills-registry.yaml` |
| **Memory** | What the system remembers across sessions | Two-tier: MEMORY.md (short-term) + TypeDB `memory-claim-note` (long-term) |
| **Connections** | How agents reach external systems | Documented in `connections/README.md` |
| **Verification** | Ensuring outputs are correct, system improves | `skilllog` + quality labels + schema gap detection |

### Coordinator Responsibilities

1. **Load identity at session start** — Query the operator-user from TypeDB to understand who you're working for:
   ```bash
   uv run python skills/agentic-memory/agentic_memory.py get-context --operator-id <id> 2>/dev/null
   ```

2. **Dispatch sub-agents for domain work** — Read agent definitions from `.claude/agents/` and dispatch using the `Agent()` tool. Each agent has:
   - `AGENT.md` — identity, capabilities, operating rules, skill bindings
   - `agent.yaml` — structured metadata (skills, connections, memory scope, dispatch config)

   When dispatching, inject:
   - The agent's AGENT.md content as the prompt preamble
   - Relevant operator context from TypeDB
   - Relevant memory (recall by topics matching the agent's `memory-scope`)
   - The specific task

3. **Consolidate results into long-term memory** — After sub-agent work completes:
   ```bash
   uv run python skills/agentic-memory/agentic_memory.py consolidate \
     --content "<key finding>" --subject <entity-id> --fact-type knowledge --confidence 0.9
   ```

4. **Create session episodes** — At session close, capture a process account:
   ```bash
   uv run python skills/agentic-memory/agentic_memory.py create-episode \
     --skill <primary-skill> --summary "<what was accomplished>"
   ```

### Available Agents

Agents are defined in `agents/` and resolved to `.claude/agents/` via `agents-registry.yaml`:

| Agent | Skills | Purpose |
|-------|--------|---------|
| `career-assistant` | jobhunt, web-search, agentic-memory, typedb-notebook | Career assistant: pipeline management, networking, interview prep/debrief, market monitoring, JSC tracking |

Read an agent's `AGENT.md` before dispatching to understand its capabilities and operating rules.

### Core OS Components (not skills)

These are OS-level capabilities available to the coordinator and all agents, not domain skills:

- **Identity + Memory + Context**: `skills/agentic-memory/agentic_memory.py` — operator profiles, memory claims, episodes, context domains
- **Notebook**: `skills/typedb-notebook/typedb_notebook.py` — collections, notes, tagging, aboutness
- **Verification**: `local_resources/skilllog/skill_logger.py` — invocation logging, quality labels, schema gap detection

## First-Run Check

> **For agents (Claude Code, Claude Desktop, worktrees):** Before doing any work, check whether the project has been built. If `local_skills/` does not exist, run `make build` from the project root. This installs Python dependencies, clones external skills, wires `.claude/skills/` symlinks, and starts TypeDB. The build is idempotent — safe to re-run.
>
> ```bash
> # Quick check — if this prints nothing, run make build
> ls local_skills/ 2>/dev/null || echo "NOT BUILT — run: make build"
> ```
>
> **Worktrees:** `make build` works from worktrees. TypeDB is a shared Docker container (uses a fixed compose project name), so `db-start` is idempotent — it skips if the container is already running. Each worktree gets its own `.venv` and `local_skills/`.

## First-Time Infrastructure Setup

> **For agents:** Follow these steps in order. Each step includes a verification command. Do not proceed to the next step until the verification passes.

### 1. Prerequisites

Verify all prerequisites before attempting the build:

```bash
# uv (Python package manager) — must print a version string
uv --version
# If missing: curl -LsSf https://astral.sh/uv/install.sh | sh

# Docker (container runtime) — must succeed without errors
docker info
# If failing: start Docker Desktop (macOS) or `sudo systemctl start docker` (Linux)

# Docker Compose v2 (bundled with Docker Desktop) — must print "Docker Compose version v2.x.x"
docker compose version
# NOTE: use `docker compose` (with a space), NOT the old `docker-compose` (with hyphen)

# git — must print a version string
git --version
```

**macOS:** Docker Desktop includes Docker Compose v2 — just start Docker Desktop.
**Linux:** Install `docker-compose-plugin` (not the standalone `docker-compose` v1).

### 2. Full Build (recommended)

```bash
make build
```

Runs four steps in sequence: `build-env` → `build-skills` → `build-dashboard` → `build-db`.
If any step fails, run the individual steps below to diagnose.

### 3. Individual Steps with Verification

#### Step 1: Install Python dependencies

```bash
make build-env
# Verify the TypeDB driver is importable:
uv run python -c "import typedb.driver; print('✓ typedb driver OK')"
```

Expected output: `✓ typedb driver OK`. If the import fails, run `uv sync --all-extras` directly and read any error output.

#### Step 2: Resolve skills from registry

```bash
make build-skills
# Verify that all skills are present in local_skills/:
ls local_skills/
```

Expected: directories for `typedb-notebook`, `web-search`, `curation-skill-builder`, `jobhunt`, `techrecon`, `scientific-literature`, and others listed in `skills-registry.yaml`. If external skills are absent, network access to `https://github.com/sciknow-io/alhazen-skill-examples` may have failed — run `make skills-update` to retry.

#### Step 3: Start TypeDB and load schemas

```bash
make build-db
# Verify the container is running and healthy:
docker ps --filter "name=alhazen-typedb" --format "table {{.Names}}\t{{.Status}}"
```

Expected: `alhazen-typedb` with status containing `(healthy)`. The `db-start` target waits up to 60 seconds for TypeDB readiness before running `db-init`. Each `.tql` schema file prints `OK` when loaded successfully.

### 4. Post-Build Smoke Test

```bash
# Check overall status (TypeDB container + skills count):
make status

# Write a test collection to TypeDB (confirms full read/write connectivity):
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection --name "smoke-test"
```

Expected: `make status` shows TypeDB ✓ running. The insert-collection command returns JSON with `"success": true`.

### 5. Optional: Semantic Search (Qdrant)

The `scientific-literature` skill requires Qdrant for embedding-based search. It is **not** started by `make build` — start it separately only when needed:

```bash
make qdrant-start           # starts Qdrant on http://localhost:6333
export VOYAGE_API_KEY=<key> # from https://dash.voyageai.com/
```

### Troubleshooting First-Time Setup

| Symptom | Cause | Fix |
|---------|-------|-----|
| `docker info` fails | Docker not running | Open Docker Desktop (macOS) or `sudo systemctl start docker` (Linux) |
| `make build-db` hangs > 60s | TypeDB slow to start | `docker logs alhazen-typedb`; increase Docker memory in Desktop settings |
| Port 1729 in use | Another TypeDB instance | `docker ps -a \| grep 1729` then `docker stop <id>` |
| External skills absent from `local_skills/` | Git clone failed silently | `make skills-update` to retry; check network/git access |
| Schema fails `[SYR1] type not found` | Missing `entity` keyword in `.tql` | See TypeDB 3.x notes — add `entity` keyword before type name |
| Schema fails `sub attribute` syntax error | Stale 2.x schema in external skill | See External Skill Schema Fixes below |
| TypeDB auth error in Python | Wrong credentials | Default: username=`admin`, password=`password` (no `.env` setup needed) |
| Queries return empty after adding new skill | Schema not reloaded | Re-run `make db-init` after `make build-skills` adds a new skill |

### Quick Reference

```bash
make build            # Full Phase 1 build: deps + skills + agents + TypeDB
make build-env        # Install Python dependencies (uv sync --all-extras)
make build-skills     # Resolve skills-registry.yaml → local_skills/ + wire .claude/skills/
make build-agents     # Resolve agents-registry.yaml → .claude/agents/
make build-db         # Start TypeDB + load all schemas (run after build-skills)
make db-start         # Start TypeDB container only
make db-init          # (Re-)load all schemas into running TypeDB
make skills-update    # Force re-clone all external skills
make status           # Show TypeDB + skills deployment status
make deploy-macmini   # Phase 2: deploy to Mac Mini (Docker Desktop)
make deploy-vps       # Phase 2: deploy to VPS (Podman rootless)
```

## Environment Management

**This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management.**

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (creates .venv automatically)
uv sync --all-extras

# Run a script with dependencies
uv run python script.py

# Add a new dependency
uv add package-name

# Update dependencies
uv sync
```

All dependencies are defined in `pyproject.toml`. The `.venv` directory is created automatically by uv.

## Makefile Usage

Two phases, each with a primary entry point:

**Phase 1 — Build (local dev, Claude Code):**
```bash
make build            # Full build: deps + skills + TypeDB
make build-env        # Install Python dependencies only
make build-skills     # Resolve skills registry → local_skills/ + wire .claude/skills/
make build-db         # Start TypeDB + load all schemas
```

**Phase 2 — Deploy (production OpenClaw):**
```bash
make deploy-macmini   # Deploy to Mac Mini (Docker Desktop)
make deploy-vps       # Deploy to VPS (Podman rootless)
make deploy-openclaw  # Wire skills + config for local OpenClaw instance
```

**Skills management:**
```bash
make skills-list      # Show all skills from registry with resolution status
make skills-update    # Re-resolve all skills (re-link core, re-clone external)
make skills-validate  # Validate all resolved skills have correct SKILL.md
```

**Database management:**
```bash
make db-start         # Start TypeDB container
make db-stop          # Stop TypeDB container
make db-init          # Create database and load all schemas (discovers local_skills/*/schema.tql)
make db-export        # Export database to timestamped zip
make db-import ZIP=/path/to/export.zip  # Import database
```

**Backups — TypeDB (`alhazen_notebook` and `dismech`):**

Exports are written to `~/.alhazen/cache/typedb/<database>_export_<timestamp>.zip`.

```bash
# Export (works while TypeDB is running)
make db-export                                   # exports alhazen_notebook (default)
uv run python .claude/skills/typedb-notebook/typedb_notebook.py export-db --database dismech

# Restore (drops and recreates the database)
uv run python .claude/skills/typedb-notebook/typedb_notebook.py import-db \
  --zip ~/.alhazen/cache/typedb/alhazen_notebook_export_<timestamp>.zip \
  --database alhazen_notebook
# NOTE: database must not already exist — delete it first if needed:
# uv run python -c "
#   from typedb.driver import TypeDB, Credentials, DriverOptions
#   d = TypeDB.driver('localhost:1729', Credentials('admin','password'), DriverOptions(is_tls_enabled=False))
#   d.databases.get('alhazen_notebook').delete(); d.close()
# "
```

**Backups — Qdrant vector store (`dismech_benchmark`, `apt-notes`, `alhazen_papers`):**

Snapshots are created online (no downtime) and stored inside the container at `/qdrant/snapshots/<collection>/`.
Copy them out immediately — they do not persist across container recreation.

```bash
# Create snapshots (run for each collection)
curl -X POST http://localhost:6333/collections/dismech_benchmark/snapshots
curl -X POST http://localhost:6333/collections/apt-notes/snapshots
curl -X POST http://localhost:6333/collections/alhazen_papers/snapshots

# Copy out of container
mkdir -p ~/.alhazen/cache/qdrant-snapshots
docker cp alhazen-qdrant:/qdrant/snapshots/dismech_benchmark/. ~/.alhazen/cache/qdrant-snapshots/
docker cp alhazen-qdrant:/qdrant/snapshots/apt-notes/. ~/.alhazen/cache/qdrant-snapshots/
docker cp alhazen-qdrant:/qdrant/snapshots/alhazen_papers/. ~/.alhazen/cache/qdrant-snapshots/

# Restore a collection from snapshot
curl -X POST "http://localhost:6333/collections/dismech_benchmark/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "file:///path/to/dismech_benchmark-<id>.snapshot"}'
```

**What to back up and when:**
- `alhazen_notebook` — contains all tech-recon, jobhunt, APT, and notebook data. Back up after significant work sessions. Most recent backup: `alhazen_notebook_export_20260425_*.zip`.
- `dismech` — the DisMech 797-disorder knowledge graph. Can be fully rebuilt from `git pull` + `make ingest` in the `alhazen-skill-dismech` repo, but a backup saves ~1 hour of ingest time. Most recent backup: `dismech_export_20260425_*.zip`.
- Qdrant `dismech_benchmark` — 25K embedded points (Voyage AI). Expensive to rebuild (API cost + time). Back up after any corpus update. Most recent snapshot: `dismech_benchmark-*-2026-04-26-*.snapshot`.
- Qdrant `alhazen_papers` / `apt-notes` — lower priority; rebuildable from source.

**Development:**
```bash
make help             # Show all available targets
make status           # Show project status
make test             # Run tests
make lint             # Run ruff linter
make clean            # Clean generated files
```

## TypeDB Version

**Current: TypeDB 3.x (3.8.0 server, 3.8.x Python driver)**

Migration from TypeDB 2.x to 3.x was completed Feb 2026. Key changes:
- Docker image: `typedb/typedb:3.8.0` (was `vaticle/typedb:2.25.0`)
- Python driver: `typedb-driver>=3.8.0` (was `typedb-driver>=2.25.0,<3.0.0`)
- No more sessions — use `driver.transaction(database, TransactionType.X)` directly
- Unified query method: `tx.query(query_string).resolve()` for all query types
- Fetch syntax: `fetch { "key": $var.attr };` (JSON-style, replaces `fetch $var: attr1, attr2;`)
- Schema: `attribute X, value T;` syntax (not `X sub attribute, value T;`)
- Abstract sub-entities: `entity X @abstract, sub Y,` (comma after `@abstract`, before `sub`) — **only works when Y is also abstract** (SVL14)
- `agent` is now `sub domain-thing` (inherits description, created-at, etc. from identifiable-entity)

**TypeDB 3.x `redefine` for schema changes:**
```typeql
redefine entity agent sub identifiable-entity;  -- in-place schema change without data migration
```

**TypeDB 3.x Connection (Python):**
```python
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType

driver = TypeDB.driver(
    f"{TYPEDB_HOST}:{TYPEDB_PORT}",
    Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
    DriverOptions(is_tls_enabled=False),
)

# Write transaction
with driver.transaction(database, TransactionType.WRITE) as tx:
    tx.query("insert $x isa collection, has id 'abc', has name 'Test';").resolve()
    tx.commit()

# Read transaction (fetch returns plain Python dicts)
with driver.transaction(database, TransactionType.READ) as tx:
    results = list(tx.query('''
        match $c isa collection;
        fetch { "id": $c.id, "name": $c.name };
    ''').resolve())
```

**Data migration note:** TypeDB 2.x `.typedb` binary exports are NOT directly importable into TypeDB 3.x. Data must be re-ingested using the skills after upgrading.

## Architecture

### TypeDB Schema
- `local_resources/typedb/alhazen_notebook.tql` - Core notebook schema
- `local_resources/typedb/docs/` - Generated schema documentation

### Alhazen's Notebook Model

The data model uses a three-branch hierarchy rooted at `identifiable-entity`:

```
identifiable-entity (abstract)         — id, name, description, provenance
├── domain-thing                       — real-world objects (papers, genes, jobs)
│   ├── agent                          — operational actors (human or AI)
│   │   ├── ai-agent                   — Claude, GPT-4, etc.
│   │   └── person                     — enriched: name, email, linkedin, title, bio, phone
│   │       ├── operator-user          — 10 context domains (identity, role, goals, etc.)
│   │       ├── author                 — publication authorship
│   │       └── jobhunt-contact        — contact-role (recruiter, hiring manager, etc.)
│   ├── organization                   — enriched: linkedin, website, location, industry
│   │   └── jobhunt-company            — job search context company
│   └── interaction                    — type, date, outcome, follow-up tracking
├── collection                         — typed sets (corpora, searches, case files)
└── information-content-entity (abstract) — content, format, cache-path
    ├── artifact                       — raw captured content (PDF, HTML, email, calendar)
    ├── fragment                       — extracted piece of an artifact
    └── note                           — Claude's analysis or annotation
```

- **domain-thing** is the base for all domain objects. Namespace subtypes (e.g., `scilit-paper`, `jobhunt-position`, `apm-gene`) inherit from it.
- **person** (sub agent) is the universal person model. All people — operator, authors, contacts — inherit from it. Enriched with linkedin-url, title, bio, phone-number. Plays works-at:employee and interaction-participation:participant.
- **organization** (sub domain-thing) is enriched with linkedin-url, company-url, location, industry. Plays works-at:employer. `jobhunt-company` inherits from it.
- **interaction** (sub domain-thing) tracks meetings, calls, emails, and interviews. Has type, date, outcome, follow-up tracking. Linked to participants via `interaction-participation` relation.
- **collection** is typed per namespace: `scilit-corpus`, `jobhunt-search`, `apm-case-file`, `apm-disease-family`, `apm-patient-cohort`.
- **information-content-entity** is only for content-bearing entities that own `content`, `cache-path`, `format`, etc.

### MCP Server
- `src/skillful_alhazen/mcp/typedb_client.py` - TypeDB client library
- `src/skillful_alhazen/mcp/typedb_server.py` - FastMCP server

### Artifact Cache

Large artifacts (PDFs, HTML, images) are stored in a file cache organized by content type:
- `~/.alhazen/cache/html/` - Web pages (job postings, company pages)
- `~/.alhazen/cache/pdf/` - Documents (papers, reports)
- `~/.alhazen/cache/image/` - Images (screenshots, diagrams)
- `~/.alhazen/cache/json/` - Structured data (API responses)
- `~/.alhazen/cache/text/` - Plain text files
- `~/.alhazen/cache/github/` - Github repos (indexed by <organization>/<repo>)

**Storage Strategy:**
- Content < 50KB: Stored inline in TypeDB `content` attribute
- Content >= 50KB: Stored in cache, referenced via `cache-path` attribute

**Artifact types are shared across skills.** A PDF ingested by jobhunt (resume) uses the same `pdf/` directory as papers ingested by scientific-literature. This enables cross-skill artifact reuse and consistent type handling.

**Cache Utilities:**
- `src/skillful_alhazen/utils/cache.py` - Cache management functions
- Use `should_cache()` to check if content exceeds threshold
- Use `save_to_cache()` to store and get metadata
- Use `load_from_cache_text()` to retrieve content

### Skills

Skills follow a **self-contained directory architecture**:
```
skills/<name>/          (core skills, committed to this repo)
  SKILL.md              — Short selection file (~30 lines): when to use, quick start
  USAGE.md              — Full reference (on-demand): commands, workflows, data model
  skill.yaml            — structured metadata (name, description, license, etc.)
  <name>.py             — CLI entry point
  schema.tql            — TypeDB schema extension (loaded by make build-db)

local_skills/<name>/    (gitignored build artifact — DO NOT EDIT HERE)
  → core skills: symlinked from ../skills/<name>
  → external skills: cloned from git
```

**SKILL.md / USAGE.md convention:**
- **SKILL.md** (~30 lines) is loaded into context on every conversation. Keep it short: frontmatter, purpose, triggers, prerequisites, one quick-start example, and a line saying "read USAGE.md before executing commands."
- **USAGE.md** is read on-demand when actively using the skill. Put all command details, sensemaking workflows, data model tables, TypeDB pitfalls, and examples here.
- This split reduces static context from ~26,600 → ~2,000 tokens for SKILL.mds.

**Single source of truth:** `skills-registry.yaml` — lists all skills (core with `path:`, external with `git:`).

**`make build-skills`** resolves the registry into `local_skills/` and wires `.claude/skills/` symlinks.

**Schema loading:** `make build-db` automatically discovers `local_skills/*/schema.tql` — no manual registration needed.

**Core OS Components** (managed by coordinator, not domain skills):

- **agentic-memory** *(core OS)* — Identity, memory, context (operator profiles, memory claims, episodes)
  - `skills/agentic-memory/`
- **typedb-notebook** *(core OS)* — Knowledge operations (collections, notes, tagging, aboutness)
  - `skills/typedb-notebook/`

**Domain Skills** (see `make skills-list` for live status):

- **web-search** *(core)* — Web search via SearXNG
  - `skills/web-search/`
- **curation-skill-builder** *(core)* — Design guidance for new TypeDB-backed curation skills (use official `skill-creator` plugin for all other skill development)
  - `skills/curation-skill-builder/`
- **jobhunt** *(external)* — Job hunting notebook
  - registered in `skills-registry.yaml`, resolved to `local_skills/jobhunt/`
- **tech-recon** *(core)* — Goal-driven technology investigation
  - `skills/tech-recon/`
- **scientific-literature** *(external)* — Multi-source scientific literature search and ingestion
  - Europe PMC, PubMed, OpenAlex, bioRxiv/medRxiv + semantic search (Voyage AI + Qdrant)
  - registered in `skills-registry.yaml`, resolved to `local_skills/scientific-literature/`

**Adding a new skill:**
1. Copy template: `cp -r skills/_template skills/<skill-name>`
2. Implement short `SKILL.md` (triggers, prereqs, quick start, USAGE.md reference), full `USAGE.md` (commands, workflows, data model), `skill.yaml`, `<skill-name>.py`, `schema.tql`
3. Add to `skills-registry.yaml` with `path: skills/<skill-name>`
4. Run `make build-skills` to wire it into Claude Code
5. See wiki [Skill Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) for full guide

### Agents

Agents are named sub-agents that bind to specific skills. They follow the **same directory convention as skills**:

```
agents/<name>/          (agent definitions, committed to this repo)
  AGENT.md              — Agent identity, capabilities, operating rules, skill bindings
  agent.yaml            — Structured metadata (skills, connections, memory scope, dispatch config)
```

**Single source of truth:** `agents-registry.yaml` — lists all agents (core with `path:`, external with `git:`).

**`make build-agents`** resolves the registry and symlinks agents to `.claude/agents/`.

**Adding a new agent:**
1. Copy template: `cp -r agents/_template agents/<agent-name>`
2. Define identity, skills, connections, and memory scope in `AGENT.md` and `agent.yaml`
3. Add to `agents-registry.yaml` with `path: agents/<agent-name>`
4. Run `make build-agents` to wire it into Claude Code

### Dashboards

Interactive Next.js TypeScript dashboard:

- `dashboard/` - Dashboards built with Next.js 16, shadcn/ui, and Tailwind CSS
  - Pipeline Kanban board for tracking applications
  - Skills matrix showing gaps across positions
  - Learning plan with progress tracking
  - Stats overview cards

**Skill dashboard wiring:** Each skill can contribute dashboard UI via `local_skills/<skill>/dashboard/`:
```
local_skills/<skill>/dashboard/
  lib.ts          → dashboard/src/lib/<skill>.ts       (API client functions)
  components/     → dashboard/src/components/<skill>/  (React components)
  pages/          → dashboard/src/app/(<skill>)/       (Next.js pages)
  routes/         → dashboard/src/app/api/<skill>/     (API routes)
```

- **Docker build** copies these files at build time (see `dashboard/Dockerfile` stage `node-builder`)
- **Local dev** uses symlinks — `make build-skills` wires components/routes but **not** `lib.ts` files. You must manually symlink them:
  ```bash
  cd dashboard/src/lib
  ln -sf ../../../local_skills/jobhunt/dashboard/lib.ts jobhunt.ts
  ln -sf ../../../local_skills/techrecon/dashboard/lib.ts techrecon.ts
  ```
- **Docker dashboard** runs on port 3001 (mapped from container 3000): `http://localhost:3001`

Run locally with:
```bash
cd dashboard && npm install && npm run dev
```

## Scripts and Token Efficiency

**Philosophy:** Use scripts to minimize token usage. Scripts handle heavy lifting (pagination, bulk operations, API calls, TypeDB transactions) while Claude orchestrates at a higher level.

**When to use scripts:**
- Bulk operations (searching hundreds of papers)
- Paginated API calls
- Complex TypeDB transactions
- Repetitive data transformations

**When Claude can work directly:**
- Single paper lookups
- Simple queries
- Orchestrating multiple script calls
- Analyzing results returned by scripts

**Writing new skills:** When integrating a new data source or API:
1. Copy the template: `cp -r skills/_template skills/<skill-name>`
2. Design the TypeDB schema in `skills/<skill-name>/schema.tql` (auto-discovered by `make build-db`)
3. Implement commands in `<skill-name>.py` following the template
4. Fill in `SKILL.md` and `skill.yaml` with metadata and commands
5. Add a `path: skills/<skill-name>` entry to `skills-registry.yaml`
6. Run `make build-skills` then `make build-db` to wire everything
7. See wiki [Skill Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) for full guide

**Script conventions:**
- Scripts output JSON to stdout for easy parsing
- Progress/errors go to stderr
- Use argparse with subcommands
- Handle missing dependencies gracefully (check imports, warn user)
- Include `--help` documentation

Example: To add a new literature source like Semantic Scholar:
```bash
# 1. Read their API docs via WebFetch
# 2. Create .claude/skills/semantic-scholar/
# 3. Write semantic_scholar.py following epmc_search.py pattern
# 4. Create SKILL.md documenting commands
```

## Development Commands

**Project status:**
```bash
make status         # Show TypeDB container status + skills deployment count
```

**Manual commands:**
```bash
# Installation
uv sync --all-extras

# TypeDB management
make db-start       # Start TypeDB container
make db-stop        # Stop TypeDB container

# Full stack with MCP server
docker compose -f docker-compose-typedb-mcp.yml up -d

# Testing and development
make test           # Run tests
make lint           # Run linter
make clean          # Clean generated files
```

**CLI usage:**
```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection --name "Test"
uv run python .claude/skills/scientific-literature/scientific_literature.py count --query "CRISPR"
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline
# Note: .claude/skills/* are symlinks → local_skills/* → skills/* (for core)
```

**Dashboard:**
```bash
cd dashboard && npm install && npm run dev
```

## Environment Variables

**TypeDB:**
- `TYPEDB_HOST` - TypeDB server host (default: `localhost`)
- `TYPEDB_PORT` - TypeDB server port (default: `1729`)
- `TYPEDB_DATABASE` - Database name (default: `alhazen_notebook`)
- `TYPEDB_USERNAME` - TypeDB username (default: `admin`) — no setup needed for local Docker
- `TYPEDB_PASSWORD` - TypeDB password (default: `password`) — no setup needed for local Docker

**Cache:**
- `ALHAZEN_CACHE_DIR` - File cache directory for large artifacts (default: ~/.alhazen/cache)

**Semantic Search (literature skill):**
- `VOYAGE_API_KEY` - Voyage AI API key for embeddings (from https://dash.voyageai.com/)
- `QDRANT_HOST` - Qdrant vector store host (default: localhost)
- `QDRANT_PORT` - Qdrant vector store port (default: 6333)

## Directory Structure

```
agents/                 # Named sub-agent definitions (committed)
├── _template/          # Template for new agents
└── career-assistant/   # AGENT.md, agent.yaml (jobhunt, web-search, agentic-memory)

agents-registry.yaml    # Single source of truth for agents: path: (core) + git: (external)

skills/                 # Skills (committed — core OS + domain skills)
├── _template/          # Template for new skills (excluded from registry)
├── agentic-memory/     # Core OS: identity + memory + context
├── typedb-notebook/    # Core OS: notebook operations
├── web-search/         # Domain skill
├── curation-skill-builder/  # Domain skill
└── tech-recon/         # Domain skill

skills-registry.yaml    # Single source of truth for skills: path: (core) + git: (external)

connections/            # Documented connection capabilities
└── README.md           # Index of MCP servers, CLI tools, APIs with permissions

local_skills/           # Gitignored build artifact — DO NOT EDIT
├── agentic-memory   -> ../skills/agentic-memory    (symlink, core OS)
├── typedb-notebook  -> ../skills/typedb-notebook    (symlink, core OS)
├── web-search       -> ../skills/web-search         (symlink, core)
├── jobhunt/            (real clone, external)
└── ...

.claude/skills/         # Gitignored — symlinks generated by make build-skills
├── typedb-notebook  -> ../../local_skills/typedb-notebook
└── jobhunt          -> ../../local_skills/jobhunt

.claude/agents/         # Gitignored — symlinks generated by make build-agents
└── career-assistant -> ../../agents/career-assistant

local_resources/
└── typedb/
    ├── alhazen_notebook.tql    # Core base schema (always loaded first)
    └── namespaces/             # Infrastructure schemas without a skill home
        └── skilllog.tql

src/skillful_alhazen/   # Main package
├── mcp/                # MCP server and TypeDB client
└── utils/              # Utility modules

dashboard/              # Next.js TypeScript dashboard
deploy/                 # Ansible deployment scripts for Mac Mini and VPS
tests/                  # Test files
```

## Deployment: Build → Deploy Workflow

**(Phase 1 — Build)** `make build` — local dev with Claude Code. Python deps + skills resolved + TypeDB ready.

**(Phase 2 — Deploy)** `make deploy-macmini` or `make deploy-vps` — production OpenClaw.

**(B) Hardened Local Testing** &mdash; Full OpenClaw stack on a Mac Mini or second machine. Tests container networking, Squid proxy, MCP integration, Telegram.

**(C) Production VPS** &mdash; Hardened Linux server with rootless Podman, UFW, Fail2Ban, SSH key-only auth.

```bash
# Deploy to VPS
cd deploy
./deploy.sh -t 5.78.187.158 -p anthropic -m claude-sonnet-4-6 -k "$KEY"

# Deploy to Mac Mini
./deploy.sh -t 10.0.110.100 --target-type macmini -p anthropic -m claude-sonnet-4-6 -k "$KEY"
```

**Full documentation:** See `deploy/README.md` for architecture, troubleshooting, and configuration details.

### Known Deployment Issues
- **Anthropic SDK proxy bug:** The `@anthropic-ai/sdk` honors `HTTP_PROXY` but ignores `NO_PROXY`. The agent container must NOT have proxy env vars &mdash; it gets direct internet via `openclaw-external` network.
- **LiteLLM memory:** Needs at least 1GB (`mem_limit: 1g`). The 512MB default causes OOM on startup.
- **Model IDs:** Use exact Anthropic model IDs (`claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5-20251001`). Incorrect IDs return HTTP 404.

## Schema Evolution

When a schema gap requires changing existing entity types (hierarchy changes, attribute renames, type consolidation), use the declarative migration workflow instead of manual TypeQL `redefine`:

### Workflow

1. **Detect** — Schema gap found (by agent, skilllog hook, or manual review)
2. **Save old schema** — Copy the current `.tql` file before editing:
   ```bash
   cp local_resources/typedb/alhazen_notebook.tql \
      local_resources/typedb/migration-rules/<migration-name>/old_schema.tql
   ```
3. **Fix the schema** — Edit the `.tql` file with the desired changes
4. **Write intent file** — Describe what changed and why:
   ```yaml
   # local_resources/typedb/migration-rules/<migration-name>/intent.yaml
   renames:
     - old: contact-email
       new: email-address
       reason: "Standardized on core person attribute"
   hierarchy_changes:
     - type: jobhunt-contact
       old_parent: agent
       new_parent: person
       reason: "Contacts are people, should inherit person attributes"
   ```
5. **Generate rules** — Produce migration mapping rules:
   ```bash
   uv run python src/skillful_alhazen/utils/schema_diff.py diff \
     --old local_resources/typedb/migration-rules/<migration-name>/old_schema.tql \
     --new local_resources/typedb/alhazen_notebook.tql \
     --generate-rules \
     --rules-dir local_resources/typedb/migration-rules/<migration-name>/ \
     --intent local_resources/typedb/migration-rules/<migration-name>/intent.yaml
   ```
6. **Test** — Run against temporary databases (iterative):
   ```bash
   make db-migrate-test RULES=local_resources/typedb/migration-rules/<migration-name>/
   # Read errors, fix rules, re-run until clean
   make db-migrate-test-clean   # when done testing
   ```
7. **Migrate** — Run against production:
   ```bash
   make db-migrate RULES=local_resources/typedb/migration-rules/<migration-name>/
   ```
8. **Verify** — Check reconciliation output, query migrated data

### Key Commands

```bash
# Parse and inspect a schema file
uv run python src/skillful_alhazen/utils/schema_diff.py parse --schema FILE.tql

# Diff two schemas (JSON output)
uv run python src/skillful_alhazen/utils/schema_diff.py diff --old OLD.tql --new NEW.tql

# Diff with human-readable summary
uv run python src/skillful_alhazen/utils/schema_diff.py diff --old OLD.tql --new NEW.tql --summary

# Generate migration rules
uv run python src/skillful_alhazen/utils/schema_diff.py diff \
  --old OLD.tql --new NEW.tql \
  --generate-rules --rules-dir RULES_DIR/ [--intent INTENT.yaml]

# Test migration (non-destructive, iterative)
make db-migrate-test RULES=RULES_DIR/

# Run migration (production)
make db-migrate RULES=RULES_DIR/

# Clean up test databases
make db-migrate-test-clean
```

### Why Not redefine?

TypeDB 3.x `redefine` cannot reliably change entity hierarchies when existing data uses inherited `owns` declarations. The declarative migration approach (export → new schema → map data → verify) is safer and produces an auditable trail of rules.

### Preferred Migration Method: Binary Backup + Query Transfer

When the GLAV schema_mapper approach is too complex (many entity types, unclear attribute mappings), use the **binary backup + query transfer** method:

1. **Export** current database via `make db-export` (binary backup preserves all data + schema)
2. **Import** the backup as a temporary source database:
   ```bash
   uv run python .claude/skills/typedb-notebook/typedb_notebook.py import-db \
     --zip ~/.alhazen/cache/typedb/alhazen_notebook_export_LATEST.zip \
     --database alhazen_backup
   ```
3. **Drop and recreate** the main database with the new schema:
   ```bash
   # Delete main DB
   uv run python -c "
   from typedb.driver import TypeDB, Credentials, DriverOptions
   d = TypeDB.driver('localhost:1729', Credentials('admin','password'), DriverOptions(is_tls_enabled=False))
   d.databases.get('alhazen_notebook').delete(); d.close()"
   # Recreate with new schema
   make db-init
   ```
4. **Query the backup** to re-insert data into the new database. Write targeted TypeQL queries that read from `alhazen_backup` and insert into `alhazen_notebook`:
   ```python
   # Read from backup (old schema — data is intact)
   with driver.transaction("alhazen_backup", TransactionType.READ) as tx:
       results = list(tx.query('match $p isa jobhunt-position, has id $id, has name $n; fetch { "id": $id, "name": $n };').resolve())

   # Write to new database (new schema)
   with driver.transaction("alhazen_notebook", TransactionType.WRITE) as tx:
       for r in results:
           tx.query(f'insert $p isa jobhunt-position, has id "{r["id"]}", has name "{r["name"]}";').resolve()
       tx.commit()
   ```
5. **Clean up** the backup database when satisfied

**Why this works:** The binary backup preserves data with the old schema intact. Queries against the backup use the old schema's type inference (which works correctly for its own data). The new database has a clean schema loaded from the `.tql` files. You transfer data entity-by-entity using explicit attribute names — no generic `has $a` patterns.

**Why not generic export?** TypeDB's `has $a` (match any attribute) pattern breaks when additive `define` statements have corrupted type inference. Always use explicit attribute names (`has name $n, has id $id`) when querying.

**When to use which approach:**
- **GLAV schema_mapper** — best for systematic migrations with clear attribute mappings (renames, type consolidation). Produces auditable YAML rules. Use `make db-migrate` / `make db-migrate-test`.
- **Binary backup + query transfer** — best for quick migrations, exploratory schema changes, or when you have too many entity types for hand-written rules. More manual but avoids the schema_mapper's rule-writing overhead.
- **Both together** — use binary backup as the source database for schema_mapper rules. This is what `make db-migrate` does internally.

### GLAV for External Data Integration

The GLAV (Global-as-View / Local-as-View) methodology behind `schema_mapper.py` is not limited to schema migration — it is a general-purpose **information integration** approach. Use it whenever external data sources need to be imported or linked into the notebook's TypeDB representation:

1. **Build a temporary TypeDB image** of the external database. Load the external data into a separate TypeDB database using the source's native schema (or a minimal schema that captures its structure).
2. **Write YAML mapping rules** that define how the external schema maps to the notebook's `alhazen_notebook.tql` entity types. Each rule is a `(source_match, target_insert)` pair with skolemization for deterministic ID generation.
3. **Run the mapper** from the external database into `alhazen_notebook`:
   ```bash
   uv run python src/skillful_alhazen/utils/schema_mapper.py run \
     --source-db external_source --target-db alhazen_notebook \
     --rules-dir local_resources/typedb/integration-rules/external-name/
   ```
4. **Reconcile** to verify completeness.

This is how the DisMech disease mechanism knowledge graph was originally integrated — an external dataset loaded into a temporary database, then mapped into the notebook's entity hierarchy via declarative rules. The same pattern applies to any external data source: public databases (PubMed, Monarch, ChEMBL), partner data exports, or API-harvested datasets.

**Key principle:** The notebook schema (`alhazen_notebook.tql` + skill schemas) is the **global schema** — the single integrated view. External sources are **local schemas** that get mapped into it. The mapping rules are the explicit, auditable bridge between them.

## Team Conventions

When Claude makes a mistake, add it to this section so it doesn't happen again.

### Schema Gap Reporting

A **schema gap** is when Claude tries to represent a concept, relationship, or entity type that has no place in the current TypeDB schema. Schema gaps are the primary signal for knowledge graph evolution — they reveal what the schema needs to grow to support.

**Two detection paths:**
1. **TypeDB error code in output** — the PostToolUse hook prints a `[SCHEMA-GAP-HINT]` when it detects `[SYR1]`, `[TYR01]`, `[FEX1]`, etc. in a skill's output. Follow the hint.
2. **Claude recognizes it** — during sensemaking, you realize a concept can't be stored. File immediately (don't wait until after the session).

**File a schema gap:**
```bash
uv run python local_resources/skilllog/skill_logger.py file-schema-gap \
  --skill <skill-name> \
  --concept "<concept Claude tried to represent>" \
  --missing "<which TypeDB entity/relation/attribute is absent>" \
  --suggested "<proposed TypeQL snippet, or 'unknown'>" \
  [--dry-run]
```

Repo routing is automatic: core skills (`typedb-notebook`, `web-search`, `curation-skill-builder`, `tech-recon`) → `GullyBurns/skillful-alhazen`; external skills (`jobhunt`, `scientific-literature`, `alg-precision-therapeutics`, `literature-trends`, `they-said-whaaa`) → `sciknow-io/alhazen-skill-examples`.

**Also file issues for design gaps discovered during planning** (missing constraints, schema mismatches, dashboard/schema mismatches):
```bash
gh issue create \
  --repo <repo> \
  --title "Gap [moderate][entity-schema]: <one-sentence summary>" \
  --body $'## What was missing\n<...>\n\n## What broke\n<...>\n\n## Suggested fix\n<...>\n\n## Generalizable pattern\n<...>\n\n---\n**Skill:** <skill>\n**Phase:** entity-schema\n**Severity:** moderate' \
  --label "gap:open"
```

**Severity:** `minor` = cosmetic, `moderate` = feature broken but workaround exists, `critical` = data loss or crash.

**List open gaps:** `gh issue list --repo <repo> --label "gap:open" --json number,title,url,labels`

**One-time setup** (if repo lacks labels/workflows):
```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  scaffold-improvement-loop --repo <owner/name> [--skill <name>]
```

### TypeDB 3.x Query Notes
- **Fetch syntax** - Use `fetch { "key": $var.attr };` JSON-style (NOT `fetch $var: attr1, attr2;` — that is 2.x syntax)
- **Abstract sub-entities** - Syntax is `entity X @abstract, sub Y,` (comma between `@abstract` and `sub`) — **SVL14: Y must also be abstract**; `domain-thing` is concrete so entities subtyping it cannot be `@abstract`
- **No sessions** - Use `driver.transaction(database, TransactionType.X)` directly (no `driver.session(...)` wrapper)
- **All queries use same method** - `tx.query(query_string).resolve()` for insert, fetch, delete, define
- **Fetch results are plain dicts** - No `.get("value")` unwrapping needed; access keys directly
- **Delete entity/relation syntax** - Use `delete $x;` (NOT `delete $x isa type;` — the `isa` qualifier in the delete clause is invalid in 3.x and causes a parse error)
- **Delete has-attribute syntax** - Use `delete has $v of $e;` (NOT `delete $e has attr $v;` — causes "expected OF" parse error)
- **`entity` is reserved in match clauses** - Cannot use `$x isa entity, has id ...` — `entity` is a TypeQL keyword, not a type label. Use `$x isa identifiable-entity, has id ...` to match any entity by id regardless of concrete type
- **Entity inequality** - Cannot compare entity variables with `!=` directly (causes [REP1] error). Compare id attributes: `$a has id $id1; $b has id $id2; $id1 != $id2;`
- **Note linking relation** - Use `(note: $n, subject: $e) isa aboutness` to attach a note to an entity (NOT `isa annotation` — that relation does not exist in the alhazen schema). `identifiable-entity` plays `aboutness:subject`; `note` plays `aboutness:note`
- **Entity keyword required** - New entity type definitions MUST use `entity` keyword: `entity my-type sub domain-thing,` — without it, TypeDB throws `[SYR1] The type 'X' was not found` (even for newly defined types)
- **No limit in fetch** - Fetch queries don't support `limit` modifier; apply limit in Python: `results[:N]`
- **Relations before entities** - Define relations first in namespace schemas so role names resolve when entities use `plays` clauses
- **No @key on custom attrs** - Only the inherited `id @key` works; adding `@key` to namespace attributes causes schema errors
- **Full reference** — Read `local_resources/typedb/llms.txt` on demand before writing queries; full docs at `local_resources/typedb/typedb-3x-reference.md`

### External Skill Fixes Must Go Upstream

- **Fix code in the upstream repo, not just `local_skills/`** — External skills
  (`jobhunt`, `techrecon`, etc.) are cloned from `https://github.com/sciknow-io/alhazen-skill-examples`.
  If you fix a file only in `local_skills/`, `make skills-update` will overwrite it.
  Always push the fix upstream to `sciknow-io/alhazen-skill-examples` at the matching subdirectory
  (e.g., `skills/demo/jobhunt/schema.tql`) and commit there.
- **This applies to ALL skill files** — Python scripts, schemas, dashboard components, lib.ts,
  pages, and routes. The upstream repo at `~/Documents/GitHub/alhazen-skill-examples` is the
  local clone. Fix there, commit, push, then `make skills-update` to pull into this project.
- **jobhunt + techrecon schemas were 2.x** — Both were migrated to TypeDB 3.x in Mar 2026
  (commit `6b41acf` in alhazen-skill-examples). If a schema fails on `make build-db` with a
  syntax error near `sub attribute`, the upstream source likely still has 2.x syntax.

### Dashboard Design Conventions

- **Overview-first layout**: Main entity pages (investigations, systems) show a high-level orientation summary at the top. All detail sections are click-through — do not render full content inline.
- **Notes**: Always render as a collapsible list (type badge + extracted heading visible; full markdown expands on click). Never dump all note markdown on the page at once.
- **Workflows**: Always surface workflow links on any entity page that has associated workflows.
- **Hyperlink style**: All navigation links must be visually distinct from body text. Use `text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors` consistently for all `<Link>` and `<a>` elements in techrecon dashboard pages.

### Dashboard & Docker Rebuild

- **Dashboard API errors → check skill Python scripts first** — The dashboard API routes
  (`/api/jobhunt/*`, `/api/techrecon/*`) call skill Python scripts via `child_process.execFile()`.
  If the dashboard shows "Failed to fetch data", check `docker logs alhazen-dashboard` for the
  actual TypeQL or Python error. The dashboard itself is usually fine — the skill script has the bug.
- **Docker build caching hides fixes** — After fixing files in `local_skills/`, `docker compose build`
  may use cached layers. Always use `docker compose build --no-cache dashboard` to ensure the
  fix is picked up. The full rebuild cycle:
  ```bash
  cd ~/Documents/GitHub/skillful-alhazen   # main repo, not worktree
  make skills-update                        # re-clone from upstream
  docker compose build --no-cache dashboard
  docker compose up -d dashboard
  ```
- **Dashboard page components vs API response format** — Skill dashboard page components
  (e.g., position detail page) may use `getValue()` helpers that expect TypeDB fetch format
  (`[{value: ...}]`), but `lib.ts` returns pre-extracted plain values (strings/numbers/nulls).
  When writing or fixing page components, check what format the API actually returns by
  curling the endpoint first: `curl -s http://localhost:3001/api/jobhunt/position/<id> | python3 -m json.tool`
- **TypeQL comparison operators** — In TypeDB 3.x `not {}` clauses (and elsewhere), use `==`
  for equality comparison, NOT `=`. `$var = "value"` causes a parse error: "expected comparator".

### Skill Script Queries

- **Dump before accessing** — When a skill script's JSON output schema is unknown, do a raw
  dump first to confirm key names: `| python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin),indent=2))"`
  before writing any key-access post-processor.
- **Pipeline exit 1 ≠ script failure** — In `script | python3 -c "..."`, exit code 1 almost
  always means the *post-processor* failed (KeyError, wrong key name), not the script itself.
  The script's `"success": true` in the output is the ground truth. Run the script alone to
  confirm, then fix the key names.
- **Canonical inspection one-liner:**
  ```bash
  uv run python .claude/skills/<skill>/<skill>.py <command> [args] 2>/dev/null \
      | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin),indent=2))"
  ```

### CRITICAL: Never Chain Destructive Commands With make build-skills

**Never combine `rm -rf` on skill directories with `make build-skills` (or any `make` target) in a single Bash tool call.**

In March 2026, running `rm -rf skills/literature-trends && rm -rf local_skills/literature-trends && make build-skills` in one call **deleted the entire project directory**. The exact root cause is unknown, but likely involves the PostToolUse hook (which fires during `make`) interacting with `deploy-claude-settings`, which rewrites `.claude/settings.json` using `$(shell pwd)`. The empty output from `make` should have been a warning sign.

**Rules:**
1. **Never chain `rm -rf` + `make` in one Bash call.** Split into separate tool calls with verification between each.
2. **Read the Makefile before running any `make` target** — `make build-skills` calls `deploy-claude-settings`, which has side effects (rewrites `settings.json`, touches `.claude/`).
3. **After any `rm -rf`, verify the working directory still exists** before doing anything else: `ls /Users/gullyburns/skillful-alhazen/`
4. **If `make` output is unexpectedly empty or silent, stop and investigate** before running any further commands.
