# Tech-Recon Skill — Full Reference

## 1. Overview: The 7-Phase Pipeline

| Phase | Name | What Happens | Key Commands |
|-------|------|-------------|--------------|
| 1 | Interview | 8 conversational questions → goal doc | (conversational) |
| 2 | Discovery | Find candidate systems, get user approval | `list-systems`, `add-system`, `approve-system` |
| 3 | Ingestion | Parallel subagents ingest primary sources | `ingest-page`, `ingest-repo`, `ingest-docs`, `ingest-pdf` |
| 4 | Sensemaking | Parallel subagents write structured notes | `write-note`, `list-notes`, `show-note` |
| 5 | Viz Planning | Propose visualizations for success criteria | `plan-analyses` |
| 6 | Analysis | Implement Observable Plot visualizations | `add-analysis`, `list-analyses`, `show-analysis`, `run-analysis` |
| 7 | Dashboard | Browse results at http://localhost:3001/tech-recon | (browser) |

---

## 2. Interview Workflow

Run one question per conversation turn. After the 8th answer, synthesize a concise goal statement and success criteria.

**The 8 questions:**
1. What problem are you trying to solve?
2. What does success look like — what questions must this investigation answer?
3. Are there existing tools or approaches you already know about?
4. What programming language or ecosystem are you working in?
5. What scale or performance requirements matter?
6. What licensing constraints apply?
7. What is your timeline — are you choosing now or exploring?
8. Any non-negotiables (e.g., must be open source, must have Python API)?

**Synthesis:** After Q8, write a 2-3 sentence goal statement and a bullet list of 3-5 success criteria. Present to user for approval before calling `start-investigation`.

**Goal and criteria are Markdown.** Both fields are rendered in the dashboard with full Markdown support. Use `**bold**` for emphasis, blank lines between paragraphs in the goal, and a `- **Label**: description` bullet list for success criteria.

**Start the investigation:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py start-investigation \
    --name "INVESTIGATION NAME" \
    --goal "2-3 sentence goal with **key terms** bolded.

Second paragraph if needed." \
    --success-criteria "- **Criterion one**: description of what to find
- **Criterion two**: description
- **Criterion three**: description"
```

Returns: `{ "success": true, "id": "tech-recon-investigation-<uuid>", "name": "..." }`

---

## 3. Discovery Workflow

Search for candidate systems using web-search and GitHub, then present a shortlist to the user for approval before ingestion.

**Search sources:**
- Web search: `web-search` skill
- GitHub: search by topic, language, stars
- Hugging Face: models/spaces if ML-adjacent

**Add a candidate system:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py add-system \
    --investigation INVESTIGATION_ID \
    --name "D3.js" \
    --url "https://d3js.org" \
    --github-url "https://github.com/d3/d3" \
    --description "Data-Driven Documents — low-level SVG/canvas charting"
```

**List all systems in an investigation:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py list-systems \
    --investigation INVESTIGATION_ID
```

**Approve a system for ingestion:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py approve-system \
    --id SYSTEM_ID
```

**Discovery rule:** Present a table of N candidates to the user and ask for approval before dispatching ingestion subagents. Do not ingest unapproved systems.

---

## 4. Ingestion Commands

Ingest primary sources for each approved system. Dispatch one subagent per system in parallel (see Section 8 for the verbatim prompt).

**Ingest a web page (homepage, landing page):**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py ingest-page \
    --url "https://d3js.org" \
    --system SYSTEM_ID
```

**Ingest a GitHub repository (README + file tree):**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py ingest-repo \
    --url "https://github.com/d3/d3" \
    --system SYSTEM_ID
```

**Ingest a documentation site (recursively fetches key pages):**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py ingest-docs \
    --url "https://d3js.org/getting-started" \
    --system SYSTEM_ID \
    --max-pages 20
```

**Ingest a PDF (paper, whitepaper, spec):**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py ingest-pdf \
    --url "https://example.com/paper.pdf" \
    --system SYSTEM_ID
```

**List artifacts for a system or investigation:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py list-artifacts \
    --system SYSTEM_ID

uv run python .claude/skills/tech-recon/tech_recon.py list-artifacts \
    --investigation INVESTIGATION_ID
```

**Show artifact content:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py show-artifact \
    --id ARTIFACT_ID
```

**Cache statistics:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py cache-stats \
    --investigation INVESTIGATION_ID
```

---

## 5. Sensemaking Commands

Write structured notes after reading ingested artifacts. Dispatch one subagent per system in parallel (see Section 8).

**Note types (use `--topic` to categorize):**

| Topic | When to use |
|-------|-------------|
| `architecture` | High-level design, components, data flow |
| `api` | Key APIs, interfaces, entry points |
| `data-model` | Schema, types, data structures |
| `integration` | How to embed or connect to other systems |
| `performance` | Benchmarks, scaling characteristics |
| `community` | Activity, maintainers, ecosystem |
| `comparison` | Cross-system observations |
| `assessment` | Overall fit against success criteria |

**Write a note:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py write-note \
    --system SYSTEM_ID \
    --topic architecture \
    --content "## Architecture\n\nD3 is a low-level SVG manipulation library..." \
    --tag "ingested"
```

To attach a note to an investigation (not a specific system):
```bash
uv run python .claude/skills/tech-recon/tech_recon.py write-note \
    --investigation INVESTIGATION_ID \
    --topic comparison \
    --content "## Cross-System Comparison\n\n..."
```

**List notes:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py list-notes \
    --system SYSTEM_ID

uv run python .claude/skills/tech-recon/tech_recon.py list-notes \
    --investigation INVESTIGATION_ID \
    --topic assessment
```

**Show a note:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py show-note \
    --id NOTE_ID
```

**Content format guidance:**
- Use **markdown** with `## Heading` sections for human-readable notes
- Use **YAML front-matter + markdown body** when structured fields matter (e.g., integration notes with `priority:`, `effort:`)
- Use **JSON** only for machine-readable structured data (e.g., benchmark results table)

---

## 6. Viz Planning Workflow

After sensemaking, propose a set of visualizations that directly answer the success criteria. Present the plan to the user before implementing.

**Plan analyses:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py plan-analyses \
    --investigation INVESTIGATION_ID
```

This command reads all notes and the success criteria, then outputs a YAML viz-plan like:

```yaml
analyses:
  - title: "GitHub Stars Over Time"
    type: line
    rationale: "Answers success criterion: active community"
    tql_query: |
      match $s isa tech-recon-system, has star-count $stars, has name $name;
      fetch { "name": $name, "stars": $stars };
    plot_description: "Line chart of star-count per system"

  - title: "License Compatibility Matrix"
    type: bar
    rationale: "Answers licensing constraint criterion"
    tql_query: |
      match $s isa tech-recon-system, has license $lic, has name $name;
      fetch { "name": $name, "license": $lic };
    plot_description: "Grouped bar chart by license type"
```

**Observable Plot types available:**

| Type | Best for |
|------|----------|
| `bar` | Categorical comparisons (stars, downloads) |
| `line` | Trends over time |
| `dot` | Scatter plots (two continuous dimensions) |
| `rect` | Heatmaps, calendar views |
| `text` | Annotated tables, labels |
| `link` | Network/dependency graphs |

Present the viz-plan to the user. After approval, implement each analysis.

---

## 7. Analysis Commands

**Add an analysis:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py add-analysis \
    --investigation INVESTIGATION_ID \
    --title "GitHub Stars Comparison" \
    --analysis-type bar \
    --query "match \$s isa tech-recon-system, has name \$n, has star-count \$sc; fetch { \"name\": \$n, \"stars\": \$sc };" \
    --plot-code "Plot.barY(data, {x: 'name', y: 'stars'}).plot()"
```

**List analyses:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py list-analyses \
    --investigation INVESTIGATION_ID
```

**Show an analysis:**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py show-analysis \
    --id ANALYSIS_ID
```

**Run an analysis (executes the TQL query, returns data):**
```bash
uv run python .claude/skills/tech-recon/tech_recon.py run-analysis \
    --id ANALYSIS_ID
```

Returns: `{ "success": true, "data": [...], "plot_code": "..." }`

The dashboard renders `plot_code` with the returned `data` using Observable Plot.

---

## 8. Subagent Dispatch Instructions

Dispatch subagents for Phases 3 (Ingestion) and 4 (Sensemaking) in parallel — one per approved system.

### Ingestion Subagent Prompt Template

```
You are an ingestion agent for the tech-recon skill. Your task is to ingest all
primary sources for the system with ID `{system_id}` into the alhazen cache.

Steps:
1. Show the system record:
   uv run python .claude/skills/tech-recon/tech_recon.py show-system --id {system_id}

2. Ingest the primary homepage URL:
   uv run python .claude/skills/tech-recon/tech_recon.py ingest-page \
       --url {url} --system {system_id}

3. If github-url is set, ingest the repository:
   uv run python .claude/skills/tech-recon/tech_recon.py ingest-repo \
       --url {github_url} --system {system_id}

4. Find the documentation URL from the homepage, then ingest it:
   uv run python .claude/skills/tech-recon/tech_recon.py ingest-docs \
       --url {docs_url} --system {system_id} --max-pages 20

5. If any PDF whitepapers or papers are linked, ingest them:
   uv run python .claude/skills/tech-recon/tech_recon.py ingest-pdf \
       --url {pdf_url} --system {system_id}

6. Report: "System {system_id} ({name}) ingestion complete. N artifacts recorded."
```

### Sensemaking Subagent Prompt Template

```
You are a sensemaking agent for the tech-recon skill. Your task is to read all
ingested artifacts for system `{system_id}` and write structured notes.

Steps:
1. List all artifacts:
   uv run python .claude/skills/tech-recon/tech_recon.py list-artifacts \
       --system {system_id}

2. Read each artifact with show-artifact and write one note per topic from this list:
   - architecture (how is the system structured?)
   - api (what are the key interfaces?)
   - data-model (what data structures does it use?)
   - integration (how would you embed this in another system?)
   - community (how active is the project?)
   - assessment (how well does it meet the success criteria: {success_criteria}?)

3. For each topic, call:
   uv run python .claude/skills/tech-recon/tech_recon.py write-note \
       --system {system_id} \
       --topic {topic} \
       --content "{markdown content}"

4. Report: "System {system_id} ({name}) sensemaking complete. N notes written."
```

### Analysis Subagent Prompt Template

```
You are an analysis agent for the tech-recon skill. Your task is to implement
one Observable Plot visualization for analysis `{analysis_id}`.

Steps:
1. Show the analysis:
   uv run python .claude/skills/tech-recon/tech_recon.py show-analysis \
       --id {analysis_id}

2. Run the TQL query to fetch data:
   uv run python .claude/skills/tech-recon/tech_recon.py run-analysis \
       --id {analysis_id}

3. Review the returned data shape. If the plot-code needs adjustment for the
   actual data keys, update it with:
   uv run python .claude/skills/tech-recon/tech_recon.py update-analysis \
       --id {analysis_id} \
       --plot-code "Plot.barY(data, {x: 'name', y: 'stars'}).plot()"

4. Report: "Analysis {analysis_id} ({title}) implemented. Data has N rows."
```

---

## 9. TypeDB Schema Summary

### Entities

| Entity | Subtype of | Key Attributes |
|--------|-----------|----------------|
| `tech-recon-investigation` | `collection` | `goal-description`, `success-criteria` |
| `tech-recon-system` | `domain-thing` | `url`, `github-url`, `language`, `license`, `star-count`, `status` |
| `tech-recon-artifact` | `artifact` | `artifact-type`, `url`, `content`, `cache-path` |
| `tech-recon-analysis` | `artifact` | `title`, `description`, `analysis-type`, `plot-code`, `tql-query` |
| `tech-recon-note` | `note` | `topic`, `tag`, `content` |

### Relations

| Relation | Roles | Connects |
|----------|-------|---------|
| `investigated-in` | `system`, `investigation` | system in an investigation |
| `sourced-from` | `artifact`, `source` | artifact from a system or investigation |
| `analysis-of` | `analysis`, `investigation` | analysis belongs to investigation |
| `aboutness` (core) | `note`, `subject` | note about a system or investigation |
| `collection-membership` (core) | `member`, `collection` | system enrolled in investigation |

### Inherited Core Attributes (not redefined)

`id` (key), `name`, `description`, `status`, `url`, `title`, `tag`, `language`, `license`, `format`, `content`, `cache-path`, `created-at`, `updated-at`, `provenance`

---

## 10. Dashboard

The dashboard is available at **http://localhost:3001/tech-recon** when the Next.js dev server or Docker dashboard is running.

| Route | Content |
|-------|---------|
| `/tech-recon` | List of all investigations with goal and status |
| `/tech-recon/[id]` | Investigation detail: systems, notes, analyses |
| `/tech-recon/[id]/systems` | System list with status badges |
| `/tech-recon/[id]/system/[sid]` | System detail: artifacts, notes |
| `/tech-recon/[id]/analyses` | Visualization gallery |
| `/tech-recon/[id]/analysis/[aid]` | Single visualization with Observable Plot render |

**Local dev:**
```bash
cd dashboard && npm run dev
# Then open http://localhost:3000/tech-recon
```

**Docker:**
```bash
docker compose up -d dashboard
# Then open http://localhost:3001/tech-recon
```
