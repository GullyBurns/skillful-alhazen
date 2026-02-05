---
name: epmc-search
description: Search Europe PMC for scientific papers and store them in the TypeDB knowledge graph
---

# Europe PMC Search Skill

Search Europe PMC (EPMC) for scientific literature and store results in the Alhazen TypeDB knowledge graph. Use this to build corpora of papers on research topics.

## Prerequisites

- TypeDB must be running: `docker compose -f docker-compose-typedb.yml up -d`
- TypeDB driver installed: `pip install 'typedb-driver>=2.25.0,<3.0.0'`
- requests and tqdm: `pip install requests tqdm`

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen)

---

## Commands

### Search and Store Papers

Search EPMC and store results in TypeDB as a collection.

**Triggers:** "search epmc", "search for papers", "find papers about", "build a corpus", "search pubmed", "search literature"

```bash
python .claude/skills/epmc-search/epmc_search.py search \
    --query "CRISPR AND gene editing" \
    --collection "CRISPR Papers" \
    --max-results 500
```

**Options:**
- `--query` (required): EPMC search query
- `--collection`: Name for the collection (auto-generated if not provided)
- `--collection-id`: Specific collection ID
- `--max-results`: Limit number of papers fetched
- `--page-size`: Results per API call (default: 1000)

**Returns:**
```json
{
  "success": true,
  "collection_id": "collection-abc123",
  "collection_name": "CRISPR Papers",
  "query": "CRISPR AND gene editing",
  "total_count": 15234,
  "fetched_count": 500,
  "stored_count": 487,
  "skipped_count": 13
}
```

### Count Results

Count papers matching a query without storing anything. Use this to estimate corpus size before committing.

**Triggers:** "how many papers", "count papers", "estimate corpus size"

```bash
python .claude/skills/epmc-search/epmc_search.py count --query "COVID-19 AND vaccine"
```

**Returns:**
```json
{
  "success": true,
  "query": "COVID-19 AND vaccine",
  "count": 89234
}
```

### Fetch Single Paper

Fetch a specific paper by DOI or PMID and store it.

**Triggers:** "fetch paper", "get paper", "add paper by DOI", "import paper"

```bash
# By DOI
python .claude/skills/epmc-search/epmc_search.py fetch-paper --doi "10.1038/s41586-020-2008-3"

# By PMID
python .claude/skills/epmc-search/epmc_search.py fetch-paper --pmid "32015507"

# Add to existing collection
python .claude/skills/epmc-search/epmc_search.py fetch-paper --doi "10.1038/s41586-020-2008-3" --collection "collection-abc123"
```

**Returns:**
```json
{
  "success": true,
  "paper_id": "doi-10_1038-s41586-020-2008-3",
  "doi": "10.1038/s41586-020-2008-3",
  "title": "A pneumonia outbreak associated with a new coronavirus...",
  "type": "ScientificPrimaryResearchArticle"
}
```

### List Collections

List all collections created from EPMC searches.

**Triggers:** "list collections", "show my collections", "what collections do I have"

```bash
python .claude/skills/epmc-search/epmc_search.py list-collections
```

---

## Query Syntax

Europe PMC supports powerful query syntax:

### Boolean Operators
- `AND`, `OR`, `NOT`
- `""` for exact phrase
- `*` for wildcard
- `()` for grouping

### Field-Specific Searches
| Field | Example |
|-------|---------|
| `TITLE:` | `TITLE:CRISPR` |
| `ABSTRACT:` | `ABSTRACT:"gene editing"` |
| `AUTH:` | `AUTH:"Smith J"` |
| `JOURNAL:` | `JOURNAL:Nature` |
| `DOI:` | `DOI:"10.1038/..."` |
| `PMID:` | `PMID:12345678` |
| `GRANT_ID:` | `GRANT_ID:R01GM123456` |
| `GRANT_AGENCY:` | `GRANT_AGENCY:NIH` |

### Date Filters
```
PUB_YEAR:2023
FIRST_PDATE:[2020-01-01 TO 2024-12-31]
FIRST_PDATE:[2023-01-01 TO *]
```

### Publication Type
```
PUB_TYPE:"journal article"
PUB_TYPE:review
PUB_TYPE:preprint
```

### Open Access
```
OPEN_ACCESS:y
```

### Complex Query Examples

```bash
# CRISPR papers from 2022 onwards
python .claude/skills/epmc-search/epmc_search.py search \
    --query "CRISPR AND (Cas9 OR Cas12) AND FIRST_PDATE:[2022-01-01 TO *]" \
    --collection "Recent CRISPR"

# Open access single-cell papers
python .claude/skills/epmc-search/epmc_search.py search \
    --query '"single cell" AND (RNA-seq OR transcriptomics) AND OPEN_ACCESS:y' \
    --collection "Open Access scRNA-seq"

# Papers by author in specific journal
python .claude/skills/epmc-search/epmc_search.py search \
    --query 'AUTH:"Doudna J" AND JOURNAL:Science' \
    --collection "Doudna Science Papers"
```

---

## Workflows

### Literature Corpus Building

```bash
# 1. Estimate size
python .claude/skills/epmc-search/epmc_search.py count --query "your query"

# 2. Search and store (adjust max-results based on count)
python .claude/skills/epmc-search/epmc_search.py search \
    --query "your query" \
    --collection "Descriptive Name" \
    --max-results 1000

# 3. Review collection
python .claude/skills/typedb-notebook/typedb_notebook.py query-collection --id "collection-xxx"

# 4. Add notes about papers
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-id" \
    --content "Key finding: ..."
```

### Targeted Paper Import

```bash
# 1. Create collection
python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection --name "Key Papers"

# 2. Fetch specific papers
python .claude/skills/epmc-search/epmc_search.py fetch-paper --doi "10.1234/paper1" --collection "collection-xxx"
python .claude/skills/epmc-search/epmc_search.py fetch-paper --doi "10.1234/paper2" --collection "collection-xxx"

# 3. Add analysis notes
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "doi-10_1234-paper1" \
    --content "Analysis: ..."
```

---

## API Documentation

For writing new scripts or understanding the API:
- Europe PMC REST API: https://europepmc.org/RestfulWebService
- Search syntax: https://europepmc.org/searchsyntax
- API endpoint: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`

The script uses `resultType=core` to get full metadata including abstracts.
