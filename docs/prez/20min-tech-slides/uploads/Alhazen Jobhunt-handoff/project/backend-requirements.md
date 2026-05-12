# Mission Control Dashboard — Backend Requirements

**Audience:** Claude Code instance maintaining `jobhunt.py` + the TypeDB schema.
**Context:** The Mission Control dashboard (Opportunity Dossier + pipeline views) reads exclusively via the `jobhunt.py` CLI. This document lists the schema and CLI changes the dashboard needs to render correctly. Changes are sized small on purpose — nothing here invents new concepts; we're extending existing patterns.

---

## TL;DR

- **2 new note entity types** (CC feedback + CC brief)
- **6 lines** in `cmd_add_note` and the two `show-*` commands to surface them
- **One new query block** in `show-position` / `show-opportunity` to return linked contacts
- **One new command** (`list-attention`) for the pipeline-level Triage Inbox — recommended, not strictly required
- No new relations. No new attributes on existing types.

---

## 1. Schema additions (`jobhunt.tql`)

Add two note subtypes. Both inherit `name`, `content`, `created-at` from `note`. No new attributes, no new relations.

```typeql
# CC's running interpretation of an opportunity. Most-recent one is "current."
entity jobhunt-cc-brief-note sub note;

# Operator's structured feedback to CC. Channel subscribes to writes of this type.
entity jobhunt-cc-feedback-note sub note;
```

**Channel trigger:** CC's ingestion process should subscribe to writes of `jobhunt-cc-feedback-note`. When the dashboard's "send to CC" composer fires, it writes a note of this type — that's the signal for CC to read, comprehend, and respond (typically by writing a new `jobhunt-cc-brief-note` and/or other notes back to the same opportunity).

---

## 2. CLI additions to `jobhunt.py`

### 2a. `cmd_add_note` — extend `type_map`

Add two entries so the dashboard can write the new note subtypes via the existing `add-note` command:

```python
type_map = {
    "research": "jobhunt-research-note",
    "interview": "jobhunt-interview-note",
    "strategy": "jobhunt-strategy-note",
    "skill-gap": "jobhunt-skill-gap-note",
    "fit-analysis": "jobhunt-fit-analysis-note",
    "interaction": "jobhunt-interaction-note",
    "application": "jobhunt-application-note",
    "cc-brief": "jobhunt-cc-brief-note",          # NEW
    "cc-feedback": "jobhunt-cc-feedback-note",    # NEW
    "general": "note",
}
```

And add `cc-brief` and `cc-feedback` to the `--type` argparse choices for `add-note`.

### 2b. `cmd_show_position` — extend `NOTE_TYPE_ATTRS`

Add the two new types so they're returned in the notes array with the same shape as other notes:

```python
NOTE_TYPE_ATTRS = {
    "jobhunt-application-note":   ["id", "name", "content", "application-status",
                                   "applied-date", "response-date"],
    "jobhunt-fit-analysis-note":  ["id", "name", "content", "fit-score", "fit-summary"],
    "jobhunt-interview-note":     ["id", "name", "content", "interview-date"],
    "jobhunt-interaction-note":   ["id", "name", "content", "interaction-type",
                                   "interaction-date"],
    "jobhunt-research-note":      ["id", "name", "content"],
    "jobhunt-strategy-note":      ["id", "name", "content"],
    "jobhunt-skill-gap-note":     ["id", "name", "content"],
    "jobhunt-cc-brief-note":      ["id", "name", "content"],   # NEW
    "jobhunt-cc-feedback-note":   ["id", "name", "content"],   # NEW
}
```

### 2c. `cmd_show_opportunity` — same extension

`cmd_show_opportunity` currently returns notes via a single generic query that doesn't preserve subtype. Mirror the per-subtype pattern from `cmd_show_position` so callers can distinguish CC notes from operator notes. Either:

- **Option A (preferred):** refactor `cmd_show_opportunity` to use the same `NOTE_TYPE_ATTRS` loop as `cmd_show_position`. Keeps the two commands consistent.
- **Option B:** keep the generic query but add a `type` field by querying the entity's TypeDB type label. Less invasive but exposes a different shape than `show-position`.

The dashboard prefers Option A — same JSON shape across both commands means one renderer.

### 2d. `cmd_show_position` and `cmd_show_opportunity` — return linked contacts

The dossier renders a contacts panel (recruiter, hiring manager, peers, referrers). This is a hard requirement; without it the timeline reads as disembodied events.

Add a contacts query block to both commands. Linkage is via `aboutness` (notes about the opportunity that mention contacts) or via a direct relation if one exists; below assumes contacts are linked through interaction-notes:

```python
# In cmd_show_position / cmd_show_opportunity, alongside the existing queries:
contacts_query = f'''match
    $p isa jobhunt-position, has id "{args.id}";       # or jobhunt-opportunity
    (note: $n, subject: $p) isa aboutness;
    $n isa jobhunt-interaction-note;
    (note: $n, subject: $person) isa aboutness;
    $person isa jobhunt-contact;
fetch {{
    "id": $person.id,
    "name": $person.name,
    "contact-role": $person.contact-role,
    "contact-email": $person.contact-email
}};'''
contacts_result = list(tx.query(contacts_query).resolve())
```

Add `"contacts": contacts_result` to the output dict. Deduplicate by `id` if a contact appears in multiple interaction-notes.

**Alternative if contacts are linked directly:** if there's (or you'd like to add) a `(opportunity, contact) isa <relation>`, query that instead. Simpler and faster than going through notes.

### 2e. `cmd_show_opportunity` — return tags for parity

`cmd_show_position` returns a `tags` array; `cmd_show_opportunity` doesn't. Add the same tags query block to `cmd_show_opportunity`. Cosmetic but the dashboard's renderer assumes parity.

---

## 3. Recommended (not required) — pipeline-level Triage Inbox

The pipeline view ("what needs my attention this week") wants, per opportunity:

- latest `jobhunt-cc-brief-note` timestamp (how stale is CC's read)
- count of `jobhunt-cc-feedback-note`s newer than the latest brief (operator has signaled, CC hasn't replied)
- `days-since-last-touch` — most recent note's `created-at`
- deadline (already on `jobhunt-opportunity`)
- status, priority (already returned by `list-opportunities`)

Today the dashboard would N+1 this by calling `list-opportunities` + `show-opportunity` per row. A single endpoint:

```
list-attention [--type position|engagement|venture|lead|all]
              [--since <date>]
```

Returns one row per opportunity with the fields above. ~30 lines, two TypeDB queries (one for opportunities, one for the per-opp note aggregates) joined client-side or via a single match-fetch.

Defer if you want; the dashboard will work via N+1 in the meantime.

---

## 4. Out of scope for v2

Listing these so they don't get conflated with the requirements:

- **`supersedes` relation** between briefs / notes — not needed. Most-recent-by-`created-at` is sufficient for "current brief."
- **`author` attribute** on `note` — not needed. CC vs. operator authorship is implicit in the entity type.
- **`confidence` attribute** on CC inferences — defer until we see a UX need.
- **`cc-proposal-note` subtype** for next-actions — interesting but deferred. v2 treats CC's proposed actions as bullet points inside the brief content rather than separate entities.
- **Provenance relation** linking CC notes back to the operator notes they were derived from — defer. Could be added later as `(derived-from: $cc-note, source: $op-note) isa derivation` without changing the dashboard.

---

## 5. Quick checklist for the backend CC

- [ ] Add `jobhunt-cc-brief-note sub note;` and `jobhunt-cc-feedback-note sub note;` to the schema.
- [ ] Extend `cmd_add_note` `type_map` and argparse choices with `cc-brief` and `cc-feedback`.
- [ ] Extend `cmd_show_position` `NOTE_TYPE_ATTRS` with the two new types.
- [ ] Refactor `cmd_show_opportunity` to use per-subtype note queries (mirror `cmd_show_position`).
- [ ] Add a `contacts` query block to both `cmd_show_position` and `cmd_show_opportunity`; include `"contacts": [...]` in the response.
- [ ] Add a `tags` query block to `cmd_show_opportunity` for parity.
- [ ] Configure CC's channel to fire on writes of `jobhunt-cc-feedback-note`.
- [ ] *(Optional)* Add `cmd_list_attention` for the pipeline Triage Inbox.

Everything else the dashboard needs is already returned by the existing CLI.
