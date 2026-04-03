# tech-recon: Deeper Investigation, Synthesis Report & Completion Evaluation

## Context

The tech-recon skill was rebuilt (PR merged April 2026) with a 7-phase pipeline, 25 CLI commands, and a Next.js dashboard. User feedback after first real use: **the investigation is too shallow, the dashboard doesn't synthesize findings, and there is no evaluation of whether the question was actually answered.**

Specific problems identified:
1. **Ingestion is API-only, not clone-based**: `ingest-repo` only fetches README + file tree JSON via the GitHub API. It never clones the repository. Sensemaking agents therefore have almost no raw material — they can't read source files, architecture docs, or configuration.
2. **No Explore-subagent pass over repos**: There is no mechanism to dispatch a Claude Explore subagent over a cloned repo to understand its structure. The `repos/` cache directory exists but is only populated manually.
3. **Sensemaking is not question-directed**: Notes cover generic topics but don't explicitly reference success criteria. There is no mandated `assessment` note per system.
4. **No synthesis report**: No compiled document that answers the investigation question with evidence.
5. **No completion evaluation**: No check that each success criterion has actually been addressed.

**Correct approach for repos** (user clarified): Clone the whole repository → dispatch a Claude Explore subagent over the local clone → derive fragments (notes) from the actual source files found there → use those fragments as primary sensemaking material.

---

## Architecture Change: Clone-First Ingestion

The new ingestion pipeline for systems with GitHub repos:

```
ingest-repo --clone            → git clone --depth 1 → ~/.alhazen/cache/repos/{owner}/{repo}/
                                  Stores artifact: type="repo-clone", cache-path="repos/owner/repo"

explore-repo --system <id>     → data-gathering command: returns clone path + file tree listing
                                  USAGE.md instructs Claude to dispatch Explore subagent over clone path
                                  Explore subagent reads key files, writes notes back via write-note

extract-fragments --artifact   → reads files from the local clone via the repo-clone artifact's cache-path
                                  splits source files by class/function/section → stores as fragment notes
```

The Explore subagent has read access to the local filesystem (`~/.alhazen/cache/repos/{owner}/{repo}/`). It can navigate directories, read source files, identify architecture, understand data models — then write structured notes back to TypeDB. This replaces the per-file GitHub API fetching entirely.

---

## Scope of Changes

- `skills/tech-recon/tech_recon.py` — modify `ingest-repo`, add `explore-repo`, `extract-fragments`, `compile-report`, `evaluate-completion`; add `_clone_repo()` helper
- `skills/tech-recon/USAGE.md` — 2 new phases, clone-first ingestion workflow, Explore subagent dispatch instructions, updated sensemaking prompts
- `skills/tech-recon/SKILL.md` — update phase table (7 → 9 phases), quick start
- `skills/tech-recon/schema.tql` — add `repo-clone` to `artifact-type` values (no new entities needed — strings are not enforced in TypeDB)
- `skills/tech-recon/dashboard/lib.ts` — 2 new exports
- `skills/tech-recon/dashboard/routes/note/[id]/route.ts` — NEW (fetch full note content for report tab)
- `skills/tech-recon/dashboard/pages/tech-recon/investigation/[id]/page.tsx` — 2 new tabs + header badge
- `skills/tech-recon/dashboard/components/stage-indicator.tsx` — add synthesis + evaluating stages

---

## Part 1: Python (`tech_recon.py`)

### New helper: `_clone_repo(url, owner, repo) → clone_path | None`

```python
def _clone_repo(url: str, owner: str, repo: str) -> str | None:
    """Git clone --depth 1 into ALHAZEN_CACHE_DIR/repos/{owner}/{repo}. Return clone path or None."""
    import subprocess
    cache_dir = os.environ.get("ALHAZEN_CACHE_DIR", os.path.expanduser("~/.alhazen/cache"))
    clone_path = os.path.join(cache_dir, "repos", owner, repo)
    if os.path.isdir(os.path.join(clone_path, ".git")):
        return clone_path  # already cloned — idempotent
    os.makedirs(os.path.dirname(clone_path), exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, clone_path],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        return None  # caller logs stderr
    return clone_path
```

### Modified command: `ingest-repo` — add `--clone` flag

Add to argparser:
```python
p.add_argument("--clone", action="store_true", default=False,
               help="Git clone the repo into ~/.alhazen/cache/repos/{owner}/{repo}")
```

After inserting the README and file-tree artifacts, if `--clone` is set:
1. Call `_clone_repo(url, owner, repo)`.
2. If successful: insert a `tech-recon-artifact` with `artifact-type = "repo-clone"`, `format = "directory"`, `tech-recon-url = url`, `cache-path = "repos/{owner}/{repo}"`, linked to the system via `sourced-from`.
3. If failed: include `"clone_error": result.stderr` in the return JSON but continue (partial success is fine).
4. Add `"clone_path": clone_path` and `"clone_artifact_id": id` to the return JSON.

### New command: `explore-repo`

```
explore-repo --system SYSTEM_ID [--investigation INVESTIGATION_ID]
```

Data-gathering command. Returns the clone path, directory tree, and dispatch instructions for a Claude Explore subagent.

1. Find the `repo-clone` artifact for this system:
   ```typeql
   match $sys isa tech-recon-system, has id "{sys_id}";
         $art isa tech-recon-artifact, has artifact-type "repo-clone";
         (artifact: $art, source: $sys) isa sourced-from;
   fetch { "id": $art.id, "cache_path": $art.cache-path, "url": $art.tech-recon-url };
   ```
2. Expand the cache path to absolute: `os.path.join(ALHAZEN_CACHE_DIR, cache_path)`.
3. If the clone path doesn't exist: return `{"success": false, "error": "repo not cloned — run ingest-repo --clone first"}`.
4. Walk the directory tree (using `os.walk`, skip `.git/`, filter to files with extensions `.py .ts .js .rs .go .java .md .tql .yaml .toml .json .prisma`). Return up to 200 file paths, sorted by depth then name.
5. If investigation ID is given, fetch goal + criteria from TypeDB.
6. Return:
   ```json
   {
     "success": true,
     "system_id": "trs-...",
     "system_name": "...",
     "clone_path": "/Users/.../.alhazen/cache/repos/owner/repo",
     "repo_url": "https://github.com/owner/repo",
     "files": ["README.md", "src/main.py", "src/models.py", "pyproject.toml", ...],
     "investigation_goal": "...",
     "success_criteria": "...",
     "instruction": "Dispatch an Explore subagent over clone_path. The subagent should: (1) read README and key source files, (2) understand the architecture and how it addresses the investigation criteria, (3) call write-note for each topic found. See USAGE.md §9 for the full Explore subagent prompt template."
   }
   ```

### New command: `extract-fragments`

```
extract-fragments --artifact ARTIFACT_ID [--max-fragments 30]
```

Works for both HTML artifacts and `repo-clone` artifacts.

**For `repo-clone` artifacts:**
1. Get `cache_path` → expand to absolute directory.
2. Walk files with text extensions (`.py .ts .js .rs .go .md .tql .yaml .json`), skip `.git/`, skip files > 100 KB.
3. For Python/TypeScript/JavaScript/Rust/Go: split on top-level class/function definitions using regex (`^class `, `^def `, `^function `, `^export function`, `^pub fn`, `^func `). Section heading = `{filename}::{class_or_function_name}`.
4. For Markdown: split on `^## ` headings. Section heading = `{filename}::{heading}`.
5. For YAML/TOML: split on top-level keys. Section heading = `{filename}::{key}`.
6. Call `_insert_note(tx, system_id, "fragment", section_text, "text", [section_heading])` for each section.

**For HTML artifacts** (existing websites from `ingest-page`/`ingest-docs`):
1. Load from cache path using `load_from_cache_text`.
2. Parse with `BeautifulSoup`. Split on `h2`/`h3` headings. Section heading = heading text.
3. Same `_insert_note` call.

**Dedup guard**: Before inserting, check for existing fragment note with matching `tech-recon-tag` for this system. Skip duplicates.

**Return:** `{"success": true, "artifact_id": ..., "artifact_type": ..., "fragments_extracted": N, "notes": [...]}`

### New helper: `_insert_note(tx, subject_id, topic, content, fmt, tags=None) → note_id`

Extract the note-insertion logic from `cmd_write_note` into a helper that accepts an open write transaction. Allows `extract-fragments` to batch-insert many notes in a single transaction without reopening per note.

### New command: `compile-report`

```
compile-report --investigation INVESTIGATION_ID [--force]
```

Data-gathering command. Returns all notes (full content, not 200-char preview) + artifact references + investigation context for Claude to write the synthesis document.

1. If `synthesis-report` note exists on the investigation and `--force` not set → return `{"already_exists": true, "note_id": ..., "content_preview": ...}`.
2. Fetch investigation: `id`, `name`, `goal-description`, `success-criteria`.
3. For each system: fetch ALL notes with **full content** (NOT `[:200]` preview). Key distinction from `plan-analyses`:
   ```typeql
   match $sys isa tech-recon-system, has id "{sys_id}";
         $n isa tech-recon-note;
         (note: $n, subject: $sys) isa aboutness;
   fetch { "id": $n.id, "topic": $n.topic, "format": $n.format, "content": $n.content };
   ```
4. Fetch investigation-level notes (same query with `$inv`).
5. Fetch artifact list per system (ids, types, urls, cache_paths, to show what raw material exists).
6. Return full JSON context with `"instruction"` field describing required report structure:
   ```
   ## Executive Summary
   ## Criterion N: [criterion text]  ← one section per criterion with evidence + note IDs cited
   ## System Comparison              ← prose narrative, not just a table
   ## Key Findings                   ← 3–7 bullets
   ## Gaps & Uncertainties
   ```
   Cite notes inline as `[note:trn-abc123 — SystemName/topic]`.

### New command: `evaluate-completion`

```
evaluate-completion --investigation INVESTIGATION_ID
```

Data-gathering command. Returns coverage statistics for Claude to evaluate and write a completion assessment.

1. Fetch investigation, parse `success-criteria` into `criteria_list` (split on `;` or `\n`).
2. For each system: count artifacts, count notes, list topics covered, flag `has_assessment` (topic "assessment" exists), flag `is_shallow` (artifact_count < 3 OR no repo-clone artifact).
3. Check if `completion-assessment` note exists on the investigation.
4. Return JSON with `criteria_list`, per-system coverage stats, `completion_assessment_exists`, and an `"instruction"` field with the required completion note structure:
   ```
   | Criterion | Status (YES/PARTIAL/NO) | Strongest evidence | Gaps |
   ## Systems Needing More Work
   ## Missing Topics
   ## Recommended Next Steps
   ```

**YES/PARTIAL/NO definitions (include in instruction):**
- **YES**: ≥ 2 systems have `assessment` notes explicitly addressing this criterion with positive findings
- **PARTIAL**: evidence exists but from only 1 system, or contradictory, or inferred rather than explicit
- **NO**: no `assessment` note directly addresses this criterion

### Add `synthesis` and `evaluating` to `update-investigation` status choices

### Update module docstring

Add new commands to the top-level command list at module top.

---

## Part 2: Dashboard

### New file: `dashboard/routes/note/[id]/route.ts`

Returns full note content (needed because `list-notes` returns only `content_preview[:200]`):

```typescript
import { NextResponse } from 'next/server';
import { getNote } from '@/lib/tech-recon';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const data = await getNote(id);
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
```

`getNote` is already in `lib.ts` → calls `show-note --id <id>` → returns full `content`. No Python changes needed.

### Modified: `dashboard/lib.ts`

Add two exports:
```typescript
export async function compileReport(investigationId: string, force = false): Promise<unknown> {
  const args = ['compile-report', '--investigation', investigationId];
  if (force) args.push('--force');
  return runTechRecon(args) as any;
}

export async function evaluateCompletion(investigationId: string): Promise<unknown> {
  return runTechRecon(['evaluate-completion', '--investigation', investigationId]) as any;
}
```

### New client component: `dashboard/components/tech-recon/report-content.tsx`

Must be `'use client'` (uses `useState`/`useEffect`). The parent investigation page is a server component and cannot contain hooks directly.

```typescript
'use client';
import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { TechReconNote } from '@/lib/tech-recon';

export function ReportContent({ noteId, preview }: { noteId: string; preview?: string }) {
  const [content, setContent] = useState<string>(preview ?? '');
  useEffect(() => {
    fetch(`/api/tech-recon/note/${noteId}`)
      .then(r => r.json())
      .then(d => { if (d.note?.content) setContent(d.note.content); });
  }, [noteId]);
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
```

### Modified: `dashboard/pages/tech-recon/investigation/[id]/page.tsx`

**Note filtering** (add after existing `vizPlanNotes` extraction):
```typescript
const synthesisNote = allNotes.find(n => n.topic === 'synthesis-report') ?? null;
const completionNote = allNotes.find(n => n.topic === 'completion-assessment') ?? null;
const otherNotes = allNotes.filter(
  n => !['viz-plan', 'synthesis-report', 'completion-assessment'].includes(n.topic)
);
```

**Header badge** (add after existing status badge, inside header):
```tsx
{completionNote
  ? <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-xs">Assessed</Badge>
  : <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs">Not evaluated</Badge>
}
```

**Tab state** — change default from `'analyses'` to `'report'`:
```typescript
const [activeTab, setActiveTab] = useState<'report'|'analyses'|'viz-plan'|'notes'|'completion'>('report');
```

**Tab list** — add Report (first) and Completion (last):
```tsx
[
  { key: 'report',     label: 'Report',     icon: FileText },
  { key: 'analyses',   label: 'Analyses',   icon: BarChart2 },
  { key: 'viz-plan',   label: 'Viz Plan',   icon: BarChart },
  { key: 'notes',      label: 'Notes',      icon: StickyNote },
  { key: 'completion', label: 'Completion', icon: ClipboardCheck },
]
```
New imports: `FileText`, `ClipboardCheck` from `lucide-react`. Import `ReportContent` from `@/components/tech-recon/report-content`.

**Report tab content** (replace `activeTab === 'analyses'` guard, add before it):
```tsx
{activeTab === 'report' && (
  <div>
    {!synthesisNote ? (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground italic">No synthesis report yet. Run:</p>
        <pre className="text-xs bg-muted/50 border border-border/40 rounded p-3 whitespace-pre-wrap">
          {`uv run python .claude/skills/tech-recon/tech_recon.py compile-report --investigation ${id}`}
        </pre>
        <p className="text-xs text-muted-foreground">Then ask Claude to write the synthesis report using the returned context.</p>
      </div>
    ) : (
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">Note: {synthesisNote.id}</p>
        <ReportContent noteId={synthesisNote.id} preview={synthesisNote.content_preview} />
      </div>
    )}
  </div>
)}
```

**Completion tab content** (add after analyses/notes blocks):
```tsx
{activeTab === 'completion' && (
  <div>
    {!completionNote ? (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground italic">No completion assessment yet. Run:</p>
        <pre className="text-xs bg-muted/50 border border-border/40 rounded p-3 whitespace-pre-wrap">
          {`uv run python .claude/skills/tech-recon/tech_recon.py evaluate-completion --investigation ${id}`}
        </pre>
        <p className="text-xs text-muted-foreground">Then ask Claude to write the completion assessment using the returned context.</p>
      </div>
    ) : (
      <ReportContent noteId={completionNote.id} preview={completionNote.content_preview} />
    )}
  </div>
)}
```

**Notes tab** — use `otherNotes` instead of `notes`:
```tsx
{activeTab === 'notes' && <NotesList notes={otherNotes} />}
```

### Modified: `dashboard/components/stage-indicator.tsx`

Add `synthesis` and `evaluating` to the `STAGES` array:
```typescript
{ key: 'synthesis',  label: 'Synthesis' },   // after 'analysis'
{ key: 'evaluating', label: 'Evaluating' },  // after 'synthesis'
```
(Both before `'done'`)

---

## Part 3: USAGE.md

### Section 1: Phase table — expand to 9 phases

| Phase | Name | What Happens | Key Commands |
|-------|------|-------------|--------------|
| 1 | Interview | Conversational goal + criteria capture | (conversational) |
| 2 | Discovery | Find candidates, user approves | `add-system`, `approve-system` |
| 3 | Ingestion | Clone repos, fetch pages and docs | `ingest-page`, `ingest-repo --clone`, `ingest-docs`, `ingest-pdf` |
| 4 | Repo Exploration | Explore subagent reads cloned repos | `explore-repo` → dispatch Explore subagent |
| 5 | Sensemaking | Question-directed notes per system | `write-note`, `extract-fragments` |
| 6 | Viz Planning | Propose plots for success criteria | `plan-analyses` |
| 7 | Analysis | Observable Plot + TypeQL per plot | `add-analysis`, `run-analysis` |
| 8 | Synthesis | Compile report answering the question | `compile-report` → `write-note --topic synthesis-report` |
| 9 | Completion | Evaluate criterion satisfaction | `evaluate-completion` → `write-note --topic completion-assessment` |

### Section 4 (Ingestion): Add `--clone` flag docs + "sufficient ingestion" checklist

**New `--clone` flag documentation:**
```bash
# Clone the full repo (recommended — enables explore-repo and extract-fragments):
uv run python .claude/skills/tech-recon/tech_recon.py ingest-repo \
    --url "https://github.com/owner/repo" \
    --system SYSTEM_ID \
    --clone
# Clone stored at ~/.alhazen/cache/repos/owner/repo/
# Creates artifact type="repo-clone" with cache-path="repos/owner/repo"
```

**New `explore-repo` command docs:**
```bash
# Returns clone path + file listing + Explore subagent dispatch instructions:
uv run python .claude/skills/tech-recon/tech_recon.py explore-repo \
    --system SYSTEM_ID \
    [--investigation INVESTIGATION_ID]
# Returns clone_path, files list, investigation goal/criteria.
# See §9 for the Explore subagent prompt template to use after running this.
```

**Sufficient ingestion checklist (add as new subsection):**
```
### What constitutes sufficient ingestion?

Per-system minimum before sensemaking:
- [ ] Homepage (ingest-page)
- [ ] GitHub repo cloned (ingest-repo --clone)  ← enables explore-repo and extract-fragments
- [ ] Documentation site (ingest-docs --max-pages 15)
- [ ] Any whitepaper or paper (ingest-pdf)

A system without a repo-clone artifact is flagged "shallow" by evaluate-completion.
Target: 4+ artifacts per system, with at least one repo-clone if a GitHub URL is known.
```

### New Section 4.5: Repo Exploration

```markdown
## 4.5. Repo Exploration (Phase 4)

After cloning a repo with `ingest-repo --clone`, dispatch a Claude Explore subagent
over the local clone to understand the codebase.

**Step 1: Get the clone path:**
uv run python .claude/skills/tech-recon/tech_recon.py explore-repo \
    --system SYSTEM_ID \
    --investigation INVESTIGATION_ID

**Step 2: Dispatch Explore subagent** (see §9 for full prompt template)
The subagent receives the clone_path, file list, and investigation criteria.
It reads key source files and writes notes back via write-note.

**Step 3: Extract fragments from large source files:**
uv run python .claude/skills/tech-recon/tech_recon.py extract-fragments \
    --artifact REPO_CLONE_ARTIFACT_ID \
    [--max-fragments 30]

Splits source files by class/function (Python/TypeScript) or heading (Markdown)
and stores each section as a fragment note. Fragment notes are topic="fragment"
with tech-recon-tag = "filename::classname".
```

### Section 5 (Sensemaking): Add question-directed guidance + mandatory assessment note

**New subsection "Question-Directed Sensemaking":**
```
Every note must address the investigation's success criteria, not just describe
the system generically. When writing any note, ask: "What does this tell me
about [success criterion N]?"

The `assessment` note is MANDATORY for every system. Structure:

## Assessment — [System Name]
**Criterion: [text]** → Status: YES / PARTIAL / NOT MET. Evidence: [finding].
(one block per criterion)
**Overall fit:** [1–2 sentence summary]

If a sensemaking subagent completes without writing an assessment note, the
investigation is incomplete for that system.
```

### New Section 8: Synthesis Report

Documents `compile-report`, `--force` flag, and required synthesis note structure.
Instructs: cite notes inline as `[note:trn-abc123 — SystemName/topic]`.

### New Section 9: Completion Evaluation

Documents `evaluate-completion` and YES/PARTIAL/NO definitions.
Required completion-assessment structure: criteria table, shallow systems list, missing topics, recommended next steps.

### Update Section 10 (Subagent Dispatch): Add Explore subagent prompt template for repo exploration

**New: Explore Subagent Prompt Template (Repo Exploration):**
```
You are a repo exploration agent for the tech-recon skill. Your task is to read
the cloned repository for system `{system_id}` ({system_name}) and write
structured, question-directed notes about its architecture and capabilities.

The local clone is at: {clone_path}
Investigation goal: {goal}
Success criteria: {success_criteria}

Steps:
1. Read the README.md and any ARCHITECTURE.md, DESIGN.md, or docs/ files.
2. Identify the entry points (main.py, index.ts, app.py, etc.) and read them.
3. Read 3–5 key source files that reveal the core architecture.
4. For each note topic below, write a note if relevant:
   - architecture (overall structure, components, data flow)
   - data-model (schema, types, key data structures)
   - api (key interfaces and entry points)
   - integration (how to embed or connect to this system)
   - performance (benchmarks, scaling, resource usage)
   - community (activity, maintainers, license)
   - assessment (MANDATORY — YES/PARTIAL/NOT MET per criterion with evidence)

For each note:
   uv run python .claude/skills/tech-recon/tech_recon.py write-note \
       --subject-id {system_id} \
       --topic {topic} \
       --format markdown \
       --content "{markdown content}"

5. Report: "Repo exploration for {system_name} complete. N notes written."

Key rule: every note must reference which success criteria it informs.
```

Update existing ingestion and sensemaking subagent templates to pass `{goal}` and `{success_criteria}`.

---

## Part 4: SKILL.md

- Update phase table from 7 to 9 phases (add Exploration, Synthesis, Completion)
- Add `explore-repo`, `compile-report`, `evaluate-completion` to quick start section

---

## Implementation Sequence

**Step 1 — Python: clone + explore (no schema changes needed)**
1. Add `_clone_repo(url, owner, repo)` helper at top of utility helpers section
2. Add `_insert_note(tx, subject_id, topic, content, fmt, tags)` helper (extracted from `cmd_write_note`)
3. Modify `cmd_ingest_repo`: add `--clone`/no-extra-args, call `_clone_repo`, insert `repo-clone` artifact if successful
4. Add `cmd_explore_repo` + argparser entry
5. Add `cmd_extract_fragments` + argparser entry
6. Update module docstring

**Verify Step 1:**
```bash
uv run python skills/tech-recon/tech_recon.py ingest-repo --help   # shows --clone flag
uv run python skills/tech-recon/tech_recon.py explore-repo --help
uv run python skills/tech-recon/tech_recon.py extract-fragments --help
# Test with current investigation:
uv run python skills/tech-recon/tech_recon.py ingest-repo \
    --url https://github.com/gsd-build/gsd-2 \
    --system trs-a5200a9d69ab \
    --clone 2>/dev/null | python3 -m json.tool | head -20
uv run python skills/tech-recon/tech_recon.py explore-repo \
    --system trs-a5200a9d69ab \
    --investigation tri-83965be7bf6a 2>/dev/null | python3 -m json.tool | head -30
```

**Step 2 — Python: synthesis + completion**
7. Add `cmd_compile_report` + argparser entry
8. Add `cmd_evaluate_completion` + argparser entry
9. Add `synthesis`/`evaluating` to `update-investigation` status choices
10. Update module docstring

**Verify Step 2:**
```bash
uv run python skills/tech-recon/tech_recon.py compile-report --help
uv run python skills/tech-recon/tech_recon.py evaluate-completion \
    --investigation tri-83965be7bf6a 2>/dev/null | python3 -m json.tool | head -30
```

**Step 3 — Dashboard routes + components**
11. Create `dashboard/routes/note/[id]/route.ts`
12. Add `compileReport`, `evaluateCompletion` exports to `dashboard/lib.ts`
13. Create `dashboard/components/tech-recon/report-content.tsx` (`'use client'` component)

**Step 4 — Dashboard investigation page**
14. Modify `dashboard/pages/tech-recon/investigation/[id]/page.tsx`: 2 new tabs, header badge, filtered notes, imports
15. Modify `dashboard/components/stage-indicator.tsx`: add synthesis + evaluating

**Verify Steps 3–4 (local dev):**
```bash
cd dashboard && npm run dev
# Navigate to http://localhost:3000/tech-recon/investigation/tri-83965be7bf6a
# ✓ Report tab appears first, shows "No synthesis report yet" with command
# ✓ Completion tab shows "No completion assessment" with command
# ✓ Stage indicator shows 8+ stages
# ✓ No TypeScript build errors
```

**Step 5 — Documentation**
16. Update `skills/tech-recon/USAGE.md`: 9-phase table, explore-repo section, sufficient ingestion checklist, question-directed sensemaking guidance, synthesis + completion sections, updated subagent prompts
17. Update `skills/tech-recon/SKILL.md`: 9-phase table, quick start

**Step 6 — End-to-end test with current investigation**
18. Test `ingest-repo --clone` on a real system (e.g., trs-a5200a9d69ab GSD-2)
19. Test `explore-repo` → verify returns clone path + file list
20. Run `compile-report --investigation tri-83965be7bf6a` → verify returns full note content
21. Ask Claude to write synthesis report → verify stored in TypeDB
22. Run `evaluate-completion` → verify returns criteria_list + coverage stats
23. Ask Claude to write completion assessment → verify stored
24. Rebuild Docker: `docker compose build --no-cache dashboard && docker compose up -d dashboard`
25. Verify Report tab renders markdown in full
26. Verify Completion tab renders assessment

**Step 7 — Upstream push**
27. Commit changes separately from any `rm` commands (never chain)
28. Push to `~/Documents/GitHub/alhazen-skill-examples` under `skills/demo/tech-recon/`
29. `make skills-update` (separate Bash call)

---

## Key Pitfalls

- **`_clone_repo` is idempotent**: check for existing `.git/` before cloning. If already cloned, return existing path. The repo-clone artifact insert should also be idempotent — check TypeDB for existing artifact before inserting.
- **`list-notes` returns `content_preview[:200]`**: `cmd_compile_report` must use full `$n.content` in the fetch clause, not the preview. Do NOT slice content in `compile-report` queries.
- **`'use client'` for `ReportContent`**: The investigation detail page is a Next.js server component. `ReportContent` uses `useState`/`useEffect` and must be a separate client component file (`report-content.tsx`), not inline in the server page.
- **BeautifulSoup is already imported** in `tech_recon.py` for `ingest-docs` — safe to reuse in `extract-fragments`.
- **`entity` keyword reserved in TypeQL match clauses** — use `$x isa identifiable-entity` not `$x isa entity`.
- **Fragment dedup**: check for existing note with same `tech-recon-tag` + system before inserting. Skip duplicates.
- **`git clone --depth 1` timeout**: 120s default. Large repos may timeout. If subprocess returns non-zero, log stderr in return JSON but do not crash — partial success (README + file tree already stored) is acceptable.
- **`explore-repo` requires prior `ingest-repo --clone`**: return clear error if no `repo-clone` artifact found; don't silently fail.
