# Connections

Documented capabilities for how agents reach external systems. Each connection is a code artifact (MCP server, CLI tool, Python package, or API). This directory documents what's available, permissions, and which agents use each connection.

## Active Connections

### MCP Servers (configured in `.mcp.json`)

| Connection | Type | Permissions | Used By |
|------------|------|-------------|---------|
| **Playwright** | MCP server (`@playwright/mcp`) | Read/Write (browser automation) | investigator |

### CLI Tools (Python packages via `uv run`)

| Connection | Package | Permissions | Used By |
|------------|---------|-------------|---------|
| **PubMed/EPMC** | `scientific-literature` skill | Read-only (API queries) | researcher |
| **OpenAlex** | `scientific-literature` skill | Read-only (API queries) | researcher |
| **bioRxiv/medRxiv** | `scientific-literature` skill | Read-only (API queries) | researcher |
| **GitHub** | `git clone` + GitHub API | Read-only (repo cloning) | investigator, curator |
| **Monarch Initiative** | REST API (`api-v3.monarchinitiative.org`) | Read-only | analyst |

### Search

| Connection | Type | Permissions | Used By |
|------------|------|-------------|---------|
| **SearXNG** | Self-hosted metasearch (Docker) | Read-only | researcher, investigator |

### Vector Stores

| Connection | Type | Permissions | Used By |
|------------|------|-------------|---------|
| **Qdrant** | Docker container (`localhost:6333`) | Read/Write | researcher, analyst |

### Embedding APIs

| Connection | Type | Permissions | Used By |
|------------|------|-------------|---------|
| **Voyage AI** | Cloud API (requires `VOYAGE_API_KEY`) | Read-only | researcher |

## Adding a New Connection

1. Install the connection (MCP server in `.mcp.json`, Python package in `pyproject.toml`, or Docker service in `docker-compose.yml`)
2. Document it in this file with: type, permissions, and which agents use it
3. Reference it in the relevant agent's `AGENT.md` frontmatter `connections:` list
4. Start with **read-only** access; add write access after observing agent behavior

## Permission Principles

- Start read-only for all new connections
- Write access requires explicit operator approval
- MCP servers should use scoped permissions where available
- Document any API keys or credentials needed (but never store them here)
