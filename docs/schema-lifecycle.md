# Schema Lifecycle

> How the Alhazen knowledge graph detects schema gaps, plans fixes, migrates data safely, and ships changes through human-reviewed PRs.

---

## Overview

The TypeDB schema grows organically from use. When a skill tries to express something the schema can't represent yet, that's a **schema gap** — not a crash, but a mismatch between what the knowledge work demands and what the current schema supports.

Schema gaps are signal, not noise. Filing the issue is the right response — not silently skipping the write or working around it in Python.

---

## Phase 1: Detect

Three detection paths:

### 1a. PostToolUse Hook (automatic)

The PostToolUse hook watches for TypeDB error codes in skill output:

```
[SYR1]  — type not found (missing entity/relation definition)
[TYR01] — invalid concept conversion
[FEX1]  — fetch expression error (e.g., fetching attribute from relation)
[INF2]  — type label not found
[INF11] — type-inference failure
```

When one appears, the hook prints a `[SCHEMA-GAP-HINT]` message prompting Claude to file immediately.

### 1b. Claude Recognizes It

During sensemaking, Claude realizes a concept can't be stored — e.g., a disease entity that can't play `aboutness:subject` because the relation isn't defined in the skill's schema. File immediately rather than waiting.

### 1c. Design Audit (proactive)

Periodic review of schema for unnecessary complexity, redundancy, or misalignment with how the system actually works. Example: discovering that position status was tracked via note indirection when a direct attribute would suffice.

---

## Phase 2: File

### CLI command

```bash
uv run python local_resources/skilllog/skill_logger.py file-slog-schema-gap \
  --skill <skill-name> \
  --concept "<concept Claude tried to represent>" \
  --missing "<which TypeDB entity/relation/attribute is absent>" \
  --suggested "<proposed TypeQL snippet, or 'unknown'>" \
  [--dry-run]
```

**What it does:**
1. Routes the issue to the correct GitHub repo (see Routing below)
2. Deduplicates: checks for existing open `gap:open` issues with the same concept
3. Builds a structured issue body
4. Runs `gh issue create` with the `gap:open` label

### Repo routing

```python
SKILL_REPO_MAP = {
    "dismech": "sciknow-io/alhazen-skill-dismech",
}
CORE_SKILLS = {"typedb-notebook", "web-search", "curation-skill-builder", "tech-recon"}

# Core skills -> GullyBurns/skillful-alhazen
# Mapped skills -> their specific repo
# Everything else -> sciknow-io/alhazen-skill-examples
```

### Issue body structure

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

### Labels

| Label | Meaning |
|-------|---------|
| `gap:open` | Filed, no fix started |
| `gap:in-progress` | Branch created, fix underway |
| `gap:pr-open` | Draft PR, awaiting review |
| `severity:minor / moderate / critical` | Impact level |
| `phase:entity-schema / source-schema / derivation / analysis` | Lifecycle phase |
| `skill:<name>` | Owning skill |

---

## Phase 3: Plan

### 3a. Save old schema

```bash
mkdir -p local_resources/typedb/migration-rules/<migration-name>/
cp local_skills/<skill>/schema.tql \
   local_resources/typedb/migration-rules/<migration-name>/old_schema.tql
```

### 3b. Write intent file

```yaml
# local_resources/typedb/migration-rules/<migration-name>/intent.md
description: "What this migration does and why"
removals:
  - type: <entity-or-attribute-name>
    reason: "Why it's being removed"
attribute_moves:
  - attribute: <attr>
    from: <old-type>
    to: <new-type>
    reason: "Why it's moving"
```

Note: Use `.md` extension (not `.yaml`) to avoid being parsed as a GLAV rule by `schema_mapper.py`.

### 3c. Choose migration method

See [Appendix C: Decision Tree](#appendix-c-when-to-use-which-method) for guidance.

#### Method A: In-place Mutation

Best for: additive changes, moving attributes between types that share data, removing types after data is deleted.

Steps:
1. Query existing data and write it to new locations (same DB, write transactions)
2. Delete obsolete entities/relations
3. `undefine` removed types (see [Appendix B](#appendix-b-typedb-3x-undefine-syntax))
4. `define` new owns/plays as needed

Advantages: No separate backup DB needed, no GLAV rules to write, simplest for small changes.

#### Method B: GLAV Rules

Best for: systematic renames, hierarchy restructuring, large-scale type consolidation.

Steps:
1. Edit schema.tql with desired changes
2. Generate rules: `uv run python src/skillful_alhazen/utils/schema_diff.py diff --old OLD.tql --new NEW.tql --generate-rules --rules-dir RULES_DIR/`
3. Hand-write custom rules for non-trivial transforms
4. Test iteratively with `make db-migrate-test RULES=RULES_DIR/`
5. Execute with `make db-migrate RULES=RULES_DIR/`

GLAV rule format:
```yaml
name: rule_name
description: "What this rule does"
depends_on: [other_rule_names]
idempotent: true
source_match: |
  match $x isa old-type, has id $id, has name $n;
  fetch { "id": $id, "name": $n };
target_insert: |
  match $existing isa new-type, has id $id;  # optional match for updates
  insert $x isa new-type, has id $id, has name $n;
skolem_keys: [id]
```

**Known limitation**: Auto-generated rules use `$x.attr` fetch syntax which returns no rows when the attribute is absent in TypeDB 3.x. For optional attributes, write custom rules using `has attr $var` in the match clause instead.

#### Method C: Binary Backup + Query Transfer

Best for: quick migrations, exploratory schema changes, or when GLAV rule-writing overhead isn't justified.

Steps:
1. `make db-export` (binary backup)
2. Import backup as temp source: `import-db --zip BACKUP.zip --database alhazen_backup`
3. Drop + recreate main DB with new schema: delete DB, `make db-init`
4. Query backup → insert into new DB (explicit attribute names, not `has $a` patterns)
5. Clean up backup DB

---

## Phase 4: Test

```bash
# GLAV method
make db-migrate-test RULES=local_resources/typedb/migration-rules/<name>/
# Iterate: fix rules, re-run until reconciliation passes
make db-migrate-test-clean   # when done

# In-place method
# Test against a cloned database first:
# 1. export, import as test DB, run mutations, verify
```

---

## Phase 5: Execute

### Start the fix (creates branch, updates issue)

```bash
uv run python local_resources/skilllog/skill_logger.py fix-gap \
  --issue <N> --repo <owner/repo>
```

Creates branch `fix/gap-N-<slug>`, labels issue `gap:in-progress`.

### Run the migration

```bash
# GLAV method
make db-migrate RULES=local_resources/typedb/migration-rules/<name>/

# In-place method
# Run the mutation script against production DB
```

### Apply code changes

Update all skill code that referenced the old schema:
- Python CLI commands (TypeQL queries)
- `embedding_map.py` (status/metadata queries)
- Dashboard views, pages, routes
- Forager scripts

---

## Phase 6: Ship

### Open a draft PR

```bash
uv run python local_resources/skilllog/skill_logger.py submit-gap-pr \
  --issue <N> --repo <owner/repo> \
  --decisions "brief description of key decisions made"
```

**What it does:**
1. Confirms commits ahead of `main`
2. Runs tests if available
3. Builds PR title: `fix(<skill>): <slug> (closes #N)`
4. Pushes branch, creates draft PR via `gh pr create --draft`
5. Labels issue `gap:pr-open`

### Human merge

The PR is always a **draft**. The human reviews, promotes to ready, and merges. This is the only step that cannot be automated — intentionally a human gate.

---

## Phase 7: Verify

Post-merge verification checklist:

1. Schema loads cleanly: `make db-init` on empty DB succeeds
2. Data completeness: migrated entity counts match source
3. No orphaned data: entities reference valid types
4. CLI smoke tests: key commands work with new schema
5. Dashboard displays correctly
6. Other skills unaffected: commands for unrelated skills still work
7. Removed types confirmed gone: querying them returns "type not found"

---

## Appendix A: GLAV Rule Format Reference

### Required fields

| Field | Description |
|-------|-------------|
| `name` | Unique identifier for this rule |
| `source_match` | TypeQL match + fetch query (runs against source DB) |
| `target_insert` | TypeQL insert (optionally with match prefix, runs against target DB) |
| `skolem_keys` | List of fetch variable names to hash for dedup/idempotency |

### Optional fields

| Field | Description |
|-------|-------------|
| `description` | Human-readable description |
| `depends_on` | List of rule names that must run first |
| `idempotent` | If true (default), skip entities with existing skolem_id |

### Skolem ID generation

```python
# Format: dm-{rule_name}-{sha256(key1|key2|...)[:12]}
payload = "|".join(str(v) for v in values)
digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
return f"dm-{rule_name}-{digest}"
```

### Variable substitution

- `$skolem_id` in target_insert is replaced with the computed deterministic ID
- All other `$variable` names are matched against fetch result keys
- Strings are quoted and escaped; numbers/booleans left bare

### Key commands

```bash
# Run migration
uv run python src/skillful_alhazen/utils/schema_mapper.py run \
  --source-db SOURCE --target-db TARGET --rules-dir RULES/

# Reconcile (count source vs target, report deltas)
uv run python src/skillful_alhazen/utils/schema_mapper.py reconcile \
  --source-db SOURCE --target-db TARGET --rules-dir RULES/

# Schema diff (summary)
uv run python src/skillful_alhazen/utils/schema_diff.py diff --old OLD.tql --new NEW.tql --summary

# Generate rules from diff
uv run python src/skillful_alhazen/utils/schema_diff.py diff \
  --old OLD.tql --new NEW.tql --generate-rules --rules-dir RULES/ [--intent INTENT.yaml]
```

---

## Appendix B: TypeDB 3.x undefine Syntax

TypeDB 3.8 uses a different `undefine` syntax than documented in some references:

```typeql
-- Remove an owns from a type:
undefine owns my-attribute from my-entity;

-- Remove a sub (supertype) from a type:
undefine sub parent-type from child-type;

-- Remove a type entirely (must have no instances, no sub-types):
undefine my-entity;

-- Remove an attribute type:
undefine my-attribute;
```

**Common errors:**
- `undefine entity X, owns Y;` -- INVALID in 3.8 (syntax error)
- `undefine X owns Y;` -- INVALID (expects "from" keyword)
- `undefine attribute X, value string;` -- INVALID

**Correct order for removing an entity type with owns:**
1. `undefine owns attr1 from my-entity;` (repeat for each owned attribute)
2. `undefine sub parent-type from my-entity;` (remove supertype)
3. `undefine my-entity;` (remove the vestigial type)

---

## Appendix C: When to Use Which Method

```
Is the change purely additive (new type, new owns)?
  YES -> define statement only, no migration needed
  NO  -> continue

Are you removing a type or attribute?
  YES -> Do instances of that type exist?
    YES -> Method A (in-place): query data, write to new location, delete old, undefine
    NO  -> Direct undefine (no migration needed)
  NO  -> continue

Are you renaming types/attributes or restructuring hierarchy?
  YES -> How many types are affected?
    1-3 types -> Method A (in-place mutation)
    4+ types with clear mappings -> Method B (GLAV rules)
    Complex/unclear mappings -> Method C (binary backup + query transfer)
  NO  -> continue

Are you moving attributes between types?
  YES -> Are both types populated?
    YES -> Method A (query old location, write to new, delete from old)
    NO  -> Method A (just add owns, define on new type)
```

**Rule of thumb:** Start with Method A unless the scale or complexity clearly demands B or C. Method A is the fastest to execute and easiest to verify. Method B produces an auditable rule set. Method C is the safety net when nothing else fits.

---

## Namespace Governance

Each skill declares its schema namespace in `skill.yaml`:

```yaml
schema:
  namespace: jhunt        # all types start with this prefix
  depends_on: []          # skill names whose schemas must load first
```

This compiles into `skills-registry.yaml` under `schema_map` (load_order + namespaces).

**Key commands:**
- `make db-audit` — reports namespace health: types, instances, orphans
- `make db-retire-skill SKILL=<name>` — removes a skill's schema + data (supports `--dry-run`)
- `validate-namespace --skill-dir <path>` — verifies type prefixes match declared namespace

**Namespace rules** (enforced by curation-skill-builder):
1. Every skill with `schema.tql` must declare a namespace in `skill.yaml`
2. Prefix is lowercase hyphenated (e.g., `jobhunt`, `tech-recon`)
3. All owned types must start with the namespace prefix
4. Cross-namespace `plays` clauses require `depends_on`
5. Core types (`domain-thing`, `collection`, `note`, etc.) are always available

---

## File Locations

| File | Purpose |
|------|---------|
| `local_resources/skilllog/skill_logger.py` | CLI: `file-slog-schema-gap`, `fix-gap`, `submit-gap-pr` |
| `src/skillful_alhazen/utils/schema_mapper.py` | GLAV migration engine |
| `src/skillful_alhazen/utils/schema_diff.py` | Schema diff + rule generation |
| `local_resources/typedb/migration-rules/` | Migration rule sets (one dir per migration) |
| `skills/curation-skill-builder/skill_builder.py` | `scaffold-improvement-loop`, `validate-namespace` |
| `scripts/db_retire_namespace.py` | Retire a skill's schema + data from live DB |
| `skills-registry.yaml` | Compiled `schema_map` with load order + namespace declarations |

---

## Design Principles

1. **Schema gaps are signal, not noise.** A gap means the knowledge work has outgrown the model.
2. **Issues as the interface.** GitHub issues are the unit of work — reviewable, discussable, linkable.
3. **Local execution only.** Schema changes require a running TypeDB for validation. GitHub Actions can't do this.
4. **Deduplication by default.** Same gap twice is common; filing it twice is noise.
5. **Draft PRs, human merges.** The merge gate is always human.
6. **Back up before destruction.** Always `make db-export` before any destructive schema operation.
