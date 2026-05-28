# Single Paper Deep Dive — Command Reference

## Commands

### `new-analysis` — Start a new paper analysis

```bash
uv run python single_paper_deep_dive.py new-analysis \
  --doi DOI \
  --title "Full Paper Title" \
  [--year YYYY] \
  [--paper-type research|review|meta-analysis|preprint|book-chapter]
```

Creates a new `dive-analysis` in TypeDB. If an analysis already exists for the DOI, returns the existing record without modification.

**Returns:** `{"success": true, "analysis_id": "dive-...", "doi": "...", "title": "...", "status": "in-progress"}`

---

### `add-claim` — Add a claim to an analysis

```bash
uv run python single_paper_deep_dive.py add-claim \
  --analysis-doi DOI \
  --type primary|secondary|peripheral \
  --statement "Precise, falsifiable claim text"
```

**Returns:** `{"success": true, "claim_id": "claim-...", "type": "...", "statement": "..."}`

**Note:** The `--statement` text is stored verbatim. Use it exactly in subsequent `add-evidence` calls.

---

### `add-evidence` — Add evidence for a claim

```bash
uv run python single_paper_deep_dive.py add-evidence \
  --analysis-doi DOI \
  --claim-statement "EXACT claim text as stored" \
  --evidence-type experimental|observational|computational|review|theoretical|anecdotal \
  [--source-doi DOI] \
  [--source-title "Source paper title"] \
  [--source-url URL] \
  [--experimental-design "Design description"] \
  [--data-summary "Actual data / results"]
```

**Returns:** `{"success": true, "evidence_id": "ev-...", "evidence_type": "...", "source_doi": "...", "source_title": "..."}`

**Important:** `--claim-statement` must match the stored claim exactly (case-sensitive). If the match fails, the command prints an error and exits 1.

---

### `add-citation-impact` — Record how a citing paper relates to the focal paper

```bash
uv run python single_paper_deep_dive.py add-citation-impact \
  --analysis-doi DOI \
  --citing-doi DOI \
  --citing-title "Citing paper title" \
  --impact-type supports|refutes|extends|nuances|uses|unrelated \
  --impact-summary "1-2 sentence description"
```

**Returns:** `{"success": true, "impact_id": "impact-...", "citing_doi": "...", "impact_type": "..."}`

---

### `complete-analysis` — Mark an analysis as complete

```bash
uv run python single_paper_deep_dive.py complete-analysis \
  --doi DOI \
  [--source-count N] \
  [--scope-note "What was/wasn't covered"] \
  [--status complete|scope-exhausted]
```

Updates `dive-analysis-status` in TypeDB. Default status is `complete`; use `scope-exhausted` if the 100-source limit was reached.

**Returns:** `{"success": true, "doi": "...", "status": "...", "source_count": N}`

---

### `get-analysis` — Retrieve full analysis

```bash
uv run python single_paper_deep_dive.py get-analysis --doi DOI
```

Returns the full analysis including all claims (with their evidence) and all citation impacts.

**Returns:**
```json
{
  "success": true,
  "analysis": {
    "id": "dive-...",
    "doi": "...",
    "title": "...",
    "year": 2023,
    "paper_type": "research",
    "status": "complete",
    "source_count": 47,
    "scope_note": "...",
    "claims": [
      {
        "id": "claim-...",
        "type": "primary",
        "statement": "...",
        "evidence": [
          {
            "id": "ev-...",
            "evidence_type": "experimental",
            "experimental_design": "...",
            "data_summary": "...",
            "source_doi": "...",
            "source_title": "...",
            "source_url": null
          }
        ]
      }
    ],
    "citation_impacts": [
      {
        "id": "impact-...",
        "impact_type": "extends",
        "impact_summary": "...",
        "citing_doi": "...",
        "citing_title": "..."
      }
    ]
  }
}
```

---

### `list-analyses` — List all stored analyses

```bash
uv run python single_paper_deep_dive.py list-analyses
```

**Returns:** `{"success": true, "count": N, "analyses": [{"doi": "...", "title": "...", "status": "...", ...}]}`

---

### `export-analysis` — Export as formatted markdown or JSON

```bash
uv run python single_paper_deep_dive.py export-analysis --doi DOI [--format md|json]
```

`--format md` (default): Returns a formatted markdown document suitable for presenting to the user.
`--format json`: Returns the same JSON as `get-analysis`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TYPEDB_HOST` | `localhost` | TypeDB server host |
| `TYPEDB_PORT` | `1729` | TypeDB server port |
| `TYPEDB_DATABASE` | `alhazen_notebook` | Database name |
| `TYPEDB_USERNAME` | `admin` | TypeDB username |
| `TYPEDB_PASSWORD` | `password` | TypeDB password |

## TypeDB Schema (dive namespace)

| Type | Kind | Description |
|---|---|---|
| `dive-analysis` | entity (sub alh-collection) | Root analysis record for a paper |
| `dive-claim` | entity (sub alh-note) | A single claim extracted from the paper |
| `dive-evidence` | entity (sub alh-note) | Evidence supporting a claim |
| `dive-citation-impact` | entity (sub alh-note) | Record of how a citing paper relates to the focal paper |
| `dive-analysis-has-claim` | relation | Links analysis to its claims |
| `dive-claim-has-evidence` | relation | Links claim to its evidence items |
| `dive-evidence-cites-source` | relation | Links evidence to an alh-artifact source |
| `dive-analysis-cited-by` | relation | Links analysis to citation impact records |
