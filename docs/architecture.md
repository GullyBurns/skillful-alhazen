# Architecture

## TypeDB Schema
- `local_resources/typedb/alhazen_notebook.tql` - Core notebook schema
- `local_resources/typedb/docs/` - Generated schema documentation

## Alhazen's Notebook Model

The data model uses a three-branch hierarchy rooted at `alh-identifiable-entity`:

```
alh-identifiable-entity (abstract)         — id, name, description, provenance
├── alh-domain-thing                       — real-world objects (papers, genes, jobs)
│   ├── agent                          — operational actors (human or AI)
│   │   ├── alh-ai-agent                   — Claude, GPT-4, etc.
│   │   └── person                     — enriched: name, email, linkedin, title, bio, phone
│   │       ├── (bears roles via alh-role-bearing)
│   │       ├── author                 — publication authorship
│   │       └── jhunt-contact        — jhunt-contact-role (recruiter, hiring manager, etc.)
│   ├── alh-role                       — anti-rigid, bearer-dependent (BFO/UFO pattern)
│   │   ├── nbmem-operator-role        — 6 context domains (identity, role, goals, etc.)
│   │   └── jhunt-job-seeker-role      — job search preferences
│   ├── organization                   — enriched: linkedin, website, location, industry
│   │   └── jhunt-company            — job search context company
│   └── interaction                    — type, date, outcome, follow-up tracking
├── collection                         — typed sets (corpora, searches, case files)
└── alh-information-content-entity (abstract) — content, format, cache-path
    ├── artifact                       — raw captured content (PDF, HTML, email, calendar)
    ├── fragment                       — extracted piece of an artifact
    └── note                           — Claude's analysis or annotation
```

- **alh-domain-thing** is the base for all domain objects. Namespace subtypes (e.g., `scilit-paper`, `jhunt-position`, `apm-gene`) inherit from it.
- **person** (sub alh-agent) is the universal person model. All people — operator, authors, contacts — inherit from it. Enriched with alh-linkedin-url, title, bio, alh-phone-number. Plays alh-works-at:employee and alh-interaction-participation:participant.
- **organization** (sub alh-domain-thing) is enriched with alh-linkedin-url, alh-company-url, location, industry. Plays alh-works-at:employer. `jhunt-company` inherits from it.
- **interaction** (sub alh-domain-thing) tracks meetings, calls, emails, and interviews. Has type, date, outcome, follow-up tracking. Linked to participants via `alh-interaction-participation` relation.
- **collection** is typed per namespace: `scilit-corpus`, `jhunt-search`, `apm-case-file`, `apm-disease-family`, `apm-patient-cohort`.
- **alh-information-content-entity** is only for content-bearing entities that own `content`, `cache-path`, `format`, etc.

## MCP Server
- `src/skillful_alhazen/mcp/typedb_client.py` - TypeDB client library
- `src/skillful_alhazen/mcp/typedb_server.py` - FastMCP server

## Artifact Cache

Large artifacts (PDFs, HTML, images) are stored in a file cache organized by content type:
- `~/.alhazen/cache/html/` - Web pages (job postings, company pages)
- `~/.alhazen/cache/pdf/` - Documents (papers, reports)
- `~/.alhazen/cache/image/` - Images (screenshots, diagrams)
- `~/.alhazen/cache/json/` - Structured data (API responses)
- `~/.alhazen/cache/text/` - Plain text files
- `~/.alhazen/cache/github/` - Github repos (indexed by <organization>/<repo>)

**Storage Strategy:**
- Content < 50KB: Stored inline in TypeDB `content` attribute
- Content >= 50KB: Stored in cache, referenced via `cache-path` attribute

**Artifact types are shared across skills.** A PDF ingested by jobhunt (resume) uses the same `pdf/` directory as papers ingested by scientific-literature. This enables cross-skill artifact reuse and consistent type handling.

**Cache Utilities:**
- `src/skillful_alhazen/utils/cache.py` - Cache management functions
- Use `should_cache()` to check if content exceeds threshold
- Use `save_to_cache()` to store and get metadata
- Use `load_from_cache_text()` to retrieve content

## Skills

Skills follow a **self-contained directory architecture**:
```
skills/<name>/          (core skills, committed to this repo)
  SKILL.md              — Complete skill reference: triggers, workflows, commands, data model
  skill.yaml            — structured metadata (name, description, license, etc.)
  <name>.py             — CLI entry point
  schema.tql            — TypeDB schema extension (loaded by make build-db)
  quality-checks.yaml   — data quality audit rules (optional)
  dashboard/            — Optional Next.js dashboard components

local_skills/<name>/    (gitignored build artifact — DO NOT EDIT HERE)
  → core skills: symlinked from ../skills/<name>
  → external skills: cloned from git
```

**SKILL.md convention:**
- **Single file** containing everything: triggers, prerequisites, workflows (organized by curation phase), commands, data model, quality checks.
- Use a `read_strategy` field in the YAML frontmatter to tell Claude which sections to read for which tasks — not every section needs to be read every time.
- Organize by **curation phases**: Discovery -> Ingestion -> Sensemaking -> Analysis -> Reporting. This maps to the natural workflow of how a skill processes information.

**Single source of truth:** `skills-registry.yaml` — lists all skills (core with `path:`, external with `git:`).

**`make build-skills`** resolves the registry into `local_skills/` and wires `.claude/skills/` symlinks.

**Schema loading:** `make build-db` automatically discovers `local_skills/*/schema.tql` — no manual registration needed.

**Core OS Components** (managed by coordinator, not domain skills):

- **agentic-memory** *(core OS)* — Identity, memory, context (operator profiles, memory claims, episodes)
  - `skills/agentic-memory/`
- **typedb-notebook** *(core OS)* — Knowledge operations (collections, notes, tagging, aboutness)
  - `skills/typedb-notebook/`

**Domain Skills** (see `make skills-list` for live status):

- **web-search** *(core)* — Web search via SearXNG
  - `skills/web-search/`
- **curation-skill-builder** *(core)* — Design guidance for new TypeDB-backed curation skills (use official `skill-creator` plugin for all other skill development)
  - `skills/curation-skill-builder/`
- **jobhunt** *(external)* — Job hunting notebook
  - registered in `skills-registry.yaml`, resolved to `local_skills/jobhunt/`
- **tech-recon** *(core)* — Goal-driven technology investigation
  - `skills/tech-recon/`
- **scientific-literature** *(external)* — Multi-source scientific literature search and ingestion
  - Europe PMC, PubMed, OpenAlex, bioRxiv/medRxiv + semantic search (Voyage AI + Qdrant)
  - registered in `skills-registry.yaml`, resolved to `local_skills/scientific-literature/`

**Adding a new skill:**
1. Copy template: `cp -r skills/_template skills/<slog-skill-name>`
2. Implement `SKILL.md` (triggers, prereqs, workflows by curation phase, commands, data model), `skill.yaml`, `<slog-skill-name>.py`, `schema.tql`
3. Add to `skills-registry.yaml` with `path: skills/<slog-skill-name>`
4. Run `make build-skills` to wire it into Claude Code
5. See wiki [Skill Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) for full guide

## Scripts and Token Efficiency

**Philosophy:** Use scripts to minimize token usage. Scripts handle heavy lifting (pagination, bulk operations, API calls, TypeDB transactions) while Claude orchestrates at a higher level.

**When to use scripts:**
- Bulk operations (searching hundreds of papers)
- Paginated API calls
- Complex TypeDB transactions
- Repetitive data transformations

**When Claude can work directly:**
- Single paper lookups
- Simple queries
- Orchestrating multiple script calls
- Analyzing results returned by scripts

**Writing new skills:** When integrating a new data source or API:
1. Copy the template: `cp -r skills/_template skills/<slog-skill-name>`
2. Design the TypeDB schema in `skills/<slog-skill-name>/schema.tql` (auto-discovered by `make build-db`)
3. Implement commands in `<slog-skill-name>.py` following the template
4. Fill in `SKILL.md` and `skill.yaml` with metadata and commands
5. Add a `path: skills/<slog-skill-name>` entry to `skills-registry.yaml`
6. Run `make build-skills` then `make build-db` to wire everything
7. See wiki [Skill Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) for full guide

**Script conventions:**
- Scripts output JSON to stdout for easy parsing
- Progress/errors go to stderr
- Use argparse with subcommands
- Handle missing dependencies gracefully (check imports, warn user)
- Include `--help` documentation

## Agents

Agents are named sub-agents that bind to specific skills. They follow the **same directory convention as skills**:

```
agents/<name>/          (agent definitions, committed to this repo)
  AGENT.md              — Agent identity, capabilities, operating rules, skill bindings
  agent.yaml            — Structured metadata (skills, connections, memory scope, dispatch config)
```

**Single source of truth:** `agents-registry.yaml` — lists all agents (core with `path:`, external with `git:`).

**`make build-agents`** resolves the registry and symlinks agents to `.claude/agents/`.

**Adding a new agent:**
1. Copy template: `cp -r agents/_template agents/<agent-name>`
2. Define identity, skills, connections, and memory scope in `AGENT.md` and `agent.yaml`
3. Add to `agents-registry.yaml` with `path: agents/<agent-name>`
4. Run `make build-agents` to wire it into Claude Code

## Dashboards

Interactive Next.js TypeScript dashboard:

- `dashboard/` - Dashboards built with Next.js 16, shadcn/ui, and Tailwind CSS
  - Pipeline Kanban board for tracking applications
  - Skills matrix showing gaps across positions
  - Learning plan with progress tracking
  - Stats overview cards

**Skill dashboard wiring:** Each skill can contribute dashboard UI via `local_skills/<skill>/dashboard/`:
```
local_skills/<skill>/dashboard/
  lib.ts          → dashboard/src/lib/<skill>.ts       (API client functions)
  components/     → dashboard/src/components/<skill>/  (React components)
  pages/          → dashboard/src/app/(<skill>)/       (Next.js pages)
  routes/         → dashboard/src/app/api/<skill>/     (API routes)
```

- **Docker build** copies these files at build time (see `dashboard/Dockerfile` stage `node-builder`)
- **Local dev** uses symlinks — `make build-skills` wires components/routes but **not** `lib.ts` files. You must manually symlink them:
  ```bash
  cd dashboard/src/lib
  ln -sf ../../../local_skills/jobhunt/dashboard/lib.ts jobhunt.ts
  ln -sf ../../../local_skills/techrecon/dashboard/lib.ts techrecon.ts
  ```
- **Docker dashboard** runs on port 3001 (mapped from container 3000): `http://localhost:3001`

Run locally with:
```bash
cd dashboard && npm install && npm run dev
```

For a full guide to building a new skill dashboard, see [`docs/dashboard-guide.md`](dashboard-guide.md).
