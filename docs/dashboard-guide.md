# Building a Skill Dashboard

Step-by-step guide for adding a dashboard to a skill. Follows the curation-skill-builder methodology (foraging → ingestion → sensemaking → analysis → **reporting**). The dashboard is the reporting layer.

## Architecture

Every skill dashboard has 4 layers:

```
Python CLI (skill script)          ← queries TypeDB, returns JSON
    ↓
TypeScript lib (lib.ts)            ← wraps CLI via child_process.execFile
    ↓
API routes (routes/)               ← thin Next.js handlers calling lib functions
    ↓
Pages (pages/)                     ← React components fetching from API routes
```

All 4 layers live in the skill's `dashboard/` directory:

```
skills/{name}/dashboard/           # or local_skills/{name}/dashboard/
├── lib.ts                         → dashboard/src/lib/{name}.ts
├── components/                    → dashboard/src/components/{name}/
├── pages/{name}/                  → dashboard/src/app/({name})/{name}/
│   └── page.tsx
│   └── detail/[id]/page.tsx
└── routes/                        → dashboard/src/app/api/{name}/
    └── stats/route.ts
    └── items/route.ts
```

`make build-dashboard` copies these into the Next.js app. **Never edit `dashboard/src/` directly** — those are generated copies.

## Step 1: Python CLI

Create `{skill_name}.py` in the skill directory with commands that query TypeDB and print JSON to stdout.

```python
#!/usr/bin/env python3
import argparse, json, os, sys

# IMPORTANT: Do NOT import from skillful_alhazen — it's not available in Docker.
# Inline any helpers you need.
def escape_string(s):
    """Escape special characters for TypeQL string literals."""
    if s is None: return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")

def cmd_stats(args):
    from typedb.driver import TransactionType
    driver = _get_driver()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        # ... queries ...
        pass
    print(json.dumps({"success": True, "count": 42}))

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stats")
    # ... more commands ...
    args = parser.parse_args()
    {"stats": cmd_stats}[args.command](args)

if __name__ == "__main__":
    main()
```

**Key rules:**
- Every command prints a single JSON object to stdout
- Never import from `skillful_alhazen.utils` — inline `escape_string` and any other helpers. The Docker container runs skill scripts via `uv run python` in an isolated venv that doesn't have the main project package.
- Always set `TYPEDB_DATABASE` default to `alhazen_notebook`
- Test with: `uv run python {script}.py stats`

## Step 2: TypeScript lib

Create `dashboard/lib.ts`:

```typescript
import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);
const SKILL_ROOT = process.env.MY_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'my_skill.py')
  : path.join(PROJECT_ROOT, '.claude/skills/my-skill/my_skill.py');

const CWD = SKILL_ROOT || PROJECT_ROOT;

async function runSkill(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', SCRIPT, ...args],
    {
      cwd: CWD,
      maxBuffer: 10 * 1024 * 1024,
      env: { ...process.env, TYPEDB_DATABASE: 'alhazen_notebook' },
    }
  );
  return JSON.parse(stdout);
}

// Type interfaces for responses
export interface Stats { diseases: number; /* ... */ }

// Exported functions
export async function getStats(): Promise<Stats> {
  return runSkill(['stats']) as Promise<Stats>;
}
```

**Key rules:**
- Always pass `TYPEDB_DATABASE: 'alhazen_notebook'` in the env
- Add TypeScript interfaces for all response shapes
- The script path resolves via `.claude/skills/{name}/` (where `make build-skills` symlinks it)

## Step 3: API Routes

Create route files under `dashboard/routes/`. Each is a thin wrapper:

```typescript
// dashboard/routes/stats/route.ts
import { NextResponse } from 'next/server';
import { getStats } from '@/lib/my-skill';

export async function GET() {
  try {
    const data = await getStats();
    return NextResponse.json(data);
  } catch (error) {
    console.error('stats error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
```

For dynamic routes with parameters:

```typescript
// dashboard/routes/item/[id]/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { getItem } from '@/lib/my-skill';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const decoded = decodeURIComponent(id);
  try {
    const data = await getItem(decoded);
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
```

**Note:** The lib import path is `@/lib/{skill-name}` (with hyphens, matching the filename that `make build-dashboard` creates).

## Step 4: Pages

Create pages under `dashboard/pages/{url-slug}/`. Use `'use client'` for interactivity.

```
dashboard/pages/
├── layout.tsx                    # metadata wrapper
└── my-skill/
    ├── page.tsx                  # browse/list page
    └── detail/[id]/page.tsx      # detail page
```

Layout is minimal:
```tsx
export const metadata = { title: 'My Skill' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
```

Pages fetch from API routes:
```tsx
'use client';
import { useState, useEffect, use } from 'react';

export default function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);  // Next.js 15+ async params
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch(`/api/my-skill/item/${encodeURIComponent(id)}`)
      .then(r => r.json())
      .then(setData);
  }, [id]);
  // ... render ...
}
```

## Step 5: Hub Card

Add your skill to `skills-registry.yaml` with a `dashboard:` block:

```yaml
- name: my-skill
  path: skills/my-skill    # or git: https://github.com/...
  dashboard:
    enabled: true
    name: My Skill
    description: What this dashboard shows.
    url_path: /my-skill     # matches the pages/ directory name
    icon: Dna               # Lucide icon name
    color: teal              # palette color
```

Then run `make build-dashboard` — this generates `dashboard/public/skills-config.json` which the hub page reads.

## Step 6: Wire and Test

```bash
make build-skills       # copies skill to local_skills/ and .claude/skills/
make build-dashboard    # wires dashboard files into Next.js app
cd dashboard && npm run dev   # start dev server
```

Verify:
1. `curl http://localhost:3000/api/{skill-name}/stats` returns JSON
2. Visit `http://localhost:3000/{url-slug}` — page renders
3. Click through to detail pages

## TypeDB Content Gotchas

### Escaped newlines in markdown

TypeDB stores string content with `\n` escaped as literal two-character sequences (`\` + `n`). When rendering with ReactMarkdown, the content appears as a wall of text with visible `\n` instead of line breaks.

**Always unescape before rendering:**

```tsx
// Helper — add to every file that uses ReactMarkdown
function unesc(s: string | undefined | null): string {
  return (s ?? '').replace(/\\n/g, '\n');
}

// Usage
<ReactMarkdown remarkPlugins={[remarkGfm]}>
  {unesc(note.content)}    {/* NOT: {note.content} */}
</ReactMarkdown>
```

If your skill uses a shared `MarkdownContent` component (like tech-recon's `atoms.tsx`), put the unescape there once:

```tsx
export function MarkdownContent({ content }: { content: string }) {
  const unescaped = content.replace(/\\n/g, '\n');
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
      {unescaped}
    </ReactMarkdown>
  );
}
```

### JSON content rendered as text

Analysis entities may store JSON arrays in their `content` field. The Python CLI maps `content` → `description` in API responses. If the page renders `description` as a `<p>` tag, large JSON blobs appear as unreadable walls of text.

**Skip paragraph rendering when content is JSON:**

```tsx
{analysis.description
  && !analysis.description.trimStart().startsWith('[')
  && !analysis.description.trimStart().startsWith('{')
  && (
    <p>{analysis.description}</p>
  )}
```

The `AnalysisRunner` component handles JSON content automatically — it parses it and renders as a table.

## Docker Compatibility

### No `skillful_alhazen` imports

Skill Python scripts run via `uv run python` inside Docker, which does NOT have the main project package installed. Any `from skillful_alhazen.utils.skill_helpers import ...` will fail with `ModuleNotFoundError`.

**Always inline helpers:**

```python
# BAD — breaks in Docker
from skillful_alhazen.utils.skill_helpers import escape_string

# GOOD — self-contained
def escape_string(s):
    if s is None: return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
```

### Rebuild cycle

After changing skill files:

```bash
make skills-update                          # pull from upstream repos
docker compose build --no-cache dashboard   # rebuild without cache
docker compose up -d dashboard              # restart
```

## Available UI Components

The dashboard uses shadcn/ui (dark theme) with Tailwind CSS v4:

- **Layout**: Card, Tabs, Table, Dialog, Separator
- **Interactive**: Button, Input, Select, Badge, Dropdown, Tooltip
- **Data display**: Progress, Table with sortable columns
- **Content**: ReactMarkdown + remarkGfm for markdown rendering
- **Charts**: @observablehq/plot (bar, scatter, heatmap), recharts, sigma (network graphs)
- **Icons**: lucide-react (Dna, Brain, Search, ArrowLeft, ExternalLink, etc.)
- **Utility**: `cn()` from `@/lib/utils` for class merging

Import from `@/components/ui/`:
```tsx
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
```

## Design Conventions

From the curation-skill-builder methodology:

- **Overview-first**: Main pages show stats cards + searchable list. Detail is click-through.
- **Notes as collapsible list**: Show topic badge + first line. Full markdown expands on click.
- **Color-coded badges**: Use `Record<string, string>` maps for status/category → Tailwind classes.
- **Pipeline views**: Show entities moving through states.
- **Matrix views**: Compare across dimensions.
- **Evidence links**: PMIDs link to `https://pubmed.ncbi.nlm.nih.gov/{id}`, HPO to `https://hpo.jax.org/browse/term/{id}`, MONDO to `https://purl.obolibrary.org/obo/{id}`.

## Reference Implementations

| Skill | Complexity | Good example of |
|-------|-----------|----------------|
| dismech-notebook | Medium | Browse + detail + tabbed sections + evidence |
| tech-recon | High | Multi-section investigation + analysis runner + source code viewer |
| jobhunt | High | Embedding map + pipeline board + skills matrix |
| agentic-memory | Medium | Schema browser + entity detail + graph visualization |
| coach | Medium | Metric cards + trend charts + recommendations |
