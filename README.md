# Skillful-Alhazen

**A TypeDB-powered scientific knowledge notebook, built on Claude Code**

> *"The duty of the man who investigates the writings of scientists, if learning the truth is his goal, is to make himself an enemy of all that he reads, and, applying his mind to the core and margins of its content, attack it from every side."*
>
> — Ibn al-Haytham (Alhazen), 965-1039 AD

## What is Alhazen?

Alhazen is a **curation system** that helps researchers make sense of information—not just store it. You interact with Claude through natural language, and Claude handles all the complexity of storing, querying, and reasoning over your knowledge graph.

The system combines:
- **Claude Code** as the agentic interface—you talk to Claude, Claude does the work
- **TypeDB** as the knowledge graph backend (you never touch it directly)
- **Skills** for domain-specific workflows (literature review, job hunting, etc.)

The system embodies Alhazen's philosophy: be an enemy of all you read. Don't passively collect—actively interrogate, extract meaning, and build understanding.

## Quick Start

### Prerequisites

1. [Claude Code](https://claude.ai/code) installed and configured
2. [Docker](https://www.docker.com/) for running TypeDB
3. [uv](https://docs.astral.sh/uv/) for Python dependency management

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/gullyburns/skillful-alhazen
cd skillful-alhazen

# 2. Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh  # if needed
uv sync --all-extras

# 3. Start TypeDB
docker compose -f docker-compose-typedb.yml up -d
```

### Using Alhazen

Open Claude Code in this directory and start working. Claude will initialize the database if needed.

**Example conversations:**

```
You: I found an interesting job posting at https://example.com/senior-ml-engineer
Claude: [Uses /jobhunt to ingest and analyze the posting, extracts requirements,
        compares to your profile, identifies skill gaps]

You: Search for papers about CRISPR delivery mechanisms
Claude: [Uses /epmc-search to find papers, shows results, offers to add to a collection]

You: Remember that the Smith et al. paper claims lipid nanoparticles are most effective
Claude: [Uses /typedb-notebook to store this finding with provenance]

You: What skill gaps do I have across my top job prospects?
Claude: [Queries the knowledge graph, synthesizes across positions, recommends learning priorities]
```

Claude handles all TypeDB operations behind the scenes. You just have a conversation.

## History & Origins

Skillful-Alhazen is forked from CZI's [alhazen](https://github.com/chanzuckerberg/alhazen) project, originally built to help Chan Zuckerberg Initiative researchers understand scientific literature at scale. The original system used LangChain, PostgreSQL, and various LLM providers.

This fork reimagines the architecture around:
- **Claude Code** as the primary agentic layer (replacing LangChain agents)
- **TypeDB** as the knowledge representation layer (replacing PostgreSQL)
- **Skills** as modular domain capabilities (replacing monolithic notebooks)

The goal remains the same: AI-powered scientific knowledge engineering.

## Design Principles

### 1. Curation as Core Mission

The system exists to help you **make sense** of material, not just store it. Every component serves the curation workflow:

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

### 2. Claude Code as the Interface

You interact through natural conversation. Claude:
- Understands your intent
- Chooses the right skill for the task
- Handles all database operations
- Synthesizes and reports back

You never write queries, call APIs, or manage data directly.

### 3. Clear Separation: Scripts Handle I/O, Claude Thinks

Behind the scenes, skills have two components:

**Python scripts handle:**
- Fetching from APIs (pagination, rate limits, bulk operations)
- Storing raw artifacts with provenance
- TypeDB transactions
- Returning structured data

**Claude handles:**
- Reading and comprehending content
- Extracting entities and relationships
- Creating structured notes
- Synthesizing across sources
- Recommending actions

This separation minimizes token usage while maximizing Claude's comprehension capabilities.

### 4. TypeDB as Ontological Memory

TypeDB provides a logic-driven knowledge graph where:
- **Schema defines concepts** Claude thinks with (entities, relations, attributes)
- **Queries are logical** (pattern matching, inference rules)
- **Provenance is preserved** (artifacts → fragments → notes chain)

The schema isn't just storage—it's the conceptual vocabulary for reasoning about a domain. But you don't need to know TypeDB exists. Claude handles it.

### 5. Embrace the Bitter Lesson

Following [Richard Sutton's insight](http://www.incompleteideas.net/IncIdeas/BitterLesson.html): general methods that leverage computation win in the long run. We don't over-engineer extraction pipelines or hand-code entity recognizers. Instead:

- Let Claude read and comprehend
- Store what Claude extracts
- Query and synthesize

The system improves as Claude improves, without brittle extraction rules.

## Where Does the Name 'Alhazen' Come From?

### The Scholar

Ibn al-Haytham (965-1039 AD), latinized as **Alhazen**, was an Arab mathematician, astronomer, and physicist. He pioneered the scientific method through rigorous experimentation, five centuries before Renaissance scientists followed the same paradigm.

His work on optics—the *Book of Optics* (Kitab al-Manazir)—fundamentally shaped understanding of vision, light, and perception. He was the first to correctly explain that vision occurs when light reflects from objects into the eye, overturning the ancient Greek theory that eyes emit rays.

But it's his philosophy of critical reading that inspires this project. The quote above captures an approach to knowledge that remains radical: make yourself an *enemy* of what you read, attack it from every side, and suspect even yourself.

### The Nile Project Legend

According to historical accounts ([Tbakhi & Amir 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC6074172/)), Ibn al-Haytham's critical method emerged from an extraordinary circumstance.

The Fatimid Caliph of Egypt, al-Hakim bi-Amr Allah, invited Ibn al-Haytham to regulate the flooding of the Nile River. Ibn al-Haytham proposed building a dam south of Aswan—remarkably close to where the modern Aswan High Dam stands today.

But when Ibn al-Haytham traveled south to survey the site, he realized the scheme was impractical with the technology of his era. He had to return to Cairo and inform the Caliph that his grand plan would fail.

This was dangerous. Al-Hakim was notoriously volatile and violent—he had executed scholars for less. Ibn al-Haytham, by some accounts, feigned madness to escape punishment. He was placed under house arrest, where he remained for roughly ten years until al-Hakim's assassination in 1021.

During this confinement, Ibn al-Haytham produced his greatest works, including the *Book of Optics*. Sometimes the most productive work happens under constraint.

### References

- [Wikipedia: Ibn al-Haytham](https://en.wikipedia.org/wiki/Ibn_al-Haytham)
- [Tbakhi & Amir 2007: Ibn Al-Haytham: Father of Modern Optics](https://pmc.ncbi.nlm.nih.gov/articles/PMC6074172/)
- [ibnalhaytham.com](https://www.ibnalhaytham.com/)
- [Britannica: Ibn al-Haytham](https://www.britannica.com/biography/Ibn-al-Haytham)

## Available Skills

### `/jobhunt` - Job Application Tracking

Track job applications through a pipeline with sensemaking:
- "Ingest this job posting: [URL]"
- "What are my skill gaps for this position?"
- "Show my application pipeline"
- "What should I learn next?"

### `/epmc-search` - Europe PMC Literature Search

Search scientific literature and build reading lists:
- "Search for papers about [topic]"
- "How many papers match [query]?"
- "Add these to my [collection name] collection"

### `/typedb-notebook` - General Knowledge Operations

Core operations for the knowledge graph:
- "Remember that [finding] from [source]"
- "What do I know about [topic]?"
- "Organize my notes on [subject]"

### `/domain-modeling` - Meta-Skill

Design new domain skills following the curation pattern. Use this when you want to track a new type of information systematically.

## Dashboard

An interactive Next.js dashboard visualizes your knowledge graph:

```bash
cd dashboard && npm install && npm run dev
```

Features:
- Pipeline Kanban for job applications
- Skills matrix showing gaps across positions
- Learning plan with progress tracking

## Architecture (For Contributors)

### TypeDB Schema

The core schema (`local_resources/typedb/alhazen_notebook.tql`) defines five entity types:

- **Collection** - A named group of Things
- **Thing** - Any recorded item (paper, company, position, etc.)
- **Artifact** - Raw captured content with provenance
- **Fragment** - Extracted portion of an Artifact
- **Note** - Claude's structured annotation about any entity

Domain-specific extensions:
- `namespaces/scilit.tql` - Scientific literature
- `namespaces/jobhunt.tql` - Job hunting

### Skills Structure

```
.claude/skills/
├── typedb-notebook/    # Core knowledge operations
│   ├── SKILL.md        # Instructions for Claude
│   └── *.py            # TypeDB transaction scripts
├── epmc-search/        # Literature search
├── jobhunt/            # Job tracking
└── domain-modeling/    # Meta-skill for new domains
```

### Development Setup

```bash
# Install dependencies
uv sync --all-extras

# Start TypeDB
docker compose -f docker-compose-typedb.yml up -d

# Run tests
uv run pytest tests/ -v
```

### TypeDB Version

Currently using TypeDB 2.x (2.25.0 server, 2.29.x driver). Migration to TypeDB 3.0 planned when Python drivers stabilize.

Reference: `local_resources/typedb/typedb-2x-documentation.md`

## Caution & Caveats

- **Data licensing**: This toolkit can download information from the web. Users should abide by data licensing requirements and third-party terms of service.
- **LLM accuracy**: All data generated by Large Language Models should be reviewed for accuracy. Claude's extractions and analyses are interpretations, not ground truth.

## Contributing

Contributions welcome! Please open an issue or pull request.

When contributing new skills:
1. Follow the curation pattern (see `/domain-modeling`)
2. Separate script responsibilities from Claude responsibilities
3. Include `SKILL.md` documentation
4. Add schema extensions if needed

## License

This project is a fork of [CZI's Alhazen](https://github.com/chanzuckerberg/alhazen), originally released under the MIT License.
