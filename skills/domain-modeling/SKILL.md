---
name: domain-modeling
description: Design and implement domain-specific knowledge skills using the curation pattern
---

# Domain Modeling Skill

Use this skill when designing a **new knowledge domain** for the Alhazen notebook system. This is a meta-skill that teaches how to build domain-specific skills following the curation pattern.

**When to use:** "design a new domain", "create a new skill", "model a new domain", "build a knowledge skill for", "add a new skill for tracking", "how do I create a skill"

## The Curation Pattern (6 phases)

All domain skills follow: **TASK DEFINITION → FORAGING → INGESTION → SENSEMAKING → ANALYSIS → REPORTING**

- **Task Definition (Phase 0)**: Define the goal or decision the curation is meant to serve (natural language, stored as a `task` entity)
- **Foraging**: Discover sources (URLs, APIs, databases)
- **Ingestion**: Capture raw content with provenance (script responsibility — no parsing)
- **Sensemaking**: Claude reads artifacts and creates structured understanding (entities, fragments, notes)
- **Analysis**: Reason across many notes over time to generate insights
- **Reporting**: Dashboard views for human decision-making

## Quick Start (Design a New Domain)

```bash
# Copy the template to get started
cp -r skills/_template skills/<your-domain>
# Then implement SKILL.md, skill.yaml, <name>.py, schema.tql
# Add to skills-registry.yaml and run make build-skills
```

## Quick Start (Design Process Tracking)

```bash
# Create a tracking project for a domain
uv run python .claude/skills/domain-modeling/domain_modeling.py \
    init-domain --name "My Domain" --skill my-skill

# Set the natural-language task the skill performs (Phase 0)
uv run python .claude/skills/domain-modeling/domain_modeling.py \
    set-task --domain-id dm-domain-XXXX \
    --task "Ingest FDA 510k clearances and query clearance history"

# Snapshot the full skill directory (schema + scripts + prompts + tests)
uv run python .claude/skills/domain-modeling/domain_modeling.py \
    snapshot-skill --domain-id dm-domain-XXXX \
    --skill-dir local_skills/my-skill/ --repo-dir .

# Record a design decision and its rationale
uv run python .claude/skills/domain-modeling/domain_modeling.py \
    add-decision --domain-id dm-domain-XXXX --type entity \
    --summary "Use collection as base for domain grouping"

# Export annotated Markdown design changelog
uv run python .claude/skills/domain-modeling/domain_modeling.py \
    export-design --domain-id dm-domain-XXXX
```

**Before executing commands, read `USAGE.md` in this directory for the complete phase breakdown, design tracking workflow, schema templates, and documentation checklist.**
