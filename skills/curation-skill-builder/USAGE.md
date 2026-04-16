# Skill Builder — Usage Reference

## Overview: What You're Building

A **skill** is a bundle of five artifacts that implements a curation pipeline:

| Artifact | Purpose |
|----------|---------|
| `schema.tql` | TypeDB entity/relation/attribute definitions |
| `<skill>.py` | CLI script: ingest, list, show, update commands |
| `SKILL.md` | Short selection file (~30 lines) for Claude's context |
| `USAGE.md` | Full reference: commands, workflows, sensemaking instructions |
| `evals/` | Test cases measuring extraction performance (depending on the skill) |
| `docs/` | Detailed technical documentation about the schema, script, skill, and evals |
| `dash/` | Detailed technical documentation about the schema, script, skill, and evals |

---

## The Curation Workflow Pattern

This is the 7-phase investigation lifecycle that MUST be followed for any skill that curates knowledge from external sources. The tech-recon skill is the reference implementation — see `skills/tech-recon/USAGE.md` for concrete commands matching each phase.

---

### Phase 1: Goal Specification

Before any discovery or ingestion, interview the user to produce a measurable goal and success criteria.

**Interview pattern — 8 questions, one per conversation turn:**
1. What problem are you trying to solve?
2. What does success look like — what questions must this answer?
3. Are there existing tools or approaches you already know about?
4. What programming language or ecosystem are you working in?
5. What scale or performance requirements matter?
6. What licensing constraints apply?
7. What is your timeline — are you choosing now or exploring?
8. Any non-negotiables?

**After Q8:** Synthesize a 2-3 sentence goal statement and 3-5 success criteria. Present for user approval before proceeding.

**Goal quality bar:** The goal must be answerable yes/no at the end of the investigation — "Can we identify X such that Y?" not "Learn about X." Each success criterion must be independently verifiable.

**Goal and criteria are Markdown.** Use `**bold**` for emphasis and `- **Label**: description` bullet format for criteria. Both are rendered in the dashboard.

---

### Phase 2: Discovery (with approval gate)

Search for candidate entities (systems, papers, datasets, companies — whatever the skill domain defines as its primary subjects) from multiple sources. Present a table of N candidates to the user.

**Do not proceed to ingestion without explicit user approval.** Ingestion is expensive (many subagents, significant time). Spending it on wrong candidates wastes everything.

**Sources to search:**
- Web search (SearXNG)
- GitHub (by topic, language, stars)
- Hugging Face (models, spaces — if ML-adjacent)
- arXiv / OpenAlex (if research-adjacent)
- Domain-specific directories or registries

**Approval gate:** Present the candidate table, wait for user confirmation, then dispatch ingestion subagents.

---

### Phase 3: Ingestion

Execute the ingestion process defined in the skill's specification. The specifics (which commands, which sources, how many pages) live in the skill's own USAGE.md.

**Exhaustiveness principle:** It is better to over-ingest and have unused artifacts than to under-ingest and miss key evidence. The sensemaking phase filters; ingestion should cast wide.

**Subagent dispatch:** Dispatch one ingestion subagent per approved entity in parallel. Each subagent:
1. Shows the entity record
2. Ingests all sources it can find
3. Reports "N artifacts recorded" when complete

**User-assisted ingestion:** Some sources require user participation — content behind a paywall, pages requiring authentication, or files the user must download manually. In those cases, guide the user through the acquisition step and copy the material to the cache. Facilitating user-assisted acquisition is a first-class part of the ingestion workflow, not a fallback.

**Access in sensemaking:** Cached files are readable in Phase 4 via the native `Read` tool (supports PDFs, images, notebooks). See Phase 4 for details.

---

### Phase 4: Sensemaking (detailed and structured)

For each ingested entity, one sensemaking subagent reads all artifacts and writes one note per topic. Each note should be substantive and self-sufficient — the notes alone should be sufficient to answer the success criteria without returning to the raw artifacts.

**Note format:** Notes may be Markdown (narrative analysis, 300-1000 words) or JSON (structured data for downstream TypeQL queries) depending on whether the content is prose analysis or machine-readable facts. Choose based on what will be most useful for the analysis phase.

**Typical sensemaking topics:**

| Topic | Content |
|-------|---------|
| `architecture` | How the system is structured, components, data flow |
| `api` | Key interfaces, entry points |
| `data-model` | Schema, types, data structures |
| `integration` | How to embed in another system |
| `performance` | Benchmarks, scaling characteristics |
| `community` | Activity, maintainers, ecosystem |
| `assessment` | Fit against each success criterion (explicit per-criterion scoring) |

**Reading cached artifacts:** When a sensemaking subagent needs to read a local file from the artifact cache (`~/.alhazen/cache/`), always use the native `Read` tool — NOT Bash `cat` or `head`. The `Read` tool handles PDFs (use the `pages:` parameter for large documents), images (rendered natively as multimodal input), and Jupyter notebooks. Use `Grep` to search across cached files rather than `grep`/`rg`. See `skills/curation-skill-builder/claude-native-capabilities.md` for the full reference.

**Iterative sensemaking:** Notes from earlier passes provide context for later passes. Re-analyze after getting broader context across multiple entities.

---

### Phase 5: Analysis

Review the sensemaking notes against the success criteria. Propose a set of analyses that directly answer each criterion — visualizations, comparisons, derived metrics. Implement them as stored artifacts (TypeQL query + Observable Plot code or equivalent).

**Goal alignment:** Every analysis should trace back to a specific success criterion. Don't build charts for their own sake.

**Viz planning workflow:**
1. Review all sensemaking notes and the success criteria
2. Propose a viz-plan: for each analysis, state which criterion it answers, what TypeQL query extracts the data, and what chart type renders it
3. Present the viz-plan to the user (or proceed autonomously if criteria are clear)
4. Implement each approved analysis as a stored artifact

**Observable Plot types:**

| Type | Best for |
|------|----------|
| `bar` | Categorical comparisons |
| `line` | Trends over time |
| `dot` | Scatter (two continuous dimensions) |
| `rect` | Heatmaps |
| `text` | Annotated tables |

---

### Phase 6: Report + Completion Evaluation

Two required outputs:

**Synthesis Report** (topic: `synthesis-report`) — Markdown note that directly addresses each success criterion with findings, compares across candidates, and gives a single recommendation with rationale.

**Completion Assessment** (topic: `completion-assessment`) — Binary verdict per criterion:
- COMPLETE: specific evidence cited
- PARTIAL: what was found, what gap remains
- NOT COMPLETE: why the criterion cannot be answered with current data

The assessment must be conservative: if in doubt, mark PARTIAL. The investigation's goal document should be answerable yes/no after reading the synthesis.

---

### Phase 7: Iteration

If the completion assessment reveals gaps:

1. `advance-iteration --investigation ID` — increments iteration counter
2. Targeted re-ingestion or new entity discovery
3. New notes tagged with `--iteration N`
4. New synthesis + assessment tagged with `--iteration N`
5. Dashboard shows `v1 | v2 | v3` selector bar when multiple iterations exist

**Schema requirement:** Both the collection entity and note entity must own `iteration-number` (integer, defaults to 1) to support versioning. Filter notes by iteration in dashboard components using `(n.iteration_number ?? 1) === selectedIteration`.

---

## Skill Builder Workflow

The **Skill Builder Workflow** uses domain modeling to *create* the artifacts that execute the curation process — it is a design-time curation process where you (A) run ingestion over source documents and design specifications generated by the domain modeler; (B) use staged sensemaking to map those documents and specifications into schema, skill prompts, and scripts; (C) use analysis to validate and evaluate performance on sample data; and (D) generate the source artifacts for the target skill as a form of reporting.

The workflow is a structured framework for using domain modeling to build skills. It should be rerun when new data comes to light to generate new versions of the skill.

The 5-phase workflow captures the full design record for a skill from goal to analysis. Each phase produces TypeDB entities that link spec notes and design gaps polymorphically.

| Phase | Entity type | Purpose |
|-------|-------------|---------|
| 1 | `dm-goal` + `dm-goal-eval` | What the system is for and how success is measured |
| 2 | `dm-entity-schema` | TypeDB entity/relation/attribute types defined |
| 3 | `dm-source-schema` | External data sources and artifact types needed |
| 4 | `dm-derivation-skill` | Ingestion functions: artifact types in, entity types out |
| 5 | `dm-analysis-skill` | Analysis functions: entity types queried, outputs produced |

Spec notes (`dm-phase-spec`) and design gaps (`dm-design-gap`) link to whichever phase entity they belong to via `dm-phase-artifact` — the relation handles all five phases polymorphically.

### Phase 1: System Goal

Describe the domain being modeled and the goal of the curation process in detail. First, ingest all relevant source documents pertaining to the domain and the goal. Second, based on source documents (including design specs captured from a human designer), define the goals and evaluation criteria for the domain.   

> **Recommended:** Ingest source documents *before* writing the goal description. They give Claude a rich, citable evidence base — "I modeled this way because the paper describes X."

#### 1a. Ingest Source Documents

Here, 

```bash
# Step 1: Get the blank template, fill it out, save as domain-spec.md
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  generate-template > domain-spec.md
# ... edit domain-spec.md in your editor ...

# Step 2: Ingest the filled template
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --file domain-spec.md --doc-type template \
  --title "My Domain — spec"

# Step 3: Ingest reference papers (PDF from local file)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --file path/to/might-2017.pdf \
  --doc-type paper \
  --title "Might 2017 -- Undiagnosed Diseases Algorithm"

# Step 4: Ingest inline text (e.g. pasted email)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --text "The algorithm begins with a patient who has..." \
  --doc-type email --title "Matt Might email 2024-03-01"

# Step 5: Ingest content fetched by Playwright (JS-heavy or paywalled pages)
# Use browser_navigate + browser_snapshot to get text, then pipe it:
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN --stdin \
  --url "https://example.com/paper" --doc-type paper --title "..."
# (pipe fetched text via stdin; --url is always recorded as source-uri)

# Step 6: Simple direct URL fetch (urllib fallback — works for direct downloads only)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  ingest-source-doc --domain-id $DOMAIN \
  --url "https://arxiv.org/pdf/1234.5678.pdf" \
  --doc-type paper --title "ArXiv paper 1234.5678"

# Confirm ingestion
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  list-source-docs --domain-id $DOMAIN

# Read a source doc (returns content or cache-path for large files)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  show-source-doc --doc-id dm-source-doc-XXXX
```

**Input priority:** `--file` > `--stdin` > `--text` > `--url` (urllib). `--url` is always recorded as `source-uri` regardless of input method.

**For JS-heavy or paywalled URLs:** Use Playwright MCP tools to fetch content, then pipe to the script:
- Text content: `browser_navigate` → `browser_snapshot` → pass text via `--text` or `--stdin`
- Screenshots/diagrams: `browser_take_screenshot` → save PNG → `--file screenshot.png --doc-type image`
- PDFs: download via browser → `--file path/to/downloaded.pdf`

**After ingesting source docs, Claude should read them before writing the goal description:**
```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  list-source-docs --domain-id $DOMAIN \
  | python3 -c "import json,sys; [print(d['id'], d['name']) for d in json.load(sys.stdin)['source_docs']]"

uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  show-source-doc --doc-id dm-source-doc-XXXX \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['doc']; print(d.get('content') or 'cached at: '+str(d.get('cache_path')))"
```

#### 1b. Define Goal and Evaluation Criteria

```bash
# Create domain (if not already done)
DOMAIN=$(uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  init-domain --name "my-domain" --skill my-skill \
  --description "Complete and full description of the use case / domain of interest as an MD file. This should be verbose, rich, coherent, and complete." \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Define the system goal
GOAL=$(uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  define-goal --domain-id $DOMAIN \
  --name "What information is the curation process generating? What purpose does it serve? This should be verbose, rich, coherent, and complete." \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Add an evaluation criterion
# How would you know if the
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-evaluation \
  --goal-id $GOAL --domain-id $DOMAIN \
  --name "Coverage criterion" \
  --description "What fraction of real-world cases the schema can represent." \
  --criterion-type completeness \
  --success-condition "For 80% of test cases, zero unknown entity types" \
  --approach "Manual review of 20 randomly sampled real examples"

# Show goal + evaluations
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  show-goal --domain-id $DOMAIN
```

### Phase 2: Entity Schema

Think carefully about the domain and the goal of the curation work. What collections, domain-entities, and relations are needed to satisfy the goal. For example, if we were curating inforation about a job search, we would track positions, opportunities, candidate skills, etc. If we were curating information about disease mechanisms, we would track diseases, genes, mutataions, pathways, experiments, claims, etc. The task here is to model the main domain-specific entities needed to satisfy the curation process' goal.  

```bash
SCHEMA=$(uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-entity-schema --domain-id $DOMAIN \
  --name "Core entities" \
  --description "my-domain-entity, my-domain-artifact, my-domain-relation" \
  --feasibility yes \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Attach a TypeQL spec note
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-phase-spec --phase-id $SCHEMA \
  --content "entity my-domain-entity sub domain-thing, owns my-domain-attr-1;"

# Show the phase item with specs
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  show-phase-item --phase-id $SCHEMA
```

### Phase 3: Source Schema

Think carefully about the domain, the goal, and the entities developed in phase 2. What remotely available information do you need to be able to populate the schema generated in phase 2? If we were curating information about job search , we would need to capture online job postings, contacts, emails / conversations, websites, linkedin posts + profiles etc. If we were curating disease mechanisms, we'd need Pubmed, MONDO, and Uniprot records. The task here is to model the main information sources that we would need in order to be able to describe domain-specific entities from phase 2.  

```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-source-schema --domain-id $DOMAIN \
  --name "Primary data source" \
  --description "Source API or database; one HTML/JSON artifact per ingested item" \
  --feasibility yes
```

### Phase 4: Derivation Skills

Think carefully about the processes needed to generate domain entities from sources. Capture those processes as prompts and script commands that involve database updates.  

```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-derivation-skill --domain-id $DOMAIN \
  --name "ingest-source" \
  --description "Fetch source page, store artifact, extract domain entities" \
  --input-types "html artifact (source page)" \
  --output-types "my-domain-entity, my-domain-artifact" \
  --feasibility yes
```

### Phase 5: Analysis Skills

Think carefully about the processes needed to understand and interpret domain entities in order to satisfy the goal of the curation pipeline. Capture those processes as prompts and script commands that involve database updates.  

```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-analysis-skill --domain-id $DOMAIN \
  --name "analyze-entities" \
  --description "Reason across ingested entities to answer the curation goal" \
  --input-types "my-domain-entity, my-domain-relation" \
  --output-types "Markdown report with findings and gaps flagged" \
  --feasibility partial
```

### Cross-Phase Dependencies

Use `--depends-on` to record that one phase entity builds on another:

```bash
# Derivation skill depends on the source schema
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-derivation-skill --domain-id $DOMAIN \
  --name "ingest-secondary-source" \
  --description "Ingest secondary data source" \
  --input-types "json artifact (API response)" \
  --output-types "my-domain-secondary-entity" \
  --depends-on $SOURCE_ID
```

### Design Gaps

Design gaps discovered during implementation are filed as **GitHub Issues** in the skill's repo — not in TypeDB. This keeps the improvement loop where the fixes happen (GitHub branches, PRs, code review).

See the "Improvement Loop" section below for the full workflow.

### Export

```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  export-design-phases --domain-id $DOMAIN \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['markdown'])"
```

The export produces a Markdown document with Phase 1 goal + evaluations, followed by sections for each phase entity with embedded spec notes and open gaps.

#### docs/ Convention — Save as the Skill's Design Document

As the **Phase 5 reporting artifact**, the exported Markdown should be saved to `docs/design.md` inside the skill directory. This file becomes the authoritative design record for the skill — readable by humans and by future Claude sessions.

```bash
# Save the export directly to the skill's docs/ file
mkdir -p skills/$SKILL_NAME/docs
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  export-design-phases --domain-id $DOMAIN \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['markdown'])" \
  > skills/$SKILL_NAME/docs/design.md
```

**When to regenerate:** After adding new phase items, resolving gaps, recording design decisions, or completing a new implementation iteration — re-run the export to keep `docs/design.md` in sync with the TypeDB record.

**What the file captures:**
- System goal and evaluation criteria (Phase 1)
- Entity schema decisions and specs (Phase 2)
- Source schema and feasibility assessments (Phase 3)
- Derivation skill inputs/outputs (Phase 4)
- Analysis skill designs (Phase 5)
- Open and resolved design gaps at each phase

This output, combined with all the content developed in the modeling process, provides structured input for Claude to generate or regenerate a complete set of skill artifacts.

### `generate-evals` — Generate runtime evals from design criteria

After completing the 5 design phases, generate `evals/evals.json` for the skill you've designed. This converts TypeDB design-time criteria (`dm-goal-eval` entries) and phase entities into skill-creator-compatible test cases.

```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  generate-evals --domain-id $DOMAIN \
  --output-dir skills/$SKILL_NAME/
```

This creates `skills/$SKILL_NAME/evals/evals.json` with:
- One test case per `dm-goal-eval` criterion (from Phase 1) — driven by `success-condition` and `approach`
- One test case per `dm-derivation-skill` (from Phase 4) — exercises the ingestion workflow
- One test case per `dm-analysis-skill` (from Phase 5) — exercises the analysis workflow

To preview without writing to disk (stdout only):

```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  generate-evals --domain-id $DOMAIN \
  2>/dev/null | python3 -m json.tool
```

Once `evals/evals.json` exists in your skill directory, run it with the skill-creator plugin: invoke the `skill-creator` skill and say "run evals on \<your-skill-name\>".

**When to regenerate:** After adding or updating `dm-goal-eval` entries, or after defining new derivation or analysis skills — re-run `generate-evals` to keep the test cases in sync with the design.

---

## Improvement Loop

Each skill's repo owns its improvement loop natively — GitHub Issues track gaps, GitHub Actions automate triage and weekly review, and PRs close issues. The `curation-skill-builder` bootstraps this infrastructure once at skill creation time, then steps away.

### One-Time Setup: `scaffold-improvement-loop`

Run once when creating a new skill repo (or adding the loop to an existing one):

```bash
# For a skill in its own dedicated repo
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  scaffold-improvement-loop \
  --repo owner/my-skill-repo

# For a skill in a monorepo (creates an extra skill:<name> label)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  scaffold-improvement-loop \
  --repo sciknow-io/alhazen-skill-examples \
  --skill jobhunt
```

This creates (via GitHub API — no local clone needed):
- **15 standard labels**: `severity:*`, `phase:*`, `gap:*` (+ `skill:<name>` if `--skill` given)
- **`.github/ISSUE_TEMPLATE/skill-gap.md`**: structured gap template
- **`.github/workflows/gap-triage.yml`**: auto-labels new issues that match the template
- **`.github/workflows/weekly-gap-review.yml`**: Monday digest of all open gaps
- **`.github/workflows/claude-autofix.yml`**: when `gap:open` label is applied, Claude Code
  automatically creates a fix branch, implements the fix, and opens a PR.
  Requires `CLAUDE_CODE_OAUTH_TOKEN` secret (Settings → Secrets → Actions → New repository secret).
  If the secret is absent the workflow is skipped silently — other workflows are unaffected.

### Filing a Gap

After completing a plan that modifies a skill's schema, scripts, dashboard, or prompts:

```bash
# Skill in alhazen-skill-examples (jobhunt, scientific-literature, etc.)
gh issue create \
  --repo sciknow-io/alhazen-skill-examples \
  --title "Gap [moderate][entity-schema]: status attribute has no null guard" \
  --body $'## What was missing\nThe status attribute had no required constraint.\n\n## What broke\nBadge called .toLowerCase() on null, crashing the page.\n\n## Suggested fix\nAdded null guard to getBadgeColor().\n\n## Generalizable pattern\nAny optional string rendered in a badge must guard against null.\n\n---\n**Skill:** jobhunt\n**Phase:** entity-schema\n**Severity:** moderate' \
  --label "severity:moderate,phase:entity-schema,gap:open,skill:jobhunt"

# Skill in GullyBurns/skillful-alhazen (typedb-notebook, web-search, tech-recon, etc.)
gh issue create \
  --repo GullyBurns/skillful-alhazen \
  --title "Gap [minor][derivation]: ..." \
  --label "severity:minor,phase:derivation,gap:open,skill:typedb-notebook"
```

The `gap-triage.yml` workflow fires automatically on `issues: [opened]`, parses `**Phase:**`, `**Severity:**`, and `**Skill:**` from the body, and applies the correct labels even if the reporter omitted them.

### Fixing a Gap

```bash
# 1. Create a fix branch in the skill's local clone
git checkout -b fix/gap-<N>-<short-description>

# 2. Mark the issue as in-progress
gh issue edit <N> --repo <repo> --add-label gap:in-progress --remove-label gap:open

# 3. Make edits, commit, push
git push -u origin fix/gap-<N>-<short-description>

# 4. Create a PR that closes the issue
gh pr create --repo <repo> \
  --base main \
  --head fix/gap-<N>-<short-description> \
  --title "fix: <short description> (closes #<N>)" \
  --body "Closes #<N>"
```

Merging the PR closes the issue. The weekly digest skips closed issues automatically.

### List Open Gaps

```bash
# All open gaps in a repo
gh issue list --repo sciknow-io/alhazen-skill-examples \
  --label "gap:open" --json number,title,url,labels

# Critical gaps only
gh issue list --repo sciknow-io/alhazen-skill-examples \
  --label "gap:open" --label "severity:critical" --json number,title,url

# Gaps for a specific skill in a monorepo
gh issue list --repo sciknow-io/alhazen-skill-examples \
  --label "gap:open" --label "skill:jobhunt" --json number,title,url,labels
```

---

## Evaluation

The curation-skill-builder uses two complementary evaluation mechanisms:

### Design-Time: Evaluation Criteria in TypeDB

When defining a skill's goal (Phase 1), record measurable success criteria as `dm-goal-eval` entities. These live in TypeDB and become the source of truth for what the runtime evals should test.

```bash
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
  add-evaluation \
  --goal-id $GOAL --domain-id $DOMAIN \
  --name "Entity extraction coverage" \
  --description "Fraction of real-world entities the schema can represent" \
  --criterion-type completeness \
  --success-condition "For 80% of test cases, zero unknown entity types" \
  --approach "Manual review of 20 randomly sampled real examples"
```

Criterion types: `accuracy`, `coverage`, `usability`, `completeness`.

### Runtime: evals.json Test Cases (skill-creator format)

The `evals/evals.json` file contains concrete prompts that exercise the skill's workflow end-to-end. Run them using the official `skill-creator` plugin (install once with `/plugin` → search "skill-creator"):

1. Invoke the `skill-creator` skill and specify "run evals on curation-skill-builder"
2. skill-creator reads `evals/evals.json`, spawns parallel subagents (with-skill and without-skill) for each test case
3. Captures execution transcripts and output files
4. Grades each assertion → `grading.json` with `text`, `passed`, `evidence` per assertion
5. Aggregates results → `benchmark.json` with mean/stddev/delta statistics
6. Launches the HTML review viewer at http://localhost:3117

**evals.json structure:**
```json
{
  "skill_name": "curation-skill-builder",
  "evals": [
    {
      "id": 1,
      "prompt": "Concrete task prompt for Claude to execute",
      "expected_output": "Human-readable description of success",
      "expectations": [
        "Specific verifiable assertion about what happened",
        "Another verifiable assertion"
      ]
    }
  ]
}
```

**Assertion rules (from skill-creator grader):**
- Must be verifiable from the execution transcript and output files
- PASS only when the skill genuinely succeeded — not by surface compliance or coincidence
- Checking that a command *was called* is weaker than checking the *output it produced*
- The grader's burden of proof is on the expectation: uncertain = FAIL

### Connecting the Two Systems

Each `dm-goal-eval` `success-condition` should map to one or more `expectations` in `evals.json`. For example, if the success condition is "For 80% of test cases, all defined entities appear in the exported schema", the corresponding assertion is "export-design-phases output contains all entity types defined in add-entity-schema calls".

After running evals, record any gaps discovered as `dm-design-gap` entries (see Design Gaps section and CLAUDE.md).

---

## Domain Lifecycle Commands

```bash
# Create a tracking project
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    init-domain --name "Scientific Literature" --description "Tracks topics and subjects reported in the scientific literature" \
    --skill newskill

# Set the Phase 0 task (what is this skill FOR?)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    set-task --domain-id dm-domain-XXXX \
    --task "Ingest abstracts and full text papers pertaining to a specific subject into TypeDB"

# List all domains
uv run python .claude/skills/curation-skill-builder/skill_builder.py list-domains

# Full history: snapshots, decisions, experiments, errors
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    show-domain --id dm-domain-XXXX
```

---

## Designing the Curation Pipeline

### Step 1: Identify Entity Types

| Alhazen Type | Your Domain | Example (Job Hunt) | Example (Lit Review) |
|--------------|-------------|-------------------|---------------------|
| **Task** | The goal framing the curation | "Find a senior ML role" | "Understand CRISPR off-target effects" |
| **Thing** | Primary items you track | Company, Position | Paper, Author |
| **Artifact** | Raw captured content | Job Description | PDF, Abstract |
| **Fragment** | Extracted pieces | Requirement | Claim, Method |
| **Note** | Claude's analysis | Fit Analysis | Critique, Summary |

### Step 2: Define Attributes

```typeql
jobhunt-position sub domain-thing,
    owns job-url,
    owns salary-range,
    owns location,
    owns remote-policy;
```

### Step 3: Define Relations

```typeql
position-at-company sub relation,
    relates position,
    relates employer;
```

### Step 4: Design Script Commands

**Ingestion commands** (script does the work):
- `ingest-<source>` - Fetch and store raw content
- `add-<entity>` - Manual entity creation

**Query commands** (script queries, returns data):
- `list-<entities>` - List with filters
- `show-<entity>` - Full details
- `list-artifacts` - Artifacts pending analysis

**Update commands** (script updates TypeDB):
- `update-<attribute>` - Change entity attributes
- `tag` - Add tags to entities

### Step 5: Write Sensemaking Instructions

In your USAGE.md, tell Claude what to extract. Example:

```markdown
## Sensemaking Workflow

When user asks to "analyze [artifact]":

1. Read artifact content
   ```bash
   uv run python .claude/skills/domain/script.py show-artifact --id "artifact-xyz"
   ```

2. Extract entities:
   - [List what to look for]

3. Create fragments:
   - [List fragment types and what they contain]

4. Create analysis notes:
   - [List note types and their purpose]

5. Flag uncertainties with "uncertain" tag

6. Report summary to user
```

---

## TypeDB Schema Template

```typeql
define

# =============================================================================
# ATTRIBUTES (domain-specific)
# =============================================================================

domain-attr-1, value string;
domain-attr-2, value datetime;
task-status, value string;   # active | completed | on-hold

# =============================================================================
# ENTITIES - Task (Phase 0: what this curation is FOR)
# =============================================================================

# Inherits id @key, name, description from domain-thing.
# Natural-language goal goes in description.
my-domain-task sub domain-thing,
    owns task-status,
    plays task-scope:task,
    plays task-contribution:task;

# =============================================================================
# ENTITIES - Things
# =============================================================================

my-domain-entity sub domain-thing,
    owns domain-attr-1,
    plays domain-relation:role;

# =============================================================================
# ENTITIES - Artifacts
# =============================================================================

my-domain-artifact sub artifact;

# =============================================================================
# ENTITIES - Fragments
# =============================================================================

my-domain-fragment sub fragment,
    owns domain-attr-1,
    plays domain-relation:role;

# =============================================================================
# ENTITIES - Notes
# =============================================================================

my-domain-note sub note,
    plays task-contribution:note;

# =============================================================================
# RELATIONS
# =============================================================================

domain-relation sub relation,
    relates role1,
    relates role2;

# Task scopes a collection (what body of knowledge serves this goal?)
task-scope sub relation,
    relates task,
    relates collection;

# Note contributes to a task (links sensemaking output back to the goal)
task-contribution sub relation,
    relates task,
    relates note;
```

---

## Runtime Process Reference

All domain skills follow a 6-phase curation workflow. This is what the skill *does* at runtime after it has been built:

---

### Separation of Concerns

#### What Scripts Do (Python)

```
SCRIPT RESPONSIBILITIES
+----------------------------------------+
| Discover:                              |
| - Search APIs                          |
| - List sources                         |
| - Discover links                       |
|                                        |
| Ingestion:                             |
| - Fetch URL content                    |
| - Store raw HTML/text                  |
| - Record provenance                    |
| - Create artifact                      |
| - NO parsing, NO extraction            |
|                                        |
| Queries:                               |
| - List artifacts                       |
| - List entities                        |
| - Pipeline views                       |
| - Return data for Claude to reason     |
+----------------------------------------+
```

#### What Claude Does (via SKILL.md)

```
CLAUDE RESPONSIBILITIES
+----------------------------------------+
| Sensemaking:                           |
| - Read artifact content                |
| - Extract entities                     |
| - Create fragments                     |
| - Write notes                          |
| - Flag uncertainties                   |
|                                        |
| Analysis:                              |
| - Query across notes                   |
| - Generate synthesis                   |
| - Compare to profiles                  |
| - Make recommendations                 |
|                                        |
| Interaction:                           |
| - Present findings to user             |
| - Ask clarifying questions             |
| - Suggest next actions                 |
+----------------------------------------+
```

---

## Iterating and Improving

The full improvement loop connects live gap discovery through design decisions to automated optimization:

```
discover gap during workflow
    |
    v
log gap (typedb-notebook record-gap)          <-- surface-level observation
    |
    v
snapshot-skill (captures current skill files)
    |
    +-- add-decision (what schema change fixes it?)
    |       |
    |       +-- add-rationale (why this fix?)
    |       +-- link-gap (connect observed gap to fixing decision)
    |
    +-- start-experiment (test the fix)
    |       |
    |       +-- record-result (metric + value)
    |       +-- complete-experiment
    |
    +-- (gaps filed as GitHub Issues -- see "Improvement Loop" section)
    |
    v
export-design / export-design-phases (Markdown changelog)
```

### Gap Mechanisms

| Mechanism | Where | When to Use |
|-----------|-------|-------------|
| **Observed gap** | `typedb-notebook record-gap` (TypeDB) | Claude had to ask for something that should be stored, or made a wrong inference — logged during live skill use |
| **Design gap** | `gh issue create` (GitHub Issues) | A structural gap discovered during implementation — logged as a GitHub Issue in the skill's repo |
| **Link them** | `skill-builder link-gap` | Connect an observed gap (skilllog ID) to the design decision that fixes it |

### Skill Snapshots

```bash
# Capture all skill files (auto-detects git: commit, branch, remote, message)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    snapshot-skill --domain-id dm-domain-XXXX \
    --skill-dir local_skills/newskill/ --version v1.0 --repo-dir .
# Returns: snapshot ID + list of captured files (schema, script, prompts, tests)

# List all snapshots for a domain
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    list-versions --domain-id dm-domain-XXXX

# List files captured in a snapshot
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    list-files --snapshot-id dm-skill-snapshot-YYYY

# Show content of a captured file
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    show-file --file-id dm-skill-file-ZZZZ

# Attach a plan document (Claude's design plan) to a snapshot
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    add-plan --snapshot-id dm-skill-snapshot-YYYY \
    --plan-file ~/.claude/plans/my-plan.md --order 1 \
    --description "Initial implementation plan"

# Install post-commit hook (auto-snapshots skill on every git commit)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    install-hook --domain-id dm-domain-XXXX \
    --skill-dir local_skills/newskill/ --repo-dir .
chmod +x .git/hooks/post-commit
```

**Idempotency:** `snapshot-skill` checks the current commit SHA; if already snapshotted for this domain, it returns the existing record without duplicating.

**Large files:** Files >50KB are stored in the file cache (`~/.alhazen/cache/text/`) and referenced via `cache-path`. Smaller files are stored inline in TypeDB.

### Design Decisions

```bash
# Record a decision (types: entity | relation | attribute | hierarchy | constraint)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    add-decision --domain-id dm-domain-XXXX --type entity \
    --summary "Use dm-domain sub collection to group all design artifacts" \
    --version-id dm-skill-snapshot-YYYY \
    --alternatives "sub domain-thing: rejected, lacks collection grouping semantics"

# Add Claude's reasoning
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    add-rationale --decision-id dm-decision-ZZZZ \
    --rationale "collection already has collection-membership and nesting relations; reusing these avoids duplicating grouping infrastructure" \
    --alternatives "domain-thing would require custom grouping relations"

# Link a schema-gap (from skilllog) as motivation for the decision
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    link-gap --decision-id dm-decision-ZZZZ --gap-id gap-abc123

# List decisions (optionally filter by type)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    list-decisions --domain-id dm-domain-XXXX --type entity
```

### Experiments and Metrics

```bash
# Start an experiment
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    start-experiment --domain-id dm-domain-XXXX \
    --hypothesis "v1.0 schema supports all required newskill queries" \
    --version-id dm-skill-snapshot-YYYY

# Record a quantitative result
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    record-result --experiment-id dm-experiment-AAAA \
    --metric coverage --value 0.92 \
    --notes "8 of 100 test cases failed on missing causal-link relation"

# Mark complete
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    complete-experiment --experiment-id dm-experiment-AAAA

# List experiments
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    list-experiments --domain-id dm-domain-XXXX --status running
```

### Representation Errors

```bash
# Report an error (error types: type-mismatch | missing-concept | wrong-cardinality |
#   wrong-inheritance | semantic-ambiguity | over-generalization | under-generalization)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    report-error --domain-id dm-domain-XXXX \
    --type missing-concept \
    --summary "No entity type for 510k predicate device -- couldn't link predicate lineage" \
    --severity moderate --version-id dm-skill-snapshot-YYYY

# Resolve an error (link to the fixing decision)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    resolve-error --error-id dm-error-BBBB --decision-id dm-decision-ZZZZ

# List open errors
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    list-errors --domain-id dm-domain-XXXX --status open
```

### Skill Gap Logging (typedb-notebook)

Record deficiencies discovered during skill use. When Claude has to ask something that should have been stored, or makes an incorrect inference, log it as a `schema-gap` for systematic improvement.

| Gap Type | When to Log |
|----------|-------------|
| `missing-user-context` | Had to ask the user for something that should be in the profile |
| `missing-entity-type` | No TypeDB type exists for something we needed to store |
| `missing-attribute` | Existing type lacks an attribute the workflow needed |
| `unclear-workflow` | Sensemaking instructions were ambiguous or produced wrong output |
| `incorrect-inference` | Claude's reasoning produced a factually wrong result |

```bash
# Record a gap
uv run python .claude/skills/typedb-notebook/typedb_notebook.py record-gap \
    --skill jobhunt \
    --type missing-user-context \
    --description "User home location not stored; had to ask about on-site viability" \
    --severity moderate \
    --example "GenBio AI on-site Palo Alto role: asked user if Palo Alto commute was viable"

# List open gaps for a skill
uv run python .claude/skills/typedb-notebook/typedb_notebook.py list-gaps --skill jobhunt

# List all open gaps
uv run python .claude/skills/typedb-notebook/typedb_notebook.py list-gaps

# Close a gap once addressed
uv run python .claude/skills/typedb-notebook/typedb_notebook.py close-gap \
    --id "gap-abc123" --status addressed
```

The `skill-model` entity (auto-created by `record-gap`) is the first-class representation of each skill in the knowledge graph. Multiple gaps can be linked to one skill-model.

Link an observed gap to the design decision that fixes it:

```bash
# Step 1: Record the gap (skilllog)
uv run python .claude/skills/typedb-notebook/typedb_notebook.py record-gap \
    --skill newskill --type missing-entity-type \
    --description "No type for 510k predicate device"

# Step 2: Link it to the fixing decision (skill-builder)
uv run python .claude/skills/curation-skill-builder/skill_builder.py \
    link-gap --decision-id dm-decision-ZZZZ --gap-id gap-abc123
```

The gap ID is stored as a `dm-linked-gap-id` attribute (multi-valued: one per linked gap). The `show-domain` output includes linked gap IDs for cross-referencing.

---

## Reference: Artifact Types Registry

Artifact types are shared across all skills. Reuse existing types rather than creating new ones.

### Standard Artifact Types

| Type | Cache Dir | MIME Types | Example Uses |
|------|-----------|------------|--------------|
| `html` | `html/` | text/html | Job postings, web articles, company pages |
| `pdf` | `pdf/` | application/pdf | Papers, resumes, reports, cover letters |
| `image` | `image/` | image/* | Screenshots, figures, diagrams |
| `json` | `json/` | application/json | API responses, structured exports |
| `text` | `text/` | text/plain, text/markdown | Plain text content, notes |

### Storage Strategy

- **< 50KB:** Store inline in TypeDB `content` attribute
- **>= 50KB:** Store in cache, reference via `cache-path`

```python
from skillful_alhazen.utils.cache import should_cache, save_to_cache

if should_cache(content):
    cache_result = save_to_cache(artifact_id, content, mime_type)
    # Store cache_result['cache_path'] in TypeDB
else:
    # Store content inline in TypeDB
```

---

## Reference: User Profile Pattern

For domains where sensemaking depends on stable facts about the user — location,
constraints, preferences — define a profile entity so Claude never has to ask.

**When to use:** Any skill where analysis depends on the user-as-subject.
Examples: job hunting (location viability, salary floor), health tracking (conditions,
medications), learning (time budget, current level).

### Schema Template (TypeDB 3.x)

```typeql
# Profile attributes
attribute home-location, value string;
attribute my-domain-constraint, value string;

# Profile entity - inherits id, name, description from domain-thing.
# sub agent if the user is acting (job seeker, patient, learner).
# sub domain-thing if the user is an object being tracked.
# Singleton in practice; schema supports multi-user scenarios.
entity my-domain-user-profile sub agent,
    owns home-location,
    owns my-domain-constraint;
```

### CLI Convention

Two commands, always paired:

```bash
# Upsert: create if none exists, replace if one exists
script.py set-profile --location "..." --constraint "..."

# Read: single call that returns everything Claude needs for sensemaking
script.py show-profile
```

### Sensemaking Integration

In USAGE.md, instruct Claude to call `show-profile` **before** any analysis that
depends on user context:

```markdown
## Sensemaking Workflow
1. **Load seeker profile** (call FIRST -- never ask the user for this information)
   script.py show-profile
   Use result to automatically assess: location viability, constraint alignment, gaps
```

The `show-profile` command should return the profile entity plus all related
inventory (skills, learning resources, etc.) in a single JSON response.

### Reference Implementation

See `local_skills/jobhunt/jobhunt.py` `cmd_set_profile` and `cmd_show_profile` for
a complete example (`jobhunt-seeker sub agent` with `home-location`, `salary-floor`,
`remote-preference`, linked skills and learning resources).

---

## Reference: Schema Entity Map

| Entity | Base Type | When to Create |
|--------|-----------|----------------|
| `dm-domain` | `collection` | Once per skill/domain being designed |
| `dm-skill-snapshot` | `artifact` | Umbrella snapshot of full skill at one git commit |
| `dm-skill-file` | `artifact` | One captured file within a snapshot |
| `dm-design-decision` | `domain-thing` | Each significant schema choice |
| `dm-design-rationale` | `note` | Claude's reasoning for a decision |
| `dm-experiment` | `domain-thing` | Each hypothesis being tested |
| `dm-experiment-result` | `note` | Quantitative/qualitative observation |
| `dm-representation-error` | `domain-thing` | Each case where schema failed real data |

### Captured File Types

| `dm-file-type` | Files captured | `format` |
|---|---|---|
| `schema` | `schema.tql` | `typeql` |
| `script` | `<skill-name>.py` (main CLI) | `python` |
| `prompt-short` | `SKILL.md` | `markdown` |
| `prompt-full` | `USAGE.md` | `markdown` |
| `manifest` | `skill.yaml` | `yaml` |
| `test` | `tests/*.py` | `python` |
| `experiment` | `experiments/*.py`, `experiments/*.ipynb` | `python` / `ipynb` |
| `plan` | Added explicitly via `add-plan` | `markdown` |

**Note:** `dm-file-type = "experiment"` means a script in the skill's `experiments/` directory (captured as an artifact). This is distinct from `dm-experiment` entities, which track design hypotheses tested in TypeDB.

---

## Reference: TypeQL Query Examples

```typeql
# List all open design gaps for a domain
match $g isa dm-design-gap, has dm-error-status "open";
      $d isa dm-domain, has id "dm-domain-XXXX";
      (subject: $g, domain: $d) isa dm-in-domain;
fetch { "id": $g.id, "description": $g.description,
        "severity": $g.dm-error-severity, "phase": $g.dm-phase-number };

# Trace a derivation skill's outputs
match $sk isa dm-derivation-skill, has id "dm-derivation-skill-YYYY";
fetch { "id": $sk.id, "name": $sk.name,
        "inputs": $sk.dm-input-types, "outputs": $sk.dm-output-types,
        "feasibility": $sk.dm-feasibility };
```

---

## Reference: Dashboard Design Principles

1. **Query the graph** - Don't duplicate data; dashboards query TypeDB
2. **Pipeline views** - Show entities moving through states
3. **Matrix views** - Compare across dimensions
4. **Progress tracking** - Show completion of plans
5. **Deep dives** - Click to see all context about an entity

---

## Reference: Documenting Your New Domain

Every new domain skill needs documentation at four levels:

### Step 1: Skill Manifest (`skill.yaml`)

```yaml
name: my-domain
description: "Short description of what this skill does"
license: Apache-2.0
script: my_domain.py
schema: my_domain.tql
requires:
  bins: [uv, docker]
  env: [TYPEDB_HOST, TYPEDB_PORT, TYPEDB_DATABASE]
pattern: curation
phases:
  - foraging: "How sources are discovered"
  - ingestion: "How raw content is captured"
  - sensemaking: "What Claude extracts and analyzes"
  - analysis: "What cross-entity reasoning looks like"
  - reporting: "What dashboard views exist"
```

### Step 2: Query Examples (`local_resources/typedb/docs/query_examples.json`)

Add curated TypeQL examples for your namespace.

### Step 3: Regenerate Schema Docs

```bash
make docs-schema       # Generate local docs
make docs-schema-wiki  # Generate docs AND update wiki pages
```

### Step 4: Wiki Skill Page

Create `Skills:-<Domain>.md` in `~/Documents/Coding/skillful-alhazen.wiki/`. Follow `Skills:-Jobhunt.md` as a pattern.

### Step 5: Update CLAUDE.md

Add your skill to the "Available Skills" section so Claude knows about it.

### Documentation Maintenance

When you modify a schema:
1. `make docs-schema-wiki` — regenerate schema docs + wiki
2. Push wiki: `cd ~/Documents/Coding/skillful-alhazen.wiki && git add . && git commit -m 'Update schema docs' && git push`
3. Update `CLAUDE.md` Architecture section if hierarchy changed

---

## Reference: When to Create a New Domain

Create a new domain skill when:
1. You have a **specific information type** to track (papers, jobs, news, etc.)
2. Information comes from **discoverable sources** (APIs, URLs, databases)
3. You need to **reason over time** (not just one-shot questions)
4. Structure matters - entities have **attributes and relationships**
5. You want **Claude to build understanding** through sensemaking

Don't create a domain for:
- Simple lookups (use web search)
- One-time questions (just ask)
- Unstructured brainstorming (use notes)

---

## Examples: Job Hunting Domain

### Entity Types
- `jobhunt-company` (Thing) - An employer
- `jobhunt-position` (Thing) - A job posting
- `jobhunt-job-description` (Artifact) - Raw JD content
- `jobhunt-requirement` (Fragment) - Extracted skill requirement
- `jobhunt-fit-analysis-note` (Note) - Claude's fit assessment

### Script Commands
- `ingest-job --url` - Fetch and store job posting
- `add-skill --name --level` - Add to your skill profile
- `list-artifacts --status raw` - Artifacts needing analysis
- `show-artifact --id` - Get artifact for Claude to read
- `list-pipeline` - Show application status

### Sensemaking Flow
1. Script ingests URL -> creates artifact + placeholder position
2. User says "analyze that job posting"
3. Claude reads artifact content
4. Claude extracts: company, title, requirements, responsibilities
5. Claude compares to user's skill profile
6. Claude creates fit-analysis note with score and gaps
7. Claude reports findings and suggests next steps

---

## Examples: Literature Review Domain

### Entity Types
- `litreview-paper` (Thing) - A scientific paper
- `litreview-author` (Thing) - A researcher
- `litreview-pdf` (Artifact) - PDF content
- `litreview-claim` (Fragment) - Key claim with evidence
- `litreview-synthesis` (Note) - Cross-paper analysis

### Script Commands
- `ingest-paper --doi` - Fetch from DOI
- `ingest-paper --pmid` - Fetch from PubMed
- `search-papers --query` - Search literature databases
- `list-papers --collection` - Papers in a collection
- `show-paper --id` - Full paper details

---

## Dashboard Design System

When a skill includes a dashboard component, use the **sciknow.io / Starry Night** design system. This applies to all skill dashboard pages, components, and the main `dashboard/` app.

### Color Palette

Derived from the sciknow.io spiral icon, which mirrors Van Gogh's Starry Night:

| Role | Hex | Usage |
|------|-----|-------|
| Teal (primary) | `#5aadaf` | Primary accent, links, icons, borders |
| Aqua | `#62c4bc` | Hover states, secondary accent |
| Steel blue | `#5b8ab8` | Secondary UI elements, indigo replacement |
| Deep cobalt | `#3d5c8f` | Borders, subtle backgrounds, purple replacement |
| Warm chartreuse | `#b8c84a` | Accent spark, amber replacement, highlights |
| Midnight navy | `#070d1c` | Background |
| Deep navy | `#0c1628` | Card background |
| Cool blue-white | `#c8dde8` | Foreground text |
| Mid blue-gray | `#8ba4b8` | Muted text |

### Font Stack

- **Display (h1):** DM Serif Display, weight 400 — scholarly, distinctive
- **Body/UI:** DM Sans — contemporary, readable, not generic
- **Mono:** JetBrains Mono — distinctive for code

### Applying to a New Skill Dashboard

The color system is implemented as Tailwind v4 `@theme inline` overrides in `dashboard/src/app/globals.css`. This means all standard Tailwind color utilities (`text-cyan-400`, `bg-indigo-500/20`, `from-amber-400`, etc.) automatically resolve to Starry Night colors — **new skill dashboard files do not need custom color logic**.

Use standard Tailwind color classes as normal:
- Primary accent → `text-cyan-400`, `border-cyan-500/50`, `bg-cyan-500/20`
- Secondary/steel → `text-indigo-400`, `bg-indigo-500/20`
- Warm accent → `text-amber-400`, `bg-amber-500/20`
- Deep/cobalt → `text-purple-400`, `bg-purple-500/20`

Page headers should use: `bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent`

### Background & Structure

```css
/* Body: radial depth (already in globals.css) */
background:
  radial-gradient(ellipse at 20% 10%, rgba(61, 92, 143, 0.25) 0%, transparent 50%),
  radial-gradient(ellipse at 80% 90%, rgba(90, 173, 175, 0.1) 0%, transparent 40%),
  #070d1c;
```

Decorative spiral background for landing/hub pages:
```tsx
<div className="fixed inset-0 pointer-events-none overflow-hidden">
  <div className="absolute -right-48 -top-48 w-[800px] h-[800px] opacity-[0.04] rotate-[-15deg]">
    <Image src="/sciknow-icon.png" alt="" fill className="object-contain" />
  </div>
</div>
```

### sciknow.io Website (Jekyll)

The sciknow-io.github.io site uses the same palette via its Tailwind CDN config in `_layouts/default.html`:
- `midnight: '#070d1c'`, `accent: '#5aadaf'`, `secondary: '#b8c84a'`

---

## Skill Dashboard Design Patterns

Patterns distilled from the tech-recon dashboard build (Apr 2026). Apply these when adding or updating skill dashboard pages.

---

### Pattern 1: Tailwind v4 Gradient Text — Use Hardcoded Hex Values

Skill pages are copied into `dashboard/src/app/` at Docker build time, AFTER Tailwind's scanner runs. Named gradient utilities (`from-cyan-400`, `to-blue-400`) are purged because they only appear in dynamically-copied files; the heading text becomes invisible.

**Rule:** Always use arbitrary hex values in skill pages:
```tsx
// WRONG — gets purged at Docker build time
<h1 className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">

// CORRECT
<h1 className="bg-gradient-to-r from-[#5aadaf] to-[#4a7ab5] bg-clip-text text-transparent">
```

Theme hex values (from `dashboard/src/app/globals.css`): `cyan-400 = #5aadaf`, `blue-400 = #4a7ab5`.

This applies to all five files in a skill's `pages/` subtree. Verify by checking the compiled CSS bundle for the hex values after a Docker rebuild.

---

### Pattern 2: Sidebar Navigation Over Tabs

For multi-phase investigation workflows, use a vertical sidebar nav (not horizontal tabs). Lazy-load section data only when the user navigates to that section — don't fetch everything upfront.

```tsx
// Lazy-load: only fetch system data when user navigates to discovery/sensemaking
useEffect(() => {
  if (!['discovery', 'sensemaking'].includes(activeSection) || systemDataMap !== null || !data) return;
  // dispatch parallel fetches...
}, [activeSection, data, systemDataMap]);
```

---

### Pattern 3: Stage Indicators — Icons Not Numbers

Use `CheckCircle2` (green) / `XCircle` (red) from lucide-react for binary completion. Derive completion booleans from data, not from a status string.

```tsx
import { CheckCircle2, XCircle } from 'lucide-react';

// Derive from data — no status string needed
const completion = {
  scope: !!(investigation.goal || investigation.criteria),
  discovery: systems.length > 0,
  sensemaking: totalArtifacts > 0 && totalNotes > 0,
  analysis: analyses.length > 0,
  outputs: synthesisNote !== null,
};

// Render
{isCompleted ? (
  <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
) : (
  <XCircle className="w-3.5 h-3.5 text-red-400" />
)}
```

---

### Pattern 4: Compact Pills + Expandable Detail

Show entities as compact pills (`Name — Xa/Yn`). Expand to a detail panel on click. Never dump full content inline in a list.

```tsx
<button onClick={() => setSelectedId(isActive ? null : s.id)}>
  {s.name}
  <span className="text-xs text-muted-foreground font-normal ml-1">
    — {artCount}a/{noteCount}n
  </span>
</button>

{selected && (
  <div className="rounded-lg border border-cyan-500/30 bg-card/30 p-4">
    <SystemDetail system={selected} data={selectedData} />
  </div>
)}
```

---

### Pattern 5: Collapse-on-Demand for Notes

Show topic badge + first line preview. Fetch full content from the API only when the user expands a note. Cache in component state with a `fetched` flag to prevent re-fetching.

```tsx
const [fetched, setFetched] = useState(false);

const load = () => {
  if (fetched) return;
  setFetched(true);
  fetch(`/api/<skill>/note/${note.id}`)
    .then(r => r.json())
    .then(d => { if (d.note?.content) setFullContent(d.note.content); });
};
```

---

### Pattern 6: Iteration Tracking at Schema Level

Add `iteration-number` (integer) to both the collection entity and the note entity in the skill schema. Default to 1 (`?? 1`) everywhere for backward compatibility. Show the `v1|v2|v3` selector bar only when `iterations.length > 1`.

```typeql
# In schema.tql
attribute iteration-number, value integer;

entity my-skill-investigation sub collection,
    owns iteration-number;

entity my-skill-note sub note,
    owns iteration-number;
```

```tsx
// In the page component
const iterations = Array.from(new Set(notes.map(n => n.iteration_number ?? 1))).sort((a, b) => a - b);
const activeIteration = selectedIteration ?? (investigation.iteration_number ?? 1);
const iterNotes = notes.filter(n => (n.iteration_number ?? 1) === activeIteration);
```

---

### Pattern 7: Docker Wiring — Files Not Symlinks

Skill dashboard structure and where each subdirectory maps at Docker build time:

```
skills/<name>/dashboard/
  lib.ts          -> dashboard/src/lib/<name>.ts
  components/     -> dashboard/src/components/<name>/
  pages/          -> dashboard/src/app/(<name>)/
  routes/         -> dashboard/src/app/api/<name>/
```

After changing skill dashboard files: `make skills-update && docker compose build --no-cache dashboard && docker compose up -d dashboard`.

**Local dev:** Use symlinks for `lib.ts` (not wired by `make build-skills`):
```bash
cd dashboard/src/lib
ln -sf ../../../local_skills/<name>/dashboard/lib.ts <name>.ts
```

---

### Pattern 8: lib.ts as Thin CLI Wrapper

All business logic stays in Python. `lib.ts` only calls `uv run python <skill>.py` via `execFile`. Always pass `TYPEDB_DATABASE: 'alhazen_notebook'` explicitly in the env.

```typescript
export async function runSkill(args: string[]): Promise<unknown> {
  return new Promise((resolve, reject) => {
    execFile('uv', ['run', 'python', scriptPath, ...args], {
      env: { ...process.env, TYPEDB_DATABASE: 'alhazen_notebook' },
    }, (err, stdout) => {
      if (err) reject(err);
      else resolve(JSON.parse(stdout));
    });
  });
}
```
- Gradient text in `assets/css/custom.css`: `linear-gradient(135deg, #5aadaf, #b8c84a)`
