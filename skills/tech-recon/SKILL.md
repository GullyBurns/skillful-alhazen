---
name: tech-recon
description: Goal-driven technology investigation — interview, discover, ingest, analyze, and visualize competing systems against user-defined success criteria
triggers:
  - investigate [technology/framework/library]
  - compare [tools/systems]
  - tech recon
  - research alternatives to X
  - evaluate [tool] for [use case]
  - what are the options for [problem]
prerequisites:
  - TypeDB running: make db-start
  - make build-skills
---

# Tech-Recon Skill

Systematic, goal-driven technology investigation. Interview the user to define success criteria → discover candidate systems → ingest sources → write structured notes → plan + implement Observable Plot visualizations → dashboard.

## Quick Start

When a user asks to investigate technology, run the **8-question interview** (one question per turn — see USAGE.md §2 for exact questions). Then:

```bash
uv run python .claude/skills/tech-recon/tech_recon.py start-investigation \
    --name "Graph DB alternatives" \
    --goal "Choose a graph DB for knowledge graph + agent memory" \
    --success-criteria "Schema inference, Python API, active community, open source"
```

## Investigation Phases

1. **Interview** — conversational, defines goal + success criteria
2. **Discovery** — search for candidates (web-search + GitHub + HF), user approves
3. **Ingestion** — parallel subagents per system (see USAGE.md §8 for prompt)
4. **Sensemaking** — parallel subagents per system (see USAGE.md §8 for prompt)
5. **Viz Planning** — propose plots mapped to success criteria, user approves
6. **Analysis** — Observable Plot + TypeQL per approved plot
7. **Dashboard** — `http://localhost:3001/tech-recon`

**Read USAGE.md before executing any commands.**
