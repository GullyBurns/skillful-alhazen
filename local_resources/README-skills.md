# Skill Portability Documentation

This document provides a comprehensive comparison of skill formats across different AI agent frameworks and describes how skills can be made portable between them.

## Framework Comparison

### AgentSkills (Open Standard by Anthropic)

**Overview:** AgentSkills is an open standard for defining reusable AI agent capabilities as structured markdown documents.

**Location Pattern:** `<name>/SKILL.md`

**Frontmatter Schema:**
```yaml
---
name: skill-name                    # Required: lowercase, hyphens, 1-64 chars
description: "Brief description"    # Required: 1-1024 chars
license: "Apache-2.0"              # Optional: SPDX license identifier
compatibility: "Requirements desc" # Optional: System requirements
metadata:                          # Optional: key-value map
  key: value
allowed-tools:                     # Optional: list of allowed tools
  - web_search
  - exec
---
```

**Directory Structure:**
```
skill-name/
├── SKILL.md          # Required: Main skill definition
├── scripts/          # Optional: Helper scripts
├── references/       # Optional: Documentation, examples
└── assets/          # Optional: Data files, configs
```

**Body Format:** Free-form markdown instructions that tell the AI agent how to use the skill.

### Claude Code (Native AgentSkills)

**Overview:** Claude Code uses AgentSkills natively without extensions.

**Location:** `.claude/skills/<name>/SKILL.md`

**Frontmatter:** Standard AgentSkills format (only `name` and `description` required)

**Working Directory:** Repository root  
**Path Resolution:** Relative to repository root  
**Tool Access:** Standard Claude tools (read, write, exec, etc.)

**Example:**
```yaml
---
name: typedb-notebook
description: "Store and retrieve knowledge in the Alhazen TypeDB knowledge graph"
---

# TypeDB Notebook Skill

Use this skill to store and retrieve knowledge...

## Usage

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py query-notes --subject "paper-xyz"
```
```

**Key Features:**
- No special configuration needed
- Works directly with repository files
- Inherits all Claude Code capabilities
- Portable across any AgentSkills-compatible system

### OpenClaw (AgentSkills-Compatible with Extensions)

**Overview:** OpenClaw supports AgentSkills with additional metadata for enhanced functionality.

**Location:** `~/.openclaw/workspace/skills/<name>/SKILL.md` (or symlinked)

**Frontmatter:** Standard AgentSkills + `metadata.openclaw` extensions:

```yaml
---
name: typedb-notebook
description: "Store and retrieve knowledge in TypeDB"
metadata:
  openclaw:
    requires:
      bins: ["uv", "docker"]           # Binary dependencies
      env: ["TYPEDB_HOST", "TYPEDB_PORT"] # Required env vars
    optional_env: ["ALHAZEN_CACHE_DIR"] # Optional env vars
    primaryEnv: "TYPEDB_API_KEY"        # Primary API key env var
    os: ["linux", "darwin"]            # Platform filter
    install:                            # Installation specs
      apt: ["package-name"]
      brew: ["formula-name"]
      python: ["requirement"]
---
```

**Working Directory:** OpenClaw workspace (NOT repo root)  
**Path Resolution:** `{baseDir}` resolves to skill directory  
**Environment Injection:** Via `skills.entries.<name>.env` in openclaw.json config

**Configuration Integration:**
OpenClaw can inject environment variables per skill:

```json
{
  "skills": {
    "entries": {
      "typedb-notebook": {
        "env": {
          "TYPEDB_HOST": "localhost",
          "TYPEDB_PORT": "1729",
          "ALHAZEN_PROJECT_ROOT": "/Users/username/skillful-alhazen"
        }
      }
    }
  }
}
```

### Goose (Block) - Skills Platform Extension

**Overview:** Goose primarily uses MCP (Model Context Protocol) servers, but has a Skills platform extension that can load AgentSkills-format files.

**Location:** Configured in `~/.config/goose/profiles.yaml`

**Integration:**
```yaml
# ~/.config/goose/profiles.yaml
default:
  providers:
    - provider: skills
      requires: ["~/.openclaw/workspace/skills"]
```

**Capabilities:**
- Loads AgentSkills SKILL.md files
- Provides them as callable functions to Goose sessions
- Inherits skill dependencies and requirements
- Bridges AgentSkills → MCP protocol

## Portability Strategy

### Gold Standard: YAML Manifests

This repository maintains skill metadata in `local_resources/skills/*.yaml` files as the **source of truth**. These manifests contain portable metadata that can generate framework-specific configurations.

**Example:** `local_resources/skills/typedb-notebook.yaml`
```yaml
name: typedb-notebook
description: "Store and retrieve knowledge in the Alhazen TypeDB knowledge graph"
license: Apache-2.0
compatibility: "Requires uv, docker, and TypeDB 2.x running"

# Core files
script: typedb_notebook.py
schema: alhazen_notebook.tql

# Dependencies
requires:
  bins: [uv, docker]
  env: [TYPEDB_HOST, TYPEDB_PORT, TYPEDB_DATABASE]
  optional_env: [ALHAZEN_CACHE_DIR]

# TypeDB specific
namespaces:
  - scilit.tql
```

### Deployment Targets

The Makefile provides targets to deploy skills to different frameworks:

1. **`make deploy-claude`** - Copy to `.claude/skills/` (Claude Code)
2. **`make deploy-openclaw`** - Symlink + configure for OpenClaw  
3. **`make deploy-goose`** - Generate MCP configuration (future)

### Framework-Specific Adaptations

**Claude Code:**
- Uses YAML manifest to generate standard AgentSkills SKILL.md
- Paths relative to repository root
- No additional configuration needed

**OpenClaw:**
- Creates symlinks to avoid duplication
- Generates `metadata.openclaw` section from YAML `requires`
- Injects `ALHAZEN_PROJECT_ROOT` environment variable
- Handles path resolution differences

**Goose/MCP:**
- Potential future integration via Skills platform
- Could generate MCP server configurations
- May require wrapper scripts for complex dependencies

### Path Resolution Strategy

Different frameworks have different working directory expectations:

| Framework | Working Dir | Path Resolution |
|-----------|-------------|-----------------|
| Claude Code | Repo root | `uv run python .claude/skills/name/script.py` |
| OpenClaw | Workspace | `uv run python {baseDir}/script.py` where `{baseDir}` = skill dir |

**Solution:** Environment variable injection. OpenClaw skills get `ALHAZEN_PROJECT_ROOT` pointing to the repository, allowing them to reference repo-relative paths.

### Skill Synchronization

The `make skills-sync` target keeps deployed skills in sync with the gold standard:

1. Reads `local_resources/skills/*.yaml` manifests
2. Updates frontmatter in deployed `SKILL.md` files
3. Preserves skill body content (the markdown instructions)
4. Updates only the metadata portions

## Best Practices

### Skill Development

1. **Start with AgentSkills standard** - Ensures maximum compatibility
2. **Use environment variables** for configuration instead of hardcoded paths
3. **Document dependencies clearly** in the `compatibility` field
4. **Keep skills focused** - One clear capability per skill
5. **Include working examples** in the skill documentation

### Framework Extensions

When adding framework-specific features:

1. **Extend, don't replace** - Add to `metadata` sections, don't change core structure
2. **Graceful degradation** - Skills should work without extensions on other platforms
3. **Document clearly** - Explain what functionality requires specific frameworks

### Deployment Management

1. **Use the Makefile** - Don't manually copy skills between locations
2. **Update manifests first** - The YAML files are the source of truth
3. **Sync regularly** - Run `make skills-sync` after updating manifests
4. **Test across frameworks** - Verify skills work in target environments

## Migration Guide

### From Framework-Specific to Portable

1. **Extract metadata** - Move configuration to YAML manifest
2. **Use environment variables** - Replace hardcoded paths
3. **Standard frontmatter** - Ensure SKILL.md follows AgentSkills format
4. **Test deployment** - Verify skill works via Makefile targets

### Adding New Framework Support

1. **Study framework requirements** - Understand skill format expectations
2. **Extend YAML schema** - Add framework-specific metadata if needed  
3. **Add Makefile target** - Create deployment automation
4. **Update sync logic** - Ensure `skills-sync` handles new format
5. **Document differences** - Update this README with new framework section

## Troubleshooting

### Common Issues

**Skill not found:**
- Check deployment: `make deploy-<framework>`
- Verify symlinks (OpenClaw): `ls -la ~/.openclaw/workspace/skills/`
- Check permissions on skill files

**Dependencies missing:**
- Review `requires.bins` in skill manifest
- Install dependencies: `make setup` or manual installation
- Check environment variables are set correctly

**Path resolution errors:**
- Ensure `ALHAZEN_PROJECT_ROOT` is set (OpenClaw)
- Check working directory assumptions in skill scripts
- Use absolute paths from environment variables

**Configuration not applied:**
- Run `make deploy-<framework>` to apply config changes
- Check OpenClaw config: `cat ~/.openclaw/openclaw.json | jq .skills`
- Restart framework after configuration changes

### Validation

Use the validation target to check skill integrity:

```bash
make skills-validate
```

This checks:
- YAML manifest syntax
- Required fields present
- SKILL.md frontmatter matches manifest
- Dependencies are available

## Future Directions

### Enhanced Portability

- **Skill marketplace** - Shared repository of portable skills
- **Automatic testing** - CI/CD for multi-framework validation
- **Dependency management** - Automated installation of skill requirements
- **Version management** - Semantic versioning for skill updates

### Framework Integration

- **MCP bridge** - Full Goose/MCP integration
- **VS Code extension** - Skills available in VS Code AI features
- **API standardization** - Common interface for skill execution
- **Performance optimization** - Caching and optimization across frameworks

This portability system ensures that skills developed for one framework can be easily deployed and used across multiple AI agent platforms, reducing duplication of effort and maximizing the value of skill development investments.