# Gap / Skilllog Architecture

> How Skillful Alhazen detects, tracks, and fixes schema gaps — the primary signal for knowledge graph evolution.

---

## Core Problem

Standard skill improvement tracks *execution failures*: tools that crash, queries that return empty, APIs that are down. These are handled by ordinary error logging.

Alhazen has a second, more important failure mode:

> **When does Claude try to express something the TypeDB schema doesn't have a place for yet?**

This is a *schema gap* — not a crash, but a mismatch between what the knowledge work demands and what the current schema supports. Detecting and resolving gaps is how the knowledge graph grows organically from use.

---

## Two Failure Modes

| Type | Symptom | Handler |
|------|---------|---------|
| **Execution failure** | Tool crash, empty result, API error | Standard error log + retry |
| **Schema gap** | TypeDB write error (`[SYR1]`, `[TYR01]`, `[FEX1]`…), or Claude identifies a concept it can't represent | PostToolUse hook → `file-schema-gap` → GitHub issue |

Schema gaps always pass the "did it run?" test but fail the "did it say everything it needed to?" test.

---

## Detection

### 1. PostToolUse Hook (automatic)

`CLAUDE.md` registers a PostToolUse hook via `settings.json`. After every tool call, the hook reads stdout/stderr for TypeDB error codes:

```
[SYR1]  — type not found (missing entity/relation definition)
[TYR01] — invalid concept conversion
[FEX1]  — fetch expression error (e.g., fetching attribute from relation)
[INF2]  — type label not found
[INF11] — type-inference failure
```

When one of these appears, the hook prints a `[SCHEMA-GAP-HINT]` message prompting Claude to file an issue immediately.

### 2. Claude recognizes it

During sensemaking, Claude realizes a concept can't be stored — e.g., a disease entity that can't play `aboutness:subject` because the relation isn't defined in the `dismech` schema. Claude is instructed in `CLAUDE.md` to file immediately rather than waiting.

---

## Issue Filing

### CLI command: `file-schema-gap`

```bash
uv run python local_resources/skilllog/skill_logger.py file-schema-gap \
  --skill <skill-name> \
  --concept "<concept Claude tried to represent>" \
  --missing "<which TypeDB entity/relation/attribute is absent>" \
  --suggested "<proposed TypeQL snippet, or 'unknown'>" \
  [--dry-run]
```

**What it does:**
1. Routes the issue to the correct GitHub repo based on skill name (see Routing below)
2. Deduplicates: checks for existing open `gap:open` issues with the same concept (use `--skip-dedup` to override)
3. Builds a structured issue body matching the `gap-triage.yml` parser expectations
4. Runs `gh issue create` with the `gap:open` label

**Issue body structure:**
```
## What was missing
<concept description>

## What broke
<missing TypeDB element>

## Suggested fix
<TypeQL snippet>

## Generalizable pattern
<broader lesson>

---
**Skill:** <name>
**Phase:** entity-schema
**Severity:** moderate
```

### Repo routing

```python
# local_resources/skilllog/skill_logger.py

SKILL_REPO_MAP = {
    "dismech": "sciknow-io/alhazen-skill-dismech",
}

CORE_SKILLS = {"typedb-notebook", "web-search", "curation-skill-builder", "tech-recon"}

def get_gap_repo(skill_name):
    if skill_name in SKILL_REPO_MAP:
        return SKILL_REPO_MAP[skill_name]
    return "GullyBurns/skillful-alhazen" if skill_name in CORE_SKILLS \
        else "sciknow-io/alhazen-skill-examples"
```

Skills in non-standard repos (like `dismech`) are added to `SKILL_REPO_MAP`.

---

## GitHub Workflow: Issue Lifecycle

### Labels

| Label | Meaning |
|-------|---------|
| `gap:open` | Issue filed, no fix started |
| `gap:in-progress` | Local branch created, fix underway |
| `gap:pr-open` | Draft PR created, awaiting human review |
| `severity:minor / moderate / critical` | Impact level |
| `phase:entity-schema / source-schema / derivation / analysis` | Where in the skill lifecycle |
| `skill:<name>` | Which skill owns this gap |

### Automatic triage: `gap-triage.yml`

Triggers on every new issue. If the body contains `## What was missing`, it:
- Parses `**Severity:**`, `**Phase:**`, `**Skill:**` from the body and applies matching labels
- Adds `gap:open`
- Posts a comment with the local fix commands (see Local Fix Workflow below)

### Weekly review: `weekly-gap-review.yml`

Runs every Monday at 9 AM. Fetches all `gap:open` issues, groups by severity, creates a summary issue. Critical gaps open > 7 days receive a reminder comment.

### Guidance workflow: `claude-guidance.yml`

Triggers when `gap:open` is labeled. Posts a structured comment with the exact CLI commands for local fix (no code execution on GitHub — schema changes require a running local TypeDB instance).

---

## Local Fix Workflow

Schema changes cannot be validated on GitHub Actions runners (no TypeDB instance). All fixes happen locally.

### Step 1: Start the fix

```bash
uv run python local_resources/skilllog/skill_logger.py fix-gap \
  --issue <N> \
  --repo <owner/repo>
```

**What it does:**
- Fetches issue details from GitHub
- Creates branch `fix/gap-N-<slug>` (slug derived from issue title)
- Labels issue `gap:in-progress`, removes `gap:open`
- Posts a "Fix started" comment on the issue with the branch name

### Step 2: Implement and validate

Edit schema files and Python scripts. Validate against the running TypeDB:

```bash
# Test schema loads cleanly
make db-init

# Smoke test the affected commands
uv run python .claude/skills/<skill>/<skill>.py <command> [args]
```

Post implementation decisions as comments on the GitHub issue. These will be pulled into the PR body automatically.

### Step 3: Open a draft PR

```bash
uv run python local_resources/skilllog/skill_logger.py submit-gap-pr \
  --issue <N> \
  --repo <owner/repo> \
  --decisions "brief description of key decisions made"
```

**What it does:**
1. Confirms the current branch has commits ahead of `main` (aborts if not)
2. Runs `uv run pytest` if a test suite exists (aborts if tests fail)
3. Fetches implementation decision comments from the issue
4. Builds a PR title: `fix(<skill>): <slug> (closes #N)`
5. Builds a PR body with: `Closes #N`, summary, decisions, test status
6. Pushes branch and runs `gh pr create --draft`
7. Posts the PR URL as an issue comment
8. Labels issue `gap:pr-open`, removes `gap:in-progress`

**Output:**
```json
{
  "success": true,
  "pr_url": "https://github.com/…/pull/6",
  "pr_draft": true,
  "issue": 3,
  "test_status": "All local tests passed.",
  "next_step": "Review and merge at https://github.com/…/pull/6"
}
```

### Step 4: Human merge

The PR is created as a **draft**. The human:
1. Reviews the diff on GitHub
2. Promotes from draft to ready
3. Merges

This is the only step that cannot be automated — it is intentionally a human gate.

---

## Scaffolding a New Repo

To set up the full gap tracking infrastructure in a skill repo:

```bash
uv run python skills/curation-skill-builder/skill_builder.py \
  scaffold-improvement-loop \
  --repo <owner/repo> \
  --skill <skill-name>
```

Creates via GitHub API (no local clone required):
- `.github/ISSUE_TEMPLATE/skill-gap.md` — structured issue template
- `.github/workflows/gap-triage.yml` — auto-labels + posts local fix instructions
- `.github/workflows/weekly-gap-review.yml` — Monday summary + critical gap reminders
- `.github/workflows/claude-guidance.yml` — posts local fix commands on `gap:open` label

Does **not** create a GitHub Actions runner-based autofix workflow. All code execution is local.

---

## Design Principles

**Schema gaps are signal, not noise.** A gap means the knowledge work has outgrown the model. Filing the issue is the right response — not silently skipping the write or working around it in Python.

**Local execution only.** Schema changes require a running TypeDB instance for real-time validation. GitHub Actions runners can't do this. All fix implementation happens locally; GitHub is used only for issue tracking and PR review.

**Issues as the interface.** GitHub issues are the right unit of work for schema evolution — reviewable, discussable, linkable to PRs, searchable across time.

**Deduplication by default.** `file-schema-gap` checks for existing open issues with the same concept before filing. Hitting the same gap twice is common; filing it twice is noise.

**Draft PRs, human merges.** `submit-gap-pr` always creates a draft PR. The merge gate is always human. This ensures schema changes get a second set of eyes before landing.

---

## File Locations

| File | Purpose |
|------|---------|
| `local_resources/skilllog/skill_logger.py` | CLI: `file-schema-gap`, `fix-gap`, `submit-gap-pr` |
| `skills/curation-skill-builder/skill_builder.py` | `scaffold-improvement-loop` command + workflow templates |
| `local_resources/typedb/alhazen_notebook.tql` | Core schema (gaps in core skills file here) |
| `skills/<name>/schema.tql` | Per-skill schema extension |
| `.github/workflows/gap-triage.yml` | Auto-label + comment on new issues |
| `.github/workflows/weekly-gap-review.yml` | Monday gap summary |
| `.github/workflows/claude-guidance.yml` | Local fix instructions on `gap:open` label |

---

## Open Questions (from original design doc)

- **Backward compatibility during evolution**: when a schema attribute type changes (e.g., string → datetime), existing data needs migration. Currently handled by re-ingestion; no automated migration path exists yet.
- **Schema versioning**: gaps are filed against the current schema version. If a PR fixing gap #3 is still open when gap #7 is filed touching the same entity, the two fixes could conflict. No tooling to detect this yet.
- **Proposed vs. committed extensions**: all schema changes go directly to `schema.tql`. There's no "proposed" intermediate state — the issue + PR branch serves that role.
