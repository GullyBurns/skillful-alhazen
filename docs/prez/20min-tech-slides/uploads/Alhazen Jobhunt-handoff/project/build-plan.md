# Build plan — In Play dashboard

How to map the dashboard at `Opportunity Dossier.html` onto the
`alhazen-jobhunt` repo. Written so you can hand the whole thing to a
contributor (or to Claude Code) and ship it in roughly that order.

The dashboard is intentionally thin: it consumes two CLI endpoints,
both of which already exist in some form. The schema delta is **two
new note subtypes**. Everything else is plumbing.

---

## 0. Mental model (one paragraph)

Each opportunity is a **lead** — a campaign in progress, opened
deliberately, worked over time. CC writes **briefs** (`cc-brief-note`)
that summarize where you stand and what to do next. You write **feedback**
(`cc-feedback-note`) when you want to push back, redirect, or correct
CC's read. Writing feedback fires CC's channel, which causes CC to
re-read the dossier and emit a fresh brief. The dashboard is the
operator-side view of this loop, plus the rest of the existing notes
(application, interaction, fit-analysis, research, strategy) rendered
chronologically.

---

## 1. Schema delta — `jobhunt.tql`

```typeql
# Two new note subtypes. Both inherit name, content, created-at from note.
entity jobhunt-cc-brief-note    sub note;
entity jobhunt-cc-feedback-note sub note;
```

That is the entire schema change. No new attributes. No new relations.
Both are linked to the opportunity via the existing `aboutness` relation.

**Migration**: zero. Existing data unaffected; we just add two new types.

---

## 2. CLI delta — `jobhunt.py`

### 2a. `add-note` — accept the two new subtypes

In whatever map turns a `--type` value into an entity name (`type_map`
or similar), add two entries:

```python
type_map = {
    # ...existing entries...
    'cc-brief':    'jobhunt-cc-brief-note',
    'cc-feedback': 'jobhunt-cc-feedback-note',
}
```

Both have no type-specific attributes, so `NOTE_TYPE_ATTRS` gets two
empty entries (or whatever structure is in use):

```python
NOTE_TYPE_ATTRS = {
    # ...existing entries...
    'jobhunt-cc-brief-note':    [],
    'jobhunt-cc-feedback-note': [],
}
```

**Acceptance**: `python jobhunt.py add-note --type cc-brief --about <opp-id> --content "..."`
runs and creates a `jobhunt-cc-brief-note` linked to the opportunity.

### 2b. `show-opportunity` — return the new note types in `notes[]`

This is the polymorphic command (already routes by opportunity type to
`show-position` / `show-engagement` / `show-venture` / `show-lead`).
Whatever query collects notes via `aboutness` should already return them
once the new types exist — but **double-check** the query doesn't whitelist
specific note subtypes. If it does, add the two new types.

The JSON shape per note must be:

```json
{
  "id": "n-...",
  "type": "jobhunt-cc-brief-note",
  "name": "Brief · phone screen prep window",
  "content": "...",
  "created_at": "2026-04-30T09:00:00Z"
}
```

Type-specific attributes (e.g. `application_status`, `fit_score`,
`contact_name`) appear as top-level keys on note objects whose `type`
warrants them. The dashboard already handles missing attrs gracefully.

**Acceptance**: `show-opportunity --json <pos-id>` returns notes including
the two new types, sorted (or sortable) by `created_at`.

### 2c. `list-attention` — implement / extend

If this command doesn't exist yet, add it. Shape per opportunity:

```json
{
  "id": "pos-augura-staff-mle",
  "name": "Staff ML Engineer, Biomedical AI",
  "type": "jobhunt-position",
  "status": "phone-screen",
  "priority": "high",
  "deadline": "2026-05-06T12:00:00Z",
  "company": { "id": "co-augura", "name": "Augura Health" },
  "latest_cc_brief": "2026-04-30T09:00:00Z",
  "pending_feedback_count": 0,
  "days_since_last_touch": 0
}
```

Field-by-field:

- `latest_cc_brief` — `created_at` of the most recent `jobhunt-cc-brief-note`
  linked to this opportunity. `null` if none.
- `pending_feedback_count` — count of `jobhunt-cc-feedback-note`s with
  `created_at > latest_cc_brief` (or all of them, if `latest_cc_brief` is null).
  This is the metric that says "CC owes you a re-read."
- `days_since_last_touch` — days since the most recent note of *any* type
  (or most recent status change). Rounded down. `0` for today.

Sort order: priority (`high` → `medium` → `low`), then `days_since_last_touch`
ascending (freshest first within a priority bucket).

Filter: only opportunities with active status — i.e. exclude `rejected`,
`withdrawn`, `closed-won`, `closed-lost`. The exact set depends on the
status vocabulary per kind.

**Acceptance**: `list-attention --json` returns an array shaped exactly
as above, sorted as above.

### 2d. CC channel subscription

`cc-feedback-note` writes need to fire CC's channel so CC can re-read and
emit a fresh `cc-brief-note`. If channels subscribe by entity type, just
add `jobhunt-cc-feedback-note` to CC's subscription list. If by event,
ensure the event payload includes the entity type so CC can filter.

This is the only behavioral change — the rest is read-side rendering.

---

## 3. Front-end integration

The dashboard is a single HTML file plus five JSX modules. To ship it
inside an existing app, two paths:

### Option A — embed as-is (fastest)
Drop `Opportunity Dossier.html` and its `.jsx` siblings under `static/`,
serve at e.g. `/dashboard/in-play`. Replace the mock layer in `data.jsx`
with a small fetch wrapper:

```js
window.api = {
  showOpportunity: async (id) => (await fetch(`/api/opportunity/${id}`)).json(),
  listAttention:   async ()   => (await fetch(`/api/attention`)).json(),
};
```

…and change the `App` component to `await` those calls (currently it
calls them synchronously, which works because the mock is sync).

The two `/api` endpoints are thin shims around the CLI commands — call
`jobhunt.py show-opportunity --json <id>` and `jobhunt.py list-attention --json`,
return the JSON. Or wire them directly to the underlying TypeDB queries.

### Option B — port to your existing front-end
The five JSX files are framework-agnostic React components. Lift them
into your real app's component tree. The only globals they touch are
`window.TOKENS` (palette), `window.Icon` (inline SVGs), and `window.api`
(the data layer above). Replace the `window.*` references with normal
imports.

**Recommend**: Option A first, to get it in front of users. Port later
if/when the dashboard accretes more views.

---

## 4. Suggested merge order

1. **PR 1 — schema + CLI write path.** Add the two entity types to
   `jobhunt.tql`. Add the two `type_map` entries. Verify
   `add-note --type cc-brief` and `add-note --type cc-feedback` write
   successfully and round-trip via `show-opportunity`. Tests: assert each
   new note type appears in the `notes[]` array of `show-opportunity`.
2. **PR 2 — CC channel.** Subscribe CC to `jobhunt-cc-feedback-note`
   writes. Manually verify: writing a feedback note triggers a fresh
   brief.
3. **PR 3 — `list-attention`.** Implement (or extend) the command with
   the shape above, including the `latest_cc_brief` and
   `pending_feedback_count` derivations. Tests: assert sort order,
   assert active-only filter, assert metrics computed correctly with and
   without briefs/feedback.
4. **PR 4 — dashboard.** Embed via Option A. Replace `data.jsx` with
   the fetch wrapper. Smoke-test against a real notebook.
5. **PR 5 — polish.** Loading states, empty states, real `TODAY`
   instead of the hard-coded mock date in `daysAgo`/`fmtTimestamp`.

PR 1 + 2 are independently shippable — they unblock CC writing briefs
in the existing chat UI, which is useful even before the dashboard
lands.

---

## 5. Open questions

- **Status vocabulary per kind.** The dashboard renders whatever string
  comes back in `opportunity.status`. If you want a constrained vocabulary
  (e.g. `researching | applied | phone-screen | ...` for positions vs.
  `scoping | contracted | delivering | wrapped` for engagements), that's
  a separate schema decision. Defer.
- **Brief revision semantics.** Currently the dashboard treats the most
  recent `cc-brief-note` as canonical and shows older ones as history.
  This is fine, but if you later want explicit "this brief supersedes
  that one" semantics, add a `supersedes` relation. Don't add it
  preemptively.
- **Contacts query in `show-opportunity`.** The dashboard expects a
  `contacts[]` array. If `show-opportunity` doesn't currently return
  contacts, add a sub-query: union of `jobhunt-contact`s linked via
  `interaction-note → contact_name` and via a `works-at` relation to the
  opportunity's company. (You may have already done this — verify.)
- **Attention threshold tuning.** The dashboard groups leads into "Fresh
  from CC / Your move / Waiting" using thresholds (brief age ≤3d, last
  touch >7d). These live in `triage-inbox.jsx#bucket()`. Worth tuning
  with real data after a week of use.
- **Lead kind in the dashboard.** Today the dashboard renders position,
  engagement, venture. `jobhunt-lead` is in the schema but not yet wired
  in. It would render fine — same shell, no requirements panel — but the
  `In play` inbox will show leads the dashboard can't open. Either
  build the lead dossier or filter leads out of `list-attention` until
  the operator promotes them to a real opportunity.

---

## 6. What I'd build first

If the goal is "ship the smallest useful slice":

1. PR 1 (schema + write path).
2. CC starts writing briefs in chat or via direct CLI calls. No
   dashboard yet. Operators read briefs from the existing notes view.
3. PR 2 (CC channel) so the feedback loop actually closes.
4. Then PR 3+4 to put the dashboard in front of it.

That ordering means CC's brief-writing behavior gets exercised
*before* the UI exists, so by the time the dashboard ships you have
real briefs to render and have already iterated on tone/length/format.

---

*End of plan.*
