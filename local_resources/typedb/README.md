# local_resources/typedb — TypeDB Schema Infrastructure

This directory holds the **foundational schema** and **reference documentation** for the Alhazen knowledge graph. It is shared infrastructure, not a skill.

---

## Why the core schema lives here (not in a skill)

Each Alhazen skill owns its own `schema.tql` (e.g. `local_skills/jobhunt/schema.tql`). Those files define domain extensions that are loaded *after* the core schema and depend on types it defines.

`alhazen_notebook.tql` is different: it defines the abstract type hierarchy (`identifiable-entity`, `domain-thing`, `collection`, `information-content-entity`) that **every skill's schema extends**. The Makefile reflects this by loading it explicitly first, before any skill schemas are discovered:

```makefile
# db-init load order (from Makefile):
# 1. local_resources/typedb/alhazen_notebook.tql   ← always first (hardcoded)
# 2. local_skills/*/schema.tql                     ← skill extensions (glob)
# 3. local_resources/typedb/namespaces/*.tql        ← namespace stopgaps (see below)
```

Moving `alhazen_notebook.tql` into a skill directory would make it a peer of the schemas that depend on it, with undefined load order. Its home here is intentional.

---

## Files

| File | Purpose |
|------|---------|
| `alhazen_notebook.tql` | Core schema — the foundation loaded first by `make build-db` |
| `namespaces/skilllog.tql` | Skill invocation logging types — infrastructure with no skill home |
| `llms.txt` | TypeDB 3.x cheat sheet — read on demand before writing queries |
| `typedb-3x-reference.md` | Full TypeDB 3.x reference (generated from official docs) |
| `generate_schema_docs.py` | Regenerates `docs/` from the loaded schema |
| `migrate_schema_v2.py` | 2.x → 3.x migration utility (migration complete Feb 2026, kept for reference) |
| `docs/` | Auto-generated schema documentation (`make docs-typedb` to regenerate) |

---

## Core Schema Hierarchy

The three-branch hierarchy rooted at `identifiable-entity`:

```
identifiable-entity (abstract)         — id @key, name, description, created-at, provenance
├── domain-thing                        — real-world objects (papers, genes, jobs, skills)
├── collection                          — typed sets (corpora, searches, case files)
└── information-content-entity (abstract) — content-bearing entities
    ├── artifact                        — raw captured content (PDF, HTML, API response)
    ├── fragment                        — extracted piece of an artifact
    └── note                            — Claude's analysis or annotation
```

Skill schemas add subtypes. For example, `jobhunt/schema.tql` defines `jobhunt-position sub domain-thing` and `jobhunt-application-note sub note`.

---

## Loading the schema

```bash
make build-db       # start TypeDB container + load all schemas in correct order
make db-init        # load schemas only (container must already be running)
```

Do not load schemas manually via TypeDB console — the Makefile handles ordering correctly.

---

## namespaces/ — Stopgap schemas

Files in `namespaces/` are schemas that lack a proper skill home:

- **`skilllog.tql`** — skill invocation logging; no external skill repo, lives here permanently.

---

## Reference documentation

**Before writing TypeDB queries**, read:
- `llms.txt` — quick reference for TypeDB 3.x syntax (fetch, define, delete, relations)
- `typedb-3x-reference.md` — full reference if llms.txt is insufficient

Full reference is also in CLAUDE.md under "TypeDB 3.x Query Notes".
