---
name: domain-modeling
description: Design and implement domain-specific knowledge skills using the curation pattern
---

# Domain Modeling Skill

Use this skill when designing a **new knowledge domain** for the Alhazen notebook system. This is a meta-skill that teaches how to build domain-specific skills following the curation pattern.

**When to use:** "design a new domain", "create a new skill", "model a new domain", "build a knowledge skill for", "add a new skill for tracking", "how do I create a skill"

## The Curation Pattern (5 phases)

All domain skills follow: **FORAGING → INGESTION → SENSEMAKING → ANALYSIS → REPORTING**

- **Foraging**: Discover sources (URLs, APIs, databases)
- **Ingestion**: Capture raw content with provenance (script responsibility — no parsing)
- **Sensemaking**: Claude reads artifacts and creates structured understanding (entities, fragments, notes)
- **Analysis**: Reason across many notes over time to generate insights
- **Reporting**: Dashboard views for human decision-making

## Quick Start

```bash
# Copy the template to get started
cp -r skills/_template skills/<your-domain>
# Then implement SKILL.md, skill.yaml, <name>.py, schema.tql
# Add to skills-registry.yaml and run make build-skills
```

**Before designing your domain, read `USAGE.md` in this directory for the complete phase breakdown, schema templates, examples, and documentation checklist.**
