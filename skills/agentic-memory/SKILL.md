---
name: agentic-memory
description: TypeDB-backed two-tier memory architecture — short-term files to long-term ontological storage. Models persons (operators + application users) with 10-domain personal context, memory-claim-notes (typed, time-bounded propositions), and session episodes.
triggers:
  - remember this / record this decision / consolidate
  - what do I know about... / recall facts about...
  - create an episode / anchor this session
  - update my context / who is...
  - create operator user / set up personal context
prerequisites:
  - TypeDB running: make db-start
  - make build-skills
---

# Agentic Memory Skill

Two-tier memory for Alhazen: short-term (MEMORY.md, context window) → long-term (TypeDB typed knowledge graph).

**Three entity types:**
- **operator-user** — person running Alhazen (you); holds 10-domain personal context
- **memory-claim-note** — crystallized proposition (sub note); fact-type: knowledge | decision | goal | preference | schema-gap
- **episode** — process account of a work session (4th ICE sibling); links to entities touched

## Quick Start

```bash
# Create operator profile
uv run python .claude/skills/agentic-memory/agentic_memory.py create-operator \
  --name "Gully Burns" --identity "Biomedical researcher..." --role "Principal Investigator"

# Consolidate a decision into long-term memory
uv run python .claude/skills/agentic-memory/agentic_memory.py consolidate \
  --content "TypeDB is the ontological storage layer for all Alhazen memory" \
  --subject <operator-id> --fact-type knowledge --confidence 0.95

# Create a session episode
uv run python .claude/skills/agentic-memory/agentic_memory.py create-episode \
  --skill agentic-memory --summary "Designed and implemented agentic-memory skill schema"

# Recall what we know about an entity
uv run python .claude/skills/agentic-memory/agentic_memory.py recall --subject <id>
```

## Consolidation Trigger

When skilllog marks an invocation `evaluation-label: golden`, that is the signal to call `consolidate` to crystallize key outputs as memory-claim-notes. Create an episode at session close.

## Command Output Pattern

`uv run` emits a `VIRTUAL_ENV` warning to stderr. Always use `2>/dev/null` when piping output to a JSON parser — never `2>&1`, which merges the warning into stdout and breaks JSON parsing.

**Read USAGE.md before executing commands.**
