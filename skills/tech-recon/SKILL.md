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

## Command Output Pattern

`uv run` always emits a `VIRTUAL_ENV` warning to stderr. **Never use `2>&1` when piping to a JSON parser** — the warning merges into stdout and breaks JSON parsing. Always redirect stderr away first:

```bash
# CORRECT — stderr suppressed before JSON parse
uv run python .claude/skills/tech-recon/tech_recon.py <cmd> [args] \
  2>/dev/null | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin),indent=2))"

# WRONG — VIRTUAL_ENV warning corrupts the JSON stream
uv run python .claude/skills/tech-recon/tech_recon.py <cmd> [args] \
  2>&1 | python3 -c "import json,sys; ..."
```

When a command fails (wrong args), stdout is empty → JSON parse throws `JSONDecodeError: Expecting value`. To debug, drop the JSON pipe and use `2>&1 | head -5` to see the raw error.

## Command Quick Reference

Use exact argument names — wrong names cause silent failures.

| Command | Required args |
|---------|--------------|
| `show-investigation` | `--id ID` |
| `list-investigations` | _(none)_ |
| `update-investigation` | `--id ID [--status S] [--goal G] [--criteria C]` |
| `advance-iteration` | `--investigation INVESTIGATION` |
| `delete-investigation` | `--id ID --force` |
| `list-systems` | `--investigation INVESTIGATION [--status {candidate,confirmed,ingested,analyzed,excluded,all}]` |
| `show-system` | `--id ID` |
| `add-system` | `--investigation INVESTIGATION --name N --url U [--github-url U] [--description D]` |
| `approve-system` | `--id ID` |
| `delete-system` | `--id ID --force` |
| `ingest-page` | `--url URL --system SYSTEM` |
| `ingest-repo` | `--url URL --system SYSTEM` |
| `ingest-docs` | `--url URL --system SYSTEM [--max-pages N]` |
| `ingest-pdf` | `--url URL --system SYSTEM` |
| `list-artifacts` | `--system SYSTEM [--type {webpage,github-repo,pdf,source-file,file-tree}]` |
| `show-artifact` | `--id ID` |
| `cache-stats` | _(none)_ |
| `write-note` | `--subject-id SUBJECT_ID --topic T --format {markdown,yaml,json} --content C [--tags T] [--iteration N] [--replace]` _(subject = system or investigation ID)_ |
| `list-notes` | `--subject-id SUBJECT_ID [--topic T]`  _(subject = system or investigation ID)_ |
| `show-note` | `--id ID` |
| `delete-note` | `--id ID` |
| `list-analyses` | `--investigation INVESTIGATION` |
| `show-analysis` | `--id ID` |
| `run-analysis` | `--id ID` |
| `add-analysis` | `--investigation INVESTIGATION --title T --description D --plot-code CODE --query QUERY [--analysis-type {plot,table,prose}]` |
| `add-pipeline` | `--investigation INVESTIGATION --title T --pipeline-script "code or @path" --pipeline-config JSON [--analysis-type pipeline-plot]` |
| `run-pipeline` | `--id ID` |
| `plan-analyses` | `--investigation INVESTIGATION` |
| `compile-report` | `--investigation INVESTIGATION [--force]` |
| `evaluate-completion` | `--investigation INVESTIGATION` |
| `explore-repo` | `--system SYSTEM` or `--investigation INVESTIGATION` |
| `extract-fragments` | `--artifact ARTIFACT [--max-fragments N]` |
