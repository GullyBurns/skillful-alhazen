---
name: typedb-notebook
description: Store and retrieve knowledge in the Alhazen TypeDB knowledge graph - remember, recall, organize papers and notes
---

# TypeDB Notebook Skill

Use this skill to store and retrieve knowledge in the Alhazen TypeDB knowledge graph. This allows you to "remember" information about papers, create notes, and recall them later.

## Prerequisites

- TypeDB must be running: `docker compose -f docker-compose-typedb.yml up -d`
- TypeDB driver installed: `pip install 'typedb-driver>=2.25.0,<3.0.0'`

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen)

---

## Core Memory Operations

### Remember (insert-note)

Store information in the knowledge graph for later retrieval. Use this whenever you learn something worth remembering about a paper, concept, or any research topic.

**Triggers:** "remember this", "remember that", "save this", "note that", "store", "make a note", "don't forget", "keep track of"

```bash
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
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
python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-xyz789"
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
python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection \
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

### Add to Corpus (insert-paper)

Add a paper or research item to an existing collection.

**Triggers:** "add to collection", "add to corpus", "include in", "add this paper to"

```bash
python .claude/skills/typedb-notebook/typedb_notebook.py insert-paper \
    --name "CRISPR-Cas9 in Mouse Liver Cells" \
    --abstract "We demonstrate 95% editing efficiency..." \
    --doi "10.1234/example" \
    --pmid "12345678" \
    --year 2024 \
    --collection "collection-abc123"
```

**Options:**
- `--name` (required): Paper title
- `--abstract`: Paper abstract
- `--doi`: DOI
- `--pmid`: PubMed ID
- `--year`: Publication year
- `--collection`: Collection ID to add to
- `--id`: Specific ID (auto-generated if not provided)

Returns: `{"success": true, "paper_id": "paper-xyz789", "name": "CRISPR-Cas9 in Mouse Liver Cells"}`

### Query Collection (query-collection)

Get collection details and members.

```bash
python .claude/skills/typedb-notebook/typedb_notebook.py query-collection --id "collection-abc123"
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
python .claude/skills/typedb-notebook/typedb_notebook.py tag --entity "paper-xyz789" --tag "high-impact"
```

Returns: `{"success": true, "entity": "paper-xyz789", "tag": "high-impact"}`

### Find by Category (search-tag)

Find all entities matching a category or tag.

**Triggers:** "find all", "show me", "list", "what papers are tagged", "which ones are"

```bash
python .claude/skills/typedb-notebook/typedb_notebook.py search-tag --tag "crispr"
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
python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-123"
python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-456"

# Then create a synthesis note about one of the sources (or create a collection first)
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "collection-abc123" \
    --content "Synthesis: Both papers demonstrate >90% efficiency. Paper-123 uses lipid nanoparticles while paper-456 uses viral vectors. Key difference is delivery mechanism affects tissue targeting." \
    --name "Delivery Methods Synthesis" \
    --tags synthesis delivery-methods comparison
```

### Compare

Create a comparative note about two or more entities. Use this to record similarities, differences, or relationships between papers, methods, or findings.

**Triggers:** "compare", "contrast", "how does X differ from Y", "what's the difference between", "similarities between"

```bash
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-123" \
    --content "Comparison with paper-456: Both achieve high editing efficiency. Paper-123 is more suitable for liver targeting, paper-456 for systemic delivery." \
    --name "Method Comparison" \
    --tags comparison methods
```

---

## Workflow Examples

### Literature Review Workflow

1. Create a collection for the review topic
2. Add papers as you encounter them
3. Create notes with key findings for each paper
4. Tag papers by methodology, findings, etc.
5. Create synthesis notes that reference multiple papers

```bash
# 1. Create collection
python .claude/skills/typedb-notebook/typedb_notebook.py insert-collection \
    --name "COVID-19 Vaccine Papers" \
    --description "Papers about COVID-19 vaccine development"

# 2. Add papers
python .claude/skills/typedb-notebook/typedb_notebook.py insert-paper \
    --name "mRNA Vaccine Efficacy Study" \
    --doi "10.1234/mrna" \
    --year 2024 \
    --collection "collection-xxx"

# 3. Create notes
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-yyy" \
    --content "Key finding: 95% efficacy in preventing severe disease" \
    --tags efficacy mrna

# 4. Tag papers
python .claude/skills/typedb-notebook/typedb_notebook.py tag --entity "paper-yyy" --tag "high-efficacy"

# 5. Create synthesis
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "collection-xxx" \
    --content "Summary: mRNA vaccines show consistently high efficacy..." \
    --name "Literature Review Summary" \
    --tags synthesis review
```

### Remember and Recall Pattern

When you learn something worth remembering:
```bash
# Remember
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-123" \
    --content "This paper introduces a novel approach to X" \
    --tags important methodology
```

When you need to recall:
```bash
# Recall by subject
python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-123"

# Or search by tag
python .claude/skills/typedb-notebook/typedb_notebook.py search-tag --tag "methodology"
```

### Question-Answering Workflow

1. Search by tag to find relevant entities
2. Get notes for each entity
3. Create an answer note linking the question to sources

```bash
# 1. Find relevant papers
python .claude/skills/typedb-notebook/typedb_notebook.py search-tag --tag "crispr"

# 2. Get notes about each
python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-123"

# 3. Create answer note
python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
    --subject "paper-123" \
    --content "Answer: The most efficient CRISPR delivery method appears to be..." \
    --name "Research Question Answer" \
    --tags answer crispr-delivery
```

---

## Data Model

- **Collection**: Groups of papers/items (extensional or intensional)
- **Research-Item / Paper**: Scientific publications (scilit-paper)
- **Note**: Your observations and findings (can be about anything, including other notes)
- **Tag**: Lightweight classification labels

---

## Command Reference

| Command | Description | Required Args |
|---------|-------------|---------------|
| `insert-collection` | Create a collection | `--name` |
| `insert-paper` | Add a paper | `--name` |
| `insert-note` | Create a note | `--subject`, `--content` |
| `query-collection` | Get collection info | `--id` |
| `query-notes` | Find notes about entity | `--subject` |
| `tag` | Tag an entity | `--entity`, `--tag` |
| `search-tag` | Search by tag | `--tag` |
