# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Skillful-Alhazen is a TypeDB-powered scientific knowledge notebook. It helps researchers build knowledge graphs from papers and notes using AI-powered analysis. Named after Ibn al-Haytham (965-1039 AD), an early pioneer of the scientific method.

Forked from the CZI [alhazen](https://github.com/chanzuckerberg/alhazen) project.

## Quick Start

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install dependencies
uv sync --all-extras

# 3. Start TypeDB
docker compose -f docker-compose-typedb.yml up -d

# 4. Initialize database with schemas
docker exec -i alhazen-typedb /opt/typedb-all-linux-x86_64/typedb console --server=localhost:1729 << 'EOF'
database create alhazen_notebook
transaction alhazen_notebook schema write
source /schema/alhazen_notebook.tql
commit
transaction alhazen_notebook schema write
source /schema/namespaces/scilit.tql
commit
transaction alhazen_notebook schema write
source /schema/namespaces/jobhunt.tql
commit
EOF

# 5. Use the skills
/typedb-notebook remember "key finding from paper X"
/jobhunt ingest-job --url "https://example.com/job"
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
- `local_resources/typedb/agent-memory-typedb-schema.md` - Documentation

### Alhazen's Notebook Model

The data model uses five core entity types in TypeDB:
- **Collection** - A named group of Things (papers, documents, etc.)
- **Thing** - Any recorded item (typically a scientific publication)
- **Artifact** - A specific representation of a Thing (e.g., PDF, JATS XML, citation record)
- **Fragment** - A selected portion of an Artifact (section, paragraph, etc.)
- **Note** - A structured annotation about any entity

### MCP Server
- `src/skillful_alhazen/mcp/typedb_client.py` - TypeDB client library
- `src/skillful_alhazen/mcp/typedb_server.py` - FastMCP server

### Skills

Skills follow a **three-component architecture**:
1. **TypeDB Schema** (`local_resources/typedb/namespaces/<domain>.tql`) - Data model
2. **Skill Definition** (`.claude/skills/<domain>/SKILL.md` + `<domain>.py`) - Claude's interface
3. **Dashboard** (optional) (`dashboard/`) - Web UI

**Documentation:**
- Wiki: [Skill Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) - Complete guide for humans
- `.claude/skills/domain-modeling/SKILL.md` - Design guidance (callable skill for Claude)
- `.claude/skills/_template/` - Template files for creating new skills

**Available Skills:**

- **typedb-notebook** - Knowledge operations (remember, recall, organize)
  - `.claude/skills/typedb-notebook/SKILL.md`
  - `.claude/skills/typedb-notebook/typedb_notebook.py`

- **epmc-search** - Europe PMC literature search
  - `.claude/skills/epmc-search/SKILL.md`
  - `.claude/skills/epmc-search/epmc_search.py`

- **jobhunt** - Job hunting notebook (positions, companies, skills, learning)
  - `.claude/skills/jobhunt/SKILL.md`
  - `.claude/skills/jobhunt/jobhunt.py`
  - `local_resources/typedb/namespaces/jobhunt.tql`
  - `dashboard/` (full-stack example)

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
1. Copy the template: `cp -r .claude/skills/_template .claude/skills/<skill-name>`
2. Design the TypeDB schema in `schema.tql`, copy to `local_resources/typedb/namespaces/`
3. Implement commands in `<skill-name>.py` following the template
4. Document in `SKILL.md` with commands and sensemaking workflow
5. See wiki [Skill Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) for full guide

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

**Installation:**
```bash
uv sync --all-extras
```

**Start TypeDB:**
```bash
docker compose -f docker-compose-typedb.yml up -d
```

**Full stack with MCP server:**
```bash
docker compose -f docker-compose-typedb-mcp.yml up -d
```

**Running tests:**
```bash
uv run pytest tests/test_typedb_client.py -v
```

**CLI usage:**
```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection --name "Test"
uv run python .claude/skills/epmc-search/epmc_search.py count --query "CRISPR"
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline
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

## Directory Structure

```
src/skillful_alhazen/   # Main package
├── __init__.py         # Package version
├── mcp/                # MCP server and TypeDB client
│   ├── typedb_client.py
│   └── typedb_server.py
└── utils/              # Utility modules (placeholder)

tests/                  # Test files
local_resources/
└── typedb/             # TypeDB schemas
    ├── alhazen_notebook.tql
    └── namespaces/
        ├── scilit.tql
        └── jobhunt.tql

dashboard/              # Next.js TypeScript dashboard
├── src/
│   ├── app/            # App router pages and API routes
│   ├── components/     # React components (shadcn/ui)
│   └── lib/            # TypeDB client utilities
├── package.json
└── tailwind.config.ts

.claude/
└── skills/             # Claude Code skills (each with SKILL.md + script)
    ├── typedb-notebook/
    ├── epmc-search/
    └── jobhunt/
```

## Team Conventions

When Claude makes a mistake, add it to this section so it doesn't happen again.

### TypeDB 2.x Query Notes
- **No `optional` in fetch queries** - TypeDB 2.x doesn't support optional joins in fetch. Use separate queries instead.
- **Fetch syntax** - Use `fetch $var: attr1, attr2;` not `fetch $var.attr1, $var.attr2;`
