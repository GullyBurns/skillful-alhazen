---
name: your-domain-name
description: Brief description of what this skill does
---

# Your Domain Name Skill

Use this skill to [describe primary use case]. Claude acts as [describe Claude's role in this domain].

**When to use:** [Triggers: "ingest [item]", "analyze [item]", "show [entity]", ...]

## Prerequisites

- TypeDB must be running: `make db-start`
- Dependencies installed: `uv sync --all-extras` (from project root)
- Schema loaded: run `make build-db` after adding your `schema.tql`

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen_notebook)

## Quick Start

```bash
uv run python .claude/skills/<your-domain>/<your-domain>.py list-entities
```

**Before executing any commands, read `USAGE.md` in this directory for the complete command reference, workflows, and data model.**
