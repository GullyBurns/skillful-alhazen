# Agentic Memory — Full Usage Reference

## Overview

Implements a two-tier memory architecture:

1. **Short-term** — MEMORY.md files, context window (fast, ephemeral, file-based)
2. **Long-term** — TypeDB knowledge graph (structured, typed, reasoned over, persistent)

**Consolidation** is explicit: Claude judges when something is worth crystallizing, then calls `consolidate` to create a `memory-claim-note` entity. The quality signal from skilllog (`evaluation-label: golden`) IS the consolidation trigger.

---

## Data Model

### Core entities (defined in alhazen_notebook.tql)

```
identifiable-entity (abstract)
├── domain-thing                    -- real-world objects
│   └── agent sub domain-thing
│       └── person sub agent       -- real-world humans
│           ├── author sub person  -- publication authors
│           ├── operator-user      -- Alhazen operators (YOU)
│           └── application-user   -- end users of Alhazen apps
└── information-content-entity (abstract) -- content-bearing
    ├── artifact
    ├── fragment
    ├── note
    │   └── memory-claim-note      -- crystallized propositions (agentic-memory schema)
    └── episode                    -- process accounts of work sessions
```

### Personal context: 10 domains

| Domain | Storage | `--domain` key |
|--------|---------|----------------|
| Identity | `identity-summary` attribute | `identity` |
| Role + responsibilities | `role-description` attribute | `role` |
| Current projects | `project-involvement` → collection | (use `link-project`) |
| Team + relationships | `relationship-context` → person | (use `link-person`) |
| Tools + systems | `tool-familiarity` → domain-thing | (use `link-tool`) |
| Communication style | `communication-style` attribute | `style` |
| Goals + priorities | `goals-summary` attribute + memory-claim-notes (goal) | `goals` |
| Preferences + constraints | `preferences-summary` attribute | `preferences` |
| Domain knowledge | `domain-expertise` attribute + memory-claim-notes (knowledge) | `expertise` |
| Decision log | memory-claim-note (fact-type: decision) + episode-evidence | (use `consolidate`) |

### memory-claim-note fact-types

| fact-type | Use case |
|-----------|----------|
| `knowledge` | Factual propositions about the domain |
| `decision` | Architectural or design decisions made |
| `goal` | Objectives and priorities |
| `preference` | User preferences and working style constraints |
| `schema-gap` | Missing TypeDB schema elements (connects to skilllog gap workflow) |

---

## Command Reference

### Person / Context

#### `create-operator`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py create-operator \
  --name "Full Name" \
  [--given-name "First"] \
  [--family-name "Last"] \
  [--identity "Brief identity prose"] \
  [--role "Role and responsibilities prose"]
```
Returns: `{"success": true, "id": "op-<hex>", "name": "..."}`

#### `update-context-domain`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py update-context-domain \
  --person <id> \
  --domain identity|role|style|goals|preferences|expertise \
  --content "New prose content"
```

#### `get-context`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py get-context --person <id>
```
Returns context object with all 10 domains, linked projects and tools.

#### `link-project`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py link-project \
  --person <person-id> --collection <collection-id>
```

#### `link-tool`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py link-tool \
  --person <person-id> --entity <domain-thing-id>
```

#### `link-person`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py link-person \
  --from-person <id-a> --to-person <id-b> \
  [--context "Relationship description"]
```

#### `list-persons`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py list-persons
```

---

### Memory Claim Notes

#### `consolidate`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py consolidate \
  --content "Typed claim about the subject entity" \
  --subject <entity-id> \
  [--fact-type knowledge|decision|goal|preference|schema-gap] \
  [--confidence 0.0-1.0] \
  [--valid-until 2026-12-31T00:00:00] \
  [--source-episode <episode-id>] \
  [--source-note <note-id>]
```
Returns: `{"success": true, "id": "mcn-<hex>", "fact_type": "..."}`

The note is linked to its subject via `(note: $n, subject: $e) isa aboutness`.
Provenance is linked via `(derived: $n, source: $src) isa fact-evidence` if source provided.

#### `recall`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py recall --subject <entity-id>
```
Returns all active memory-claim-notes about the entity.

#### `recall-person`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py recall-person --person <id>
```

#### `invalidate`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py invalidate <claim-id>
```
Sets `valid-until` to now. The claim remains in the graph as historical record.

#### `list-claims`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py list-claims \
  [--fact-type knowledge] \
  [--person <id>] \
  [--limit 50]
```

---

### Episodes

#### `create-episode`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py create-episode \
  --summary "Narrative: what happened in this session" \
  [--skill agentic-memory] \
  [--session-id <skilllog-session-id>]
```
Returns: `{"success": true, "id": "ep-<hex>", "session_id": "..."}`

The `session-id` is shared with `skilllog-session.session-id` to link performance spine (skilllog) with semantic spine (episode).

#### `link-episode`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py link-episode \
  --episode <episode-id> \
  --entities "id1,id2,id3"
```
Creates `(session: $ep, subject: $e) isa episode-mention` for each entity.

#### `show-episode`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py show-episode <episode-id>
```
Returns episode metadata + list of linked entities.

#### `list-episodes`
```bash
uv run python .claude/skills/agentic-memory/agentic_memory.py list-episodes \
  [--skill agentic-memory] \
  [--limit 20]
```

---

## Reconciliation with Skilllog

| Skilllog concept | Agentic-memory concept | Relationship |
|---|---|---|
| `skilllog-session` (collection) | `episode` (ICE) | Same `session-id`. Session = performance spine. Episode = semantic spine. |
| `evaluation-label: golden` | `consolidate` trigger | **Unified**: golden label IS the memory trigger. |
| `schema-gap` (domain-thing) | `memory-claim-note` (fact-type: schema-gap) | memory-claim-note generalizes schema-gap |
| `skill-model` (domain-thing) | target of `tool-familiarity` | operator-users linked to skill-models they use |
| `agent-id` + `model-name` attrs | `ai-agent sub agent` | ai-agent gives typed identity to AI actors |

---

## Trigger Flow

1. `PostToolUse` hook fires → `skill_logger.py` records invocation
2. Claude marks invocation `golden` → hook prints `[CONSOLIDATION-HINT]` → call `consolidate`
3. At session close → call `create-episode`, then `link-episode` with key entities touched

---

## TypeDB Notes

- `memory-claim-note sub note` — inherits `content`, `confidence`, `valid-from`, `valid-until`, `created-at` from core
- `episode sub information-content-entity` — `content` holds the narrative; `session-id` links to skilllog
- `episode-mention` relation: `(session: $ep, subject: $e)` — any `identifiable-entity` can be a subject
- Queries: use `isa identifiable-entity, has id "..."` to match any entity by id regardless of concrete type
