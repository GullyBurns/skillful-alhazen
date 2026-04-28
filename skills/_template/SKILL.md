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

## Schema Gap Recognition

During sensemaking, if you encounter a concept, relationship, or entity type that has no place in the current TypeDB schema, that is a **schema gap** — a signal for schema evolution, not a failure.

When you notice a schema gap:
1. Complete as much as possible with the current schema (partial knowledge > none)
2. Immediately file a gap issue:

```bash
uv run python local_resources/skilllog/skill_logger.py file-schema-gap \
  --skill <this-skill-name> \
  --concept "<the concept you tried to represent>" \
  --missing "<which TypeDB entity/relation/attribute is absent>" \
  --suggested "<proposed TypeQL addition, or 'unknown' if unsure>"
```

**Examples of schema gaps:**
- A paper has a methodology section but there's no `methodology` attribute on `scilit-paper`
- A job posting mentions a work arrangement type that isn't in the schema
- A disease has a phenotype frequency that can't be attached to the current relation

Use `--dry-run` first to review the issue before filing it.

## Command Output Pattern

`uv run` emits a `VIRTUAL_ENV` warning to stderr. Always use `2>/dev/null` when piping output to a JSON parser — never `2>&1`, which merges the warning into stdout and breaks JSON parsing.

**Before executing any commands, read `USAGE.md` in this directory for the complete command reference, workflows, and data model.**
