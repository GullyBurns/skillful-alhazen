# Skillful Alhazen

**A TypeDB-powered agentic knowledge notebook — run interactively with Claude Code or deployed persistently via OpenClaw**

> **Prototype software** — APIs, schemas, and skill interfaces are subject to change without notice.

> *"The duty of the man who investigates the writings of scientists, if learning the truth is his goal, is to make himself an enemy of all that he reads, and, applying his mind to the core and margins of its content, attack it from every side."*
>
> — Ibn al-Haytham (Alhazen), 965–1039 AD

---

## What is it?

Skillful Alhazen is an **agentic curation system with knowledge graph memory**. The agent reads scientific papers, disease databases, job postings, news articles, and more — building structured understanding in a TypeDB knowledge graph that persists across sessions and grows over time.

Three layers work together:

- **Agent** — Claude Code (interactive) or OpenClaw (persistent service). You talk; the agent curates.
- **TypeDB** — ontological memory. The schema defines the concepts the agent reasons *about*; the data is what it has learned so far.
- **Skills** — domain modules combining a TypeDB schema namespace, Python CLI scripts, and agent instructions. Each skill extends what the agent can do and remember in a specific domain.

Skills are not just prompts. Each skill contributes a typed schema namespace to the knowledge graph, a set of CLI commands the agent calls to read and write structured data, and (optionally) a Next.js dashboard for browsing what has been learned.

📖 **Full documentation: [github.com/GullyBurns/skillful-alhazen/wiki](https://github.com/GullyBurns/skillful-alhazen/wiki)**

---

## Quick Start

**Prerequisites:** [Claude Code](https://claude.ai/code), [Docker](https://www.docker.com/), [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/GullyBurns/skillful-alhazen
cd skillful-alhazen
make build   # install deps + resolve skills + start TypeDB
claude       # open Claude Code and start talking
```

Then just talk to Claude:

```
You: Search PubMed for papers about CRISPR delivery mechanisms and build a corpus
You: What are the pathophysiological mechanisms underlying Marfan syndrome?
You: Ingest this job posting: https://example.com/senior-ml-engineer
You: Remember that lipid nanoparticles are most effective for hepatic delivery
You: What skill gaps do I have across my top three job prospects?
```

---

## Skills

### Core Skills

Built into this repository (`skills/` directory). Always available.

| Skill | What it does |
|-------|-------------|
| `typedb-notebook` | Core knowledge operations — remember facts, recall notes, create collections, tag entities, track schema gaps |
| `web-search` | Web search via SearXNG (self-hosted metasearch, no API key needed) |
| `curation-skill-builder` | Design and build new TypeDB-backed curation skills; 6-phase system design framework with TypeDB tracking |

### External Skills

Resolved from [`sciknow-io/alhazen-skill-examples`](https://github.com/sciknow-io/alhazen-skill-examples) and custom repositories. Cloned into `local_skills/` on `make build-skills`.

| Skill | Domain | What it does | Dashboard |
|-------|--------|-------------|-----------|
| `scientific-literature` | Biomedical research | Multi-source literature search (Europe PMC, PubMed, OpenAlex, bioRxiv/medRxiv) + semantic search via Voyage AI + Qdrant | — |
| `alg-precision-therapeutics` | Rare disease | Investigate disease mechanism of harm and therapeutic landscape from a MONDO diagnosis | ✓ |
| `literature-trends` | Research analysis | Trace how explanatory hypotheses evolve over time in a tagged literature corpus | — |
| `they-said-whaaa` | Journalism | Track consistency of public figures — ingest transcripts and articles, extract claims, detect contradictions | ✓ |
| `jobhunt` | Career | Track job applications — ingest postings, fit analysis, skill gap identification | ✓ |
| `tech-recon` | Technology | Systematic investigation of software systems against user-defined success criteria | ✓ |
| `dismech` | Disease mechanisms | Browse the DisMech knowledge graph (750+ curated disease mechanism entries) | — |

---

## Three Ways to Run

| Mode | Setup | Best for |
|------|-------|----------|
| **(A) Claude Code** | `make build && claude` | Exploration, skill development, one-off research |
| **(B) OpenClaw on Mac Mini** | `./deploy/deploy.sh --target-type macmini` | Persistent local service with Telegram triage |
| **(C) OpenClaw on VPS** | `./deploy/deploy.sh --target-type vps` | Always-on, hardened production deployment |

See the [Deployment guide](https://github.com/GullyBurns/skillful-alhazen/wiki/Deployment) for the A → B → C progression.

---

## Architecture

```
identifiable-entity (abstract root)
├── domain-thing              # Real-world objects: papers, diseases, genes, companies, jobs
├── collection                # Typed sets: corpora, search campaigns, investigations
└── information-content-entity (abstract)
    ├── artifact              # Raw captured content (PDFs, HTML, API responses)
    ├── fragment              # Extracted pieces (phenotype associations, requirements)
    └── note                  # Agent analysis (fit scores, mechanism notes, syntheses)
```

Each skill extends this hierarchy with domain-specific types. A gene or disease is a `domain-thing`. A paper ingested from PubMed is an `artifact`. The agent's synthesis of a paper's key claims is a `note`. Collections group domain objects into research corpora.

**Schema gaps** — when the agent tries to represent something that has no place in the current schema — are the primary signal for knowledge graph evolution. The skilllog system detects gaps automatically (via a PostToolUse hook), files them as GitHub issues, and provides a local fix workflow. See [Gap Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Gap-Architecture).

---

## Adding Skills

Skills are self-contained directories. The skills registry (`skills-registry.yaml`) is the single source of truth.

```bash
cp -r skills/_template skills/my-skill
# implement SKILL.md, USAGE.md, schema.tql, my-skill.py
# add a path: entry to skills-registry.yaml
make build-skills && make build-db
```

See the [Skill Architecture guide](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture).

---

## History

Forked from CZI's [alhazen](https://github.com/chanzuckerberg/alhazen), reimagined around Claude Code, TypeDB 3.x, and a skill-based architecture. Named after Ibn al-Haytham (965–1039 AD), who pioneered the scientific method five centuries before the Renaissance. See [History](https://github.com/GullyBurns/skillful-alhazen/wiki/History).

## Caveats

- **Data licensing:** Users are responsible for complying with data licensing requirements and third-party terms of service for all external sources queried by skills.
- **LLM accuracy:** All LLM-generated content should be reviewed. Claude's extractions are interpretations, not ground truth.

## License

Fork of [CZI's Alhazen](https://github.com/chanzuckerberg/alhazen), originally released under the MIT License.
