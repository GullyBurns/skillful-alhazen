---
name: jobhunt
description: Track job applications, analyze positions, identify skill gaps, and plan your job search strategy
---

# Job Hunting Notebook Skill

Use this skill to manage your job search as a knowledge graph. Claude acts as your career coach, building understanding of positions, companies, and your fit over time.

## Philosophy: The Curation Pattern

This skill follows the **curation design pattern**:

1. **FORAGING** - Discover job postings (user provides URLs)
2. **INGESTION** - Script fetches raw content, stores as artifact
3. **SENSEMAKING** - Claude reads artifact, extracts entities, creates notes
4. **ANALYSIS** - Query across notes to answer questions
5. **REPORTING** - Dashboard views of pipeline and skills

**Key separation:**
- **Script handles**: Fetching URLs, storing raw content, TypeDB queries
- **Claude handles**: Reading artifacts, extracting meaning, creating notes, reasoning

## Prerequisites

- TypeDB must be running: `docker compose -f docker-compose-typedb.yml up -d`
- Dependencies installed: `uv sync --all-extras` (from project root)

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen_notebook)

---

## Your Skill Profile

Before analyzing jobs, set up your skill profile for gap analysis.

### Add Your Skills

```bash
# Add skills with your level
uv run python .claude/skills/jobhunt/jobhunt.py add-skill \
    --name "Python" --level "strong"

uv run python .claude/skills/jobhunt/jobhunt.py add-skill \
    --name "Machine Learning" --level "strong"

uv run python .claude/skills/jobhunt/jobhunt.py add-skill \
    --name "Distributed Systems" --level "some" \
    --description "Built caching layer, some k8s experience"

uv run python .claude/skills/jobhunt/jobhunt.py add-skill \
    --name "Rust" --level "learning"
```

**Skill levels:**
- `strong` - Confident, production experience
- `some` - Working knowledge, need to brush up
- `learning` - Currently studying
- `none` - No experience yet

### View Your Skills

```bash
uv run python .claude/skills/jobhunt/jobhunt.py list-skills
```

---

## Ingestion: Adding Job Postings

### From URL

**Triggers:** "add job", "ingest job", "new position", "found a job posting", "here's a job"

```bash
uv run python .claude/skills/jobhunt/jobhunt.py ingest-job \
    --url "https://boards.greenhouse.io/anthropic/jobs/123456" \
    --priority high \
    --tags "ai" "ml" "safety"
```

This stores the raw job posting as an artifact. Claude will do the sensemaking.

**Options:**
- `--url` (required): Job posting URL
- `--priority`: Set priority (high/medium/low)
- `--tags`: Space-separated tags

**Returns:**
```json
{
  "success": true,
  "position_id": "position-abc123",
  "artifact_id": "artifact-xyz789",
  "status": "raw",
  "message": "Artifact stored - ask Claude to 'analyze this job posting' for sensemaking."
}
```

---

## Sensemaking: Claude Analyzes Artifacts

**This is where Claude's comprehension matters.** When the user asks to analyze a job posting, Claude reads the raw artifact and extracts structured information.

### List Artifacts Needing Analysis

```bash
# Show artifacts that haven't been analyzed yet
uv run python .claude/skills/jobhunt/jobhunt.py list-artifacts --status raw

# Show all artifacts
uv run python .claude/skills/jobhunt/jobhunt.py list-artifacts --status all
```

### Get Artifact Content

```bash
uv run python .claude/skills/jobhunt/jobhunt.py show-artifact --id "artifact-xyz789"
```

### Sensemaking Workflow

**When user says "analyze this job posting" or "make sense of [position]":**

1. **Get the artifact content**
   ```bash
   uv run python .claude/skills/jobhunt/jobhunt.py show-artifact --id "artifact-xyz"
   ```

2. **Read and comprehend the content**
   - Look for: company name, job title, location, salary, remote policy
   - Identify: requirements, responsibilities, qualifications
   - Note: team info, culture signals, growth opportunities

3. **Create/update the company**
   If company doesn't exist yet:
   ```bash
   uv run python .claude/skills/jobhunt/jobhunt.py add-company \
       --name "Anthropic" \
       --url "https://anthropic.com" \
       --description "AI safety research company"
   ```

4. **Extract requirements as fragments**
   For each distinct skill/requirement:
   ```bash
   uv run python .claude/skills/jobhunt/jobhunt.py add-requirement \
       --position "position-abc123" \
       --skill "Python" \
       --level "required" \
       --your-level "strong" \
       --content "5+ years Python experience, focus on ML systems"
   ```

   Compare `--skill` to user's profile:
   - Look up skill in `list-skills`
   - Set `--your-level` based on match

5. **Create analysis notes**

   **Fit Analysis Note:**
   ```bash
   uv run python .claude/skills/jobhunt/jobhunt.py add-note \
       --about "position-abc123" \
       --type fit-analysis \
       --content "Strong fit for core requirements (Python, ML). Gap in distributed systems (required) - you have some experience but need to demonstrate scale." \
       --fit-score 0.82 \
       --fit-summary "Strong technical fit, one gap to address"
   ```

   **Research Note (company info):**
   ```bash
   uv run python .claude/skills/jobhunt/jobhunt.py add-note \
       --about "company-xyz" \
       --type research \
       --content "Series C, $4B raised. Strong safety focus. Engineering blog shows Rust and Python stack."
   ```

   **Skill Gap Note (for each gap):**
   ```bash
   uv run python .claude/skills/jobhunt/jobhunt.py add-note \
       --about "position-abc123" \
       --type skill-gap \
       --content "Distributed systems is required but you only have 'some' experience. Recommend: DDIA book, MIT 6.824 course."
   ```

6. **Flag uncertainties**
   If something is unclear, add tag "uncertain":
   ```bash
   uv run python .claude/skills/jobhunt/jobhunt.py tag \
       --entity "requirement-xyz" \
       --tag "uncertain"
   ```

7. **Report findings to user**
   Summarize:
   - Company and role overview
   - Your fit score and breakdown
   - Key gaps to address
   - Suggested next steps

### Example Sensemaking Output

```
## Analysis: Senior Software Engineer at Anthropic

**Company:** Anthropic - AI safety research, Series C ($4B+), San Francisco (hybrid)

**Role:** Senior Software Engineer, Claude Infrastructure team

**Your Fit: 85%**

| Requirement | Level | You | Match |
|-------------|-------|-----|-------|
| Python | Required | Strong | ✓ |
| ML Systems | Required | Strong | ✓ |
| API Design | Required | Strong | ✓ |
| Distributed Systems | Required | Some | △ |
| Rust | Preferred | Learning | △ |

**Gap Analysis:**
- Distributed systems is required - you have experience but should prepare examples
- Rust is preferred - continue learning, mention progress in interview

**Suggested Next Steps:**
1. Review DDIA chapters 1-3 for distributed systems concepts
2. Prepare 2 STAR stories about scaling challenges
3. Research their engineering blog for culture fit

Shall I create a strategy note with talking points?
```

---

## Application Tracking

### Update Status

```bash
uv run python .claude/skills/jobhunt/jobhunt.py update-status \
    --position "position-abc123" \
    --status "applied" \
    --date "2025-02-05"
```

**Status values:** `researching`, `applied`, `phone-screen`, `interviewing`, `offer`, `rejected`, `withdrawn`

### Add Notes

```bash
# Research note
uv run python .claude/skills/jobhunt/jobhunt.py add-note \
    --about "company-xyz" \
    --type research \
    --content "Read engineering blog - strong focus on reliability."

# Interaction note
uv run python .claude/skills/jobhunt/jobhunt.py add-note \
    --about "position-abc123" \
    --type interaction \
    --content "Phone screen went well, moving to technical round." \
    --interaction-type "call" \
    --interaction-date "2025-02-05"

# Strategy note
uv run python .claude/skills/jobhunt/jobhunt.py add-note \
    --about "position-abc123" \
    --type strategy \
    --content "Lead with distributed systems experience from caching project."
```

**Note types:** `research`, `strategy`, `interview`, `interaction`, `skill-gap`, `fit-analysis`, `general`

### Add Learning Resources

```bash
uv run python .claude/skills/jobhunt/jobhunt.py add-resource \
    --name "Designing Data-Intensive Applications" \
    --type "book" \
    --url "https://dataintensive.net" \
    --hours 30 \
    --skills "distributed-systems" "system-design"
```

---

## Query Commands

### List Pipeline

```bash
# All positions
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline

# Filter by status
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline --status "interviewing"

# Filter by priority
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline --priority "high"
```

### Show Position Details

```bash
uv run python .claude/skills/jobhunt/jobhunt.py show-position --id "position-abc123"
```

Returns: Position details, company info, requirements, all notes, fit analysis.

### Show Company Details

```bash
uv run python .claude/skills/jobhunt/jobhunt.py show-company --id "company-xyz"
```

### Show Skill Gaps

```bash
uv run python .claude/skills/jobhunt/jobhunt.py show-gaps
```

Returns: Skills by frequency across active applications, your level, linked resources.

### Learning Plan

```bash
uv run python .claude/skills/jobhunt/jobhunt.py learning-plan
```

---

## Tagging

```bash
# Tag an entity
uv run python .claude/skills/jobhunt/jobhunt.py tag \
    --entity "position-abc123" \
    --tag "bucket:engineering"

# Search by tag
uv run python .claude/skills/jobhunt/jobhunt.py search-tag --tag "bucket:engineering"
```

**Common tag patterns:**
- `bucket:engineering`, `bucket:research`, `bucket:leadership`
- `tech:python`, `tech:ml`, `tech:llm`
- `priority:high`, `priority:medium`, `priority:low`
- `fit:excellent`, `fit:good`, `fit:stretch`
- `uncertain` - for items needing review

---

## Complete Workflow Example

```
User: Here's a job I'm interested in: https://boards.greenhouse.io/anthropic/jobs/123

Claude: I'll ingest this posting and then analyze it.

[Runs ingest-job command]

Stored artifact. Now analyzing...

[Runs show-artifact to read content]
[Extracts company info, creates/updates company]
[Extracts requirements, creates requirement fragments]
[Compares to user's skill profile]
[Creates fit-analysis note, research note, skill-gap notes]

## Analysis: Senior Software Engineer at Anthropic

**Your Fit: 85%**
✓ Python (required) - you: strong
✓ ML Systems (required) - you: strong
△ Distributed Systems (required) - you: some
△ Rust (preferred) - you: learning

**Action Items:**
1. Review distributed systems concepts before applying
2. Set priority level?
3. Add to learning plan?

User: Set it to high priority. And yes, add a learning plan note.

Claude: [Updates priority, creates learning plan note]

Done! This is now a high-priority position. I've noted that you should
focus on distributed systems prep. Want me to find specific resources?
```

---

## Cross-Skill: Literature as Learning Resources

Paper collections from the **epmc-search** skill can be linked to skill gaps, and learning resources can reference specific papers. This bridges scientific literature with your learning plan.

### Link a Paper Collection to a Skill Gap

```bash
# Link to a specific requirement
uv run python .claude/skills/jobhunt/jobhunt.py link-collection \
    --collection "collection-abc123" \
    --requirement "requirement-xyz789"

# Link to all requirements matching a skill name
uv run python .claude/skills/jobhunt/jobhunt.py link-collection \
    --collection "collection-abc123" \
    --skill "machine-learning"
```

### Link a Learning Resource to a Paper

```bash
uv run python .claude/skills/jobhunt/jobhunt.py link-paper \
    --resource "resource-abc123" \
    --paper "doi-10_1234-paper1"
```

### Workflow: From Skill Gap to Reading List

```
1. Identify gaps:       jobhunt show-gaps
2. Search literature:   epmc-search search --query "topic" --collection "Reading List"
3. Link to gap:         jobhunt link-collection --collection <id> --skill "topic"
4. View plan:           jobhunt learning-plan  → shows collections alongside courses
5. Link key papers:     jobhunt link-paper --resource <id> --paper <id>
```

The `show-gaps` and `learning-plan` commands now include linked collections and referenced papers in their output.

---

## Data Model

### Entity Types

| Type | Description |
|------|-------------|
| `your-skill` | Your skills for gap analysis |
| `jobhunt-company` | An employer organization |
| `jobhunt-position` | A specific job posting |
| `jobhunt-learning-resource` | Course, book, tutorial |
| `jobhunt-contact` | Person at a company |

### Artifact Types

| Type | Description |
|------|-------------|
| `jobhunt-job-description` | Full JD text (raw) |
| `jobhunt-resume` | Your resume version |
| `jobhunt-cover-letter` | Tailored cover letter |

### Fragment Types

| Type | Description |
|------|-------------|
| `jobhunt-requirement` | Single skill/requirement |
| `jobhunt-responsibility` | Job responsibility |
| `jobhunt-qualification` | Qualification |

### Note Types

| Type | Purpose |
|------|---------|
| `jobhunt-application-note` | Status tracking |
| `jobhunt-research-note` | Company research |
| `jobhunt-interview-note` | Interview prep/feedback |
| `jobhunt-strategy-note` | Talking points, approach |
| `jobhunt-skill-gap-note` | Learning needs |
| `jobhunt-fit-analysis-note` | Fit assessment |
| `jobhunt-interaction-note` | Contact logs |

---

## Command Reference

| Command | Description | Key Args |
|---------|-------------|----------|
| `ingest-job` | Fetch job URL, store raw | `--url` |
| `add-skill` | Add to your skill profile | `--name`, `--level` |
| `list-skills` | Show your skills | |
| `list-artifacts` | List artifacts by status | `--status` |
| `show-artifact` | Get artifact content | `--id` |
| `add-company` | Add company | `--name` |
| `add-position` | Add position manually | `--title` |
| `add-requirement` | Add skill requirement | `--position`, `--skill` |
| `update-status` | Change application status | `--position`, `--status` |
| `add-note` | Create any note type | `--about`, `--type`, `--content` |
| `add-resource` | Add learning resource | `--name`, `--type` |
| `link-resource` | Link resource to requirement | `--resource`, `--requirement` |
| `link-collection` | Link paper collection to skill gap | `--collection`, `--requirement` or `--skill` |
| `link-paper` | Link learning resource to a paper | `--resource`, `--paper` |
| `list-pipeline` | Show applications | `--status`, `--priority` |
| `show-position` | Position details | `--id` |
| `show-company` | Company details | `--id` |
| `show-gaps` | Skill gap analysis | |
| `learning-plan` | Prioritized study list | |
| `tag` | Tag an entity | `--entity`, `--tag` |
| `search-tag` | Find by tag | `--tag` |
| `report-pipeline` | Pipeline overview (Markdown) | |
| `report-stats` | Stats summary (Markdown) | |
| `report-gaps` | Skill gaps report (Markdown) | |
| `report-position` | Position detail (Markdown) | `--id` |

---

## Reports (Markdown Output)

These commands output formatted Markdown suitable for messaging apps (Telegram, Discord, etc.) instead of JSON. Use them when displaying information directly to users.

### Pipeline Report

```bash
uv run python .claude/skills/jobhunt/jobhunt.py report-pipeline
```

Shows all positions grouped by status (Interviewing → Applied → Researching) with priority indicators and counts.

### Stats Overview

```bash
uv run python .claude/skills/jobhunt/jobhunt.py report-stats
```

Quick summary: total positions, active applications, high priority count, breakdown by status.

### Skill Gaps Report

```bash
uv run python .claude/skills/jobhunt/jobhunt.py report-gaps
```

Shows skills where your profile level is below what positions require. Sorted by requirement level (required first) and number of positions needing the skill. Requires skill profile to be populated via `add-skill`.

### Position Detail

```bash
uv run python .claude/skills/jobhunt/jobhunt.py report-position --id "position-xyz"
```

Full position detail: status, priority, URL, salary, location, and all notes (truncated to 500 chars each for messaging).

**When to use reports vs JSON commands:**
- **Reports** (`report-*`): When displaying to users in chat/messaging. Output is Markdown text.
- **JSON commands** (`list-pipeline`, `show-position`, etc.): When processing data programmatically or doing sensemaking. Output is JSON.

---

## TypeDB 2.x Reference

When writing custom TypeDB queries or scripts for job hunting data, consult the TypeDB documentation:

- **Full Reference:** `.claude/skills/typedb-notebook/typedb-2x-documentation.md`
- **JobHunt Schema:** `local_resources/typedb/namespaces/jobhunt.tql`
- **Core Schema:** `local_resources/typedb/alhazen_notebook.tql`

### Quick TypeQL Examples

```typeql
# Find all positions with a specific status
match
  $p isa jobhunt-position;
  $n isa jobhunt-application-note, has application-status "interviewing";
  (about: $p, note: $n) isa notation;
fetch $p: name, job-url;

# Update an attribute (delete old, insert new)
match
  $r isa jobhunt-learning-resource, has resource-url $old;
  $old "https://old-url.com";
delete $r has $old;
insert $r has resource-url "https://new-url.com";
```

### Common Pitfalls

- **No `optional` in fetch** - Use separate queries for optional attributes
- **Update = delete + insert** - Can't modify attributes in place
- **Use semicolons** between match patterns (implicit AND)
