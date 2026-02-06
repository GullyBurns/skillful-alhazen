---
name: your-domain-name
description: Brief description of what this skill does
---

# Your Domain Name Skill

Use this skill to [describe primary use case]. Claude acts as [describe Claude's role in this domain].

## Philosophy: The Curation Pattern

This skill follows the **curation design pattern**:

1. **FORAGING** - Discover [what sources?]
2. **INGESTION** - Script fetches raw content, stores as artifact
3. **SENSEMAKING** - Claude reads artifact, extracts entities, creates notes
4. **ANALYSIS** - Query across notes to answer questions
5. **REPORTING** - [Dashboard views / CLI output]

**Key separation:**
- **Script handles**: Fetching data, storing raw content, TypeDB queries
- **Claude handles**: Reading artifacts, extracting meaning, creating notes, reasoning

## Prerequisites

- TypeDB must be running: `docker compose -f docker-compose-typedb.yml up -d`
- Dependencies installed: `uv sync --all-extras` (from project root)
- Schema loaded: `<your-domain>.tql` in TypeDB

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen_notebook)

---

## Ingestion Commands

### Ingest from URL

**Triggers:** "add [item]", "ingest", "fetch", "new [item]"

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py ingest \
    --url "https://example.com/item" \
    --tags "tag1" "tag2"
```

**Options:**
- `--url` (required): Source URL
- `--tags`: Space-separated tags

**Returns:**
```json
{
  "success": true,
  "artifact_id": "artifact-abc123",
  "entity_id": "entity-xyz789",
  "status": "raw",
  "message": "Artifact stored - ask Claude to 'analyze this' for sensemaking."
}
```

### Add Entity Manually

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py add-entity \
    --name "Entity Name" \
    --description "Description"
```

---

## Sensemaking Workflow

**When user says "analyze [entity]" or "make sense of [artifact]":**

1. **Get the artifact content**
   ```bash
   uv run python .claude/skills/<your-domain>/<your-domain>.py show-artifact --id "artifact-xyz"
   ```

2. **Read and comprehend the content**
   - Look for: [list key things to extract]
   - Identify: [list entities to create]
   - Note: [list observations to make]

3. **Create/update related entities**
   ```bash
   uv run python .claude/skills/<your-domain>/<your-domain>.py add-entity \
       --name "Extracted Entity" \
       --description "..."
   ```

4. **Create fragments for key pieces**
   ```bash
   uv run python .claude/skills/<your-domain>/<your-domain>.py add-fragment \
       --artifact "artifact-xyz" \
       --content "Extracted piece"
   ```

5. **Create analysis notes**
   ```bash
   uv run python .claude/skills/<your-domain>/<your-domain>.py add-note \
       --about "entity-xyz" \
       --type "analysis" \
       --content "Claude's interpretation and insights..."
   ```

6. **Flag uncertainties** with "uncertain" tag

7. **Report findings to user**
   - Summary of what was found
   - Key insights
   - Suggested next steps

---

## Query Commands

### List Entities

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py list-entities
uv run python .claude/skills/<your-domain>/<your-domain>.py list-entities --status "active"
```

### Show Entity Details

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py show-entity --id "entity-xyz"
```

### List Artifacts

```bash
# Show artifacts needing analysis
uv run python .claude/skills/<your-domain>/<your-domain>.py list-artifacts --status raw

# Show all artifacts
uv run python .claude/skills/<your-domain>/<your-domain>.py list-artifacts --status all
```

---

## Update Commands

### Update Status

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py update-status \
    --entity "entity-xyz" \
    --status "active"
```

### Add Note

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py add-note \
    --about "entity-xyz" \
    --type "research" \
    --content "Note content here"
```

### Tag Entity

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py tag \
    --entity "entity-xyz" \
    --tag "important"
```

---

## Data Model

### Entity Types

| Type | Description |
|------|-------------|
| `<domain>-entity` | Primary thing you track |
| `<domain>-artifact` | Raw captured content |
| `<domain>-fragment` | Extracted piece |
| `<domain>-note` | Claude's analysis |

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `attribute-1` | string | Description |
| `attribute-2` | datetime | Description |

### Relations

| Relation | Description |
|----------|-------------|
| `relation-1` | How entities connect |

---

## Command Reference

| Command | Description | Key Args |
|---------|-------------|----------|
| `ingest` | Fetch and store raw content | `--url` |
| `add-entity` | Create entity manually | `--name` |
| `add-note` | Create a note | `--about`, `--type`, `--content` |
| `list-entities` | List all entities | `--status` |
| `show-entity` | Get entity details | `--id` |
| `list-artifacts` | List artifacts | `--status` |
| `show-artifact` | Get artifact content | `--id` |
| `update-status` | Change entity status | `--entity`, `--status` |
| `tag` | Tag an entity | `--entity`, `--tag` |
| `search-tag` | Find by tag | `--tag` |

---

## TypeDB 2.x Reference

When writing custom queries, consult:

- **Full Reference:** `.claude/skills/typedb-notebook/typedb-2x-documentation.md`
- **This Skill's Schema:** `local_resources/typedb/namespaces/<your-domain>.tql`
- **Core Schema:** `local_resources/typedb/alhazen_notebook.tql`

### Common Pitfalls

- **No `optional` in fetch** - Use separate queries for optional attributes
- **Update = delete + insert** - Can't modify attributes in place
- **Use semicolons** between match patterns (implicit AND)
