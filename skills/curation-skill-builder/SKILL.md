---
name: curation-skill-builder
description: Design and implement TypeDB-backed curation skills using the Skillful Alhazen methodology
---

# Curation Skill Builder

Use this skill when designing and building a **new TypeDB-backed curation skill** for the Alhazen notebook system. This is a meta-skill that applies domain modeling to create domain-specific skills following the Skillful Alhazen curation pattern.

**When to use:** "build a curation notebook skill", "create a new Alhazen skill", "design a TypeDB-backed skill", "model a new domain for the notebook", "add a new skill for tracking X in the knowledge graph", "design a skill using the Skillful Alhazen methodology"

**Use the official `skill-creator` plugin instead** for all other skill development — when you want to build, evaluate, or improve a Claude Code skill that does NOT use TypeDB or the Alhazen curation notebook methodology.

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
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    init-domain --name "My Domain" --skill my-skill

# Set the natural-language task the skill performs (Phase 0)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    set-task --domain-id dm-domain-XXXX \
    --task "Ingest FDA 510k clearances and query clearance history"

# Snapshot the full skill directory (schema + scripts + prompts + tests)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    snapshot-skill --domain-id dm-domain-XXXX \
    --skill-dir local_skills/my-skill/ --repo-dir .

# Record a design decision and its rationale
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    add-decision --domain-id dm-domain-XXXX --type entity \
    --summary "Use collection as base for domain grouping"

# Export annotated Markdown design changelog
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    export-design --domain-id dm-domain-XXXX
```

## 5-Phase System Design Workflow

Use the structured phase workflow to build a TypeDB record of the full design process for a skill. Each phase captures what the system is for, what data it models, where data comes from, what skills ingest it, and what skills analyze it.

| Phase | What it captures | Key command |
|-------|-----------------|-------------|
| 1 -- Goal | System purpose + evaluation criteria | `define-goal`, `add-evaluation` |
| 2 -- Entity Schema | TypeDB types the domain defines | `add-entity-schema` |
| 3 -- Source Schema | External data sources + artifact types | `add-source-schema` |
| 4 -- Derivation Skills | Ingestion functions (artifact -> entity) | `add-derivation-skill` |
| 5 -- Analysis Skills | Query functions (entity -> insight) | `add-analysis-skill` |

Spec notes attach to phase entities via `add-phase-spec`. Design gaps discovered during implementation are filed as GitHub Issues with `gh issue create` (see USAGE.md "Improvement Loop").
Export the full structured report with `export-design-phases`.

**Read USAGE.md section "5-Phase System Design Workflow" before using these commands.**

## Namespace Rules

Every skill with a `schema.tql` must follow these namespace conventions:

1. **Declare a namespace prefix** in `skill.yaml` under `schema.namespace` (e.g., `jobhunt`, `tech-recon`, `scilit`)
2. **Use lowercase hyphenated tokens** — no dots, underscores, or camelCase
3. **All types must start with the prefix** — `jobhunt-position`, `jobhunt-company`, etc. Exception: skills that only extend core types use `namespace: null`
4. **No prefix reuse** — each namespace prefix belongs to exactly one skill
5. **Cross-namespace references require `depends_on`** — if your schema adds a `plays` clause to a type from another skill, declare that skill in `schema.depends_on`
6. **Core types are always available** — `domain-thing`, `collection`, `note`, `artifact`, `fragment`, `person`, etc. need no `depends_on`

**Validate a skill's namespace compliance:**
```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py validate-namespace \
  --skill-dir local_skills/<skill-name> 2>/dev/null
```

**Audit all namespaces in the running database:**
```bash
make db-audit
```

## Command Output Pattern

`uv run` emits a `VIRTUAL_ENV` warning to stderr. Always use `2>/dev/null` when piping output to a JSON parser — never `2>&1`, which merges the warning into stdout and breaks JSON parsing.

**Before executing commands, read `USAGE.md` in this directory for the complete phase breakdown, design tracking workflow, schema templates, and documentation checklist.**
