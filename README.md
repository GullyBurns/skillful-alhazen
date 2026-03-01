# Skillful-Alhazen

**A TypeDB-powered agentic knowledge notebook — run interactively with Claude Code or deployed persistently via OpenClaw**

> **Prototype software** — APIs, schemas, and skill interfaces are subject to change without notice.

> *"The duty of the man who investigates the writings of scientists, if learning the truth is his goal, is to make himself an enemy of all that he reads, and, applying his mind to the core and margins of its content, attack it from every side."*
>
> — Ibn al-Haytham (Alhazen), 965-1039 AD

## What is Alhazen?

Alhazen is an **agentic curation system** with knowledge graph memory. The agent reads job postings, disease databases, and scientific literature — building structured understanding from unstructured sources. You never write queries or call APIs directly. The agent handles all of it.

Three layers:
- **Agent** — Claude Code (interactive) or OpenClaw (persistent service)
- **TypeDB** — ontological memory: schema defines the concepts the agent reasons with
- **Skills** — domain modules combining a TypeDB schema namespace, Python scripts, and agent instructions

📖 **Full documentation: [github.com/GullyBurns/skillful-alhazen/wiki](https://github.com/GullyBurns/skillful-alhazen/wiki)**

## Quick Start

**Prerequisites:** [Claude Code](https://claude.ai/code), [Docker](https://www.docker.com/), [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/gullyburns/skillful-alhazen
cd skillful-alhazen
make build   # install deps + resolve skills + start TypeDB
claude       # open Claude Code and start talking
```

Then just talk to Claude:

```
You: Search for papers about CRISPR delivery mechanisms
You: Ingest this job posting: https://example.com/senior-ml-engineer
You: Remember that lipid nanoparticles are most effective for hepatic delivery
You: What skill gaps do I have across my top job prospects?
```

## Three Ways to Run

**A. Claude Code (Interactive)** — Open Claude Code in the project directory. Best for exploration and building new skills.

**B. OpenClaw on Mac Mini** — Dedicated machine running OpenClaw with Telegram triage, cron-scheduled foragers, and security hardening. Access your knowledge graph from anywhere via messaging.

**C. OpenClaw on VPS** — Full persistent service on a hardened Linux server. Nightly foraging, always-on accumulation, no laptop required.

See the [Deployment guide](https://github.com/GullyBurns/skillful-alhazen/wiki/Deployment) for the progression from local dev to production.

## Demonstration Skills

| Skill | What it does |
|-------|-------------|
| `/jobhunt` | Track applications — ingest postings, fit analysis, skill gap identification, nightly forager |
| `/rare-disease` | Build 360° disease knowledge graphs from MONDO IDs — phenome, genome, therapeutome |
| `/epmc-search` | Search Europe PMC literature and build reading collections |
| `/typedb-notebook` | Core knowledge operations — remember, recall, organize |

## Why TypeDB?

TypeDB is the **ontological foundation** — the schema defines the concepts the agent reasons with:

```
identifiable-entity (abstract root)
├── domain-thing              # Real-world objects: diseases, genes, companies, jobs
├── collection                # Typed sets: investigations, search campaigns, corpora
└── information-content-entity (abstract)
    ├── artifact              # Raw captured content (API responses, HTML, PDFs)
    ├── fragment              # Extracted pieces (requirements, phenotype associations)
    └── note                  # Agent's analysis (fit scores, mechanism notes, syntheses)
```

A gene or job posting is not information content. Only artifacts, fragments, and notes carry content. Domain objects are what you reason *about*; ICEs are what you reason *with*.

## Adding Skills

Skills are self-contained directories with a TypeDB schema, Python scripts, and agent instructions:

```bash
cp -r skills/_template skills/my-skill
# implement SKILL.md, USAGE.md, schema.tql, my-skill.py
# add to skills-registry.yaml
make build-skills && make build-db
```

See the [Skill Architecture guide](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture).

## History

Forked from CZI's [alhazen](https://github.com/chanzuckerberg/alhazen), reimagined around Claude Code, TypeDB 3.x, and a skill-based architecture. Named after Ibn al-Haytham (965–1039 AD), who pioneered the scientific method five centuries before the Renaissance. See [History](https://github.com/GullyBurns/skillful-alhazen/wiki/History).

## Caveats

- **Data licensing**: Users are responsible for complying with data licensing requirements and third-party terms of service.
- **LLM accuracy**: All LLM-generated content should be reviewed. Claude's extractions are interpretations, not ground truth.

## License

Fork of [CZI's Alhazen](https://github.com/chanzuckerberg/alhazen), originally released under the MIT License.
