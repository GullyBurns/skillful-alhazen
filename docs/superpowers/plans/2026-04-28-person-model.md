# Unified Person & Organization Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the core `person` and `organization` entities, add a first-class `interaction` entity, align jobhunt's contact/company types to inherit from core, and support email/calendar artifact integration.

**Architecture:** Three schema files change: core `alhazen_notebook.tql` (new attributes, enriched person/organization, new interaction entity + relation, works-at promoted from jobhunt), agentic-memory `schema.tql` (remove redundant plays declarations), and jobhunt `schema.tql` (jobhunt-contact sub person, jobhunt-company sub organization, remove duplicated definitions). A migration script exports existing data and re-inserts under the new hierarchy.

**Tech Stack:** TypeDB 3.x (TypeQL define/redefine), Python (typedb-driver), existing Makefile targets (`make db-init`).

**Spec:** `docs/superpowers/specs/2026-04-28-person-model-design.md`

---

### Task 1: Export existing data before schema changes

**Files:**
- Create: `scripts/migrate_person_model.py`

Before changing any schema, capture the current state of entities that will be affected.

- [ ] **Step 1: Create the migration export script**

```python
#!/usr/bin/env python3
"""Export jobhunt-contact and jobhunt-company data before person model migration."""
import json
import sys
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType

TYPEDB_HOST = "localhost"
TYPEDB_PORT = 1729
TYPEDB_DATABASE = "alhazen_notebook"

def export_data():
    driver = TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials("admin", "password"),
        DriverOptions(is_tls_enabled=False),
    )

    data = {"contacts": [], "companies": [], "works_at": []}

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        # Export contacts
        contacts = list(tx.query('''
            match $c isa jobhunt-contact;
            fetch {
                "id": $c.id,
                "name": $c.name,
                "contact_role": $c.contact-role,
                "contact_email": $c.contact-email,
                "linkedin_url": $c.linkedin-url
            };
        ''').resolve())
        data["contacts"] = contacts
        print(f"Exported {len(contacts)} contacts", file=sys.stderr)

        # Export companies
        companies = list(tx.query('''
            match $c isa jobhunt-company;
            fetch {
                "id": $c.id,
                "name": $c.name,
                "company_url": $c.company-url,
                "linkedin_url": $c.linkedin-url,
                "location": $c.location
            };
        ''').resolve())
        data["companies"] = companies
        print(f"Exported {len(companies)} companies", file=sys.stderr)

        # Export works-at relations
        works_at = list(tx.query('''
            match
                (employee: $e, employer: $c) isa works-at;
                $e has id $eid;
                $c has id $cid;
            fetch { "employee_id": $eid, "company_id": $cid };
        ''').resolve())
        data["works_at"] = works_at
        print(f"Exported {len(works_at)} works-at relations", file=sys.stderr)

    driver.close()
    json.dump(data, sys.stdout, indent=2)

if __name__ == "__main__":
    export_data()
```

- [ ] **Step 2: Run the export**

Run: `uv run python scripts/migrate_person_model.py > exports/person_model_export.json 2>&1`

Create exports dir first: `mkdir -p exports`

Expected: JSON file with contacts, companies, and works-at relations. stderr shows counts.

- [ ] **Step 3: Commit**

```bash
git add scripts/migrate_person_model.py
git commit -m "feat: add person model migration export script"
```

---

### Task 2: Update core schema — new attributes and interaction entity

**Files:**
- Modify: `local_resources/typedb/alhazen_notebook.tql`

Add new attributes, the interaction entity, interaction-participation relation, and works-at relation to the core schema. Enrich person and organization.

- [ ] **Step 1: Add new attributes to the core attributes section**

After the existing `email-address` attribute (line 73), add:

```typeql
attribute linkedin-url, value string;
attribute title, value string;
attribute phone-number, value string;
attribute bio, value string;

# Interaction tracking
attribute interaction-type, value string;
attribute interaction-date, value datetime;
attribute outcome, value string;
attribute follow-up-by, value datetime;
attribute follow-up-status, value string;
attribute participant-role, value string;

# Organization enrichment
attribute company-url, value string;
attribute location, value string;
attribute industry, value string;
```

- [ ] **Step 2: Add works-at relation to core relations section**

After the `affiliation` relation (around line 319), add:

```typeql
# WORKS-AT - Person employed at / associated with an organization
relation works-at,
    owns valid-from,
    owns valid-until,
    relates employee,
    relates employer;
```

- [ ] **Step 3: Add interaction-participation relation**

After works-at, add:

```typeql
# INTERACTION-PARTICIPATION - Links persons to interactions with roles
relation interaction-participation,
    owns participant-role,
    relates interaction,
    relates participant;
```

- [ ] **Step 4: Add interaction entity**

After the `organization` entity (around line 219), add:

```typeql
# INTERACTION - A tracked interaction between persons (meeting, call, email, interview)
entity interaction sub domain-thing,
    owns interaction-type,
    owns interaction-date,
    owns outcome,
    owns follow-up-by,
    owns follow-up-status,
    plays interaction-participation:interaction;
```

- [ ] **Step 5: Enrich the person entity**

Replace the existing person definition:

```typeql
# PERSON - Real-world human actor (sub agent: can create notes, perform operations)
entity person sub agent,
    owns given-name,
    owns family-name,
    owns email-address,
    owns linkedin-url,
    owns title,
    owns phone-number,
    owns bio,
    plays interaction-participation:participant,
    plays relationship-context:from-person,
    plays relationship-context:to-person,
    plays works-at:employee;
```

Note: `plays relationship-context` requires the relation to be defined. It is defined in `agentic-memory/schema.tql` which is loaded after the core schema. To avoid load-order issues, the `plays relationship-context` declarations should stay in the agentic-memory schema where the relation is defined. So the person entity in core should be:

```typeql
entity person sub agent,
    owns given-name,
    owns family-name,
    owns email-address,
    owns linkedin-url,
    owns title,
    owns phone-number,
    owns bio,
    plays interaction-participation:participant,
    plays works-at:employee;
```

The `plays relationship-context:from-person/to-person` will be added to `person` in the agentic-memory schema (see Task 3).

- [ ] **Step 6: Enrich the organization entity**

Replace the existing organization definition:

```typeql
# ORGANIZATION - Groups of persons/agents (sub domain-thing for full identifiable-entity hierarchy)
entity organization sub domain-thing,
    owns linkedin-url,
    owns company-url,
    owns location,
    owns industry,
    plays affiliation:organization,
    plays works-at:employer;
```

- [ ] **Step 7: Verify schema loads**

Run: `make db-init 2>&1 | tail -20`

Expected: Core schema loads OK. Skill schemas may fail (expected — jobhunt has duplicate definitions we haven't removed yet).

- [ ] **Step 8: Commit**

```bash
git add local_resources/typedb/alhazen_notebook.tql
git commit -m "feat: enrich core person/organization, add interaction entity and works-at"
```

---

### Task 3: Update agentic-memory schema

**Files:**
- Modify: `skills/agentic-memory/schema.tql`

Move `plays relationship-context` from operator-user to person (so all persons can have relationships). Keep operator-user's 10 context domains unchanged.

- [ ] **Step 1: Add relationship-context plays to person (not operator-user)**

In the agentic-memory schema, after the `relationship-context` relation definition and role bindings section, add:

```typeql
entity person
    plays relationship-context:from-person,
    plays relationship-context:to-person;
```

This uses TypeDB 3.x `redefine`-style additive declaration — adding plays clauses to an already-defined entity.

- [ ] **Step 2: Remove relationship-context plays from operator-user**

In the `operator-user` definition, remove the two lines:
```
    plays relationship-context:from-person,
    plays relationship-context:to-person;
```

The operator-user inherits these from person now.

The updated operator-user should be:

```typeql
entity operator-user sub person,
    owns identity-summary,
    owns role-description,
    owns communication-style,
    owns goals-summary,
    owns preferences-summary,
    owns domain-expertise,
    plays project-involvement:participant,
    plays tool-familiarity:practitioner;
```

- [ ] **Step 3: Verify schema loads**

Run: `make db-init 2>&1 | tail -20`

Expected: Core + agentic-memory schemas load OK. Jobhunt may still fail.

- [ ] **Step 4: Commit**

```bash
git add skills/agentic-memory/schema.tql
git commit -m "feat: move relationship-context plays from operator-user to person"
```

---

### Task 4: Update jobhunt schema

**Files:**
- Modify: `local_skills/jobhunt/schema.tql` (this is a symlink/clone from sciknow-io/alhazen-skill-examples)

Change `jobhunt-contact` to sub person, `jobhunt-company` to sub organization, remove duplicate attribute and relation definitions.

**Important:** Changes must also be pushed upstream to `sciknow-io/alhazen-skill-examples` per CLAUDE.md conventions. For now, edit `local_skills/jobhunt/schema.tql` directly, then push upstream.

- [ ] **Step 1: Remove duplicate attribute definitions**

Remove these lines from the jobhunt schema attributes section (they are now defined in core):

```typeql
attribute company-url, value string;
attribute linkedin-url, value string;
attribute location, value string;
attribute interaction-type, value string;
attribute interaction-date, value datetime;
```

Keep `contact-role` (jobhunt-specific) and `contact-email` (will be deprecated but keep for now to avoid breaking existing data queries — map to `email-address` in code).

- [ ] **Step 2: Remove works-at relation definition**

Remove the entire `works-at` relation block from jobhunt schema:

```typeql
# WORKS-AT - Contacts working at companies
relation works-at,
    owns valid-from,
    owns valid-until,
    relates employee,
    relates employer;
```

This is now in the core schema.

- [ ] **Step 3: Change jobhunt-contact to sub person**

Replace:
```typeql
entity jobhunt-contact sub agent,
    owns contact-role,
    owns contact-email,
    owns linkedin-url,
    plays works-at:employee;
```

With:
```typeql
# JOBHUNT-CONTACT - A person in the job search process (recruiter, hiring manager, etc.)
entity jobhunt-contact sub person,
    owns contact-role,
    owns contact-email;
    # Inherits from person: given-name, family-name, email-address, linkedin-url,
    #   title, phone-number, bio, plays works-at:employee,
    #   plays interaction-participation:participant
```

Note: `plays works-at:employee` is inherited from person. `linkedin-url` is inherited from person. `contact-email` is kept for backward compatibility (existing data uses it).

- [ ] **Step 4: Change jobhunt-company to sub organization**

Replace:
```typeql
entity jobhunt-company sub domain-thing,
    owns company-url,
    owns linkedin-url,
    owns location,
    plays position-at-company:employer,
    plays works-at:employer,
    plays opportunity-at-organization:organization;
```

With:
```typeql
# JOBHUNT-COMPANY - An organization in the job search context
entity jobhunt-company sub organization,
    owns board-token,
    owns board-platform,
    owns search-query,
    owns search-location,
    plays position-at-company:employer,
    plays opportunity-at-organization:organization;
    # Inherits from organization: linkedin-url, company-url, location, industry,
    #   plays works-at:employer, plays affiliation:organization
```

Note: `plays works-at:employer` is inherited from organization. `company-url`, `linkedin-url`, `location` are inherited from organization.

- [ ] **Step 5: Remove location from jobhunt-candidate and jobhunt-position**

These entities also `owns location` which is now a core attribute. Check if TypeDB 3.x allows inheriting `owns` from the core definition on `domain-thing` or `identifiable-entity`. If `location` is not on identifiable-entity, these entities need to keep their `owns location` declarations — which is fine since the attribute type is now defined in core.

Actually, `location` is a plain attribute. Each entity that needs it must declare `owns location`. The attribute *definition* moves to core, but `owns` declarations stay on each entity that uses it. So `jobhunt-candidate` and `jobhunt-position` keep `owns location` — just the `attribute location, value string;` definition line is removed from jobhunt schema.

No change needed here — just confirming the approach is correct.

- [ ] **Step 6: Verify full schema loads**

Run: `make db-init 2>&1 | tail -30`

Expected: All schemas (core + agentic-memory + jobhunt + all other skills) load without errors.

- [ ] **Step 7: Commit**

```bash
git add local_skills/jobhunt/schema.tql
git commit -m "feat(jobhunt): align contact/company to core person/organization hierarchy"
```

---

### Task 5: Rebuild database with new schema and verify data

**Files:**
- No new files — uses existing Makefile targets and the export from Task 1

The schema changes are not compatible with in-place `redefine` for entity hierarchy changes (changing `sub agent` to `sub person`). We need to drop and rebuild the database.

- [ ] **Step 1: Export current database**

```bash
make db-export
```

This creates a timestamped backup in `~/.alhazen/cache/typedb/`.

- [ ] **Step 2: Drop and recreate database with new schema**

```bash
uv run python -c "
from typedb.driver import TypeDB, Credentials, DriverOptions
d = TypeDB.driver('localhost:1729', Credentials('admin','password'), DriverOptions(is_tls_enabled=False))
d.databases.get('alhazen_notebook').delete()
d.close()
print('Database deleted')
" 2>/dev/null
make db-init
```

Expected: Database recreated with all new schemas loading successfully.

- [ ] **Step 3: Re-import data from backup**

```bash
# Import the backup created in Step 1
# Find the most recent export
LATEST=$(ls -t ~/.alhazen/cache/typedb/alhazen_notebook_export_*.zip | head -1)
echo "Importing: $LATEST"
uv run python .claude/skills/typedb-notebook/typedb_notebook.py import-db --zip "$LATEST" --database alhazen_notebook
```

Note: This may fail if the export format is incompatible with the new schema. If it fails, the data will need to be re-ingested. The jobhunt pipeline data (positions, companies) is the most important — verify it's intact.

- [ ] **Step 4: Verify pipeline data survived**

```bash
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Positions: {d[\"count\"]}')"
```

Expected: `Positions: 46` (same count as before migration).

- [ ] **Step 5: Verify new schema works — create a test interaction**

```bash
uv run python -c "
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType
d = TypeDB.driver('localhost:1729', Credentials('admin','password'), DriverOptions(is_tls_enabled=False))
with d.transaction('alhazen_notebook', TransactionType.WRITE) as tx:
    tx.query('''
        insert
        \$i isa interaction,
            has id 'test-interaction-001',
            has name 'Test coffee chat',
            has interaction-type 'coffee',
            has interaction-date 2026-04-28T10:00:00,
            has outcome 'Discussed ML engineering roles';
    ''').resolve()
    tx.commit()

with d.transaction('alhazen_notebook', TransactionType.READ) as tx:
    r = list(tx.query('''
        match \$i isa interaction, has id 'test-interaction-001';
        fetch { \"name\": \$i.name, \"type\": \$i.interaction-type };
    ''').resolve())
    print(r)

# Clean up test data
with d.transaction('alhazen_notebook', TransactionType.WRITE) as tx:
    tx.query('''
        match \$i isa interaction, has id 'test-interaction-001';
        delete \$i;
    ''').resolve()
    tx.commit()

d.close()
print('Interaction test passed')
" 2>/dev/null
```

Expected: `Interaction test passed`

- [ ] **Step 6: Verify enriched person works — create a test contact**

```bash
uv run python -c "
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType
d = TypeDB.driver('localhost:1729', Credentials('admin','password'), DriverOptions(is_tls_enabled=False))
with d.transaction('alhazen_notebook', TransactionType.WRITE) as tx:
    tx.query('''
        insert
        \$p isa jobhunt-contact,
            has id 'test-contact-001',
            has name 'Jane Recruiter',
            has given-name 'Jane',
            has family-name 'Recruiter',
            has email-address 'jane@example.com',
            has linkedin-url 'https://linkedin.com/in/jane',
            has title 'Senior Recruiter',
            has contact-role 'recruiter';
    ''').resolve()
    tx.commit()

with d.transaction('alhazen_notebook', TransactionType.READ) as tx:
    r = list(tx.query('''
        match \$p isa jobhunt-contact, has id 'test-contact-001';
        fetch { \"name\": \$p.name, \"title\": \$p.title, \"role\": \$p.contact-role };
    ''').resolve())
    print(r)

# Clean up
with d.transaction('alhazen_notebook', TransactionType.WRITE) as tx:
    tx.query('''
        match \$p isa jobhunt-contact, has id 'test-contact-001';
        delete \$p;
    ''').resolve()
    tx.commit()

d.close()
print('Contact test passed (inherits person attributes)')
" 2>/dev/null
```

Expected: Shows name, title, and role. Prints `Contact test passed (inherits person attributes)`.

- [ ] **Step 7: Commit any fixes**

If any schema adjustments were needed during verification:
```bash
git add -A
git commit -m "fix: schema adjustments from person model migration verification"
```

---

### Task 6: Update CLAUDE.md and documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-04-28-notebook-agent-os-design.md`

- [ ] **Step 1: Update Architecture section in CLAUDE.md**

In the "Alhazen's Notebook Model" section, update the entity hierarchy to include the new interaction entity and enriched person/organization:

```
identifiable-entity (abstract)         -- id, name, description, provenance
+-- domain-thing                       -- real-world objects (papers, genes, jobs)
|   +-- agent                          -- operational actors
|   |   +-- ai-agent                   -- Claude, GPT-4, etc.
|   |   +-- person                     -- enriched: name, email, linkedin, title, bio
|   |       +-- operator-user          -- 10 context domains (identity, role, goals, etc.)
|   |       +-- author                 -- publication authorship
|   |       +-- jobhunt-contact        -- contact-role (recruiter, hiring manager, etc.)
|   +-- organization                   -- enriched: linkedin, website, location, industry
|   |   +-- jobhunt-company            -- board config, search settings
|   +-- interaction                    -- type, date, outcome, follow-up tracking
+-- collection                         -- typed sets (corpora, searches, case files)
+-- information-content-entity (abstract) -- content, format, cache-path
    +-- artifact                       -- raw captured content (PDF, HTML, email, calendar)
    +-- fragment                       -- extracted piece of an artifact
    +-- note                           -- agent analysis or annotation
    +-- episode                        -- process account of a work session
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update entity hierarchy for enriched person/organization model"
```

---

### Task 7: Push jobhunt schema changes upstream

**Files:**
- Modify: `~/Documents/GitHub/alhazen-skill-examples/skills/demo/jobhunt/schema.tql`

Per CLAUDE.md conventions, changes to external skills must be pushed upstream.

- [ ] **Step 1: Copy updated schema to upstream repo**

```bash
cp local_skills/jobhunt/schema.tql ~/Documents/GitHub/alhazen-skill-examples/skills/demo/jobhunt/schema.tql
```

- [ ] **Step 2: Commit and push upstream**

```bash
cd ~/Documents/GitHub/alhazen-skill-examples
git add skills/demo/jobhunt/schema.tql
git commit -m "feat(jobhunt): align contact/company to core person/organization hierarchy

jobhunt-contact now sub person (was sub agent).
jobhunt-company now sub organization (was sub domain-thing).
Removed duplicate attribute definitions (linkedin-url, company-url, location)
and works-at relation (promoted to core alhazen_notebook.tql)."
git push
cd -
```

- [ ] **Step 3: Verify with skills-update**

```bash
make skills-update
make db-init
```

Expected: Upstream schema matches local. All schemas load cleanly.
