# TypeDB Notebook — Usage Reference

## Core Memory Operations

### Remember (insert-note)

Store information in the knowledge graph for later retrieval. Use this whenever you learn something worth remembering about a paper, concept, or any research topic.

**Triggers:** "remember this", "remember that", "save this", "note that", "store", "make a note", "don't forget", "keep track of"

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-xyz789" \
    --content "Key finding: 95% editing efficiency in liver cells. Uses novel lipid nanoparticle delivery." \
    --name "Key Findings" \
    --confidence 0.9 \
    --tags crispr liver high-efficiency
```

**Options:**
- `--subject` (required): ID of the entity this note is about
- `--content` (required): The note content
- `--name`: Optional title for the note
- `--confidence`: Confidence score (0.0-1.0)
- `--tags`: Space-separated list of tags
- `--id`: Specific ID (auto-generated if not provided)

Returns: `{"success": true, "note_id": "note-abc123", "subject": "paper-xyz789"}`

Notes can be about:
- Papers (paper-*)
- Other notes (note-*) - for meta-commentary or synthesis
- Collections (collection-*)
- Any entity in the knowledge graph

### Recall (query-notes)

Query the knowledge graph for previously stored information. Use this when you need to remember what you've learned about something.

**Triggers:** "what do I know about", "what did I learn about", "recall", "remember", "find notes about", "what notes do I have", "retrieve"

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-xyz789"
```

Returns:
```json
{
  "success": true,
  "subject": "paper-xyz789",
  "notes": [...],
  "count": 3
}
```

---

## Corpus Building Operations

### Build Corpus (insert-collection)

Create a collection of papers/documents for analysis. Collections can be defined extensionally (explicit members) or intensionally (by a logical query).

**Triggers:** "create collection", "build corpus", "gather papers", "collect papers", "create a set of", "group these papers", "make a collection"

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection \
    --name "CRISPR Research" \
    --description "Papers about CRISPR gene editing" \
    --query "CRISPR AND (gene editing OR Cas9)"
```

**Options:**
- `--name` (required): Collection name
- `--description`: Collection description
- `--query`: Logical query defining membership (for intensional collections)
- `--id`: Specific ID (auto-generated if not provided)

Returns: `{"success": true, "collection_id": "collection-abc123", "name": "CRISPR Research"}`

### Add Papers to Corpus

To ingest papers from literature sources (PubMed, OpenAlex, Europe PMC), use the **literature** or **epmc-search** skill — those handle domain-specific ingestion into the knowledge graph.

### Query Collection (query-collection)

Get collection details and members.

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py query-collection --id "collection-abc123"
```

Returns:
```json
{
  "success": true,
  "collection": {...},
  "members": [...],
  "member_count": 5
}
```

---

## Classification Operations

### Classify / Tag (tag)

Classify an entity with a tag. Use this to categorize papers by topic, method, or any other dimension.

**Triggers:** "classify", "categorize", "tag", "label", "mark as", "this is a"

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py tag --entity "paper-xyz789" --tag "high-impact"
```

Returns: `{"success": true, "entity": "paper-xyz789", "tag": "high-impact"}`

### Find by Category (search-tag)

Find all entities matching a category or tag.

**Triggers:** "find all", "show me", "list", "what papers are tagged", "which ones are"

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py search-tag --tag "crispr"
```

Returns:
```json
{
  "success": true,
  "tag": "crispr",
  "entities": [...],
  "count": 12
}
```

---

## Synthesis Operations

### Synthesize

Create a note that summarizes/synthesizes other notes or entities. Use this when you want to combine findings from multiple sources into a coherent summary or analysis.

**Triggers:** "synthesize", "summarize notes", "combine findings", "create summary", "summarize what I know", "bring together"

```bash
# First, query notes to gather information
uv run python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-123"
uv run python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-456"

# Then create a synthesis note about one of the sources (or create a collection first)
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "collection-abc123" \
    --content "Synthesis: Both papers demonstrate >90% efficiency. Paper-123 uses lipid nanoparticles while paper-456 uses viral vectors. Key difference is delivery mechanism affects tissue targeting." \
    --name "Delivery Methods Synthesis" \
    --tags synthesis delivery-methods comparison
```

### Compare

Create a comparative note about two or more entities.

**Triggers:** "compare", "contrast", "how does X differ from Y", "what's the difference between", "similarities between"

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-123" \
    --content "Comparison with paper-456: Both achieve high editing efficiency. Paper-123 is more suitable for liver targeting, paper-456 for systemic delivery." \
    --name "Method Comparison" \
    --tags comparison methods
```

---

## Workflow Examples

### Literature Review Workflow

1. Use `/literature` or `/epmc-search` to ingest papers into the knowledge graph
2. Create notes with key findings for each paper
3. Tag papers by methodology, findings, etc.
4. Create synthesis notes that reference multiple papers

```bash
# 1. Ingest papers via literature skill (see /literature for details)

# 2. Create notes about ingested papers
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-yyy" \
    --content "Key finding: 95% efficacy in preventing severe disease" \
    --tags efficacy mrna

# 3. Tag papers
uv run python .claude/skills/typedb-notebook/typedb_notebook.py tag --entity "paper-yyy" --tag "high-efficacy"

# 4. Create synthesis
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "collection-xxx" \
    --content "Summary: mRNA vaccines show consistently high efficacy..." \
    --name "Literature Review Summary" \
    --tags synthesis review
```

### Remember and Recall Pattern

When you learn something worth remembering:
```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-123" \
    --content "This paper introduces a novel approach to X" \
    --tags important methodology
```

When you need to recall:
```bash
# Recall by subject
uv run python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-123"

# Or search by tag
uv run python .claude/skills/typedb-notebook/typedb_notebook.py search-tag --tag "methodology"
```

---

## Data Model

- **Collection**: Groups of papers/items (extensional or intensional)
- **Research-Item / Paper**: Scientific publications (`scilit-paper`) — ingested via literature/epmc-search skills
- **Note**: Your observations and findings (can be about anything, including other notes)
- **Tag**: Lightweight classification labels

---

## Command Reference

| Command | Description | Required Args |
|---------|-------------|---------------|
| `insert-collection` | Create a collection | `--name` |
| `insert-note` | Create a note | `--subject`, `--content` |
| `query-collection` | Get collection info | `--id` |
| `query-notes` | Find notes about entity | `--subject` |
| `tag` | Tag an entity | `--entity`, `--tag` |
| `search-tag` | Search by tag | `--tag` |
| `export-db` | Export database to timestamped zip | `--database` |
| `import-db` | Import database from zip | `--zip`, `--database` |

---

## Database Export and Import

Export the full database for backup or migration to another TypeDB instance. Exports are saved as timestamped zips in the artifact cache (`~/.alhazen/cache/typedb/`).

### Export (export-db)

**Triggers:** "export database", "backup database", "dump database", "save database"

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py export-db \
    --database alhazen_notebook
```

**Options:**
- `--database`: Database name (default: from `TYPEDB_DATABASE` env var)
- `--container`: Docker container name (default: `alhazen-typedb`)
- `--port`: TypeDB port (default: 1729)

**Output:** Creates a zip at `~/.alhazen/cache/typedb/<database>_export_<YYYYMMDD_HHMMSS>.zip`

Returns:
```json
{
  "success": true,
  "database": "alhazen_notebook",
  "timestamp": "20260208_182846",
  "zip_path": "/Users/you/.alhazen/cache/typedb/alhazen_notebook_export_20260208_182846.zip",
  "zip_size": 192745
}
```

### Import (import-db)

**Triggers:** "import database", "restore database", "load database backup"

The target database **must not already exist**. TypeDB creates it during import.

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py import-db \
    --zip ~/.alhazen/cache/typedb/alhazen_notebook_export_20260208_182846.zip \
    --database alhazen_notebook_restored
```

**Options:**
- `--zip` (required): Path to the export zip file
- `--database` (required): Target database name (must not exist)
- `--container`: Docker container name (default: `alhazen-typedb`)
- `--port`: TypeDB port (default: 1729)

**Notes:**
- Export/import must use the same TypeDB version
- These commands use Docker CLI, not the TypeDB Python driver

---

## TypeDB Reference

When writing custom queries, consult:

- **This Skill's Schema:** `local_skills/typedb-notebook/schema.tql` (if exists)
- **Core Schema:** `local_resources/typedb/alhazen_notebook.tql`

### Common Pitfalls (TypeDB 3.x)

- **Fetch syntax** — Use `fetch { "key": $var.attr };` (JSON-style, NOT `fetch $var: attr1;`)
- **No sessions** — Use `driver.transaction(database, TransactionType.X)` directly
- **Update = delete + insert** — Can't modify attributes in place
- **Fetch results are plain dicts** — No `.get("value")` unwrapping needed
