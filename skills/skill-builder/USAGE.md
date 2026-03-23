# Domain Modeling — Usage Reference

## Overview: What You're Building

A **skill** is a bundle of five artifacts that implements a curation pipeline:

| Artifact | Purpose |
|----------|---------|
| `schema.tql` | TypeDB entity/relation/attribute definitions |
| `<skill>.py` | CLI script: ingest, list, show, update commands |
| `SKILL.md` | Short selection file (~30 lines) for Claude's context |
| `USAGE.md` | Full reference: commands, workflows, sensemaking instructions |
| `evals/` | Test cases measuring extraction performance (depending on the skill) |
| `docs/` | Detailed technical documentation about the schema, script, skill, and evals |
| `dash/` | Detailed technical documentation about the schema, script, skill, and evals |

---

## Process: How we define 'curation' 

Our model of curation follows a 5-step process. This is what the skill *does* at runtime after it has been built:

```
+-----------------------------------------------------------------------------+
|                         CURATION WORKFLOW                                   |
+-----------------------------------------------------------------------------+
|                                                                             |
|  1. DISCOVER         2. INGESTION         3. SENSEMAKING                    |
|  +----------+        +----------+         +--------------+                  |
|  | Discover |------->|  Capture |-------->| Claude reads |                  |
|  | sources  |        |   raw    |         | & extracts   |                  |
|  +----------+        +----------+         +--------------+                  |
|       |                   |                      |                          |
|       v                   v                      v                          |
|  - URLs             - Artifacts            - Fragments                      |
|  - APIs             - Provenance           - Notes                          |
|  - Feeds            - Timestamps           - Relations                      |
|                                                                             |
|                              |                                              |
|                              v                                              |
|               4. ANALYZE/SUMMARIZE        5. REPORT                         |
|               +------------------+       +--------------+                   |
|               | Reason over many |------>|  Dashboard   |                   |
|               | notes over time  |       |  & answers   |                   |
|               +------------------+       +--------------+                   |
|                        |                        |                           |
|                        v                        v                           |
|                   - Synthesis notes        - Pipeline views                 |
|                   - Trend analysis         - Strategic reports              |
|                   - Recommendations        - Output Code / Artifacts        |
|                                                                             |
+-----------------------------------------------------------------------------+
```
Note: This skill, `skill-builder`, follows this process to generate the artifacts listed above.

---

### Phase 1: Discover — Finding Information Sources

**What it is:** Finding things in the world worth capturing. Often the most creative/expansive phase.

**Examples by domain:**
| Domain | Foraging Activities |
|--------|---------------------|
| Job hunting | Job boards, company career pages, VC portfolio sites, LinkedIn, referrals |
| Literature review | PubMed, Google Scholar, citation chains, conference proceedings |
| News investigation | RSS feeds, social media, press releases, public records |
| Biology research | Databases (UniProt, GenBank), preprints, lab websites |

**Key insight:** Discovery can be recursive - finding one thing leads to finding  others.

---

### Phase 2: Ingestion — Raw Capture with Provenance

**What it is:** Pulling material in UNEDITED format. The artifact is the authoritative record. We make copies of external data, store them in the cache when needed and record their existance in the database.  

**Critical properties:**
- **Provenance** - Where did this come from? (URL, timestamp, API, email)
- **Immutability** - The raw content doesn't change after capture
- **Completeness** - Capture the whole thing, not just parts you think matter now

**Maps to TypeDB:**
```
Artifact (raw content)
+-- owns source-uri
+-- owns created-at (timestamp)
+-- owns content (full text/HTML)
+-- plays representation:artifact --> Thing
```

**Script responsibility:** Fetch and store raw content. NO parsing, NO extraction, NO interpretation.

```python
def ingest_url(url):
    content = fetch(url)
    artifact_id = store_artifact(
        content=content,
        source_url=url,
        retrieved_at=now(),
        content_type=detect_type(content)
    )
    return artifact_id  # Claude does the rest
```

**Browser-based ingestion tip:** When using Playwright to browse large web pages (especially LinkedIn profiles), use `mcp__playwright__browser_take_screenshot` instead of parsing the DOM snapshot. The accessibility tree for these pages can be 100KB+ and easy to misread. 

---

### Phase 3: Sensemaking — Claude Reads and Extracts

**What it is:** Claude reads the artifact and creates structured understanding.

**Sensemaking Subtasks:**

| Subtask | Description | Output |
|---------|-------------|--------|
| **Parsing** | Understanding document structure | Structure map |
| **Entity Extraction** | Identifying named entities | Entities -> Things |
| **Relation Extraction** | How entities connect | Relations |
| **Classification** | Categorizing (role type, seniority) | Classification Tags |
| **Summarization** | Condensing key points | Summary notes |
| **Gap Analysis** | Comparisons between entities and pre-existing standards | Gap notes |
| **Inference** | Drawing conclusions not explicitly stated | Analysis notes |

**Maps to TypeDB:**
```
Fragment (extracted piece of artifact)
+-- owns content (the specific text)
+-- plays extraction:fragment --> Artifact (provenance back to source)
+-- plays aboutness:subject <-- Note (Claude's interpretation)

Note (Claude's understanding)
+-- owns content (Claude's interpretation/analysis)
+-- owns confidence (how sure Claude is)
+-- plays aboutness:note --> [Thing, Artifact, Fragment, other Notes]
+-- owns tags
```

**Key architectural point:** Sensemaking is ITERATIVE. Claude might:
1. First pass: Extract obvious entities (company name, job title, location)
2. Second pass: Deeper analysis (requirements, responsibilities, culture signals)
3. Later: Re-analyze when you have more context (compare to other postings)
Past notes and sensemaking runs provide context for current sensemaking work. 
---

### Phase 4: Analyze / Summarize — Reasoning Over Time

**What it is:** Looking across many sensemaking notes to answer questions and generate insights.

**Examples:**
- "What skills appear most frequently across my high-priority positions?"
- "How does this company's culture compare to others I'm considering?"

**Output:** Synthesis notes that reference multiple sources

```
Synthesis Note
+-- about --> [position-1, position-2, position-3]
+-- content: "Across these three roles, distributed systems appears
|            as required in 2/3 and preferred in 1/3. This is your
|            biggest gap. Recommend prioritizing DDIA book."
+-- tags: [synthesis, skill-gaps, recommendation]
```

---

### Phase 5: Report — Presentation for Action

**Dashboard components:**
- **Pipeline views** - Where things stand (Kanban)
- **Matrices** - Comparisons across dimensions (skills x positions)
- **Progress tracking** - Learning plan completion
- **Alerts** - Deadlines, required actions
- **Deep dives** - All context about a specific entity
- **Output code** - Source code for a website / dashboard / reporting framework

**Key insight:** Reports should be generated from TypeDB data.

---

## Domain Modeling Workflow

The **Domain Modeling Workflow** is how you *build* the artifacts that execute the curation process — it is a design-time curation process where you (A) run ingestion over source documents and design specifications generated by the domain modeler; (B) use staged sensemaking to map those documents and specifications into schema, skill prompts, and scripts; (C) use analysis to validate and evaluate performance on sample data; and (D) generate the source artifacts for the target skill as a form of reporting. 

The workflow is a structured framework for performing these tasks. It should be rerun when new data comes to light to generate new versions of the skill. 

The 5-phase workflow captures the full design record for a skill from goal to analysis. Each phase produces TypeDB entities that link spec notes and design gaps polymorphically.

| Phase | Entity type | Purpose |
|-------|-------------|---------|
| 1 | `dm-goal` + `dm-goal-eval` | What the system is for and how success is measured |
| 2 | `dm-entity-schema` | TypeDB entity/relation/attribute types defined |
| 3 | `dm-source-schema` | External data sources and artifact types needed |
| 4 | `dm-derivation-skill` | Ingestion functions: artifact types in, entity types out |
| 5 | `dm-analysis-skill` | Analysis functions: entity types queried, outputs produced |

Spec notes (`dm-phase-spec`) and design gaps (`dm-design-gap`) link to whichever phase entity they belong to via `dm-phase-artifact` — the relation handles all five phases polymorphically.

### Phase 1: System Goal

Describe the domain being modeled and the goal of the curation process in detail. First, ingest all relevant source documents pertaining to the domain and the goal. Second, based on source documents (including design specs captured from a human designer), define the goals and evaluation criteria for the domain.   

> **Recommended:** Ingest source documents *before* writing the goal description. They give Claude a rich, citable evidence base — "I modeled this way because the paper describes X."

#### 1a. Ingest Source Documents

Here, 

```bash
# Step 1: Get the blank template, fill it out, save as domain-spec.md
uv run python .claude/skills/skill-builder/skill_builder.py \
  generate-template > domain-spec.md
# ... edit domain-spec.md in your editor ...

# Step 2: Ingest the filled template
uv run python .claude/skills/skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --file domain-spec.md --doc-type template \
  --title "My Domain — spec"

# Step 3: Ingest reference papers (PDF from local file)
uv run python .claude/skills/skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --file path/to/might-2017.pdf \
  --doc-type paper \
  --title "Might 2017 -- Undiagnosed Diseases Algorithm"

# Step 4: Ingest inline text (e.g. pasted email)
uv run python .claude/skills/skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --text "The algorithm begins with a patient who has..." \
  --doc-type email --title "Matt Might email 2024-03-01"

# Step 5: Ingest content fetched by Playwright (JS-heavy or paywalled pages)
# Use browser_navigate + browser_snapshot to get text, then pipe it:
uv run python .claude/skills/skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN --stdin \
  --url "https://example.com/paper" --doc-type paper --title "..."
# (pipe fetched text via stdin; --url is always recorded as source-uri)

# Step 6: Simple direct URL fetch (urllib fallback — works for direct downloads only)
uv run python .claude/skills/skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --url "https://arxiv.org/pdf/1234.5678.pdf" \
  --doc-type paper --title "ArXiv paper 1234.5678"

# Confirm ingestion
uv run python .claude/skills/skill-builder/skill_builder.py \
  list-source-docs --domain-id $DOMAIN

# Read a source doc (returns content or cache-path for large files)
uv run python .claude/skills/skill-builder/skill_builder.py \
  show-source-doc --doc-id dm-source-doc-XXXX
```

**Input priority:** `--file` > `--stdin` > `--text` > `--url` (urllib). `--url` is always recorded as `source-uri` regardless of input method.

**For JS-heavy or paywalled URLs:** Use Playwright MCP tools to fetch content, then pipe to the script:
- Text content: `browser_navigate` → `browser_snapshot` → pass text via `--text` or `--stdin`
- Screenshots/diagrams: `browser_take_screenshot` → save PNG → `--file screenshot.png --doc-type image`
- PDFs: download via browser → `--file path/to/downloaded.pdf`

**After ingesting source docs, Claude should read them before writing the goal description:**
```bash
uv run python .claude/skills/skill-builder/skill_builder.py \
  list-source-docs --domain-id $DOMAIN \
  | python3 -c "import json,sys; [print(d['id'], d['name']) for d in json.load(sys.stdin)['source_docs']]"

uv run python .claude/skills/skill-builder/skill_builder.py \
  show-source-doc --doc-id dm-source-doc-XXXX \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['doc']; print(d.get('content') or 'cached at: '+str(d.get('cache_path')))"
```

#### 1b. Define Goal and Evaluation Criteria

```bash
# Create domain (if not already done)
DOMAIN=$(uv run python .claude/skills/skill-builder/skill_builder.py \
  init-domain --name "my-domain" --skill my-skill \
  --description "Complete and full description of the use case / domain of interest as an MD file. This should be verbose, rich, coherent, and complete." \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Define the system goal
GOAL=$(uv run python .claude/skills/skill-builder/skill_builder.py \
  define-goal --domain-id $DOMAIN \
  --name "What information is the curation process generating? What purpose does it serve? This should be verbose, rich, coherent, and complete." \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Add an evaluation criterion
# How would you know if the
uv run python .claude/skills/skill-builder/skill_builder.py \
  add-evaluation \
  --goal-id $GOAL --domain-id $DOMAIN \
  --name "Coverage criterion" \
  --description "What fraction of real-world cases the schema can represent." \
  --criterion-type completeness \
  --success-condition "For 80% of test cases, zero unknown entity types" \
  --approach "Manual review of 20 randomly sampled real examples"

# Show goal + evaluations
uv run python .claude/skills/skill-builder/skill_builder.py \
  show-goal --domain-id $DOMAIN
```

### Phase 2: Entity Schema

Think carefully about the domain and the goal of the curation work. What collections, domain-entities, and relations are needed to satisfy the goal. For example, if we were curating inforation about a job search, we would track positions, opportunities, candidate skills, etc. If we were curating information about disease mechanisms, we would track diseases, genes, mutataions, pathways, experiments, claims, etc. The task here is to model the main domain-specific entities needed to satisfy the curation process' goal.  

```bash
SCHEMA=$(uv run python .claude/skills/skill-builder/skill_builder.py \
  add-entity-schema --domain-id $DOMAIN \
  --name "Core entities" \
  --description "my-domain-entity, my-domain-artifact, my-domain-relation" \
  --feasibility yes \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Attach a TypeQL spec note
uv run python .claude/skills/skill-builder/skill_builder.py \
  add-phase-spec --phase-id $SCHEMA \
  --content "entity my-domain-entity sub domain-thing, owns my-domain-attr-1;"

# Show the phase item with specs
uv run python .claude/skills/skill-builder/skill_builder.py \
  show-phase-item --phase-id $SCHEMA
```

### Phase 3: Source Schema

Think carefully about the domain, the goal, and the entities developed in phase 2. What remotely available information do you need to be able to populate the schema generated in phase 2? If we were curating information about job search , we would need to capture online job postings, contacts, emails / conversations, websites, linkedin posts + profiles etc. If we were curating disease mechanisms, we'd need Pubmed, MONDO, and Uniprot records. The task here is to model the main information sources that we would need in order to be able to describe domain-specific entities from phase 2.  

```bash
uv run python .claude/skills/skill-builder/skill_builder.py \
  add-source-schema --domain-id $DOMAIN \
  --name "Primary data source" \
  --description "Source API or database; one HTML/JSON artifact per ingested item" \
  --feasibility yes
```

### Phase 4: Derivation Skills

Think carefully about the processes needed to generate domain entities from sources. Capture those processes as prompts and script commands that involve database updates.  

```bash
uv run python .claude/skills/skill-builder/skill_builder.py \
  add-derivation-skill --domain-id $DOMAIN \
  --name "ingest-source" \
  --description "Fetch source page, store artifact, extract domain entities" \
  --input-types "html artifact (source page)" \
  --output-types "my-domain-entity, my-domain-artifact" \
  --feasibility yes
```

### Phase 5: Analysis Skills

Think carefully about the processes needed to understand and interpret domain entities in order to satisfy the goal of the curation pipeline. Capture those processes as prompts and script commands that involve database updates.  

```bash
uv run python .claude/skills/skill-builder/skill_builder.py \
  add-analysis-skill --domain-id $DOMAIN \
  --name "analyze-entities" \
  --description "Reason across ingested entities to answer the curation goal" \
  --input-types "my-domain-entity, my-domain-relation" \
  --output-types "Markdown report with findings and gaps flagged" \
  --feasibility partial
```

### Cross-Phase Dependencies

Use `--depends-on` to record that one phase entity builds on another:

```bash
# Derivation skill depends on the source schema
uv run python .claude/skills/skill-builder/skill_builder.py \
  add-derivation-skill --domain-id $DOMAIN \
  --name "ingest-secondary-source" \
  --description "Ingest secondary data source" \
  --input-types "json artifact (API response)" \
  --output-types "my-domain-secondary-entity" \
  --depends-on $SOURCE_ID
```

### Design Gaps

Track mismatches and gaps for sources and scripts that are currently missing in the design. 

```bash
# Flag something missing or unclear
GAP=$(uv run python .claude/skills/skill-builder/skill_builder.py \
  add-phase-gap \
  --phase-id $SCHEMA --domain-id $DOMAIN \
  --description "No representation for 510k substantial equivalence decision text" \
  --severity moderate \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# List open gaps
uv run python .claude/skills/skill-builder/skill_builder.py \
  list-phase-gaps --domain-id $DOMAIN --status open

# Resolve a gap
uv run python .claude/skills/skill-builder/skill_builder.py \
  resolve-phase-gap --gap-id $GAP
```

### Export

```bash
uv run python .claude/skills/skill-builder/skill_builder.py \
  export-design-phases --domain-id $DOMAIN \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['markdown'])"
```

The export produces a Markdown document with Phase 1 goal + evaluations, followed by sections for each phase entity with embedded spec notes and open gaps.

#### docs/ Convention — Save as the Skill's Design Document

As the **Phase 5 reporting artifact**, the exported Markdown should be saved to `docs/design.md` inside the skill directory. This file becomes the authoritative design record for the skill — readable by humans and by future Claude sessions.

```bash
# Save the export directly to the skill's docs/ file
mkdir -p skills/$SKILL_NAME/docs
uv run python .claude/skills/skill-builder/skill_builder.py \
  export-design-phases --domain-id $DOMAIN \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['markdown'])" \
  > skills/$SKILL_NAME/docs/design.md
```

**When to regenerate:** After adding new phase items, resolving gaps, recording design decisions, or completing a new implementation iteration — re-run the export to keep `docs/design.md` in sync with the TypeDB record.

**What the file captures:**
- System goal and evaluation criteria (Phase 1)
- Entity schema decisions and specs (Phase 2)
- Source schema and feasibility assessments (Phase 3)
- Derivation skill inputs/outputs (Phase 4)
- Analysis skill designs (Phase 5)
- Open and resolved design gaps at each phase

This output, combined with all the content developed in the modeling process, provides structured input for Claude to generate or regenerate a complete set of skill artifacts.

---

## Domain Lifecycle Commands

```bash
# Create a tracking project
uv run python .claude/skills/skill-builder/skill_builder.py \
    init-domain --name "Scientific Literature" --description "Tracks topics and subjects reported in the scientific literature" \
    --skill newskill

# Set the Phase 0 task (what is this skill FOR?)
uv run python .claude/skills/skill-builder/skill_builder.py \
    set-task --domain-id dm-domain-XXXX \
    --task "Ingest abstracts and full text papers pertaining to a specific subject into TypeDB"

# List all domains
uv run python .claude/skills/skill-builder/skill_builder.py list-domains

# Full history: snapshots, decisions, experiments, errors
uv run python .claude/skills/skill-builder/skill_builder.py \
    show-domain --id dm-domain-XXXX
```

---

## Designing the Curation Pipeline

### Step 1: Identify Entity Types

| Alhazen Type | Your Domain | Example (Job Hunt) | Example (Lit Review) |
|--------------|-------------|-------------------|---------------------|
| **Task** | The goal framing the curation | "Find a senior ML role" | "Understand CRISPR off-target effects" |
| **Thing** | Primary items you track | Company, Position | Paper, Author |
| **Artifact** | Raw captured content | Job Description | PDF, Abstract |
| **Fragment** | Extracted pieces | Requirement | Claim, Method |
| **Note** | Claude's analysis | Fit Analysis | Critique, Summary |

### Step 2: Define Attributes

```typeql
jobhunt-position sub domain-thing,
    owns job-url,
    owns salary-range,
    owns location,
    owns remote-policy;
```

### Step 3: Define Relations

```typeql
position-at-company sub relation,
    relates position,
    relates employer;
```

### Step 4: Design Script Commands

**Ingestion commands** (script does the work):
- `ingest-<source>` - Fetch and store raw content
- `add-<entity>` - Manual entity creation

**Query commands** (script queries, returns data):
- `list-<entities>` - List with filters
- `show-<entity>` - Full details
- `list-artifacts` - Artifacts pending analysis

**Update commands** (script updates TypeDB):
- `update-<attribute>` - Change entity attributes
- `tag` - Add tags to entities

### Step 5: Write Sensemaking Instructions

In your USAGE.md, tell Claude what to extract. Example:

```markdown
## Sensemaking Workflow

When user asks to "analyze [artifact]":

1. Read artifact content
   ```bash
   uv run python .claude/skills/domain/script.py show-artifact --id "artifact-xyz"
   ```

2. Extract entities:
   - [List what to look for]

3. Create fragments:
   - [List fragment types and what they contain]

4. Create analysis notes:
   - [List note types and their purpose]

5. Flag uncertainties with "uncertain" tag

6. Report summary to user
```

---

## TypeDB Schema Template

```typeql
define

# =============================================================================
# ATTRIBUTES (domain-specific)
# =============================================================================

domain-attr-1, value string;
domain-attr-2, value datetime;
task-status, value string;   # active | completed | on-hold

# =============================================================================
# ENTITIES - Task (Phase 0: what this curation is FOR)
# =============================================================================

# Inherits id @key, name, description from domain-thing.
# Natural-language goal goes in description.
my-domain-task sub domain-thing,
    owns task-status,
    plays task-scope:task,
    plays task-contribution:task;

# =============================================================================
# ENTITIES - Things
# =============================================================================

my-domain-entity sub domain-thing,
    owns domain-attr-1,
    plays domain-relation:role;

# =============================================================================
# ENTITIES - Artifacts
# =============================================================================

my-domain-artifact sub artifact;

# =============================================================================
# ENTITIES - Fragments
# =============================================================================

my-domain-fragment sub fragment,
    owns domain-attr-1,
    plays domain-relation:role;

# =============================================================================
# ENTITIES - Notes
# =============================================================================

my-domain-note sub note,
    plays task-contribution:note;

# =============================================================================
# RELATIONS
# =============================================================================

domain-relation sub relation,
    relates role1,
    relates role2;

# Task scopes a collection (what body of knowledge serves this goal?)
task-scope sub relation,
    relates task,
    relates collection;

# Note contributes to a task (links sensemaking output back to the goal)
task-contribution sub relation,
    relates task,
    relates note;
```

---

## Runtime Process Reference

All domain skills follow a 6-phase curation workflow. This is what the skill *does* at runtime after it has been built:

---

### Separation of Concerns

#### What Scripts Do (Python)

```
SCRIPT RESPONSIBILITIES
+----------------------------------------+
| Discover:                              |
| - Search APIs                          |
| - List sources                         |
| - Discover links                       |
|                                        |
| Ingestion:                             |
| - Fetch URL content                    |
| - Store raw HTML/text                  |
| - Record provenance                    |
| - Create artifact                      |
| - NO parsing, NO extraction            |
|                                        |
| Queries:                               |
| - List artifacts                       |
| - List entities                        |
| - Pipeline views                       |
| - Return data for Claude to reason     |
+----------------------------------------+
```

#### What Claude Does (via SKILL.md)

```
CLAUDE RESPONSIBILITIES
+----------------------------------------+
| Sensemaking:                           |
| - Read artifact content                |
| - Extract entities                     |
| - Create fragments                     |
| - Write notes                          |
| - Flag uncertainties                   |
|                                        |
| Analysis:                              |
| - Query across notes                   |
| - Generate synthesis                   |
| - Compare to profiles                  |
| - Make recommendations                 |
|                                        |
| Interaction:                           |
| - Present findings to user             |
| - Ask clarifying questions             |
| - Suggest next actions                 |
+----------------------------------------+
```

---

## Iterating and Improving

The full improvement loop connects live gap discovery through design decisions to automated optimization:

```
discover gap during workflow
    |
    v
log gap (typedb-notebook record-gap)          <-- surface-level observation
    |
    v
snapshot-skill (captures current skill files)
    |
    +-- add-decision (what schema change fixes it?)
    |       |
    |       +-- add-rationale (why this fix?)
    |       +-- link-gap (connect observed gap to fixing decision)
    |
    +-- start-experiment (test the fix)
    |       |
    |       +-- record-result (metric + value)
    |       +-- complete-experiment
    |
    +-- add-phase-gap (structural gap in a phase spec)  <-- design-time observation
    |       |
    |       +-- resolve-phase-gap (once addressed)
    |
    v
export-design / export-design-phases (Markdown changelog)
```

### Two Gap Mechanisms — One Improvement Loop

| Mechanism | Command | When to Use |
|-----------|---------|-------------|
| **Observed gap** | `typedb-notebook record-gap` | Claude had to ask for something that should be stored, or made a wrong inference — logged during live skill use |
| **Phase gap** | `skill-builder add-phase-gap` | A structural gap discovered while speccing a phase — logged during design review |
| **Link them** | `skill-builder link-gap` | Connect an observed gap (skilllog) to the design decision that fixes it |

### Skill Snapshots

```bash
# Capture all skill files (auto-detects git: commit, branch, remote, message)
uv run python .claude/skills/skill-builder/skill_builder.py \
    snapshot-skill --domain-id dm-domain-XXXX \
    --skill-dir local_skills/newskill/ --version v1.0 --repo-dir .
# Returns: snapshot ID + list of captured files (schema, script, prompts, tests)

# List all snapshots for a domain
uv run python .claude/skills/skill-builder/skill_builder.py \
    list-versions --domain-id dm-domain-XXXX

# List files captured in a snapshot
uv run python .claude/skills/skill-builder/skill_builder.py \
    list-files --snapshot-id dm-skill-snapshot-YYYY

# Show content of a captured file
uv run python .claude/skills/skill-builder/skill_builder.py \
    show-file --file-id dm-skill-file-ZZZZ

# Attach a plan document (Claude's design plan) to a snapshot
uv run python .claude/skills/skill-builder/skill_builder.py \
    add-plan --snapshot-id dm-skill-snapshot-YYYY \
    --plan-file ~/.claude/plans/my-plan.md --order 1 \
    --description "Initial implementation plan"

# Install post-commit hook (auto-snapshots skill on every git commit)
uv run python .claude/skills/skill-builder/skill_builder.py \
    install-hook --domain-id dm-domain-XXXX \
    --skill-dir local_skills/newskill/ --repo-dir .
chmod +x .git/hooks/post-commit
```

**Idempotency:** `snapshot-skill` checks the current commit SHA; if already snapshotted for this domain, it returns the existing record without duplicating.

**Large files:** Files >50KB are stored in the file cache (`~/.alhazen/cache/text/`) and referenced via `cache-path`. Smaller files are stored inline in TypeDB.

### Design Decisions

```bash
# Record a decision (types: entity | relation | attribute | hierarchy | constraint)
uv run python .claude/skills/skill-builder/skill_builder.py \
    add-decision --domain-id dm-domain-XXXX --type entity \
    --summary "Use dm-domain sub collection to group all design artifacts" \
    --version-id dm-skill-snapshot-YYYY \
    --alternatives "sub domain-thing: rejected, lacks collection grouping semantics"

# Add Claude's reasoning
uv run python .claude/skills/skill-builder/skill_builder.py \
    add-rationale --decision-id dm-decision-ZZZZ \
    --rationale "collection already has collection-membership and nesting relations; reusing these avoids duplicating grouping infrastructure" \
    --alternatives "domain-thing would require custom grouping relations"

# Link a schema-gap (from skilllog) as motivation for the decision
uv run python .claude/skills/skill-builder/skill_builder.py \
    link-gap --decision-id dm-decision-ZZZZ --gap-id gap-abc123

# List decisions (optionally filter by type)
uv run python .claude/skills/skill-builder/skill_builder.py \
    list-decisions --domain-id dm-domain-XXXX --type entity
```

### Experiments and Metrics

```bash
# Start an experiment
uv run python .claude/skills/skill-builder/skill_builder.py \
    start-experiment --domain-id dm-domain-XXXX \
    --hypothesis "v1.0 schema supports all required newskill queries" \
    --version-id dm-skill-snapshot-YYYY

# Record a quantitative result
uv run python .claude/skills/skill-builder/skill_builder.py \
    record-result --experiment-id dm-experiment-AAAA \
    --metric coverage --value 0.92 \
    --notes "8 of 100 test cases failed on missing causal-link relation"

# Mark complete
uv run python .claude/skills/skill-builder/skill_builder.py \
    complete-experiment --experiment-id dm-experiment-AAAA

# List experiments
uv run python .claude/skills/skill-builder/skill_builder.py \
    list-experiments --domain-id dm-domain-XXXX --status running
```

### Representation Errors

```bash
# Report an error (error types: type-mismatch | missing-concept | wrong-cardinality |
#   wrong-inheritance | semantic-ambiguity | over-generalization | under-generalization)
uv run python .claude/skills/skill-builder/skill_builder.py \
    report-error --domain-id dm-domain-XXXX \
    --type missing-concept \
    --summary "No entity type for 510k predicate device -- couldn't link predicate lineage" \
    --severity moderate --version-id dm-skill-snapshot-YYYY

# Resolve an error (link to the fixing decision)
uv run python .claude/skills/skill-builder/skill_builder.py \
    resolve-error --error-id dm-error-BBBB --decision-id dm-decision-ZZZZ

# List open errors
uv run python .claude/skills/skill-builder/skill_builder.py \
    list-errors --domain-id dm-domain-XXXX --status open
```

### Skill Gap Logging (typedb-notebook)

Record deficiencies discovered during skill use. When Claude has to ask something that should have been stored, or makes an incorrect inference, log it as a `schema-gap` for systematic improvement.

| Gap Type | When to Log |
|----------|-------------|
| `missing-user-context` | Had to ask the user for something that should be in the profile |
| `missing-entity-type` | No TypeDB type exists for something we needed to store |
| `missing-attribute` | Existing type lacks an attribute the workflow needed |
| `unclear-workflow` | Sensemaking instructions were ambiguous or produced wrong output |
| `incorrect-inference` | Claude's reasoning produced a factually wrong result |

```bash
# Record a gap
uv run python .claude/skills/typedb-notebook/typedb_notebook.py record-gap \
    --skill jobhunt \
    --type missing-user-context \
    --description "User home location not stored; had to ask about on-site viability" \
    --severity moderate \
    --example "GenBio AI on-site Palo Alto role: asked user if Palo Alto commute was viable"

# List open gaps for a skill
uv run python .claude/skills/typedb-notebook/typedb_notebook.py list-gaps --skill jobhunt

# List all open gaps
uv run python .claude/skills/typedb-notebook/typedb_notebook.py list-gaps

# Close a gap once addressed
uv run python .claude/skills/typedb-notebook/typedb_notebook.py close-gap \
    --id "gap-abc123" --status addressed
```

The `skill-model` entity (auto-created by `record-gap`) is the first-class representation of each skill in the knowledge graph. Multiple gaps can be linked to one skill-model.

Link an observed gap to the design decision that fixes it:

```bash
# Step 1: Record the gap (skilllog)
uv run python .claude/skills/typedb-notebook/typedb_notebook.py record-gap \
    --skill newskill --type missing-entity-type \
    --description "No type for 510k predicate device"

# Step 2: Link it to the fixing decision (skill-builder)
uv run python .claude/skills/skill-builder/skill_builder.py \
    link-gap --decision-id dm-decision-ZZZZ --gap-id gap-abc123
```

The gap ID is stored as a `dm-linked-gap-id` attribute (multi-valued: one per linked gap). The `show-domain` output includes linked gap IDs for cross-referencing.

---

## Reference: Artifact Types Registry

Artifact types are shared across all skills. Reuse existing types rather than creating new ones.

### Standard Artifact Types

| Type | Cache Dir | MIME Types | Example Uses |
|------|-----------|------------|--------------|
| `html` | `html/` | text/html | Job postings, web articles, company pages |
| `pdf` | `pdf/` | application/pdf | Papers, resumes, reports, cover letters |
| `image` | `image/` | image/* | Screenshots, figures, diagrams |
| `json` | `json/` | application/json | API responses, structured exports |
| `text` | `text/` | text/plain, text/markdown | Plain text content, notes |

### Storage Strategy

- **< 50KB:** Store inline in TypeDB `content` attribute
- **>= 50KB:** Store in cache, reference via `cache-path`

```python
from skillful_alhazen.utils.cache import should_cache, save_to_cache

if should_cache(content):
    cache_result = save_to_cache(artifact_id, content, mime_type)
    # Store cache_result['cache_path'] in TypeDB
else:
    # Store content inline in TypeDB
```

---

## Reference: User Profile Pattern

For domains where sensemaking depends on stable facts about the user — location,
constraints, preferences — define a profile entity so Claude never has to ask.

**When to use:** Any skill where analysis depends on the user-as-subject.
Examples: job hunting (location viability, salary floor), health tracking (conditions,
medications), learning (time budget, current level).

### Schema Template (TypeDB 3.x)

```typeql
# Profile attributes
attribute home-location, value string;
attribute my-domain-constraint, value string;

# Profile entity - inherits id, name, description from domain-thing.
# sub agent if the user is acting (job seeker, patient, learner).
# sub domain-thing if the user is an object being tracked.
# Singleton in practice; schema supports multi-user scenarios.
entity my-domain-user-profile sub agent,
    owns home-location,
    owns my-domain-constraint;
```

### CLI Convention

Two commands, always paired:

```bash
# Upsert: create if none exists, replace if one exists
script.py set-profile --location "..." --constraint "..."

# Read: single call that returns everything Claude needs for sensemaking
script.py show-profile
```

### Sensemaking Integration

In USAGE.md, instruct Claude to call `show-profile` **before** any analysis that
depends on user context:

```markdown
## Sensemaking Workflow
1. **Load seeker profile** (call FIRST -- never ask the user for this information)
   script.py show-profile
   Use result to automatically assess: location viability, constraint alignment, gaps
```

The `show-profile` command should return the profile entity plus all related
inventory (skills, learning resources, etc.) in a single JSON response.

### Reference Implementation

See `local_skills/jobhunt/jobhunt.py` `cmd_set_profile` and `cmd_show_profile` for
a complete example (`jobhunt-seeker sub agent` with `home-location`, `salary-floor`,
`remote-preference`, linked skills and learning resources).

---

## Reference: Schema Entity Map

| Entity | Base Type | When to Create |
|--------|-----------|----------------|
| `dm-domain` | `collection` | Once per skill/domain being designed |
| `dm-skill-snapshot` | `artifact` | Umbrella snapshot of full skill at one git commit |
| `dm-skill-file` | `artifact` | One captured file within a snapshot |
| `dm-design-decision` | `domain-thing` | Each significant schema choice |
| `dm-design-rationale` | `note` | Claude's reasoning for a decision |
| `dm-experiment` | `domain-thing` | Each hypothesis being tested |
| `dm-experiment-result` | `note` | Quantitative/qualitative observation |
| `dm-representation-error` | `domain-thing` | Each case where schema failed real data |

### Captured File Types

| `dm-file-type` | Files captured | `format` |
|---|---|---|
| `schema` | `schema.tql` | `typeql` |
| `script` | `<skill-name>.py` (main CLI) | `python` |
| `prompt-short` | `SKILL.md` | `markdown` |
| `prompt-full` | `USAGE.md` | `markdown` |
| `manifest` | `skill.yaml` | `yaml` |
| `test` | `tests/*.py` | `python` |
| `experiment` | `experiments/*.py`, `experiments/*.ipynb` | `python` / `ipynb` |
| `plan` | Added explicitly via `add-plan` | `markdown` |

**Note:** `dm-file-type = "experiment"` means a script in the skill's `experiments/` directory (captured as an artifact). This is distinct from `dm-experiment` entities, which track design hypotheses tested in TypeDB.

---

## Reference: TypeQL Query Examples

```typeql
# List all open design gaps for a domain
match $g isa dm-design-gap, has dm-error-status "open";
      $d isa dm-domain, has id "dm-domain-XXXX";
      (subject: $g, domain: $d) isa dm-in-domain;
fetch { "id": $g.id, "description": $g.description,
        "severity": $g.dm-error-severity, "phase": $g.dm-phase-number };

# Trace a derivation skill's outputs
match $sk isa dm-derivation-skill, has id "dm-derivation-skill-YYYY";
fetch { "id": $sk.id, "name": $sk.name,
        "inputs": $sk.dm-input-types, "outputs": $sk.dm-output-types,
        "feasibility": $sk.dm-feasibility };
```

---

## Reference: Dashboard Design Principles

1. **Query the graph** - Don't duplicate data; dashboards query TypeDB
2. **Pipeline views** - Show entities moving through states
3. **Matrix views** - Compare across dimensions
4. **Progress tracking** - Show completion of plans
5. **Deep dives** - Click to see all context about an entity

---

## Reference: Documenting Your New Domain

Every new domain skill needs documentation at four levels:

### Step 1: Skill Manifest (`skill.yaml`)

```yaml
name: my-domain
description: "Short description of what this skill does"
license: Apache-2.0
script: my_domain.py
schema: my_domain.tql
requires:
  bins: [uv, docker]
  env: [TYPEDB_HOST, TYPEDB_PORT, TYPEDB_DATABASE]
pattern: curation
phases:
  - foraging: "How sources are discovered"
  - ingestion: "How raw content is captured"
  - sensemaking: "What Claude extracts and analyzes"
  - analysis: "What cross-entity reasoning looks like"
  - reporting: "What dashboard views exist"
```

### Step 2: Query Examples (`local_resources/typedb/docs/query_examples.json`)

Add curated TypeQL examples for your namespace.

### Step 3: Regenerate Schema Docs

```bash
make docs-schema       # Generate local docs
make docs-schema-wiki  # Generate docs AND update wiki pages
```

### Step 4: Wiki Skill Page

Create `Skills:-<Domain>.md` in `~/Documents/Coding/skillful-alhazen.wiki/`. Follow `Skills:-Jobhunt.md` as a pattern.

### Step 5: Update CLAUDE.md

Add your skill to the "Available Skills" section so Claude knows about it.

### Documentation Maintenance

When you modify a schema:
1. `make docs-schema-wiki` — regenerate schema docs + wiki
2. Push wiki: `cd ~/Documents/Coding/skillful-alhazen.wiki && git add . && git commit -m 'Update schema docs' && git push`
3. Update `CLAUDE.md` Architecture section if hierarchy changed

---

## Reference: When to Create a New Domain

Create a new domain skill when:
1. You have a **specific information type** to track (papers, jobs, news, etc.)
2. Information comes from **discoverable sources** (APIs, URLs, databases)
3. You need to **reason over time** (not just one-shot questions)
4. Structure matters - entities have **attributes and relationships**
5. You want **Claude to build understanding** through sensemaking

Don't create a domain for:
- Simple lookups (use web search)
- One-time questions (just ask)
- Unstructured brainstorming (use notes)

---

## Examples: Job Hunting Domain

### Entity Types
- `jobhunt-company` (Thing) - An employer
- `jobhunt-position` (Thing) - A job posting
- `jobhunt-job-description` (Artifact) - Raw JD content
- `jobhunt-requirement` (Fragment) - Extracted skill requirement
- `jobhunt-fit-analysis-note` (Note) - Claude's fit assessment

### Script Commands
- `ingest-job --url` - Fetch and store job posting
- `add-skill --name --level` - Add to your skill profile
- `list-artifacts --status raw` - Artifacts needing analysis
- `show-artifact --id` - Get artifact for Claude to read
- `list-pipeline` - Show application status

### Sensemaking Flow
1. Script ingests URL -> creates artifact + placeholder position
2. User says "analyze that job posting"
3. Claude reads artifact content
4. Claude extracts: company, title, requirements, responsibilities
5. Claude compares to user's skill profile
6. Claude creates fit-analysis note with score and gaps
7. Claude reports findings and suggests next steps

---

## Examples: Literature Review Domain

### Entity Types
- `litreview-paper` (Thing) - A scientific paper
- `litreview-author` (Thing) - A researcher
- `litreview-pdf` (Artifact) - PDF content
- `litreview-claim` (Fragment) - Key claim with evidence
- `litreview-synthesis` (Note) - Cross-paper analysis

### Script Commands
- `ingest-paper --doi` - Fetch from DOI
- `ingest-paper --pmid` - Fetch from PubMed
- `search-papers --query` - Search literature databases
- `list-papers --collection` - Papers in a collection
- `show-paper --id` - Full paper details
