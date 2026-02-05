# Design Concepts

This document explains the architecture and design principles behind Skillful-Alhazen.

## Core Philosophy: Curation Over Collection

The system exists to help you **make sense** of material, not just store it. This distinction is crucial:

- **Collection** = passively accumulating information
- **Curation** = actively interrogating, extracting meaning, building understanding

Every component serves the curation mission. We embody Alhazen's philosophy: be an enemy of all you read.

## The Curation Workflow

All skills follow a five-stage workflow:

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

### Stage Descriptions

| Stage | Purpose | Outputs |
|-------|---------|---------|
| **Foraging** | Discover sources of information | URLs, API endpoints, feeds |
| **Ingestion** | Capture raw content with provenance | Artifacts with timestamps and sources |
| **Sensemaking** | Claude reads and extracts meaning | Fragments, notes, relationships |
| **Analysis** | Reason over accumulated knowledge | Synthesis notes, gap analysis |
| **Reporting** | Present actionable insights | Dashboards, answers, recommendations |

## Separation of Concerns

A key architectural principle: **scripts handle I/O, Claude handles thinking**.

### Python Scripts Handle:
- Fetching from APIs (pagination, rate limits, bulk operations)
- Storing raw artifacts with provenance
- TypeDB transactions
- Returning structured data to Claude

### Claude Handles:
- Reading and comprehending content
- Extracting entities and relationships
- Creating structured notes
- Synthesizing across sources
- Recommending actions

This separation:
- **Minimizes token usage** (scripts do the heavy lifting)
- **Maximizes comprehension** (Claude focuses on understanding)
- **Enables scaling** (scripts handle pagination, bulk operations)

## Claude Code as the Interface

You interact through natural conversation. You never:
- Write TypeQL queries
- Call APIs directly
- Manage database transactions
- Navigate file structures

Claude translates your intent into actions, choosing the right skill and executing the appropriate operations.

```
You: "What are my skill gaps across high-priority positions?"

Claude: [Internally]
  1. Query positions with priority:high tag
  2. For each, fetch requirements
  3. Compare against your skill profile
  4. Aggregate gaps by frequency
  5. Link to relevant learning resources

Claude: [Response]
  "Across 3 high-priority positions, the most common gaps are:
   1. Distributed Systems (required in 3/3)
   2. Kubernetes (required in 2/3)
   ..."
```

## TypeDB as Ontological Memory

TypeDB provides a logic-driven knowledge graph. Key properties:

### Schema as Conceptual Vocabulary

The schema defines the concepts Claude thinks with:

```
entity collection sub thing;
entity artifact sub thing;
entity fragment sub thing;
entity note sub thing;

relation has-artifact relates owner, relates artifact;
relation has-fragment relates source, relates fragment;
relation annotates relates note, relates subject;
```

These aren't just storage tables—they're the vocabulary for reasoning about knowledge.

### Provenance Preservation

Every piece of knowledge traces back to its source:

```
Artifact (raw job description)
    ↓
Fragment (extracted requirement)
    ↓
Note (your fit analysis)
```

You can always ask: "Where did this come from?"

### Logical Queries

TypeDB uses pattern matching:

```typeql
match
  $p isa jobhunt-position, has priority "high";
  $r isa jobhunt-requirement;
  (position: $p, requirement: $r) isa requires;
  $r has your-level "none";
fetch
  $p: title;
  $r: skill-name;
```

This finds all skill gaps in high-priority positions.

## Embrace the Bitter Lesson

Following [Richard Sutton's insight](http://www.incompleteideas.net/IncIdeas/BitterLesson.html): general methods that leverage computation win in the long run.

We don't:
- Over-engineer extraction pipelines
- Hand-code entity recognizers
- Build brittle rule systems
- Require perfect structured input

Instead:
- Let Claude read and comprehend
- Store what Claude extracts
- Query and synthesize

**The system improves as Claude improves**, without requiring code changes.

## Skills Architecture

Skills are modular domain capabilities. Each skill has:

```
.claude/skills/<skill-name>/
├── SKILL.md     # Instructions for Claude
└── *.py         # TypeDB transaction scripts
```

### SKILL.md

Tells Claude:
- When to use this skill
- What commands are available
- How to interpret results
- Domain-specific concepts

### Python Scripts

Handle the mechanics:
- API calls
- TypeDB transactions
- Data transformations
- Bulk operations

### Creating New Skills

Use the `/domain-modeling` meta-skill to design new domains following the curation pattern. It will help you:
1. Define the entity types
2. Design the schema
3. Write the SKILL.md
4. Create the transaction scripts

## Data Model

The core schema defines five entity types:

| Entity | Description | Examples |
|--------|-------------|----------|
| **Collection** | Named group of things | "CRISPR Review", "Q1 Job Hunt" |
| **Thing** | Any recorded item | Paper, company, position |
| **Artifact** | Raw captured content | Job description, PDF, API response |
| **Fragment** | Extracted portion | Requirement, finding, quote |
| **Note** | Claude's annotation | Fit analysis, research note, strategy |

Domain-specific extensions (in `namespaces/`) add specialized types:
- `scilit.tql` - Papers, authors, citations
- `jobhunt.tql` - Positions, companies, skills, requirements
