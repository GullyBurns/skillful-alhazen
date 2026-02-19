---
name: techrecon
description: Systematically investigate external software systems, libraries, frameworks, and computational tools
---

# Tech Recon Skill

Use this skill to systematically study external software systems and build understanding of their architecture, data models, and integration potential. Claude acts as your research assistant, ingesting repos, docs, and source code, then extracting structured knowledge.

## Philosophy: The Curation Pattern

This skill follows the **curation design pattern**:

1. **FORAGING** - Discover systems to investigate (user provides URLs, names)
2. **INGESTION** - Script fetches raw content (READMEs, file trees, docs, source)
3. **SENSEMAKING** - Claude reads artifacts, identifies components/concepts, creates notes
4. **ANALYSIS** - Query across investigations for architecture maps, integration paths
5. **REPORTING** - Architecture diagrams, comparison matrices, integration assessments

**Key separation:**
- **Script handles**: GitHub/HuggingFace API calls, content fetching, TypeDB storage
- **Claude handles**: Reading artifacts, identifying architecture, creating structured notes

## Prerequisites

- TypeDB must be running: `docker compose -f docker-compose-typedb.yml up -d`
- Dependencies installed: `uv sync --all-extras` (from project root)
- Schema loaded: `local_resources/typedb/namespaces/techrecon.tql`

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen_notebook)
- `GITHUB_TOKEN`: GitHub API token (optional, for higher rate limits)

---

## Starting an Investigation

**Triggers:** "investigate", "study", "research [system]", "look into", "tech recon"

### Start Investigation

```bash
uv run python .claude/skills/techrecon/techrecon.py start-investigation \
    --name "mediKanren Investigation" \
    --goal "Understand mediKanren's architecture and data model to inform APM skill design"
```

### Ingest a Repository

```bash
uv run python .claude/skills/techrecon/techrecon.py ingest-repo \
    --url "https://github.com/webyrd/mediKanren" \
    --investigation "investigation-abc123" \
    --tags "biomedical" "knowledge-graph" "reasoning"
```

This fetches:
- Repository metadata (stars, language, license)
- README content (stored as `techrecon-readme` artifact)
- File tree (stored as `techrecon-file-tree` artifact)
- Creates a `techrecon-system` entity with extracted metadata

---

## Sensemaking: Claude Analyzes Artifacts

**This is where Claude's comprehension matters.** When the user asks to analyze, Claude reads raw artifacts and extracts structured understanding.

### Get Artifacts

```bash
# List artifacts needing analysis
uv run python .claude/skills/techrecon/techrecon.py list-artifacts --status raw

# Read artifact content
uv run python .claude/skills/techrecon/techrecon.py show-artifact --id "artifact-xyz"
```

### Sensemaking Workflow

**When user says "analyze this system" or "make sense of [repo]":**

1. **Read the README artifact**
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py show-artifact --id "artifact-readme-xyz"
   ```

2. **Read the file tree artifact**
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py show-artifact --id "artifact-tree-xyz"
   ```

3. **Identify architectural components**
   For each major module/subsystem discovered:
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py add-component \
       --name "Query Engine" \
       --system "system-abc123" \
       --type "module" \
       --role "Processes miniKanren queries against biomedical knowledge graphs" \
       --file-path "medikanren2/"
   ```

4. **Identify key concepts**
   For each important concept/pattern:
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py add-concept \
       --name "miniKanren" \
       --category "algorithm" \
       --description "Relational logic programming language for constraint-based reasoning"
   ```

5. **Link concepts to components**
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py link-concept \
       --component "component-xyz" \
       --concept "concept-abc"
   ```

6. **Identify data models**
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py add-data-model \
       --name "Biolink Model" \
       --system "system-abc123" \
       --format "RDF-OWL" \
       --description "Standardized biomedical knowledge representation"
   ```

7. **Create architecture note**
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py add-note \
       --about "system-abc123" \
       --type architecture \
       --name "mediKanren Architecture Overview" \
       --content "Three-layer architecture: (1) Data ingestion from UMLS/SemMedDB/RTX-KG2... (2) Indexed graph store... (3) miniKanren query engine..."
   ```

8. **Create integration assessment**
   ```bash
   uv run python .claude/skills/techrecon/techrecon.py add-note \
       --about "system-abc123" \
       --type integration \
       --name "Integration with APM Skill" \
       --content "mediKanren's drug repurposing queries could power APM Phase 2..." \
       --priority high \
       --complexity moderate
   ```

### Example Sensemaking Output

```
## Tech Recon: mediKanren

**System:** webyrd/mediKanren - Biomedical reasoning with miniKanren
**Language:** Racket | **Stars:** 200 | **License:** MIT

### Architecture
- **Data Layer**: Ingests UMLS, SemMedDB, RTX-KG2 into indexed triples
- **Query Engine**: miniKanren relational logic for multi-hop reasoning
- **Web UI**: Simple web interface for interactive queries

### Key Concepts
- miniKanren (relational logic programming)
- Knowledge graph reasoning (multi-hop path finding)
- Drug repurposing (finding novel drug-disease connections)

### Data Model
- Biolink Model (RDF/OWL biomedical ontology)
- Custom triple store with edge properties

### Integration Assessment
**Priority:** High | **Complexity:** Moderate
mediKanren's drug repurposing capabilities directly support APM Phase 2.
Could query for drug-gene-disease paths to suggest therapeutic strategies.

Shall I dig deeper into any component or ingest specific source files?
```

---

## Deep Investigation: Source Code Analysis

For deeper understanding, ingest specific source files:

```bash
# Ingest a key source file
uv run python .claude/skills/techrecon/techrecon.py ingest-source \
    --url "https://github.com/webyrd/mediKanren/blob/master/medikanren2/neo/dbKanren/dbk/index.rkt" \
    --file-path "medikanren2/neo/dbKanren/dbk/index.rkt" \
    --language "Racket" \
    --system "system-abc123"

# Ingest documentation
uv run python .claude/skills/techrecon/techrecon.py ingest-doc \
    --url "https://biolink.github.io/biolink-model/" \
    --system "system-abc123" \
    --tags "data-model" "biolink"

# Ingest a schema file
uv run python .claude/skills/techrecon/techrecon.py ingest-schema \
    --url "https://github.com/biolink/biolink-model/blob/master/biolink-model.yaml" \
    --format "custom" \
    --system "system-abc123"

# Ingest a HuggingFace model card
uv run python .claude/skills/techrecon/techrecon.py ingest-model-card \
    --model-id "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract" \
    --system "system-abc123"
```

### Extracting Code Snippets

When analyzing source code, extract key patterns:

```bash
uv run python .claude/skills/techrecon/techrecon.py add-fragment \
    --type code-snippet \
    --source "artifact-xyz" \
    --about "component-abc" \
    --language "Racket" \
    --name "Query pattern for drug-disease paths" \
    --content "(run* (drug disease) (fresh (gene) (edge drug gene 'treats') (edge gene disease 'causes')))"
```

---

## Queries

### List Systems

```bash
uv run python .claude/skills/techrecon/techrecon.py list-systems
```

### System Details

```bash
uv run python .claude/skills/techrecon/techrecon.py show-system --id "system-abc123"
```

Returns: Full system details, components, data models, dependencies, artifacts, notes.

### Architecture Map

```bash
uv run python .claude/skills/techrecon/techrecon.py show-architecture --id "system-abc123"
```

Returns: Components with their types/roles, concept links, component dependencies.

### Component/Concept/Data Model Details

```bash
uv run python .claude/skills/techrecon/techrecon.py show-component --id "component-xyz"
uv run python .claude/skills/techrecon/techrecon.py show-concept --id "concept-xyz"
uv run python .claude/skills/techrecon/techrecon.py show-data-model --id "datamodel-xyz"
```

---

## Tagging

```bash
# Tag an entity
uv run python .claude/skills/techrecon/techrecon.py tag \
    --entity "system-abc123" \
    --tag "biomedical"

# Search by tag
uv run python .claude/skills/techrecon/techrecon.py search-tag --tag "biomedical"
```

**Common tag patterns:**
- `domain:biomedical`, `domain:nlp`, `domain:knowledge-graph`
- `lang:python`, `lang:racket`, `lang:rust`
- `status:deep-dive`, `status:surveyed`, `status:rejected`
- `integration:high-priority`, `integration:blocked`
- `relates-to:apm`, `relates-to:jobhunt`

---

## Cross-Skill Integration

### TechRecon + APM
Investigating biomedical tools (mediKanren, Monarch, OpenTargets) to inform APM skill's knowledge base sources and reasoning approaches.

### TechRecon + EPMC Search
Papers about tools can be searched via epmc-search, then linked to techrecon systems via tags or notes.

---

## Data Model

### Entity Types

| Type | Description |
|------|-------------|
| `techrecon-investigation` | An investigation (collection) |
| `techrecon-system` | Software system/library/framework |
| `techrecon-component` | Module/subsystem |
| `techrecon-concept` | Key concept/pattern/algorithm |
| `techrecon-data-model` | Data model/schema/ontology |

### Artifact Types

| Type | Description |
|------|-------------|
| `techrecon-readme` | Repository README |
| `techrecon-source-file` | Source code file |
| `techrecon-doc-page` | Documentation page |
| `techrecon-schema-file` | Schema/model definition |
| `techrecon-model-card` | HuggingFace model card |
| `techrecon-file-tree` | Repository file tree |

### Fragment Types

| Type | Description |
|------|-------------|
| `techrecon-code-snippet` | Extracted code snippet |
| `techrecon-api-spec` | API specification excerpt |
| `techrecon-schema-excerpt` | Schema excerpt |
| `techrecon-config-excerpt` | Config file excerpt |

### Note Types

| Type | Purpose |
|------|---------|
| `techrecon-architecture-note` | System architecture analysis |
| `techrecon-design-pattern-note` | Design pattern analysis |
| `techrecon-integration-note` | Integration assessment (has priority, complexity) |
| `techrecon-comparison-note` | Cross-system comparison |
| `techrecon-data-model-note` | Data model analysis |
| `techrecon-assessment-note` | Overall system assessment (has priority, complexity) |

### Relations

| Relation | Description |
|----------|-------------|
| `techrecon-has-component` | System contains component |
| `techrecon-uses-concept` | Component uses concept |
| `techrecon-has-data-model` | System uses data model |
| `techrecon-system-dependency` | System depends on system |
| `techrecon-component-dependency` | Component depends on component |

---

## Command Reference

| Command | Description | Key Args |
|---------|-------------|----------|
| `start-investigation` | Start investigation | `--name`, `--goal` |
| `list-investigations` | List investigations | `--status` |
| `update-investigation` | Update status | `--id`, `--status` |
| `add-system` | Add system | `--name`, `--repo-url` |
| `add-component` | Add component | `--name`, `--system`, `--type` |
| `add-concept` | Add concept | `--name`, `--category` |
| `add-data-model` | Add data model | `--name`, `--format` |
| `ingest-repo` | Ingest GitHub repo | `--url` |
| `ingest-doc` | Ingest doc page | `--url` |
| `ingest-source` | Ingest source file | `--url`, `--language` |
| `ingest-schema` | Ingest schema file | `--url`/`--file`, `--format` |
| `ingest-model-card` | Ingest HF model | `--model-id` |
| `link-component` | Link component | `--system`, `--component` |
| `link-concept` | Link concept | `--component`, `--concept` |
| `link-data-model` | Link data model | `--system`, `--data-model` |
| `link-dependency` | Link dependency | `--system`, `--dependency` |
| `list-systems` | List systems | |
| `show-system` | System details | `--id` |
| `show-architecture` | Architecture map | `--id` |
| `list-artifacts` | List artifacts | `--status`, `--system`, `--type` |
| `show-artifact` | Artifact content | `--id` |
| `show-component` | Component details | `--id` |
| `show-concept` | Concept details | `--id` |
| `show-data-model` | Data model details | `--id` |
| `add-note` | Add note | `--about`, `--type`, `--content` |
| `add-fragment` | Add fragment | `--type`, `--content`, `--source` |
| `tag` | Tag entity | `--entity`, `--tag` |
| `search-tag` | Search by tag | `--tag` |

---

## Complete Workflow Example

```
User: I want to investigate mediKanren for our APM skill.

Claude: I'll start an investigation and ingest the repository.

[Runs start-investigation]
[Runs ingest-repo for mediKanren]

Repository ingested. Let me analyze the README and file tree...

[Reads README artifact]
[Reads file tree artifact]
[Creates components: query engine, data ingestion, web UI]
[Creates concepts: miniKanren, knowledge graph reasoning, drug repurposing]
[Creates data model: Biolink Model]
[Creates architecture note]
[Creates integration note with priority=high, complexity=moderate]

## mediKanren Analysis

**Architecture:** Three-layer system...
**Key Finding:** Drug repurposing queries could power APM Phase 2

Shall I ingest specific source files for deeper analysis?

User: Yes, look at the query engine source code.

Claude: [Runs ingest-source for key files]
[Reads source artifacts]
[Extracts code snippets as fragments]
[Creates design-pattern note about miniKanren query patterns]
```

---

## TypeDB 2.x Reference

- **Full Reference:** `.claude/skills/typedb-notebook/typedb-2x-documentation.md`
- **TechRecon Schema:** `local_resources/typedb/namespaces/techrecon.tql`
- **Core Schema:** `local_resources/typedb/alhazen_notebook.tql`
