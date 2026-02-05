# Skillful-Alhazen Documentation

**A TypeDB-powered scientific knowledge notebook, built on Claude Code**

> *"The duty of the man who investigates the writings of scientists, if learning the truth is his goal, is to make himself an enemy of all that he reads, and, applying his mind to the core and margins of its content, attack it from every side."*
>
> — Ibn al-Haytham (Alhazen), 965-1039 AD

## What is Alhazen?

Alhazen is a **curation system** that helps researchers make sense of information—not just store it. You interact with Claude through natural language, and Claude handles all the complexity of storing, querying, and reasoning over your knowledge graph.

The system combines:
- **Claude Code** as the agentic interface—you talk to Claude, Claude does the work
- **TypeDB** as the knowledge graph backend (you never touch it directly)
- **Skills** for domain-specific workflows (literature review, job hunting, etc.)

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Installation and first steps |
| [Design Concepts](concepts.md) | Architecture and design principles |
| [History](history.md) | The story of Ibn al-Haytham and project origins |

## Available Skills

| Skill | Description |
|-------|-------------|
| [/jobhunt](skills/jobhunt.md) | Track job applications with fit analysis and skill gap identification |
| [/epmc-search](skills/epmc-search.md) | Search Europe PMC for scientific papers |
| [/typedb-notebook](skills/typedb-notebook.md) | Core knowledge operations (remember, recall, organize) |
| [/domain-modeling](skills/domain-modeling.md) | Meta-skill for designing new domain skills |

## Quick Example

```
You: I found an interesting job posting at https://example.com/senior-ml-engineer

Claude: I'll ingest and analyze this posting...

[Fetches the job description]
[Extracts company info, requirements, qualifications]
[Compares against your skill profile]
[Creates fit analysis with gap identification]

## Analysis: Senior ML Engineer at ExampleCorp

**Your Fit: 78%**

| Requirement | Level | You | Match |
|-------------|-------|-----|-------|
| Python | Required | Strong | ✓ |
| PyTorch | Required | Some | △ |
| Distributed Systems | Required | None | ✗ |

**Key Gap:** Distributed systems is required but you have no experience.
I've added learning resources for this skill.

Want me to set a priority level for this position?
```

## Links

- **Repository**: [github.com/GullyBurns/skillful-alhazen](https://github.com/GullyBurns/skillful-alhazen)
- **Original CZI Project**: [github.com/chanzuckerberg/alhazen](https://github.com/chanzuckerberg/alhazen)
