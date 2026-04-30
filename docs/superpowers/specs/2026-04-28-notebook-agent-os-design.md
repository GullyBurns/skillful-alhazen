# Notebook Agent OS - Reference Architecture Design

## Context

Alhazen already implements most of what the "Agent OS" concept describes (identity, context, skills, memory, connections, verification) but these capabilities are scattered across skills, hooks, and config files without a unifying framework. The goal is to:

1. **Organize** Alhazen's existing capabilities into a coherent 6-layer Agent OS architecture
2. **Introduce a multi-agent hub** where named sub-agents (not just skills) are the primary organizational unit for tying skills together
3. **Define a reference architecture** called "notebook-agent-os" that can later be extracted as a standalone Claude plugin

This design does NOT refactor existing code. It adds a thin organizational layer on top of what exists.

## Design Decisions (from brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Product relationship | Reference architecture first, extract later | Avoid premature abstraction |
| Storage model | TypeDB-first | Graph is single source of truth |
| Agent model | Multi-agent hub with sub-agents | Clear delineation between agent functions |
| Connections | Documented capabilities (not a registry) | Connections are code artifacts, not runtime entities |
| Verification | Observability + quality labels | Extend existing skilllog |
| Automations | Skip for now | Focus on layers 1-6 |
| OS layer documentation | SKILL.md convention | Each OS layer follows the same pattern as skills |
| Core capabilities | Part of core library, not a skill | agentic-memory, typedb-notebook, skilllog are OS-level, not domain skills |
| Plugin packaging | Lightweight skill wrappers over existing code | No duplication or refactoring |
| Sub-agent definition | Same pattern as skills (directory + AGENT.md) | Consistent architecture |

## Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │         DOMAIN SKILLS               │
                    │  tech-recon, scientific-literature,  │
                    │  dismech, jobhunt, bioskills-index   │
                    └──────────────┬──────────────────────┘
                                   │ depend on
                    ┌──────────────▼──────────────────────┐
                    │      NAMED SUB-AGENTS               │
                    │  agents/ directories with AGENT.md  │
                    │  each agent binds to specific skills │
                    └──────────────┬──────────────────────┘
                                   │ managed by
                    ┌──────────────▼──────────────────────┐
                    │     NOTEBOOK-AGENT-OS (core)        │
                    │                                     │
                    │  Layer 6: Verification (skilllog)   │
                    │  Layer 5: Connections (documented)   │
                    │  Layer 4: Memory (two-tier)          │
                    │  Layer 3: Skills (registry)          │
                    │  Layer 2: Context (structured docs)  │
                    │  Layer 1: Identity (operator-user)   │
                    │                                     │
                    │  + Agent Hub (coordinator)           │
                    │  + Notebook (collections/notes/tags) │
                    └──────────────┬──────────────────────┘
                                   │ backed by
                    ┌──────────────▼──────────────────────┐
                    │           TypeDB                     │
                    │    (knowledge graph backbone)        │
                    └─────────────────────────────────────┘
```

## The 6 Layers

### Layer 1: Identity

**What it is**: Who the operator is and what rules are enforced every session.

**Current state**: `agentic-memory` skill has `operator-user` entity with 10 context domains (identity-summary, role-description, communication-style, goals-summary, preferences-summary, domain-expertise, plus relations for projects, tools, people).

**In the OS**: Identity moves from being a skill feature to a **core OS capability**. The coordinator agent (CLAUDE.md) always has access to the operator's identity. It's loaded at session start, not on-demand.

**Implementation**:
- `operator-user` entity and its 10 context domains remain in TypeDB schema (in the core OS schema, not a skill schema)
- CLAUDE.md includes instructions for the coordinator to load identity at session start
- CLI commands: `create-operator`, `update-context-domain`, `get-context` (existing commands from `agentic_memory.py`)

### Layer 2: Context

**What it is**: Structured knowledge about the operator's situation (team, priorities, stakeholders, projects).

**Current state**: CLAUDE.md + MEMORY.md (ad-hoc), plus agentic-memory context domains and `project-involvement`, `relationship-context`, `tool-familiarity` relations.

**In the OS**: Context is the combination of:
- **TypeDB relations** (projects, people, tools) that the coordinator can query
- **Context files** in the workspace (strategy docs, stakeholder maps) that are referenced by TypeDB entities via `cache-path` or `source-uri`
- **MEMORY.md** continues as the fast short-term context index

**Implementation**:
- Existing agentic-memory commands: `link-project`, `link-tool`, `link-person`
- Context files are plain markdown in the workspace (e.g., `context/stakeholders.md`, `context/priorities.md`)
- TypeDB stores metadata about context files (what they cover, when last updated) so the coordinator knows what's available

### Layer 3: Skills

**What it is**: Reusable, domain-specific instruction sets with their own schemas, CLIs, and dashboards.

**Current state**: Fully architected. `skills-registry.yaml` + `skills/` directories + `local_skills/` resolution + `.claude/skills/` symlinks.

**In the OS**: Unchanged. Skills remain self-contained:
```
skills/<name>/
  SKILL.md              # When to use, quick start
  USAGE.md              # Full reference
  skill.yaml            # Metadata
  <name>.py             # CLI entry point
  schema.tql            # TypeDB schema extension
  dashboard/            # Optional Next.js UI
```

The only change is that skills are **bound to agents** (see Agent Hub below), not globally available to the coordinator. The coordinator dispatches sub-agents, and each sub-agent has access to its bound skills.

### Layer 4: Memory

**What it is**: What the system remembers across sessions.

**Current state**: Two-tier architecture:
- **Short-term**: MEMORY.md files (auto-memory, loaded every session)
- **Long-term**: TypeDB `memory-claim-note` entities with typed facts (knowledge, decision, goal, preference, schema-gap), time-bounded via `valid-from`/`valid-until`

**In the OS**: Memory is a core OS capability, not a skill:
- `consolidate` command promotes session insights to TypeDB memory-claim-notes
- `recall` command queries long-term memory by topic, person, or time range
- `create-episode` captures session process accounts
- The coordinator uses memory to inform sub-agent dispatches (e.g., "the researcher found X last week")

**Implementation**: Existing `agentic_memory.py` commands, promoted from skill to core OS.

### Layer 5: Connections

**What it is**: How agents reach external systems (MCP servers, CLI tools, APIs).

**Current state**: Ad-hoc. `.mcp.json` has Playwright. CLI tools call PubMed, EPMC, OpenAlex, GitHub. SearXNG for web search. No structured documentation of what's connected.

**In the OS**: Connections are **documented capabilities**, not a registry:
- Each connection is a code artifact (MCP server config, CLI tool, Python package)
- Documentation follows the skill convention: a `connections/` directory with markdown files describing each connection, its permissions (read/write), and which agents use it
- No TypeDB schema for connections (they're infrastructure, not knowledge)

**Implementation**:
- `connections/` directory with one markdown file per connection type
- A utility command that introspects `.mcp.json` + installed packages to generate/validate the docs
- Agent profiles (AGENT.md) reference which connections they can use

### Layer 6: Verification

**What it is**: Ensuring outputs are correct and the system improves over time.

**Current state**: PostToolUse hooks log all skill invocations via `skill_logger.py`. Skilllog tracks evaluation labels (golden/rejected/unlabeled). Schema gap detection auto-files GitHub issues.

**In the OS**: Verification extends what exists:
- **Per-invocation**: skilllog continues tracking every skill call with quality labels
- **Per-agent**: Agent activity is logged as episodes in TypeDB
- **System audit**: A periodic review command that identifies stale context, unused skills, memory drift, and agent performance trends
- **Consolidation trigger**: When skilllog marks an invocation as `golden`, the coordinator can consolidate key outputs into long-term memory

**Implementation**: Existing `skill_logger.py` + new `audit` command in the core OS CLI.

## Agent Hub

### Sub-Agent Definition Pattern

Sub-agents follow the **same directory convention as skills**:

```
agents/                              # Agent definitions (committed to repo)
├── _template/                       # Template for new agents
│   ├── AGENT.md                     # Agent identity + dispatch instructions
│   └── agent.yaml                   # Structured metadata
├── researcher/
│   ├── AGENT.md
│   └── agent.yaml
├── chief-of-staff/
│   ├── AGENT.md
│   └── agent.yaml
└── curator/
    ├── AGENT.md
    └── agent.yaml
```

Resolution follows the same pattern as skills:
```
agents/ → .claude/agents/            # Symlinked for Claude Code access
```

### AGENT.md Structure

```markdown
---
name: researcher
description: Scientific research specialist
skills: [scientific-literature, tech-recon, web-search]
connections: [pubmed, epmc, github, searxng]
memory-scope: [papers, investigations, literature-trends]
model: opus                          # Optional model preference
isolation: worktree                  # Optional: run in isolated worktree
---

## Identity

You are a scientific research specialist working for {{operator-name}}.
Your focus is on {{operator-domain-expertise}}.

## Capabilities

- Search and ingest scientific literature (PubMed, EPMC, OpenAlex, bioRxiv)
- Run technology investigations with systematic evaluation
- Web search for grey literature and technical documentation

## Operating Rules

- Always cite sources with DOIs or URLs
- Create notes for every significant finding
- Tag all ingested papers with EDAM ontology terms when available
- Report schema gaps immediately when TypeDB types are missing

## Dispatch Context

When dispatched, you receive:
- The operator's current project context
- Relevant memory-claim-notes from prior research sessions
- The specific research question or investigation goal
```

### agent.yaml Structure

```yaml
name: researcher
version: 0.1.0
description: Scientific research specialist
author: Gully Burns

skills:
  - scientific-literature
  - tech-recon
  - web-search

connections:
  - pubmed
  - epmc
  - github
  - searxng

memory_scope:
  - papers
  - investigations
  - literature-trends

dispatch:
  model: opus
  isolation: worktree        # Optional
  parallel: true             # Can run alongside other agents
```

### Coordinator Behavior

The coordinator (main Claude Code session) is defined by CLAUDE.md. It:

1. **Loads identity** at session start (queries `operator-user` from TypeDB)
2. **Reads agent definitions** from `.claude/agents/`
3. **Dispatches sub-agents** using Claude Code's `Agent()` tool, injecting:
   - The agent's AGENT.md as the prompt preamble
   - Relevant operator context (from TypeDB identity + context domains)
   - Relevant memory (recall by topic matching the agent's memory-scope)
   - The specific task
4. **Consolidates results** — marks quality labels, promotes findings to long-term memory
5. **Manages the hub** — creates/updates agent definitions, tracks agent activity

### Agent Registry

Analogous to `skills-registry.yaml`:

```yaml
# agents-registry.yaml
agents:
  - name: researcher
    path: agents/researcher

  - name: chief-of-staff
    path: agents/chief-of-staff

  - name: curator
    path: agents/curator

  # External agents (from other repos)
  - name: disease-specialist
    git: https://github.com/sciknow-io/alhazen-agent-examples
    path: agents/disease-specialist
```

Resolved by `make build-agents` (parallel to `make build-skills`).

## Core OS as Claude Plugin

The notebook-agent-os plugin is a **lightweight layer** over the existing skillful-alhazen code:

```
notebook-agent-os/                   # Claude plugin repo
├── skills/
│   ├── identity/
│   │   └── SKILL.md                 # Thin wrapper: calls agentic_memory.py operator commands
│   ├── memory/
│   │   └── SKILL.md                 # Thin wrapper: calls agentic_memory.py memory commands
│   ├── notebook/
│   │   └── SKILL.md                 # Thin wrapper: calls typedb_notebook.py
│   ├── agent-hub/
│   │   └── SKILL.md                 # NEW: agent management + dispatch
│   └── verification/
│       └── SKILL.md                 # Thin wrapper: calls skill_logger.py
├── agents/
│   └── _template/
│       ├── AGENT.md
│       └── agent.yaml
├── CLAUDE.md                        # Core OS coordinator instructions
├── references/
│   ├── typedb-patterns.md
│   └── agent-dispatch-patterns.md
└── plugin.yaml                      # Claude plugin manifest
```

**Key constraint**: These skills call the **same Python scripts** that already exist in skillful-alhazen. The plugin provides organization and CLAUDE.md framing, not new code. When installed in a project that has skillful-alhazen as a dependency, the CLI commands resolve to the existing implementations.

## What Changes in Skillful-Alhazen

### Promoted to Core OS (no longer skills)

| Current Location | New Role |
|------------------|----------|
| `skills/agentic-memory/` | Core OS: identity + memory + context |
| `skills/typedb-notebook/` | Core OS: notebook operations |
| `local_resources/skilllog/` | Core OS: verification |

These move conceptually (in documentation and CLAUDE.md framing) but the **code stays where it is**. The `agentic-memory` and `typedb-notebook` directories remain; they just stop being registered as "skills" in `skills-registry.yaml` and instead become core OS components referenced by CLAUDE.md.

### New Directories

| Directory | Purpose |
|-----------|---------|
| `agents/` | Named sub-agent definitions (AGENT.md + agent.yaml) |
| `agents/_template/` | Template for creating new agents |
| `agents-registry.yaml` | Agent registry (parallel to skills-registry.yaml) |
| `connections/` | Documented connection capabilities |

### New Makefile Targets

```makefile
build-agents          # Resolve agents-registry.yaml → .claude/agents/
build-os              # build-env + build-agents + build-skills + build-db
```

### Updated CLAUDE.md

CLAUDE.md gains a "Coordinator" section that describes:
- How to load operator identity at session start
- How to read and dispatch sub-agents
- How to consolidate results into long-term memory
- How to manage connections documentation
- How to run verification/audit

## Alhazen-Specific Agents (Initial Set)

| Agent | Skills | Purpose |
|-------|--------|---------|
| `researcher` | scientific-literature, web-search | Literature search, paper ingestion, semantic search |
| `investigator` | tech-recon, web-search | Technology investigation, system evaluation |
| `curator` | curation-skill-builder, typedb-notebook | Schema design, skill development |
| `analyst` | dismech, bioskills-index | Disease mechanism analysis, bioskills workflows |

These are Alhazen-specific and would NOT be part of the generic notebook-agent-os plugin.

## Verification Plan

1. **Agent definition**: Create a test agent (e.g., `researcher`) with AGENT.md and agent.yaml
2. **Agent resolution**: Run `make build-agents`, verify `.claude/agents/researcher/` is symlinked
3. **Agent dispatch**: From the coordinator, dispatch the researcher agent with a test task, verify it receives the correct skills context and operator identity
4. **Memory flow**: After the researcher completes work, verify consolidation creates memory-claim-notes in TypeDB
5. **Dashboard**: Verify agent activity appears in the agentic-memory dashboard (episodes linked to agents)
6. **Plugin extraction**: Verify the notebook-agent-os plugin structure can be installed in a fresh project and correctly wraps the core commands

## Files to Modify

| File | Change |
|------|--------|
| `CLAUDE.md` | Add coordinator section (identity loading, agent dispatch, memory consolidation) |
| `Makefile` | Add `build-agents`, `build-os` targets |
| `skills-registry.yaml` | Remove `agentic-memory` and `typedb-notebook` (promoted to core) |
| `agents-registry.yaml` | New file: agent definitions |
| `agents/_template/AGENT.md` | New file: agent template |
| `agents/_template/agent.yaml` | New file: agent metadata template |
| `agents/researcher/AGENT.md` | New file: first agent definition |
| `agents/researcher/agent.yaml` | New file: researcher metadata |
| `connections/README.md` | New file: connections documentation index |
