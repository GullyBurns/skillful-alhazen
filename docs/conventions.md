# Team Conventions

When Claude makes a mistake, add it to this section so it doesn't happen again.

## Data Quality Audit Process

Skills can define data quality checks in `quality-checks.yaml` (declarative TypeQL queries with root cause analysis). The audit runner executes these and files structured GitHub issues. The fix cycle is:

1. **Run audit**: `uv run python src/skillful_alhazen/utils/audit_runner.py run --checks local_skills/<skill>/quality-checks.yaml`
2. **File issues**: Add `--file-issues` to create GitHub issues on the skill's repo with full improvement records (finding, data fix, root cause, prevention fix, verification test)
3. **Plan the fix**: Read the issue, create a branch, write an implementation plan. **Record the plan as a comment on the issue** so it's visible in the PR trail:
   ```bash
   gh issue comment <number> --repo <repo> --body "## Implementation Plan\n..."
   ```
4. **Implement**: Fix the root cause (code/schema/prompt change) + write a one-off data repair script if needed
5. **Verify**: Re-run the audit — the finding should disappear or improve
6. **PR**: Create a PR linking the issue. The PR documents: the code fix, before/after audit comparison, and closes the issue
   ```bash
   gh pr create --title "fix: <issue title>" --body "Fixes #<number>\n\n## Before\n<audit output>\n\n## After\n<audit output>"
   ```
7. **Close**: Merge PR -> issue auto-closes

**Every fix must address the root cause**, not just repair the data. The issue's `Prevention Fix` section specifies what code/prompt/convention change prevents recurrence. The `Verification Test` section specifies how to confirm the root cause is fixed.

## Schema Gap Reporting

See [`docs/schema-lifecycle.md`](schema-lifecycle.md) for the full schema gap detection, migration, and PR workflow.

Quick reference — file a gap:
```bash
uv run python local_resources/skilllog/skill_logger.py file-slog-schema-gap \
  --skill <skill-name> \
  --concept "<concept>" --missing "<what's absent>" --suggested "<fix>"
```

## External Skill Fixes Must Go Upstream

- **Fix code in the upstream repo, not just `local_skills/`** — External skills
  (`jobhunt`, `techrecon`, etc.) are cloned from `https://github.com/sciknow-io/alhazen-skill-examples`.
  If you fix a file only in `local_skills/`, `make skills-update` will overwrite it.
  Always push the fix upstream to `sciknow-io/alhazen-skill-examples` at the matching subdirectory
  (e.g., `skills/demo/jobhunt/schema.tql`) and commit there.
- **This applies to ALL skill files** — Python scripts, schemas, dashboard components, lib.ts,
  pages, and routes. The upstream repo at `~/Documents/GitHub/alhazen-skill-examples` is the
  local clone. Fix there, commit, push, then `make skills-update` to pull into this project.
- **jobhunt + techrecon schemas were 2.x** — Both were migrated to TypeDB 3.x in Mar 2026
  (commit `6b41acf` in alhazen-skill-examples). If a schema fails on `make build-db` with a
  syntax error near `sub attribute`, the upstream source likely still has 2.x syntax.

## Dashboard Design Conventions

- **Overview-first layout**: Main entity pages (investigations, systems) show a high-level orientation summary at the top. All detail sections are click-through — do not render full content inline.
- **Notes**: Always render as a collapsible list (type badge + extracted heading visible; full markdown expands on click). Never dump all note markdown on the page at once.
- **Workflows**: Always surface workflow links on any entity page that has associated workflows.
- **Hyperlink style**: All navigation links must be visually distinct from body text. Use `text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors` consistently for all `<Link>` and `<a>` elements in techrecon dashboard pages.

## Dashboard & Docker Rebuild

- **Dashboard API errors -> check skill Python scripts first** — The dashboard API routes
  (`/api/jobhunt/*`, `/api/techrecon/*`) call skill Python scripts via `child_process.execFile()`.
  If the dashboard shows "Failed to fetch data", check `docker logs alhazen-dashboard` for the
  actual TypeQL or Python error. The dashboard itself is usually fine — the skill script has the bug.
- **Docker build caching hides fixes** — After fixing files in `local_skills/`, `docker compose build`
  may use cached layers. Always use `docker compose build --no-cache dashboard` to ensure the
  fix is picked up. The full rebuild cycle:
  ```bash
  cd ~/Documents/GitHub/skillful-alhazen   # main repo, not worktree
  make skills-update                        # re-clone from upstream
  docker compose build --no-cache dashboard
  docker compose up -d dashboard
  ```
- **Dashboard page components vs API response format** — Skill dashboard page components
  (e.g., position detail page) may use `getValue()` helpers that expect TypeDB fetch format
  (`[{value: ...}]`), but `lib.ts` returns pre-extracted plain values (strings/numbers/nulls).
  When writing or fixing page components, check what format the API actually returns by
  curling the endpoint first: `curl -s http://localhost:3001/api/jobhunt/position/<id> | python3 -m json.tool`

## Skill Script Queries

- **Dump before accessing** — When a skill script's JSON output schema is unknown, do a raw
  dump first to confirm key names: `| python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin),indent=2))"`
  before writing any key-access post-processor.
- **Pipeline exit 1 != script failure** — In `script | python3 -c "..."`, exit code 1 almost
  always means the *post-processor* failed (KeyError, wrong key name), not the script itself.
  The script's `"success": true` in the output is the ground truth. Run the script alone to
  confirm, then fix the key names.
- **Canonical inspection one-liner:**
  ```bash
  uv run python .claude/skills/<skill>/<skill>.py <command> [args] 2>/dev/null \
      | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin),indent=2))"
  ```
