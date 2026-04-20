---
name: bioskills-index
description: Permanent, updatable EDAM-annotated index of all bioskills available online. Provides semantic search, UMAP cluster visualization, and composition playlists for assembling bioskill workflows.
triggers:
  - "find bioskills for [task]"
  - "what bioskills are available for [domain]"
  - "search bioskills index"
  - "compose a bioskill workflow for"
  - "update bioskills index"
  - "add a bioskill to the index"
  - "import EDAM"
  - "annotate skill with EDAM"
prerequisites:
  - TypeDB running (make db-start)
  - VOYAGE_API_KEY set for search/embed commands (dash.voyageai.com)
  - EDAM imported: run import-edam --namespace operation && import-edam --namespace topic
---

# Bioskills Index

Permanent, EDAM-annotated index of bioskills — SKILL.md-pattern skills, MCP servers, Nextflow workflows, Python API wrappers.

## Quick Start

```bash
# Create an index
uv run python .claude/skills/bioskills-index/bioskills_index.py create-index \
    --name "Bio AI Skills v1"

# Import EDAM ontology (one-time setup)
uv run python .claude/skills/bioskills-index/bioskills_index.py import-edam \
    --namespace operation
uv run python .claude/skills/bioskills-index/bioskills_index.py import-edam \
    --namespace topic

# Seed from prior investigation
uv run python .claude/skills/bioskills-index/bioskills_index.py update \
    --index <id>

# Search
uv run python .claude/skills/bioskills-index/bioskills_index.py search \
    --index <id> --query "protein structure prediction"

# Compose a workflow
uv run python .claude/skills/bioskills-index/bioskills_index.py compose \
    --index <id> --task "analyze single-cell RNA from IPF lung samples"
```

**Read USAGE.md before executing commands.**
