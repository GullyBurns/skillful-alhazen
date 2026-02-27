# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Skillful-Alhazen is a TypeDB-powered scientific knowledge notebook. It helps researchers build knowledge graphs from papers and notes using AI-powered analysis. Named after Ibn al-Haytham (965-1039 AD), an early pioneer of the scientific method.

Forked from the CZI [alhazen](https://github.com/chanzuckerberg/alhazen) project.

## Quick Start

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Phase 1 Build: install deps + resolve all skills + start TypeDB
make build

# 3. Use the skills (Claude Code reads from .claude/skills/)
/typedb-notebook remember "key finding from paper X"
/jobhunt ingest-job --url "https://example.com/job"

# 4. Phase 2 Deploy: push to a production OpenClaw instance
make deploy-macmini   # or: make deploy-vps
```

**Individual build steps:**
```bash
make build-env    # Install Python dependencies (uv sync --all-extras)
make build-skills # Resolve skills-registry.yaml → local_skills/ + wire .claude/skills/
make build-db     # Start TypeDB + load all schemas (run after build-skills)

# Or individual db steps:
make db-start     # Start TypeDB container
make db-init      # Create database and load all schemas
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

**Development:**
```bash
make help             # Show all available targets
make status           # Show project status
make test             # Run tests
make lint             # Run ruff linter
make clean            # Clean generated files
```

## TypeDB Version

**Current: TypeDB 2.x (2.25.0 server, 2.29.x driver)**

We are staying on TypeDB 2.x because:
- TypeDB 3.0 was released Dec 2024 but Python driver is still alpha (3.0.0a9)
- Significant breaking changes in query syntax and API
- Production stability is important for this project

**TypeDB 2.x Documentation Reference:**
- `.claude/skills/typedb-notebook/typedb-2x-documentation.md` - Comprehensive TypeQL 2.x reference
- Includes: queries, patterns, statements, types, values, modifiers, keywords, Python driver
- **Always consult this file when writing TypeDB schemas or queries**

**Future Migration (planned for Q2-Q3 2025):**
When TypeDB 3.0 drivers reach stable, migration will require:
- Schema updates (Rules → Functions)
- Query syntax changes throughout codebase
- API changes (sessions eliminated, simplified transactions)
- See: https://typedb.com/blog/typedb-3-0-is-now-live/

## Architecture

### TypeDB Schema
- `local_resources/typedb/alhazen_notebook.tql` - Core notebook schema
- `local_resources/typedb/namespaces/scilit.tql` - Scientific literature extensions
- `local_resources/typedb/namespaces/jobhunt.tql` - Job hunting extensions
- `local_resources/typedb/namespaces/apm.tql` - Precision medicine extensions
- `local_resources/typedb/namespaces/techrecon.tql` - Tech recon extensions
- `local_resources/typedb/docs/` - Generated schema documentation

### Alhazen's Notebook Model

The data model uses a three-branch hierarchy rooted at `identifiable-entity`:

```
identifiable-entity (abstract)         — id, name, description, provenance
├── domain-thing                       — real-world objects (papers, genes, jobs)
├── collection                         — typed sets (corpora, searches, case files)
└── information-content-entity (abstract) — content, format, cache-path
    ├── artifact                       — raw captured content (PDF, HTML, API response)
    ├── fragment                       — extracted piece of an artifact
    └── note                           — Claude's analysis or annotation
```

- **domain-thing** is the base for all domain objects. Namespace subtypes (e.g., `scilit-paper`, `jobhunt-position`, `apm-gene`) inherit from it.
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

**Storage Strategy:**
- Content < 50KB: Stored inline in TypeDB `content` attribute
- Content >= 50KB: Stored in cache, referenced via `cache-path` attribute

**Artifact types are shared across skills.** A PDF ingested by jobhunt (resume) uses the same `pdf/` directory as papers ingested by epmc-search. This enables cross-skill artifact reuse and consistent type handling.

**Cache Utilities:**
- `src/skillful_alhazen/utils/cache.py` - Cache management functions
- Use `should_cache()` to check if content exceeds threshold
- Use `save_to_cache()` to store and get metadata
- Use `load_from_cache_text()` to retrieve content

### Skills

Skills follow a **self-contained directory architecture**:
```
skills/<name>/          (core skills, committed to this repo)
  SKILL.md              — Claude Code skill definition + frontmatter metadata
  skill.yaml            — structured metadata (name, description, license, etc.)
  <name>.py             — CLI entry point
  schema.tql            — TypeDB schema extension (loaded by make build-db)

local_skills/<name>/    (gitignored build artifact — DO NOT EDIT HERE)
  → core skills: symlinked from ../skills/<name>
  → external skills: cloned from git
```

**Single source of truth:** `skills-registry.yaml` — lists all skills (core with `path:`, external with `git:`).

**`make build-skills`** resolves the registry into `local_skills/` and wires `.claude/skills/` symlinks.

**Schema loading:** `make build-db` automatically discovers `local_skills/*/schema.tql` — no manual registration needed.

**Available Skills** (see `make skills-list` for live status):

- **typedb-notebook** *(core)* — Knowledge operations (remember, recall, organize)
  - `skills/typedb-notebook/`
- **web-search** *(core)* — Web search via SearXNG
  - `skills/web-search/`
- **domain-modeling** *(core)* — Design guidance for new skills
  - `skills/domain-modeling/`
- **jobhunt** *(external)* — Job hunting notebook
  - registered in `skills-registry.yaml`, resolved to `local_skills/jobhunt/`
- **techrecon** *(external)* — Systematic investigation of software systems
  - registered in `skills-registry.yaml`, resolved to `local_skills/techrecon/`
- **epmc-search** *(external)* — Europe PMC literature search
  - registered in `skills-registry.yaml`, resolved to `local_skills/epmc-search/`
- **apm** *(external)* — Precision medicine investigation
  - registered in `skills-registry.yaml`, resolved to `local_skills/apm/`

**Adding a new skill:**
1. Copy template: `cp -r skills/_template skills/<skill-name>`
2. Implement SKILL.md, skill.yaml, `<skill-name>.py`, schema.tql
3. Add to `skills-registry.yaml` with `path: skills/<skill-name>`
4. Run `make build-skills` to wire it into Claude Code
5. See wiki [Skill Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) for full guide

### Dashboards

Interactive Next.js TypeScript dashboard:

- `dashboard/` - Job hunt dashboard built with Next.js 16, shadcn/ui, and Tailwind CSS
  - Pipeline Kanban board for tracking applications
  - Skills matrix showing gaps across positions
  - Learning plan with progress tracking
  - Stats overview cards

Run with:
```bash
cd dashboard && npm run dev
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

**Quick setup (recommended):**
```bash
make setup          # Install dependencies + start TypeDB + initialize database
make status         # Check project status
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
uv run python .claude/skills/epmc-search/epmc_search.py count --query "CRISPR"
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline
# Note: .claude/skills/* are symlinks → local_skills/* → skills/* (for core)
```

**Dashboard:**
```bash
cd dashboard && npm install && npm run dev
```

## Environment Variables

**TypeDB:**
- `TYPEDB_HOST` - TypeDB server host (default: localhost)
- `TYPEDB_PORT` - TypeDB server port (default: 1729)
- `TYPEDB_DATABASE` - Database name (default: alhazen_notebook)

**Cache:**
- `ALHAZEN_CACHE_DIR` - File cache directory for large artifacts (default: ~/.alhazen/cache)

## Directory Structure

```
skills/                 # Core skills (committed — mirrors alhazen-skill-examples layout)
├── _template/          # Template for new skills (excluded from registry)
├── typedb-notebook/    # SKILL.md, skill.yaml, typedb_notebook.py
├── web-search/         # SKILL.md, skill.yaml
└── domain-modeling/    # SKILL.md, skill.yaml

skills-registry.yaml    # Single source of truth: path: (core) + git: (external)

local_skills/           # Gitignored build artifact — DO NOT EDIT
├── typedb-notebook  -> ../skills/typedb-notebook   (symlink, core)
├── web-search       -> ../skills/web-search        (symlink, core)
├── jobhunt/            (real clone, external)
└── ...

.claude/skills/         # Gitignored — symlinks generated by make build-skills
├── .gitignore          # * / !.gitignore
├── typedb-notebook  -> ../../local_skills/typedb-notebook
└── jobhunt          -> ../../local_skills/jobhunt

local_resources/
└── typedb/
    ├── alhazen_notebook.tql    # Core base schema (always loaded first)
    └── namespaces/             # Infrastructure schemas without a skill home
        ├── scilit.tql          # (stopgap: epmc-search has no schema.tql yet)
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

## Team Conventions

When Claude makes a mistake, add it to this section so it doesn't happen again.

### TypeDB 2.x Query Notes
- **No `optional` in fetch queries** - TypeDB 2.x doesn't support optional joins in fetch. Use separate queries instead.
- **Fetch syntax** - Use `fetch $var: attr1, attr2;` not `fetch $var.attr1, $var.attr2;`
