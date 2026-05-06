# Agentic Memory Dashboard Redesign

## Context

The current agentic-memory dashboard has three disconnected pages (persons overview, person detail, graph browser) with generic Tailwind styling. The information architecture doesn't match how the system is actually used — it splits by entity kind (persons, claims, episodes) rather than organizing around the schema that structures all knowledge.

This redesign replaces the existing dashboard with a **Dual-Pane Knowledge Explorer** that makes the agent's "mind" legible: what it knows, how the knowledge is structured, what it learned per session, and how entities connect across namespaces. The primary audience is anyone who wants to understand how the agentic memory system works — operator, demo viewer, or collaborator.

## Architecture: Dual-Pane Knowledge Explorer

**Single page** with a persistent left schema tree and an adaptive right content pane.

### Left Pane — Schema Tree (280px fixed)

Always-visible namespace-organized type hierarchy:

- **Header:** "Alhazen Notebook" title + global stats (total entities, namespace count)
- **Search field:** Filters the tree by type name
- **Namespace nodes** (top-level, collapsible):
  - `alh` (teal #5aadaf) — core schema, badge: CORE
  - `jhunt` (blue #5b8ab8) — jobhunt skill, badge: SKILL
  - `trec` (olive #b8c84a) — tech-recon skill, badge: SKILL
  - `nbmem` (mint #62c4bc) — agentic memory OS, badge: OS
  - `scilit` (default #8ba4b8) — scientific literature, badge: SKILL
  - `slog` (rust #c87a4a) — skill logging OS, badge: OS
  - `sltrend` — literature trends, badge: SKILL
  - `dm` — dismech, badge: SKILL
- **Entity type nodes** (nested under namespace): Show type name + instance count. Colored dot indicates namespace. Click selects the type, showing its instances in the right pane.
- **"unknown" namespace:** Legacy pre-prefix types (e.g., `agent`, `collection`, `note`) that haven't been migrated to `alh-` prefixed names yet. Shown dimmed with label "legacy" — these have 0 instances in the current database and exist only as schema artifacts.
- **Collapsed namespaces** show aggregate instance count.

### Right Pane — Adaptive Content

Changes based on current selection state:

#### 1. Overview Mode (no selection — home state)

**Namespace health cards** in a 3-column grid:
- Each card shows: namespace label (colored, mono), badge (CORE/OS/SKILL), instance count (large), entity type count + relation count, density bar (relative population)
- Empty namespaces rendered at 0.6 opacity — visible gaps at a glance
- Clicking a card expands that namespace in the left tree

**Recent Agent Activity** feed below the cards:
- Sourced from `alh-episode` entities
- Each row: namespace-colored dot, episode title, summary snippet, relative timestamp
- Clicking an episode navigates to its detail view

#### 2. Global Search (Cmd+K)

A search bar at the top of the right pane, always accessible:
- **Text mode** (default): Matches entity name/id across all types. Results grouped by type with namespace color.
- **Semantic mode** (toggle): Uses Qdrant-backed embedding search via `agentic_memory.py search`. Returns ranked results with similarity scores.
- Results are clickable, navigating to entity detail view.

#### 3. Type Browser (type selected in schema tree)

- **Header:** Full type name (serif, 22px) + instance count + description
- **Subtype list** if any (clickable, with counts)
- **Instance table:** Sortable columns (name, description, subtype, last touched). Rows clickable to navigate to entity detail.
- **Pagination/infinite scroll** for types with many instances (e.g., alh-artifact: 584)

#### 4. Entity Detail (instance selected)

**Header:** Entity name (serif, 24px) + type badge (namespace-colored) + ID (mono) + created/updated timestamps.

**Breadcrumb bar** above header: `namespace / type / entity-name` with namespace coloring.

**Four tabs:**

##### Attributes Tab
- **Context Domains** (operator-user only): 6 collapsible cards (Identity, Role, Goals, Preferences, Expertise, Communication Style). Expanded shows full text; collapsed shows preview snippet. Labeled with mint mono headers.
- **Attributes table:** Key-value grid for all owned attributes. Keys in mono, values with smart rendering (URLs become links, dates as relative, long text truncates with expand).
- **Type-aware rendering:** Different entity types get different domain-specific groupings above the raw attributes table. Generic entities show attributes table only.

##### Relations Tab
- Connected entities **grouped by relation type**.
- Each group header: relation name (namespace-colored, mono, uppercase), role direction arrow (employee → employer), count.
- Each connected entity: namespace-colored dot, entity name, type label (mono), ID, chevron for navigation.
- **Clickable navigation:** Clicking any entity navigates to its detail view, updating the breadcrumb and schema tree highlight.
- **Relation-owned attributes** shown inline (confidence scores, fact-type badges on memory claims).

##### Claims Tab
- Memory claim notes linked to this entity via `alh-aboutness`.
- Each claim: title, fact-type badge (knowledge=olive, decision=teal, goal=blue, preference=blue, schema-gap=rust), confidence score, content preview, timestamp.
- Expandable to show full claim content + provenance (source episode/note via `nbmem-fact-evidence`).

##### Episodes Tab
- **Vertical timeline** with a 1px rail and namespace-colored dots.
- **Month headers** on the rail for temporal grouping ("May 2026", "April 2026").
- **Date labels** left of the rail next to each episode dot ("May 2", "Apr 28").
- **Episode cards:** Skill badge (namespace-colored), time-only in header, narrative summary, highlighted operation box showing what happened to *this* entity (created/updated/analyzed badge + rationale).
- **"Also touched" chips:** Other entities modified in the same episode, clickable with per-entity operation type.
- **Filtered view:** Only shows episodes mentioning this entity.

## Visual Design — Starry Night Tokens

Typography:
- Sans: "DM Sans" — primary UI text
- Serif: "DM Serif Display" — entity names, page titles
- Mono: "JetBrains Mono" — type labels, IDs, metadata, section headers

Color palette:
- Background: `bg` #070d1c, `bgRaised` #0c1628, `bgSunken` #050a16
- Panels: `panel` rgba(12, 22, 40, 0.72), `panelHi` rgba(20, 34, 58, 0.85)
- Text: `fg` #c8dde8, `fgDim` #8ba4b8, `fgFaint` #5e7387
- Borders: `border` rgba(90, 173, 175, 0.18), `borderHi` rgba(90, 173, 175, 0.42), `borderDim` rgba(200, 221, 232, 0.08)

Namespace semantic colors:
- `alh` teal #5aadaf, `jhunt` blue #5b8ab8, `trec` olive #b8c84a
- `nbmem` mint #62c4bc, `slog` rust #c87a4a
- Remaining namespaces: fgDim #8ba4b8

Interactive states:
- Hover: rgba(90,173,175,0.06) background
- Active border: borderHi opacity
- Transitions: 0.12-0.18s cubic-bezier(.2,.7,.3,1)

Border radius: 3-4px (subtle, not rounded). Scrollbar: 10px thumb with teal at 0.18 opacity.

## Data Sources

All data fetched via API routes that invoke `agentic_memory.py` CLI commands:

| API Route | CLI Command | Purpose |
|-----------|-------------|---------|
| `/api/agentic-memory/schema` | `describe-schema --full` | Schema tree with instance counts |
| `/api/agentic-memory/schema?audit=true` | `describe-schema --audit` | Namespace groupings |
| `/api/agentic-memory/entity/[id]` | `query --typeql "match..."` | Entity attributes |
| `/api/agentic-memory/entity/[id]/neighbors` | `query --typeql "match..."` | Connected entities by relation |
| `/api/agentic-memory/facts` | `list-claims` | Memory claims |
| `/api/agentic-memory/episodes` | `list-episodes` | Episode list |
| `/api/agentic-memory/context` | `get-context --person [id]` | Operator context domains |
| `/api/agentic-memory/search` | `search --query "..."` | Semantic search |

## Files to Modify/Create

**Delete entirely** (replaced by new single-page app):
- `dashboard/src/app/(agentic-memory)/agentic-memory/page.tsx`
- `dashboard/src/app/(agentic-memory)/agentic-memory/person/[id]/page.tsx`
- `dashboard/src/app/(agentic-memory)/agentic-memory/graph-browser/page.tsx`
- `dashboard/src/components/graph-browser/` (all files: schema-tree.tsx, instance-search.tsx, sigma-graph.tsx, entity-detail-panel.tsx, graph-controls.tsx)

**Create new:**
- `dashboard/src/app/(agentic-memory)/agentic-memory/page.tsx` — single-page shell with left/right pane layout
- `dashboard/src/components/agentic-memory/schema-tree.tsx` — namespace-organized collapsible tree
- `dashboard/src/components/agentic-memory/overview-panel.tsx` — namespace health cards + activity feed
- `dashboard/src/components/agentic-memory/type-browser.tsx` — instance table with sort/filter
- `dashboard/src/components/agentic-memory/entity-detail.tsx` — tabbed detail view shell
- `dashboard/src/components/agentic-memory/attributes-tab.tsx` — context domains + raw attributes
- `dashboard/src/components/agentic-memory/relations-tab.tsx` — grouped connected entities
- `dashboard/src/components/agentic-memory/claims-tab.tsx` — memory claims list
- `dashboard/src/components/agentic-memory/episodes-tab.tsx` — timeline with date markers
- `dashboard/src/components/agentic-memory/global-search.tsx` — text + semantic search

**Modify:**
- `dashboard/src/lib/agentic-memory.ts` — add any missing data fetching functions (most already exist)

**Keep unchanged:**
- All API routes in `dashboard/src/app/api/agentic-memory/` — the existing routes already cover all needed data

## Verification

1. **Schema tree:** Run `make status` to confirm TypeDB is running. Open dashboard, verify all namespaces appear with correct instance counts matching `describe-schema --full` output.
2. **Type browser:** Click `alh-person` in schema tree. Verify 107 instances appear in the table. Click a row to navigate to detail.
3. **Entity detail:** Navigate to the operator-user. Verify all 6 context domains render. Switch to Relations tab — verify connected entities match `get-context` output. Switch to Episodes tab — verify timeline renders with date markers.
4. **Search:** Test text search for "Gully" — should find operator-user. Toggle to semantic mode, search "vector database" — should return relevant tech-recon entities.
5. **Visual fidelity:** Compare against Starry Night tokens — dark background, namespace colors, DM Sans/Serif/Mono typography, 3-4px border radius, correct hover states.
