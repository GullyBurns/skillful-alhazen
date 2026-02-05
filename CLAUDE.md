# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Skillful-Alhazen is a TypeDB-powered scientific knowledge notebook. It helps researchers build knowledge graphs from papers and notes using AI-powered analysis. Named after Ibn al-Haytham (965-1039 AD), an early pioneer of the scientific method.

Forked from the CZI [alhazen](https://github.com/chanzuckerberg/alhazen) project.

## Quick Start

```bash
# Start TypeDB
docker compose -f docker-compose-typedb.yml up -d

# Install with TypeDB support
pip install -e ".[typedb]"

# Use the skill
/typedb-notebook remember "key finding from paper X"
/typedb-notebook recall "paper X"
```

## Architecture

### TypeDB Schema
- `local_resources/typedb/alhazen_notebook.tql` - Core notebook schema
- `local_resources/typedb/namespaces/scilit.tql` - Scientific literature extensions
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

Each skill includes a SKILL.md (documentation) and Python script:

- **typedb-notebook** - Knowledge operations (remember, recall, organize)
  - `.claude/skills/typedb-notebook/SKILL.md`
  - `.claude/skills/typedb-notebook/typedb_notebook.py`

- **epmc-search** - Europe PMC literature search
  - `.claude/skills/epmc-search/SKILL.md`
  - `.claude/skills/epmc-search/epmc_search.py`

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
1. Use WebFetch to read the API documentation
2. Create a skill directory: `.claude/skills/<skill-name>/`
3. Write a script following the pattern of existing scripts
4. Create `SKILL.md` documenting the commands

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
conda create -n alhazen python=3.11
conda activate alhazen
pip install -e ".[typedb,dev]"
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
pytest tests/test_typedb_client.py -v
```

**CLI usage:**
```bash
python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection --name "Test"
python .claude/skills/epmc-search/epmc_search.py count --query "CRISPR"
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

.claude/
└── skills/             # Claude Code skills (each with SKILL.md + script)
    ├── typedb-notebook/
    │   ├── SKILL.md
    │   └── typedb_notebook.py
    └── epmc-search/
        ├── SKILL.md
        └── epmc_search.py
```

## Team Conventions

When Claude makes a mistake, add it to this section so it doesn't happen again.
