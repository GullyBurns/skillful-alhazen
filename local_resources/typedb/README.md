# TypeDB Schema for Alhazen Notebook Model

This directory contains the TypeDB schema implementation for Alhazen's knowledge graph.

## Files

- `alhazen_notebook.tql` - Main schema defining the core Notebook Model entities and relations
- `namespaces/scilit.tql` - Scientific literature namespace with domain-specific types
- `agent-memory-typedb-schema.md` - Design documentation and examples

## Quick Start

### 1. Start TypeDB Server

```bash
# From project root
docker compose -f docker-compose-typedb.yml up -d
```

### 2. Load Schema (manual)

```bash
# Connect to TypeDB container
docker exec -it alhazen-typedb /opt/typedb-all-linux-x86_64/typedb console

# In console:
> database create alhazen
> transaction alhazen schema write
> source /schema/alhazen_notebook.tql
> commit
> transaction alhazen schema write
> source /schema/namespaces/scilit.tql
> commit
```

### 3. Verify Schema

```bash
# In TypeDB console:
> transaction alhazen schema read
> match $x sub entity; get $x;
```

## Full Stack with MCP Server

```bash
# Start TypeDB + MCP server + auto-initialize schema
docker compose -f docker-compose-typedb-mcp.yml up -d

# The init container will automatically:
# 1. Create the 'alhazen' database
# 2. Load the main schema
# 3. Load the scilit namespace
```

## Core Entities

| Entity | Description |
|--------|-------------|
| `collection` | Organized groupings of Things |
| `thing` | Primary research objects (papers, datasets) |
| `artifact` | Specific representations (PDFs, XML, citations) |
| `fragment` | Parts of artifacts (sections, paragraphs, figures) |
| `note` | Agent-generated annotations |

## Scientific Literature Namespace (scilit-*)

| Entity | Description |
|--------|-------------|
| `scilit-paper` | A scientific publication with DOI, PMID, etc. |
| `scilit-dataset` | A scientific dataset |
| `scilit-jats-fulltext` | JATS XML full-text artifact |
| `scilit-pdf-fulltext` | PDF full-text artifact |
| `scilit-section` | A section fragment (abstract, methods, etc.) |
| `scilit-extraction-note` | Extracted information note |
| `scilit-synthesis-note` | Synthesis across multiple sources |

## Example Queries

### Insert a Paper

```typeql
insert $p isa scilit-paper,
    has id "paper-001",
    has name "CRISPR-Cas9 Gene Editing in Mice",
    has doi "10.1234/example",
    has abstract "We demonstrate efficient gene editing...",
    has publication-year 2024;
```

### Create a Note About a Paper

```typeql
match $p isa scilit-paper, has id "paper-001";
insert $n isa note,
    has id "note-001",
    has content "Key finding: 95% editing efficiency in liver cells",
    has confidence 0.9;
    (note: $n, subject: $p) isa aboutness;
```

### Find All Notes About a Topic

```typeql
match
    $t isa tag, has name "crispr";
    (tagged-entity: $e, tag: $t) isa tagging;
    (note: $n, subject: $e) isa aboutness;
fetch $n: content, confidence;
```

## MCP Tools

When running with the MCP server, Claude can use these tools:

| Tool | Description |
|------|-------------|
| `insert_collection` | Create a new collection |
| `insert_thing` | Add a research item |
| `insert_artifact` | Add a representation of a thing |
| `insert_fragment` | Extract a fragment from an artifact |
| `insert_note` | Store a note about entities |
| `query_collection` | Get collection info and members |
| `query_thing` | Get thing info with artifacts and notes |
| `query_notes_about` | Find notes about an entity |
| `search_by_tag` | Find entities by tag |
| `tag_entity` | Apply a tag to an entity |
| `traverse_provenance` | Get provenance chain |

## Europe PMC Integration

The `scripts/epmc_search.py` script provides integration with Europe PMC for ingesting scientific literature.

### CLI Commands

```bash
# Search EPMC and store results in TypeDB
python scripts/epmc_search.py search \
    --query "CRISPR AND gene editing" \
    --collection "CRISPR Papers" \
    --max-results 500

# Count results without storing
python scripts/epmc_search.py count --query "COVID-19 AND vaccine"

# Fetch a single paper by DOI
python scripts/epmc_search.py fetch-paper --doi "10.1038/s41586-020-2008-3"

# List all search collections
python scripts/epmc_search.py list-collections
```

### EPMC Query Syntax

```
# Basic operators
CRISPR AND gene editing
COVID-19 OR SARS-CoV-2
NOT retracted

# Field-specific searches
TITLE:machine learning
AUTH:"Smith J"
JOURNAL:Nature
DOI:10.1038/s41586-020-2008-3

# Date filters
PUB_YEAR:2023
FIRST_PDATE:[2020-01-01 TO 2024-12-31]

# Open access only
OPEN_ACCESS:y
```

### Data Flow

1. **Query EPMC API** - Fetch papers matching search criteria
2. **Create Collection** - Store search metadata with logical query
3. **Insert Papers** - Create `scilit-paper` entities with DOI, PMID, etc.
4. **Create Artifacts** - Store citation records as `scilit-citation-record`
5. **Extract Fragments** - Create title and abstract as `scilit-section` fragments
6. **Apply Tags** - Tag papers by publication type (review, preprint, etc.)

## Configuration

Environment variables for the MCP server:

| Variable | Default | Description |
|----------|---------|-------------|
| `TYPEDB_HOST` | localhost | TypeDB server hostname |
| `TYPEDB_PORT` | 1729 | TypeDB server port |
| `TYPEDB_DATABASE` | alhazen | Database name |
