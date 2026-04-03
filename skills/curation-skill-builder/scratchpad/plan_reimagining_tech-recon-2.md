# tech-recon Skill Rebuild Plan

## Context

The existing `techrecon` skill is broken in its foundations. The pre-defined entity types (component, concept, data-model, design-decision, benchmark, workflow) impose a fixed analytical frame before we understand what matters for a given investigation. The dashboard shows structure without insight. Sensemaking is terse and disconnected. There is no connection between what the investigator is trying to decide and what the dashboard shows.

This plan is a complete reimagining as `tech-recon` — a new core skill at `skills/tech-recon/` — with four architectural innovations:

1. **Goal-first**: Every investigation starts with a structured interview that defines success criteria. The dashboard orients everything around that goal.
2. **Exhaustive ingestion**: All relevant material is captured to `~/.alhazen/cache/` with TypeDB tracking provenance. Claude's native file-reading tools do the heavy lifting.
3. **Open-ended sensemaking**: Notes are free-form markdown/YAML/JSON. Claude decides the structure. TypeDB stores provenance; content is in the note.
4. **Dynamic analysis**: Claude writes Observable Plot JS + TypeQL queries tailored to each investigation's goals. These are stored as `tech-recon-analysis` artifacts and executed on demand in the dashboard.

Process notes tracking learnings for skill-builder feedback: `skills/skill-builder/scratchpad/2026-04-01_tech_recon_rebuild.md`

---

## Architecture

### Phases of an Investigation

```
INTERVIEW → DISCOVERY → INGESTION → SENSEMAKING → VIZ PLANNING → ANALYSIS → DASHBOARD
```

| Phase | What happens | Output stored in |
|-------|-------------|-----------------|
| Interview | ~8-question conversational session | `tech-recon-investigation` with goal doc |
| Discovery | Web/GitHub/HF search for related systems; user approves candidates | `tech-recon-system` (status: candidate) |
| Ingestion | Fetch homepage, repo, docs, papers → cache | `tech-recon-artifact` with cache-path |
| Sensemaking | Claude reads cached files, writes structured notes | `tech-recon-note` (markdown/YAML/JSON) |
| Viz Planning | Claude reviews goal + notes, proposes visualization set; user approves | `tech-recon-note` (topic: viz-plan, format: yaml) |
| Analysis | Claude implements each approved viz as Observable Plot + TypeQL | `tech-recon-analysis` artifacts (one per plot) |
| Dashboard | Show goal, systems, notes, render each analysis on demand | Next.js UI |

---

## Discovery Workflow

Discovery runs **after the interview** and **before ingestion**. It finds systems similar to those named in the interview and presents them as candidates. The user approves which to include.

### Discovery sources (searched in order)
1. **SearXNG web search** (`web-search` skill) — query = `"alternatives to X" OR "similar to X" site:github.com OR site:huggingface.co`, and `"best Y tools 2024 2025"` (where Y is the domain from interview)
2. **GitHub search API** — search by topic tags inferred from interview (e.g., `topic:graph-database`, `topic:knowledge-graph`)
3. **Hugging Face Hub** (`mcp__claude_ai_Hugging_Face__hub_repo_search`) — for ML/AI-adjacent systems
4. **arXiv/paper search** — find survey papers that list and compare systems in the domain

### Discovery process (conversational, in Claude Code session)
1. Claude runs searches using the above sources
2. Deduplicates results with already-known systems
3. Presents a ranked list of candidates with: name, URL, brief description, stars/downloads if available
4. User approves/rejects each (or approves all / rejects all)
5. Claude calls `add-system --status candidate` for each approved system

### Discovery commands added to tech_recon.py
```
discover-systems --investigation <id>   # Claude-driven: runs searches, returns candidates JSON
add-system --investigation <id> \
  --name <n> --url <u> \
  --status <candidate|confirmed>        # confirmed = user-approved for ingestion
approve-system --id <id>                # promote candidate → confirmed
list-systems --investigation <id> \
  --status <candidate|confirmed|all>
```

### system status field
Add `status` attribute to `tech-recon-system`:
- `candidate` — discovered, pending user approval
- `confirmed` — approved for ingestion
- `ingested` — artifacts have been fetched
- `analyzed` — notes written
- `excluded` — explicitly rejected

---

## TypeDB Schema

### Core entities

```typeql
# Collection type — one per investigation
entity tech-recon-investigation sub collection,
    owns status,            # 'scoping' | 'ingesting' | 'sensemaking' | 'analysis' | 'done'
    owns goal-description,  # what decision/question this investigation serves
    owns success-criteria;  # what the dashboard must let the user understand

# Domain object — one per surveyed system/tool/framework
entity tech-recon-system sub domain-thing,
    owns url,
    owns github-url,
    owns language,
    owns license,
    owns star-count,
    owns status;    # 'candidate' | 'confirmed' | 'ingested' | 'analyzed' | 'excluded'

# Raw captured content — page, PDF, repo, source file, file tree
entity tech-recon-artifact sub artifact,
    owns artifact-type,   # 'webpage' | 'github-repo' | 'pdf' | 'source-file' | 'file-tree'
    owns url;
    # inherits: content, cache-path, format from artifact base

# Free-form sensemaking content
entity tech-recon-note sub note,
    owns topic,           # free text label e.g. 'capability-matrix', 'performance'
    owns tag;             # multi-valued, for filtering and search
    # inherits: content, format ('markdown'|'yaml'|'json') from note base

# Analysis artifact — Observable Plot code + TypeQL query
entity tech-recon-analysis sub artifact,
    owns title,
    owns analysis-type,   # 'plot' | 'table' | 'prose'
    owns plot-code,       # Observable Plot JavaScript
    owns query;           # TypeQL query to hydrate the visualization
    # inherits: content (prose description), format from artifact base
```

### Attributes (new)
```typeql
attribute goal-description, value string;
attribute success-criteria, value string;
attribute artifact-type, value string;
attribute topic, value string;
attribute plot-code, value string;
attribute query, value string;
attribute analysis-type, value string;
attribute github-url, value string;
attribute star-count, value integer;
```

### Relations
```typeql
# System participates in investigation
relation investigated-in,
    relates system,
    relates investigation;

# Artifact was sourced from a system (or investigation-level if global)
relation sourced-from,
    relates artifact,
    relates source;

# Analysis belongs to an investigation
relation analysis-of,
    relates analysis,
    relates investigation;
```

Re-use existing `aboutness(note: $n, subject: $e)` to attach notes to systems/investigations/artifacts.

---

## Interview Workflow (SKILL.md section)

The interview is a **Claude Code conversational session** — not a CLI command. SKILL.md triggers Claude to conduct it when the user says "start a tech-recon investigation" or similar. The Python script only handles storage.

**Interview questions Claude asks (one at a time):**

1. What domain/problem space are you investigating? (e.g., "graph databases for knowledge graphs")
2. What decision will this investigation inform? (e.g., "choose a TypeDB alternative", "evaluate MCP frameworks")
3. What would make one system clearly better than another for your use case?
4. What are your hard constraints? (license, language, hosting, scale)
5. Who are the candidate systems you already know about?
6. Are there any systems you've already ruled out? Why?
7. What does the output dashboard need to let you understand? (comparisons, tradeoffs, gaps)
8. Any related papers or prior art to include?

After the interview, Claude synthesizes a goal document and calls:
```bash
uv run python tech_recon.py start-investigation \
  --name "..." \
  --goal "..." \
  --success-criteria "..." \
  --systems "System A,System B,System C"
```

The `start-investigation` command creates the `tech-recon-investigation` and initial `tech-recon-system` entities in TypeDB. The interview itself lives entirely in the Claude Code session / SKILL.md prompt.

---

## Ingestion Commands (tech_recon.py)

```
start-investigation          # run interview → create investigation
list-investigations
show-investigation --id <id>

add-system --name <n> --url <u> --investigation <id> [--status confirmed]
discover-systems --investigation <id>   # returns JSON list of candidates
approve-system --id <id>                # promote candidate → confirmed
list-systems --investigation <id> [--status candidate|confirmed|all]
show-system --id <id>

ingest-page --url <u> --system <id>        # fetch HTML → cache
ingest-repo --url <u> --system <id>        # clone/fetch repo → cache + file tree
ingest-pdf --url <u> --system <id>         # fetch PDF → cache
ingest-docs --url <u> --system <id>        # crawl doc site → cache pages

write-note --system <id> --topic <t> --format <f> --content <c>
list-notes --system <id>
show-note --id <id>

add-analysis --investigation <id> --title <t> --plot-code <js> --query <tql>
list-analyses --investigation <id>
show-analysis --id <id>

cache-stats
```

---

## Visualization Planning Workflow

Visualization planning is a **conversational Claude Code step** between sensemaking and analysis. It answers: *given our goal and what we've learned, what plots will actually answer the questions that matter?*

### How it works

1. Claude reads the investigation's `goal-description`, `success-criteria`, and all notes
2. Claude proposes a **visualization plan** — a YAML document listing proposed plots:

```yaml
# Example viz plan stored as tech-recon-note
# topic: viz-plan, format: yaml
investigation: "Graph database alternatives to TypeDB"
goal_summary: "Choose a graph DB for knowledge graph + agent memory use case"
proposed_analyses:
  - id: feature-comparison
    title: "Feature Capability Matrix"
    purpose: "Show which systems support schema inference, polymorphism, native graph, streaming"
    type: heatmap
    data_source: capability-matrix notes (YAML)
    observable_plot_type: Plot.cell

  - id: activity-timeseries
    title: "GitHub Activity Over Time"
    purpose: "Identify which systems are actively maintained vs. stagnating"
    type: time-series
    data_source: GitHub API (stars over time, commit frequency)
    observable_plot_type: Plot.lineY

  - id: similarity-cluster
    title: "Semantic Similarity Clustering"
    purpose: "Cluster systems by conceptual similarity using note embeddings"
    type: scatter-umap
    data_source: note embeddings (Qdrant)
    observable_plot_type: Plot.dot

  - id: tradeoff-radar
    title: "Multi-Criteria Tradeoff Radar"
    purpose: "Compare systems on performance, maturity, integration ease, community"
    type: radar
    data_source: assessment notes (YAML scores)
    observable_plot_type: Plot.line (polar)
```

3. User reviews and approves/modifies/rejects each proposed plot
4. Claude stores the approved plan as a `tech-recon-note` with `topic: viz-plan`
5. Claude implements each approved entry as a `tech-recon-analysis` artifact

### Key principle: plots answer goal questions
Each proposed visualization must map to a specific question from the `success-criteria`. If a visualization doesn't answer a question in the goal document, it shouldn't be in the plan.

### Plot types supported (Observable Plot)
| Type | Use case | Plot API |
|------|----------|----------|
| Bar / sorted bar | Ranking comparison (stars, downloads) | `Plot.barX`, `Plot.barY` |
| Heatmap / cell | Feature matrix across systems | `Plot.cell` |
| Time series | Activity / trend over time | `Plot.lineY` |
| Dot scatter | Tradeoff space (2 axes) | `Plot.dot` |
| UMAP scatter | Semantic clustering (from embeddings) | `Plot.dot` with precomputed coords |
| Radar / spider | Multi-criteria comparison | `Plot.line` (polar) |
| Table | Structured comparison | custom HTML table via Plot |

### Commands added
```
plan-analyses --investigation <id>   # Claude reviews notes + goal, proposes viz plan
list-analyses --investigation <id>   # show all analysis artifacts
```

---

## Dashboard Architecture

### Pages
```
/tech-recon                                  # investigation list
/tech-recon/investigation/[id]               # goal + systems grid + analysis tabs
/tech-recon/investigation/[id]/analysis/[id] # render single Observable Plot analysis
/tech-recon/system/[id]                      # system detail: artifacts + notes
/tech-recon/artifact/[id]                    # raw artifact viewer (markdown/html/text)
```

### Investigation Overview Page (`/investigation/[id]`)
- **Goal section** (always visible): goal-description + success-criteria (rendered markdown)
- **Systems grid**: card per system with name, language, license, stars, status chip
- **Stage indicator**: scoping → ingesting → sensemaking → viz-planning → analysis → done
- **Analysis tab**: grid of analysis cards — each shows title, purpose, plot type badge, "Run" button. Running executes its TypeQL query → renders Observable Plot inline. Multiple plots on the same tab, each independently runnable.
- **Viz plan tab** (if viz-plan note exists): shows the YAML viz-plan note rendered with purpose and status of each proposed plot
- **Notes tab**: all notes collapsible by topic, with format badges (md/yaml/json); viz-plan note excluded (shown in its own tab)

### System Detail Page (`/system/[id]`)
- System metadata (url, github, language, stars, license)
- **Artifacts** section: collapsible list by artifact-type
- **Notes** section: collapsible by topic, renders markdown inline, syntax-highlights YAML/JSON
- Link back to investigation

### Analysis Execution (key new pattern)
The dashboard API route `/api/tech-recon/analysis/[id]/run`:
1. Fetches `plot-code` and `query` from TypeDB for the analysis artifact
2. Executes the TypeQL query → returns JSON data
3. Returns `{ plotCode, data }` to the frontend
4. Frontend executes the plot code with the data via Observable Plot in a sandboxed `<div>`

```typescript
// Simplified execution pattern
const result = await fetch(`/api/tech-recon/analysis/${id}/run`);
const { plotCode, data } = await result.json();
// Execute: new Function('Plot', 'data', plotCode)(Plot, data)
```

---

## File Structure

```
skills/tech-recon/
  SKILL.md           # ~30 lines: triggers, interview quick-start, USAGE.md pointer
  USAGE.md           # Full command reference + sensemaking workflows
  skill.yaml         # Metadata
  tech_recon.py      # CLI entry point (all commands above)
  schema.tql         # TypeDB schema (entities/relations/attributes above)
  dashboard/
    lib.ts           # runTechRecon() CLI wrapper
    components/
      investigation-card.tsx
      systems-grid.tsx
      notes-list.tsx
      analysis-runner.tsx    # Observable Plot executor
      stage-indicator.tsx
      artifact-viewer.tsx
    pages/
      tech-recon/
        page.tsx              # investigation list
        investigation/[id]/
          page.tsx            # overview + analyses + notes
        system/[id]/
          page.tsx            # system detail
        artifact/[id]/
          page.tsx            # raw artifact viewer
    routes/
      api/tech-recon/
        investigations/route.ts
        investigation/[id]/route.ts
        system/[id]/route.ts
        artifact/[id]/route.ts
        analysis/[id]/run/route.ts   # execute plot + query
```

### skills-registry.yaml entry
```yaml
- name: tech-recon
  path: skills/tech-recon
  description: Goal-driven technology investigation with dynamic Observable Plot analysis
```

---

## Subagent Architecture

The phases split into two execution models:

| Phase | Execution model | Why |
|-------|----------------|-----|
| Interview | Main session (conversational) | Requires user interaction |
| Discovery | Main session → subagents for search → main for approval | Searches are parallelizable; approval needs user |
| Ingestion | Parallel subagents (one per system) | Independent, slow, context-heavy |
| Sensemaking | Parallel subagents (one per system) | Each agent reads one system's artifacts only |
| Viz Planning | Main session (with user approval) | Requires user judgment on goal alignment |
| Analysis | Single subagent (reads all notes, writes all plots) | Needs cross-system view |

### Discovery subagent dispatch
```
Main session:
  → dispatch 3 parallel search agents (SearXNG, GitHub, HF)
  ← collect candidate lists
  → deduplicate + present to user
  → user approves candidates
  → call tech_recon.py add-system for each
```

### Ingestion subagent dispatch (SKILL.md instruction)
After systems are confirmed, SKILL.md says:
> "For each confirmed system, dispatch a parallel ingestion agent with instructions:
>  - system ID and URL
>  - fetch homepage, GitHub repo (file tree + README + key source files), docs pages
>  - call tech_recon.py ingest-* for each artifact
>  - stop when cache-path is recorded for all primary sources"

TypeDB is the shared state — agents write independently, no coordination needed.

### Sensemaking subagent dispatch (SKILL.md instruction)
After ingestion completes:
> "For each ingested system, dispatch a parallel sensemaking agent with instructions:
>  - system ID
>  - read all cached artifacts for this system from TypeDB (list-artifacts --system <id>)
>  - read each artifact file from cache path
>  - write structured notes covering: overview, capabilities, architecture, performance, integration, tradeoffs
>  - use YAML for structured data (capability matrices, benchmark numbers), markdown for prose
>  - call tech_recon.py write-note for each note written"

### Analysis subagent dispatch (SKILL.md instruction)
After viz plan is approved:
> "Dispatch a single analysis agent with:
>  - investigation ID
>  - the approved viz-plan note content
>  - instructions to read all notes and implement each planned visualization as Observable Plot + TypeQL
>  - call tech_recon.py add-analysis for each completed plot"

### Why TypeDB as coordination medium
- TypeDB runs in a Docker container shared across all agents and the main session
- Agents write artifacts/notes/analyses to TypeDB independently
- Main session can check progress by querying status: `list-systems --status ingested` vs `--status confirmed`
- No inter-agent messaging needed — TypeDB IS the shared state

---

## Migration / Relationship to Old techrecon

- `techrecon` (old) remains in place until `tech-recon` is complete
- After `tech-recon` is operational: remove `techrecon` from `skills-registry.yaml`, archive `skills/techrecon/`
- No data migration — old investigations stay in TypeDB under old types; new investigations use new types

---

## Parallel Workstreams

The 4 subsystems can be built in parallel:

| Stream | Work | Owner |
|--------|------|-------|
| A | Schema + Python CLI skeleton (all commands, TypeDB operations) | Agent 1 |
| B | Dashboard components + pages (static mock data first) | Agent 2 |
| C | Ingestion pipeline (ingest-page, ingest-repo, ingest-pdf) | Agent 3 |
| D | Analysis execution API route + Observable Plot runner | Agent 4 |

Order: Stream A must complete schema.tql before B/C/D begin TypeDB work. B can start with mock data. C and D are independent after A.

---

## Verification

```bash
# 1. Schema loads
make build-db
docker ps --filter "name=alhazen-typedb" --format "table {{.Names}}\t{{.Status}}"

# 2. Start an investigation
uv run python .claude/skills/tech-recon/tech_recon.py start-investigation
# → prompts interview → creates investigation in TypeDB

# 3. Add a system + ingest a page
uv run python .claude/skills/tech-recon/tech_recon.py add-system \
  --name "TypeDB" --url "https://typedb.com" --investigation <id>
uv run python .claude/skills/tech-recon/tech_recon.py ingest-page \
  --url "https://typedb.com" --system <id>

# 4. Write a note
uv run python .claude/skills/tech-recon/tech_recon.py write-note \
  --system <id> --topic "overview" --format markdown \
  --content "TypeDB is a polymorphic database..."

# 5. Add an analysis artifact and run it
uv run python .claude/skills/tech-recon/tech_recon.py add-analysis \
  --investigation <id> --title "Stars comparison" \
  --plot-code "Plot.plot({marks: [Plot.barY(data, {x: 'name', y: 'stars'})]})" \
  --query "match \$s isa tech-recon-system, has name \$n, has star-count \$c; fetch { \"name\": \$n, \"stars\": \$c };"
curl http://localhost:3001/api/tech-recon/analysis/<id>/run

# 6. Dashboard smoke test
cd dashboard && npm run dev
# → open http://localhost:3000/tech-recon
```

---

## Process Notes (for skill-builder feedback)

Key learnings from this design process that should feed back into skill-builder:

1. **Interview phase is missing from current skill-builder phases** — The 6-phase curation model (Task Def → Foraging → Ingestion → Sensemaking → Analysis → Reporting) needs a Phase 0 UX that is conversational, not just a `define-goal` CLI command. The interview should output a structured goal document that drives the rest.

2. **Analysis artifacts are a new pattern** — The current skill-builder has no concept of "Claude-authored visualization code stored in TypeDB." This is a key capability gap. When analysis phase outcomes are visualizations, they should be stored as code artifacts (Observable Plot + query), not as static report text.

3. **Note format field enables schema deferral** — Storing `format: yaml` alongside `content` allows Claude to define per-investigation schemas without touching TypeDB. This is a reusable pattern: TypeDB as provenance/relationship store; content as Claude-structured documents.

4. **The goal-dashboard connection is the missing link in all skills** — Every skill that has a dashboard should have an explicit goal document that says what the dashboard is supposed to help the user understand. Without this, dashboards display data without insight.

5. **Subagent dispatch is essential for ingestion and sensemaking** — Skills that process many systems (10+) need a subagent-per-system model. This keeps the main session context clean, enables parallelism, and prevents context window exhaustion from reading large cached files. The skill-builder pattern should explicitly design which phases are subagent-dispatched vs. main-session. TypeDB as shared state is the coordination mechanism — agents don't communicate with each other, they communicate through the database.

6. **Visualization planning is a distinct phase** — The gap between "we have notes" and "we have useful visualizations" is a planning step where Claude maps goal questions to plot types. Without this step, visualizations are arbitrary rather than goal-driven. This should become a standard phase in the skill-builder curation pattern: after sensemaking, before analysis, Claude proposes a viz plan that the user approves. Each plot in the plan answers a specific success criterion.

6. **Discovery is a distinct phase between interview and ingestion** — The user names a few seed systems, but discovery searches the web/GitHub/HF to find similar systems and presents candidates for approval. This is a foraging phase that expands scope appropriately before committing to expensive ingestion. Should be a standard phase in the skill-builder curation pattern.
