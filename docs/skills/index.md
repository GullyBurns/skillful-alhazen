# Skills Reference

Skills are modular domain capabilities for Skillful-Alhazen. Each skill provides a focused set of operations for a specific domain.

## Available Skills

| Skill | Description | Key Commands |
|-------|-------------|--------------|
| [/jobhunt](jobhunt.md) | Job application tracking with fit analysis | Add posting, analyze fit, track status |
| [/epmc-search](epmc-search.md) | Europe PMC literature search | Search papers, count results, add to collections |
| [/typedb-notebook](typedb-notebook.md) | Core knowledge operations | Remember, recall, organize |
| [/domain-modeling](domain-modeling.md) | Design new domain skills | Create schemas, write SKILL.md |

## How Skills Work

Each skill consists of:

```
.claude/skills/<skill-name>/
├── SKILL.md     # Instructions for Claude (what the skill does, how to use it)
└── *.py         # Python scripts for TypeDB transactions
```

### SKILL.md

Tells Claude:
- When to use this skill (trigger phrases)
- What commands are available
- How to interpret results
- Domain-specific concepts and workflows

### Python Scripts

Handle the mechanics:
- API calls (pagination, rate limits)
- TypeDB transactions
- Data transformations
- Bulk operations

## The Curation Pattern

All skills follow the same workflow:

```
FORAGING → INGESTION → SENSEMAKING → ANALYSIS → REPORTING
```

| Stage | Script Handles | Claude Handles |
|-------|---------------|----------------|
| Foraging | - | Identifying sources |
| Ingestion | Fetching, storing raw | - |
| Sensemaking | - | Reading, extracting, noting |
| Analysis | Queries, aggregation | Synthesis, recommendations |
| Reporting | Dashboard data | Narrative summaries |

## Creating New Skills

Use the [/domain-modeling](domain-modeling.md) skill to design new domains:

```
You: I want to track grant applications I'm writing

Claude: [Guides you through entity design, schema creation, SKILL.md writing]
```

See the [domain-modeling documentation](domain-modeling.md) for details.

## Skill Independence

Skills are designed to be:

- **Modular** - Each skill is self-contained
- **Composable** - Skills can reference each other's entities
- **Extensible** - Add new skills without modifying existing ones

The core `/typedb-notebook` skill provides the foundation that other skills build upon.
