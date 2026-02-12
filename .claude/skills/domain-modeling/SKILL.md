---
name: domain-modeling
description: Design and implement domain-specific knowledge skills using the curation pattern
---

# Domain Modeling Skill

Use this skill when designing a new knowledge domain for the Alhazen notebook system. This is a **meta-skill** that teaches how to build domain-specific skills following the curation pattern.

## The Curation Design Pattern

All domain skills follow a 5-phase workflow:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CURATION WORKFLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. FORAGING          2. INGESTION         3. SENSEMAKING                   │
│  ┌──────────┐        ┌──────────┐         ┌──────────────┐                  │
│  │ Discover │───────▶│  Capture │────────▶│ Claude reads │                  │
│  │ sources  │        │   raw    │         │ & extracts   │                  │
│  └──────────┘        └──────────┘         └──────────────┘                  │
│       │                   │                      │                          │
│       ▼                   ▼                      ▼                          │
│  - URLs             - Artifacts            - Fragments                      │
│  - APIs             - Provenance           - Notes                          │
│  - Feeds            - Timestamps           - Relations                      │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│               4. ANALYZE/SUMMARIZE        5. REPORT                         │
│               ┌──────────────────┐       ┌──────────────┐                   │
│               │ Reason over many │──────▶│  Dashboard   │                   │
│               │ notes over time  │       │  & answers   │                   │
│               └──────────────────┘       └──────────────┘                   │
│                        │                        │                           │
│                        ▼                        ▼                           │
│                   - Synthesis notes        - Pipeline views                 │
│                   - Trend analysis         - Skills matrix                  │
│                   - Recommendations        - Strategic reports              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Breakdown

### Phase 1: FORAGING - Discovering Sources

**What it is:** Finding things in the world worth capturing. This is often the most creative/expansive phase.

**Examples by domain:**
| Domain | Foraging Activities |
|--------|---------------------|
| Job hunting | Job boards, company career pages, VC portfolio sites, LinkedIn, referrals |
| Literature review | PubMed, Google Scholar, citation chains, conference proceedings |
| News investigation | RSS feeds, social media, press releases, public records |
| Biology research | Databases (UniProt, GenBank), preprints, lab websites |

**Key insight:** Foraging can be recursive - finding one thing leads to discovering others.

**Script support:** Tools that help discover sources (search APIs, link extraction, sitemap parsing)

---

### Phase 2: INGESTION - Raw Capture with Provenance

**What it is:** Pulling material in UNEDITED format. The artifact is the authoritative record.

**Critical properties:**
- **Provenance** - Where did this come from? (URL, timestamp, API, email)
- **Immutability** - The raw content doesn't change after capture
- **Completeness** - Capture the whole thing, not just parts you think matter now

**Maps to TypeDB:**
```
Artifact (raw content)
├── owns source-uri
├── owns created-at (timestamp)
├── owns content (full text/HTML)
└── plays representation:artifact → Thing
```

**Script responsibility:** Fetch and store raw content. NO parsing, NO extraction, NO interpretation.

```python
# What the script should do:
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

**Browser-based ingestion tip:** When using Playwright to browse large web pages (especially LinkedIn profiles), use `mcp__playwright__browser_take_screenshot` instead of parsing the DOM snapshot. The accessibility tree for these pages can be 100KB+ and easy to misread. A screenshot gives visual context that's much easier to interpret accurately.

---

### Phase 3: SENSEMAKING - Claude Reads and Extracts

**What it is:** Claude reads the artifact and creates structured understanding. This is where the LLM's comprehension matters.

**Sensemaking Subtasks:**

| Subtask | Description | Output |
|---------|-------------|--------|
| **Parsing** | Understanding document structure (sections, headers, lists) | Structure map |
| **Entity Extraction** | Identifying named entities (company, people, skills, technologies) | Entities → Things |
| **Relation Extraction** | How entities connect (position → company, skill → required-by) | Relations |
| **Classification** | Categorizing (role type, seniority, remote policy) | Tags |
| **Summarization** | Condensing key points | Notes |
| **Gap Analysis** | Comparing against known profile | Skill-gap notes |
| **Inference** | Drawing conclusions not explicitly stated | Analysis notes |

**Maps to TypeDB:**
```
Fragment (extracted piece of artifact)
├── owns content (the specific text)
├── plays extraction:fragment → Artifact (provenance back to source)
└── plays aboutness:subject ← Note (Claude's interpretation)

Note (Claude's understanding)
├── owns content (Claude's interpretation/analysis)
├── owns confidence (how sure Claude is)
├── plays aboutness:note → [Thing, Artifact, Fragment, other Notes]
└── owns tags
```

**Key architectural point:** Sensemaking is ITERATIVE. Claude might:
1. First pass: Extract obvious entities (company name, job title, location)
2. Second pass: Deeper analysis (requirements, responsibilities, culture signals)
3. Later: Re-analyze when you have more context (compare to other postings)

---

### Phase 4: ANALYZE / SUMMARIZE - Reasoning Over Time

**What it is:** Looking across many sensemaking notes to answer questions and generate insights.

**Examples:**
- "What skills appear most frequently across my high-priority positions?"
- "How does this company's culture compare to others I'm considering?"
- "What's my overall fit trajectory as I complete learning resources?"

**Output:** Synthesis notes that reference multiple sources

```
Synthesis Note
├── about → [position-1, position-2, position-3]
├── content: "Across these three roles, distributed systems appears
│            as required in 2/3 and preferred in 1/3. This is your
│            biggest gap. Recommend prioritizing DDIA book."
└── tags: [synthesis, skill-gaps, recommendation]
```

---

### Phase 5: REPORT - Presentation for Action

**What it is:** Structuring information for human consumption and decision-making.

**Dashboard components:**
- **Pipeline views** - Where things stand (Kanban)
- **Matrices** - Comparisons across dimensions (skills × positions)
- **Progress tracking** - Learning plan completion
- **Alerts** - Deadlines, required actions
- **Deep dives** - All context about a specific entity

**Key insight:** Reports should be generated from TypeDB queries, not stored separately. The dashboard queries the knowledge graph.

---

## Separation of Concerns

### What Scripts Do (Python)

```
SCRIPT RESPONSIBILITIES
┌────────────────────────────────────────┐
│ Foraging:                              │
│ - Search APIs                          │
│ - List sources                         │
│ - Discover links                       │
│                                        │
│ Ingestion:                             │
│ - Fetch URL content                    │
│ - Store raw HTML/text                  │
│ - Record provenance                    │
│ - Create artifact                      │
│ - NO parsing, NO extraction            │
│                                        │
│ Queries:                               │
│ - List artifacts                       │
│ - List entities                        │
│ - Pipeline views                       │
│ - Return data for Claude to reason     │
└────────────────────────────────────────┘
```

### What Claude Does (via SKILL.md)

```
CLAUDE RESPONSIBILITIES
┌────────────────────────────────────────┐
│ Sensemaking:                           │
│ - Read artifact content                │
│ - Extract entities                     │
│ - Create fragments                     │
│ - Write notes                          │
│ - Flag uncertainties                   │
│                                        │
│ Analysis:                              │
│ - Query across notes                   │
│ - Generate synthesis                   │
│ - Compare to profiles                  │
│ - Make recommendations                 │
│                                        │
│ Interaction:                           │
│ - Present findings to user             │
│ - Ask clarifying questions             │
│ - Suggest next actions                 │
└────────────────────────────────────────┘
```

---

## Artifact Types Registry

Artifact types are shared across all skills. When designing a new skill, reuse existing types rather than creating new ones.

### Standard Artifact Types

| Type | Cache Dir | MIME Types | Example Uses |
|------|-----------|------------|--------------|
| `html` | `html/` | text/html | Job postings, web articles, company pages |
| `pdf` | `pdf/` | application/pdf | Papers, resumes, reports, cover letters |
| `image` | `image/` | image/* | Screenshots, figures, diagrams |
| `json` | `json/` | application/json | API responses, structured exports |
| `text` | `text/` | text/plain, text/markdown | Plain text content, notes |

### TypeDB Schema for Cached Artifacts

All artifacts inherit from `artifact` and can own these cache-related attributes:
- `cache-path` - Relative path in cache (e.g., "pdf/artifact-abc123.pdf")
- `mime-type` - Content type (e.g., "application/pdf")
- `file-size` - Size in bytes
- `content-hash` - SHA-256 hash of content

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

### Cross-Skill Artifact Sharing

Skills can consume artifacts created by other skills:
- A paper PDF ingested by `epmc-search` can be referenced by `typedb-notebook`
- A resume PDF from `jobhunt` can be analyzed by any skill
- Web content cached by one skill is available to all

When creating new artifact subtypes in your skill's schema, use the standard cache directories rather than creating new ones.

---

## Designing a New Domain

### Step 1: Identify Entity Types

Map your domain to the Alhazen model:

| Alhazen Type | Your Domain | Example (Job Hunt) | Example (Lit Review) |
|--------------|-------------|-------------------|---------------------|
| **Thing** | Primary items you track | Company, Position | Paper, Author |
| **Artifact** | Raw captured content | Job Description | PDF, Abstract |
| **Fragment** | Extracted pieces | Requirement | Claim, Method |
| **Note** | Claude's analysis | Fit Analysis | Critique, Summary |

### Step 2: Define Attributes

What properties do your entities have?

```typeql
# Pattern: domain-entity sub base-type,
#     owns domain-specific-attribute;

jobhunt-position sub domain-thing,
    owns job-url,
    owns salary-range,
    owns location,
    owns remote-policy;
```

### Step 3: Define Relations

How do entities connect?

```typeql
# Pattern: domain-relation sub relation,
#     relates role1,
#     relates role2;

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

In your SKILL.md, tell Claude what to extract. Example:

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

# [Add your domain attributes here]
domain-attr-1 sub attribute, value string;
domain-attr-2 sub attribute, value datetime;

# =============================================================================
# ENTITIES - Things
# =============================================================================

domain-thing sub domain-thing,
    owns domain-attr-1,
    plays domain-relation:role;

# =============================================================================
# ENTITIES - Artifacts
# =============================================================================

domain-artifact-type sub artifact;

# =============================================================================
# ENTITIES - Fragments
# =============================================================================

domain-fragment-type sub fragment,
    owns domain-attr-1,
    plays domain-relation:role;

# =============================================================================
# ENTITIES - Notes
# =============================================================================

domain-note-type sub note;

# =============================================================================
# RELATIONS
# =============================================================================

domain-relation sub relation,
    relates role1,
    relates role2;
```

---

## Example: Job Hunting Domain

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
1. Script ingests URL → creates artifact + placeholder position
2. User says "analyze that job posting"
3. Claude reads artifact content
4. Claude extracts: company, title, requirements, responsibilities
5. Claude compares to user's skill profile
6. Claude creates fit-analysis note with score and gaps
7. Claude reports findings and suggests next steps

---

## Example: Literature Review Domain

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

### Sensemaking Flow
1. Script searches for papers → stores metadata and PDFs
2. User says "analyze this paper"
3. Claude reads PDF/abstract content
4. Claude extracts: claims, methods, limitations, connections
5. Claude creates notes linking to other papers
6. User asks "synthesize findings on topic X"
7. Claude queries notes → creates synthesis note

---

## Your Skill Profile Pattern

For domains where you're comparing against your own capabilities (job hunting, learning), add a profile entity:

```typeql
# Your skill/capability profile
your-skill sub entity,
    owns skill-name,
    owns skill-level,     # strong/some/none/learning
    owns last-updated;
```

Script commands:
- `add-skill --name --level` - Add/update skill
- `list-skills` - Show your profile

Claude uses this for gap analysis during sensemaking.

---

## Dashboard Design Principles

1. **Query the graph** - Don't duplicate data; dashboards query TypeDB
2. **Pipeline views** - Show entities moving through states
3. **Matrix views** - Compare across dimensions
4. **Progress tracking** - Show completion of plans
5. **Deep dives** - Click to see all context about an entity

Example views:
- Job hunt: Pipeline (Kanban), Skills Matrix, Learning Plan
- Lit review: Reading List, Citation Graph, Theme Clusters
- News: Timeline, Source Network, Topic Trends

---

## When to Create a New Domain

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
