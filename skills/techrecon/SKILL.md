---
name: techrecon
description: Systematically investigate external software systems, libraries, frameworks, and computational tools
---

# Tech Recon Skill

Use this skill to systematically study external software systems and build understanding of their architecture, data models, and integration potential. Claude acts as your research assistant, ingesting repos, docs, and source code, then extracting structured knowledge.

**When to use:** "investigate", "study", "research [system]", "look into", "tech recon", "ingest repo", "analyze this codebase", "architecture assessment", "integration analysis"

## Prerequisites

- TypeDB must be running: `make db-start`
- Dependencies installed: `uv sync --all-extras` (from project root)
- `GITHUB_TOKEN` env var recommended for higher rate limits

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen_notebook)
- `GITHUB_TOKEN`: GitHub API token (optional, recommended)

## Quick Start

```bash
# Start an investigation
uv run python .claude/skills/techrecon/techrecon.py start-investigation \
    --name "mediKanren Investigation" \
    --goal "Understand architecture and data model"

# Ingest a repository
uv run python .claude/skills/techrecon/techrecon.py ingest-repo \
    --url "https://github.com/webyrd/mediKanren" \
    --investigation "investigation-abc123"

# Find and link papers about a system
uv run python .claude/skills/techrecon/techrecon.py search-literature \
    --query "knowledge graph TypeDB" \
    --system "system-abc123" \
    --source openalex --limit 10
```

**Before executing any commands, read `USAGE.md` in this directory for the complete command reference, sensemaking workflow, data model, and full investigation example.**
