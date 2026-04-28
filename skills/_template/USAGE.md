# Your Domain Name — Usage Reference

## Web Interface

<!-- Optional: remove this section if this skill has no dashboard -->

A Next.js dashboard is available at `http://localhost:3000/<your-domain>` when running `make dashboard-dev`.

**Start the dashboard:**
```bash
make dashboard-dev    # starts on http://localhost:3000
```

**Views:**
- **[View Name]** (`/<your-domain>`) — Description of the main view
- **[Item Detail]** (`/<your-domain>/item/{id}`) — Full detail page for a single item

**Internal organization** (for contributors):
- Pages: `dashboard/src/app/(<your-domain>)/<your-domain>/`
- Components: `dashboard/src/components/<your-domain>/`
- API routes: `dashboard/src/app/api/<your-domain>/`
- TypeScript wrapper: `dashboard/src/lib/<your-domain>.ts`

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

## Analysis Workflow

The Analysis phase turns accumulated sensemaking notes into structured, versioned, re-runnable insights. All curation skills use the **LinkML -> Pydantic -> Hamilton** pattern:

### 1. Define your schema (LinkML)

Copy `schema/eval_schema_template.yaml` and rename it for your domain. Fill in:
- Your **dimension names** in `DimensionScores` (rename `dimension_a`, `dimension_b`, etc.)
- Your **entity categories** in the `EntityCategory` enum
- Add optional fields freely — they default to `None`, keeping old records valid

### 2. Implement Pydantic models

Create `eval_models.py` next to your skill script. Mirror the LinkML schema as Pydantic v2:

```python
from pydantic import BaseModel, Field, model_validator
from typing import Annotated, Optional
from enum import Enum

Score = Annotated[int, Field(ge=0, le=3)]

class DimensionScores(BaseModel):
    dimension_a: Score
    dimension_b: Score
    total: int = 0

    @model_validator(mode="after")
    def compute_total(self) -> "DimensionScores":
        self.total = self.dimension_a + self.dimension_b
        return self

class EntityAssessment(BaseModel):
    id: str
    name: str
    scores: DimensionScores
    assessment_summary: Optional[str] = None
    parse_warnings: list[str] = []
```

Generate JSON Schema for documentation:
```bash
uv run python eval_models.py > schema/<skill>_schema.json
```

### 3. Write a Hamilton pipeline

Copy `pipelines/pipeline_template.py` and adapt:
- `fetch_records(investigation_id)` — TypeQL query for your entities + assessment notes
- `parse_records(fetch_records)` — keyword matching on your dimension labels
- `table_data()` — serialises to JSON (no changes needed)
- `plot_code()` — replace the placeholder with your Observable Plot expression

**The sensemaking agent must write structured score tables** in assessment notes using this format so the parser can extract scores:

```markdown
| Criterion | Score (0-3) | Notes |
|---|---|---|
| Dimension A label | 2 | explanation |
| Dimension B label | 1 | explanation |
```

### 4. Register the pipeline in TypeDB

```bash
uv run python .claude/skills/<skill>/<skill>.py add-pipeline \
  --investigation <ID> \
  --title "My Analysis" \
  --analysis-type pipeline-plot \
  --pipeline-script "@skills/<skill>/pipelines/pipeline_name.py" \
  --pipeline-config '{"outputs":["plot_code","table_data"],"inputs":{"investigation_id":"<ID>"},"env_inputs":{}}'
```

### 5. Run the pipeline

```bash
uv run python .claude/skills/<skill>/<skill>.py run-pipeline --id <analysis-id>
```

Re-run any time new sensemaking notes are added — the pipeline reads from TypeDB and re-generates outputs.

### 6. View in dashboard

Navigate to the Analysis tab of your investigation page. The heatmap renders immediately using the pre-computed `table_data` stored in TypeDB.

### Schema Evolution

Adding new analysis dimensions later:
1. Add `Optional` field to LinkML YAML and Pydantic model (new field = no migration)
2. Re-run the pipeline — existing records get `None`/0 for the new field
3. Update the sensemaking prompt to score the new dimension in future notes

---

## TypeDB Reference

When writing custom queries, consult:

- **This Skill's Schema:** `local_skills/<your-domain>/schema.tql`
- **Core Schema:** `local_resources/typedb/alhazen_notebook.tql`

### Common Pitfalls (TypeDB 3.x)

- **Fetch syntax** — Use `fetch { "key": $var.attr };` (JSON-style, NOT `fetch $var: attr1;`)
- **No sessions** — Use `driver.transaction(database, TransactionType.X)` directly
- **Update = delete + insert** — Can't modify attributes in place
