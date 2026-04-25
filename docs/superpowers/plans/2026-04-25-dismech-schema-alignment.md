# DisMech Schema Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the LinkML TypeDB generator to work with the current dismech YAML, regenerate a fresh `dismech/schema.tql`, and expand the APT schema with an explicit DisMech descriptor alignment layer.

**Architecture:** Three sequential phases: (A) fix generator incompatibility in the linkml feature-branch worktree, (B) regenerate and integrate dismech/schema.tql from the current YAML, (C) add missing descriptor types and explicit concept-mapping annotations to the APT schema. Phases A→B are sequential; Phase C is independent.

**Tech Stack:** Python 3.12, LinkML (`linkml-typedb-generator` feature branch at `/Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator/`), TypeQL/TypeDB 3.8.x, uv.

---

## Background: What We Learned

**dismech/schema.tql is faithful to the YAML.** The TypeDB schema (105 entities, 217 attributes, 96 relations) maps to all 105 YAML classes. The design choices that looked like bugs are actually correct per YAML spec:

- `disease.name @key` — correct: `Disease_name` slot has `identifier: true` in the YAML
- `causaledge.target` as string — correct: YAML `CausalEdge.target` has `range: string`
- `disease.parents` as string list — correct: YAML `parents` has `range: string, multivalued: true`
- `mechanism` entity has only name+description — correct: the YAML `Mechanism` class has only those two slots

**The real problem:** The YAML has evolved since the v0.1.0 generator run that produced the current `schema.tql`. The generator can't run on the current YAML because `obligation_level` is now serialized as a full YAML object `{text: REQUIRED, description: ...}` instead of a plain string, causing a `TypeError: cannot use 'jsonasobj2._jsonobj.JsonObj' as a dict key`.

**APT has only 4 descriptor types** (gene, anatomical, cell type, biological process) vs dismech's 27. Four more (chemical entity, molecular function, cellular component, protein complex) are needed for complete mechanism modeling. APT's `apt-mechanism` intentionally collapses dismech's `Pathophysiology` + `Mechanism` concepts — this is correct but needs explicit annotation.

---

## Files

| File | Phase | Action |
|------|-------|--------|
| `/Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator/packages/linkml_runtime/src/linkml_runtime/linkml_model/meta.py` | A | Modify line 1217 — fix ObligationLevelEnum init to handle JsonObj |
| `/Users/gullyburns/skillful-alhazen/local_skills/dismech/schema.tql` → `skills/dismech/schema.tql` | B | Replace with freshly generated TypeQL |
| `/Users/gullyburns/skillful-alhazen/skills/alg-precision-therapeutics/schema.tql` | C | Add 4 descriptor types + DisMech concept-mapping annotations |

---

## PHASE A: Fix the LinkML TypeDB Generator

### Task 1: Understand the bug and fix it

**Files:**
- Modify: `/Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator/packages/linkml_runtime/src/linkml_runtime/linkml_model/meta.py` at line 1217

**Root cause:** In the current dismech YAML, `EnumBinding.obligation_level` is serialized as a full YAML mapping object:
```yaml
obligation_level:
  text: REQUIRED
  description: The metadata element is required to be present in the model
```
When loaded, this becomes a `jsonasobj2.JsonObj` with a `.text` attribute. But `EnumBinding.__post_init__` at line 1217 passes it directly to `ObligationLevelEnum(self.obligation_level)`. `ObligationLevelEnum.__init__` (inherited from `EnumDefinitionImpl`) then tries to use this `JsonObj` as a dict key, which fails because `JsonObj` is unhashable.

- [ ] **Step 1: Read the current broken code**

```bash
sed -n '1210,1225p' /Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator/packages/linkml_runtime/src/linkml_runtime/linkml_model/meta.py
```

Expected output shows line 1217:
```python
self.obligation_level = ObligationLevelEnum(self.obligation_level)
```

- [ ] **Step 2: Apply the fix**

Change lines 1216–1217 from:
```python
        if self.obligation_level is not None and not isinstance(self.obligation_level, ObligationLevelEnum):
            self.obligation_level = ObligationLevelEnum(self.obligation_level)
```

To:
```python
        if self.obligation_level is not None and not isinstance(self.obligation_level, ObligationLevelEnum):
            level_val = self.obligation_level
            # obligation_level may be loaded as a JsonObj (YAML mapping) with a 'text' field
            # when the YAML serializes it as {text: REQUIRED, description: ...}
            if hasattr(level_val, 'text'):
                level_val = level_val.text
            elif isinstance(level_val, dict):
                level_val = level_val.get('text', str(level_val))
            self.obligation_level = ObligationLevelEnum(str(level_val))
```

Edit the file at `/Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator/packages/linkml_runtime/src/linkml_runtime/linkml_model/meta.py`.

- [ ] **Step 3: Verify the fix compiles**

```bash
cd /Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator && uv run python -c "from linkml_runtime.linkml_model.meta import EnumBinding; print('OK')"
```

Expected: `OK` (or a warning about VIRTUAL_ENV, which is harmless)

---

### Task 2: Run the generator on dismech YAML

**Files:**
- Read: `/Users/gullyburns/Documents/GitHub/dismech/elements/schema/dismech.yaml`
- Write: `/tmp/dismech_generated.tql` (staging output before integration)

- [ ] **Step 1: Run the generator**

```bash
cd /Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator && \
  uv run python -m linkml.generators.typedbgen \
    /Users/gullyburns/Documents/GitHub/dismech/elements/schema/dismech.yaml \
    > /tmp/dismech_generated.tql 2>/tmp/dismech_gen_errors.txt
echo "Exit: $?"
wc -l /tmp/dismech_generated.tql
```

Expected: exit 0, output file has 1500–2500 lines.

If there are errors in `/tmp/dismech_gen_errors.txt`, read and address them before proceeding.

- [ ] **Step 2: Verify the output is valid TypeQL**

```bash
head -30 /tmp/dismech_generated.tql
echo "---"
grep "^  entity " /tmp/dismech_generated.tql | wc -l
grep "^  relation " /tmp/dismech_generated.tql | wc -l
grep "^  attribute " /tmp/dismech_generated.tql | wc -l
```

Expected: `define` block at top, 100+ entities, 90+ relations, 200+ attributes.

- [ ] **Step 3: Diff against current schema**

```bash
# Normalize both for comparison (strip comments, sort)
grep -v "^#" /tmp/dismech_generated.tql | grep -E "^  (entity|relation|attribute)" | sort > /tmp/new_types.txt
grep -v "^#" /Users/gullyburns/skillful-alhazen/local_skills/dismech/schema.tql | grep -E "^  (entity|relation|attribute)" | sort > /tmp/old_types.txt
echo "=== In new, missing from old (additions) ===" && comm -23 /tmp/new_types.txt /tmp/old_types.txt
echo "=== In old, missing from new (removals) ===" && comm -13 /tmp/new_types.txt /tmp/old_types.txt
```

Read the diff carefully. Take note of:
- New entities/relations/attributes (newly added in YAML evolution)
- Removed ones (may have been renamed or consolidated in YAML)

- [ ] **Step 4: Check the aboutness relation**

The core alhazen schema provides the `aboutness` relation (note → subject). The generated schema must NOT redefine it. Check:

```bash
grep "aboutness" /tmp/dismech_generated.tql
```

If `aboutness` appears as a `relation` definition in the generated output, it must be removed from the generated file before integration — it lives in `alhazen_notebook.tql` core. The dismech schema.tql should only add the `plays aboutness:subject` on `disease`.

- [ ] **Step 5: Check for reserved TypeDB 3.x keywords**

```bash
# 'thing' and 'entity' are reserved in TypeDB 3.x match clauses
grep -n "\bsub thing\b\|\bisa thing\b\|\bsub entity\b" /tmp/dismech_generated.tql
```

If any appear, they need to be replaced with `identifiable-entity` or `domain-thing` in the TypeDB context.

- [ ] **Step 6: Check for any other integration issues**

Look for:
```bash
# Content attribute is defined in alhazen_notebook.tql core — must not be redefined
grep "attribute content" /tmp/dismech_generated.tql
# id attribute is defined in alhazen_notebook.tql core
grep "attribute id," /tmp/dismech_generated.tql
# name attribute - may conflict with alhazen_notebook.tql
grep "attribute name," /tmp/dismech_generated.tql
```

For each conflict found: the dismech schema.tql should reuse the attribute from core rather than redefine it.

---

### Task 3: Integrate the generated schema

**Files:**
- Modify: `/Users/gullyburns/skillful-alhazen/skills/dismech/schema.tql`
  (Note: `local_skills/dismech/schema.tql` is a symlink to this file)

- [ ] **Step 1: Read the current schema to understand the integration header**

Read the first 20 lines of the current `skills/dismech/schema.tql`. Note the header comment format and any manual additions (like the `aboutness` relation and core attribute reuse notes).

- [ ] **Step 2: Prepare the integration-ready generated file**

The generated file needs these edits before adoption:

a. Keep the header comment: `# Generated by linkml-typedb-generator...`  
b. Remove any re-definitions of attributes already in `alhazen_notebook.tql` core (id, name, description, content — check what the diff from Step 6 shows)  
c. Remove any re-definition of the `aboutness` relation  
d. Ensure `disease` entity has `plays aboutness:subject;`  
e. Ensure the file ends with a blank line

Do this with targeted edits using the Edit tool (not by overwriting blindly).

- [ ] **Step 3: Load the updated schema into TypeDB**

```bash
cd /Users/gullyburns/skillful-alhazen && make db-init
```

Expected: each schema file prints `OK`. If dismech/schema.tql has an error:
- Read the error message for the TypeQL error code (e.g., `[SYR1]`, `[TYR01]`)
- Use the CLAUDE.md TypeDB 3.x notes to diagnose
- Fix the specific line and re-run `make db-init`

- [ ] **Step 4: Smoke-test the schema loads correctly**

```bash
cd /Users/gullyburns/skillful-alhazen && uv run python local_skills/dismech/dismech.py list-diseases 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'diseases in DB: {len(d.get(\"diseases\", []))}')"
```

Expected: prints a count (may be 0 if DB is empty, but should not error).

- [ ] **Step 5: Commit**

```bash
cd /Users/gullyburns/skillful-alhazen
git add skills/dismech/schema.tql
git commit -m "feat(dismech): regenerate schema.tql from current dismech YAML via fixed gen-typedb

Fixes obligation_level JsonObj handling in linkml_runtime/meta.py EnumBinding.__post_init__.
Regenerated TypeQL reflects current YAML evolution since v0.1.0 generation.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

Also commit the generator fix in its own repo:

```bash
cd /Users/gullyburns/Documents/GitHub/linkml/.worktrees/feature-typedb-generator
git add packages/linkml_runtime/src/linkml_runtime/linkml_model/meta.py
git commit -m "fix(linkml_runtime): handle JsonObj obligation_level in EnumBinding.__post_init__

When a LinkML schema serializes EnumBinding.obligation_level as a full YAML
mapping {text: REQUIRED, description: ...}, loading it produces a JsonObj.
Extracting .text before passing to ObligationLevelEnum() fixes the TypeError.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## PHASE B: Expand APT Schema for DisMech Alignment

### Task 4: Add missing descriptor types to APT

**Files:**
- Modify: `/Users/gullyburns/skillful-alhazen/skills/alg-precision-therapeutics/schema.tql`

**Context:** APT currently has 4 descriptor types (gene, anatomical, cell type, biological process). DisMech has 27. For mechanism modeling, the four most critical missing ones are: chemical entity (CHEBI), molecular function (GO MF), cellular component (GO CC), and protein complex (GO CC complex).

These descriptors mirror the exact types that `dismech/pathophysiology` can reference, enabling APT mechanisms to be cross-queried against DisMech pathophysiology nodes.

- [ ] **Step 1: Read the current APT schema end section**

Read lines 630–690 of `/Users/gullyburns/skillful-alhazen/skills/alg-precision-therapeutics/schema.tql` (the descriptor entity section).

- [ ] **Step 2: Add new attributes for the four descriptor types**

After the existing `apt-go-id` and `apt-go-term` attribute definitions (around line 38), add:

```typeql
attribute apt-chebi-id, value string;
# ChEBI chemical entity ID (e.g. "CHEBI:15422" for ATP)

attribute apt-go-mf-id, value string;
# Gene Ontology Molecular Function term ID (e.g. "GO:0003700" for DNA-binding TF activity)

attribute apt-go-cc-id, value string;
# Gene Ontology Cellular Component term ID (e.g. "GO:0005634" for nucleus)

attribute apt-complex-id, value string;
# GO protein complex term ID or IntAct complex ID (e.g. "CPX-1")
```

- [ ] **Step 3: Add the four new descriptor entity types**

After the `apt-biologicaldescriptor` entity definition (around line 658), add:

```typeql
# APT-CHEMICALENTITYDESCRIPTOR - A chemical entity referenced by a mechanism (CHEBI)
# DisMech equivalent: ChemicalEntityDescriptor (used in pathophysiology.chemical_entities)
entity apt-chemicalentitydescriptor sub domain-thing,
    owns apt-preferred-term,
    owns apt-chebi-id,
    plays apt-mechanism-chemical-link:chemical;

# APT-MOLECULARFUNCTIONDESCRIPTOR - A molecular function referenced by a mechanism (GO MF)
# DisMech equivalent: MolecularFunctionDescriptor (used in pathophysiology.molecular_functions)
entity apt-molecularfunctiondescriptor sub domain-thing,
    owns apt-preferred-term,
    owns apt-go-mf-id,
    plays apt-mechanism-function-link:function;

# APT-CELLULARCOMPONENTDESCRIPTOR - A cellular compartment referenced by a mechanism (GO CC)
# DisMech equivalent: CellularComponentDescriptor (used in pathophysiology.cellular_components)
entity apt-cellularcomponentdescriptor sub domain-thing,
    owns apt-preferred-term,
    owns apt-go-cc-id,
    plays apt-mechanism-component-link:component;

# APT-PROTEINCOMPLEXDESCRIPTOR - A protein complex referenced by a mechanism (GO/IntAct)
# DisMech equivalent: ProteinComplexDescriptor (used in pathophysiology.protein_complexes)
entity apt-proteincomplexdescriptor sub domain-thing,
    owns apt-preferred-term,
    owns apt-complex-id,
    plays apt-mechanism-complex-link:complex;
```

- [ ] **Step 4: Add the four new link relations**

After the existing `apt-mechanism-process-link` relation (around line 609), add:

```typeql
# APT-MECHANISM-CHEMICAL-LINK - Mechanism involves a chemical entity (CHEBI)
# DisMech equivalent: pathophysiology.chemical_entities
relation apt-mechanism-chemical-link,
    owns apt-modifier,
    relates mechanism,
    relates chemical;

# APT-MECHANISM-FUNCTION-LINK - Mechanism involves a molecular function (GO MF)
# DisMech equivalent: pathophysiology.molecular_functions
relation apt-mechanism-function-link,
    owns apt-modifier,
    relates mechanism,
    relates function;

# APT-MECHANISM-COMPONENT-LINK - Mechanism occurs in/at a cellular component (GO CC)
# DisMech equivalent: pathophysiology.cellular_components
relation apt-mechanism-component-link,
    owns apt-modifier,
    relates mechanism,
    relates component;

# APT-MECHANISM-COMPLEX-LINK - Mechanism involves a protein complex
# DisMech equivalent: pathophysiology.protein_complexes
relation apt-mechanism-complex-link,
    owns apt-modifier,
    relates mechanism,
    relates complex;
```

- [ ] **Step 5: Add `plays` clauses to `apt-mechanism`**

Edit the `apt-mechanism` entity definition to add role plays for the four new link relations:

```typeql
    plays apt-mechanism-chemical-link:mechanism,
    plays apt-mechanism-function-link:mechanism,
    plays apt-mechanism-component-link:mechanism,
    plays apt-mechanism-complex-link:mechanism,
```

Add these after the existing `plays apt-mechanism-process-link:mechanism,` line.

- [ ] **Step 6: Add the DisMech concept-mapping header**

Add a section header comment after the existing file header (after line 12), before `define`:

```typeql
# =============================================================================
# DISMECH CONCEPT MAPPING
# =============================================================================
# apt-mechanism         ←→ dismech:Pathophysiology (the core mechanistic node)
#                           NOT dismech:Mechanism (which is just name+description)
# apt-causaledge        ←→ dismech:CausalEdge (reified causal link)
# apt-evidenceitem      ←→ dismech:EvidenceItem (PMID-backed evidence)
# apt-mechanism-hypothesis ←→ dismech:MechanisticHypothesis
# apt-gene-descriptor   ←→ dismech:GeneDescriptor
# apt-anatomicaldescriptor ←→ dismech:AnatomicalEntityDescriptor
# apt-celltypedescriptor ←→ dismech:CellTypeDescriptor
# apt-biologicaldescriptor ←→ dismech:BiologicalProcessDescriptor
# apt-chemicalentitydescriptor ←→ dismech:ChemicalEntityDescriptor  [NEW]
# apt-molecularfunctiondescriptor ←→ dismech:MolecularFunctionDescriptor  [NEW]
# apt-cellularcomponentdescriptor ←→ dismech:CellularComponentDescriptor  [NEW]
# apt-proteincomplexdescriptor ←→ dismech:ProteinComplexDescriptor  [NEW]
# apt-disease           ←→ dismech:Disease (subset of fields; adds OMIM/ORPHA/GARD)
# apt-phenotype         ←→ dismech:Phenotype (HPO-centric, simplified)
# apt-variant           ←→ dismech:Variant (adds HGVS notation)
# apt-drug              ←→ dismech:Treatment (splits out drug compound; adds ChEMBL)
# apt-treatment         ←→ dismech:Treatment (MAXO-coded intervention)
# apt-clinical-trial    ←→ dismech:ClinicalTrial
# apt-disease-model     ←→ dismech:AnimalModel + ExperimentalModel (collapsed)
# apt-investigation     ←→ dismech:DiseaseCollection (Alhazen notebook context)
# =============================================================================
```

- [ ] **Step 7: Load schema to verify TypeDB accepts it**

```bash
cd /Users/gullyburns/skillful-alhazen && make db-init
```

Expected: `OK` for all schema files including `alg-precision-therapeutics/schema.tql`. If there's an error:
- Read the TypeQL error code
- Fix the specific line (common issues: missing comma at end of entity definition, relation defined after entity that needs it)

- [ ] **Step 8: Verify the new types are queryable**

```bash
cd /Users/gullyburns/skillful-alhazen && uv run python -c "
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType
driver = TypeDB.driver('localhost:1729', Credentials('admin', 'password'), DriverOptions(is_tls_enabled=False))
with driver.transaction('alhazen_notebook', TransactionType.READ) as tx:
    result = list(tx.query('''
        match \$t isa apt-chemicalentitydescriptor;
        fetch { \"count\": \$t.id };
    ''').resolve())
    print(f'apt-chemicalentitydescriptor queryable, result count: {len(result)}')
    result = list(tx.query('''
        match \$t isa apt-molecularfunctiondescriptor;
        fetch { \"count\": \$t.id };
    ''').resolve())
    print(f'apt-molecularfunctiondescriptor queryable, result count: {len(result)}')
"
```

Expected: both types are queryable (0 results is fine — the schema is empty; the important thing is no `[SYR1]` error).

- [ ] **Step 9: Commit**

```bash
cd /Users/gullyburns/skillful-alhazen
git add skills/alg-precision-therapeutics/schema.tql
git commit -m "feat(apt): add 4 descriptor types + DisMech concept-mapping annotations

Adds ChemicalEntity, MolecularFunction, CellularComponent, ProteinComplex
descriptor types to apt schema, completing the descriptor set needed for
full mechanism modeling against dismech:Pathophysiology.

Also adds explicit DisMech concept-mapping header comment documenting the
equivalence between apt- types and dismech: classes for cross-skill querying.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Fix generator incompatibility (Task 1–2) — covers "fix the generator incompatibility"
- [x] Regenerate dismech schema from current YAML (Task 3) — covers "generate from dismech YAML"
- [x] Integrate fresh schema with alhazen core (Task 3 integration steps) — covers alhazen notebook compatibility
- [x] Add missing descriptor types to APT (Task 4) — covers "expand APT for dismech alignment"
- [x] Explicit concept-mapping documentation (Task 4 Step 6) — covers "mappable version" requirement

**Placeholder scan:** No TBDs, todos, or "similar to task N" patterns. All code blocks are complete.

**Type consistency:**
- `apt-mechanism-chemical-link`, `-function-link`, `-component-link`, `-complex-link` — defined in Task 4 Step 4, used by entities in Step 3, played by `apt-mechanism` in Step 5. Consistent.
- `apt-chebi-id`, `apt-go-mf-id`, `apt-go-cc-id`, `apt-complex-id` — defined in Step 2, owned by descriptor entities in Step 3. Consistent.
- Generator fix: `level_val.text` access matches the actual JsonObj structure seen in the YAML (`obligation_level: {text: REQUIRED, description: ...}`). Consistent.
