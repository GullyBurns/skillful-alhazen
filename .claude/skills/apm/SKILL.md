---
name: apm
description: Investigate rare diseases using the Algorithm for Precision Medicine - from symptoms to diagnosis to treatment
---

# Algorithm for Precision Medicine (APM) Skill

Use this skill to investigate rare diseases following Matt Might's Algorithm for Precision Medicine. Claude acts as a diagnostic detective, building a knowledge graph from symptoms through molecular diagnosis to therapeutic strategy.

## Philosophy: The APM Investigation

The APM is a two-phase systematic approach:

1. **Phase 1 (Diagnostic)** — Going from symptoms to molecular diagnosis
2. **Phase 2 (Therapeutic)** — Going from mechanism of harm to treatment

This skill follows the **curation design pattern**:

1. **FORAGING** - Discover evidence (clinical reports, ClinVar, OMIM, gnomAD, literature)
2. **INGESTION** - Script stores raw records as artifacts
3. **SENSEMAKING** - Claude reads artifacts, extracts clues, creates interpretive notes
4. **ANALYSIS** - Query across notes to build diagnostic/therapeutic reasoning chains
5. **REPORTING** - Investigation status, ACMG evidence tables, therapeutic options

**Key separation:**
- **Script handles**: Storing entities, artifacts, relations, TypeDB queries
- **Claude handles**: Reading artifacts, extracting meaning, ACMG classification, reasoning

## Prerequisites

- TypeDB must be running: `docker compose -f docker-compose-typedb.yml up -d`
- Dependencies installed: `uv sync --all-extras`
- APM schema loaded (see Schema Setup below)

## Schema Setup

```bash
docker exec -i alhazen-typedb /opt/typedb-all-linux-x86_64/typedb console --server=localhost:1729 << 'EOF'
transaction alhazen_notebook schema write
source /schema/namespaces/apm.tql
commit
EOF
```

## Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen_notebook)

---

## Starting an Investigation

### Create a Case

**Triggers:** "new case", "investigate patient", "start APM", "rare disease case"

```bash
uv run python .claude/skills/apm/apm.py add-case \
    --name "NGLY1 Patient Case" \
    --diagnostic-status "unsolved" \
    --phase "diagnostic"
```

### Add Phenotypes

```bash
uv run python .claude/skills/apm/apm.py add-phenotype \
    --hpo-id "HP:0000522" --label "Alacrima" \
    --onset "infantile" --severity "severe"

uv run python .claude/skills/apm/apm.py add-phenotype \
    --hpo-id "HP:0001250" --label "Seizures"
```

### Link Phenotypes to Case

```bash
uv run python .claude/skills/apm/apm.py link-case-phenotype \
    --case "<case-id>" --phenotype "<phenotype-id>" \
    --onset "infantile" --severity "severe"
```

### Add Genes and Variants

```bash
uv run python .claude/skills/apm/apm.py add-gene \
    --symbol "NGLY1" --entrez-id "55768" --ensembl-id "ENSG00000151092"

uv run python .claude/skills/apm/apm.py add-variant \
    --gene "<gene-id>" \
    --hgvs-c "c.1201A>T" --hgvs-p "p.Arg401Ter" \
    --acmg-class "pathogenic" --zygosity "compound-het"
```

### Add Disease

```bash
uv run python .claude/skills/apm/apm.py add-disease \
    --name "NGLY1 deficiency" \
    --omim-id "615273" \
    --inheritance "autosomal-recessive"
```

---

## Ingestion: Storing Evidence

### Ingest Sequencing Report

```bash
uv run python .claude/skills/apm/apm.py ingest-report \
    --file /path/to/exome_report.pdf \
    --name "Exome Sequencing Report"
```

### Ingest Database Record

```bash
# ClinVar record
uv run python .claude/skills/apm/apm.py ingest-record \
    --type clinvar --source-id "VCV000012345" \
    --url "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345/"

# OMIM record
uv run python .claude/skills/apm/apm.py ingest-record \
    --type omim --source-id "615273" \
    --url "https://omim.org/entry/615273"
```

---

## Sensemaking: Claude Analyzes Evidence

### List Artifacts Needing Analysis

```bash
uv run python .claude/skills/apm/apm.py list-artifacts --status raw
```

### Get Artifact Content

```bash
uv run python .claude/skills/apm/apm.py show-artifact --id "<artifact-id>"
```

### Sensemaking Workflow

**When user says "analyze this report" or "make sense of [artifact]":**

1. **Get the artifact content**
   ```bash
   uv run python .claude/skills/apm/apm.py show-artifact --id "<artifact-id>"
   ```

2. **Read and extract clues**
   - From sequencing reports: variant calls, phenotype features
   - From ClinVar: pathogenicity evidence, ACMG criteria
   - From OMIM: disease descriptions, inheritance patterns
   - From papers: mechanism claims, functional data

3. **Promote fragments to Things**
   When a `apm-variant-call` fragment is confirmed significant:
   ```bash
   uv run python .claude/skills/apm/apm.py add-variant \
       --gene "<gene-id>" --hgvs-c "c.1201A>T" \
       --acmg-class "pathogenic"
   ```

4. **Build the diagnostic chain**
   ```bash
   # Link variant to case
   uv run python .claude/skills/apm/apm.py link-case-variant \
       --case "<case-id>" --variant "<variant-id>" \
       --zygosity "compound-het"

   # Link variant to gene
   uv run python .claude/skills/apm/apm.py link-variant-gene \
       --variant "<variant-id>" --gene "<gene-id>"

   # Assess pathogenicity
   uv run python .claude/skills/apm/apm.py link-variant-disease \
       --variant "<variant-id>" --disease "<disease-id>" \
       --acmg-class "pathogenic" --confidence 0.95

   # Diagnose
   uv run python .claude/skills/apm/apm.py link-case-diagnosis \
       --case "<case-id>" --disease "<disease-id>" \
       --status "confirmed" --confidence 0.9
   ```

5. **Create interpretive notes**

   **Variant Interpretation Note (ACMG classification):**
   ```bash
   uv run python .claude/skills/apm/apm.py add-note \
       --about "<variant-id>" \
       --type variant-interpretation \
       --content "Pathogenic. PS1: same AA change known pathogenic. PM2: absent from gnomAD. PP3: PolyPhen2 damaging." \
       --acmg-class "pathogenic" \
       --acmg-criteria "PS1,PM2,PP3"
   ```

   **Diagnosis Hypothesis Note:**
   ```bash
   uv run python .claude/skills/apm/apm.py add-note \
       --about "<case-id>" \
       --type diagnosis-hypothesis \
       --content "Compound heterozygous LOF mutations in NGLY1 consistent with NGLY1 deficiency. Phenotype matches: alacrima, seizures, developmental delay, liver dysfunction." \
       --diagnostic-status "confirmed" \
       --acmg-class "pathogenic"
   ```

   **Mechanism Analysis Note (bridges Phase 1 -> Phase 2):**
   ```bash
   uv run python .claude/skills/apm/apm.py add-note \
       --about "<gene-id>" \
       --type mechanism-analysis \
       --content "Total loss of NGLY1 function. Both alleles carry LOF mutations (nonsense + splice-site). PNGase activity absent, leading to ERAD pathway dysfunction." \
       --mechanism-type "total-loss" \
       --functional-impact "absence"
   ```

   **Therapeutic Strategy Note:**
   ```bash
   uv run python .claude/skills/apm/apm.py add-note \
       --about "<case-id>" \
       --type therapeutic-strategy \
       --content "Absence of enzyme function suggests compensation strategies: enzyme replacement therapy, gene therapy, or substrate reduction therapy." \
       --therapeutic-approach "ERT" \
       --functional-impact "absence"
   ```

6. **Build the therapeutic chain**
   ```bash
   # Mechanism of harm
   uv run python .claude/skills/apm/apm.py link-mechanism \
       --variant "<variant-id>" --gene "<gene-id>" \
       --mechanism-type "total-loss" --functional-impact "absence"

   # Gene encodes protein
   uv run python .claude/skills/apm/apm.py link-gene-protein \
       --gene "<gene-id>" --protein "<protein-id>"

   # Drug targets
   uv run python .claude/skills/apm/apm.py link-drug-target \
       --drug "<drug-id>" --gene "<gene-id>" \
       --approach "gene-therapy"
   ```

7. **Report findings to user**
   Summarize:
   - Diagnostic chain: phenotypes -> variants -> gene -> disease
   - ACMG evidence summary
   - Mechanism of harm
   - Therapeutic strategy options

---

## Query Commands

### Show Case Summary

```bash
uv run python .claude/skills/apm/apm.py show-case --id "<case-id>"
```

Returns: Full case details with phenotypes, variants, genes, diagnosis, and all notes.

### List Cases

```bash
uv run python .claude/skills/apm/apm.py list-cases
uv run python .claude/skills/apm/apm.py list-cases --status "unsolved"
```

### Show Diagnostic Chain

```bash
uv run python .claude/skills/apm/apm.py show-diagnostic-chain --case "<case-id>"
```

Returns: phenotypes -> variants -> genes -> disease with ACMG evidence.

### Show Therapeutic Chain

```bash
uv run python .claude/skills/apm/apm.py show-therapeutic-chain --case "<case-id>"
```

Returns: variant -> mechanism -> gene -> protein -> drug targets.

### List Entities

```bash
uv run python .claude/skills/apm/apm.py list-genes
uv run python .claude/skills/apm/apm.py list-variants
uv run python .claude/skills/apm/apm.py list-diseases
uv run python .claude/skills/apm/apm.py list-phenotypes
uv run python .claude/skills/apm/apm.py list-drugs
```

---

## APM Investigation Workflow: Complete Example

```
User: I have a patient with alacrima, seizures, developmental delay, and elevated liver enzymes.
      Exome sequencing found compound heterozygous variants in NGLY1.

Claude: I'll set up this investigation.

[Creates case, phenotypes, gene, variants, disease]
[Links phenotypes to case]
[Links variants to case and gene]
[Creates diagnosis hypothesis note]

## Investigation: NGLY1 Patient Case

**Phase 1 (Diagnostic): CONFIRMED**

| Phenotype | HPO | Onset | Severity |
|-----------|-----|-------|----------|
| Alacrima | HP:0000522 | infantile | severe |
| Seizures | HP:0001250 | infantile | moderate |
| Developmental delay | HP:0001263 | infantile | moderate |
| Elevated liver enzymes | HP:0002910 | infantile | mild |

**Variants:**
| Gene | HGVS | Zygosity | ACMG |
|------|------|----------|------|
| NGLY1 | c.1201A>T (p.Arg401Ter) | compound-het | Pathogenic |
| NGLY1 | c.930+1G>A (splice) | compound-het | Pathogenic |

**Diagnosis:** NGLY1 deficiency (OMIM:615273) - CONFIRMED
**ACMG Evidence:** PS1, PM2, PP3, PM3

**Phase 2 (Therapeutic):**
- Mechanism: Total loss of function -> absence of PNGase activity
- Functional impact: ERAD pathway dysfunction
- Therapeutic direction: Compensation (ERT, gene therapy, substrate reduction)

Shall I search the literature for therapeutic candidates?

User: Yes, search for NGLY1 therapeutic approaches.

Claude: [Uses epmc-search skill to find papers]
[Ingests relevant papers as scilit-paper]
[Extracts mechanism claims and drug-gene interactions]
[Creates therapeutic strategy notes]

Found 3 therapeutic directions being explored:
1. Gene therapy (preclinical, mouse model)
2. Substrate reduction therapy (preclinical)
3. NGLY1 enzyme replacement (early research)
```

---

## Data Model

### Entity Types (Things)

| Type | Description |
|------|-------------|
| `apm-case` | Patient investigation |
| `apm-gene` | Gene implicated in investigation |
| `apm-variant` | Specific genomic variant |
| `apm-disease` | Disease or condition |
| `apm-phenotype` | Clinical phenotype (HPO concept) |
| `apm-protein` | Protein product |
| `apm-pathway` | Biological pathway |
| `apm-drug` | Therapeutic compound |
| `apm-disease-model` | Experimental model system |
| `apm-assay` | Functional test |

### Artifact Types

| Type | Description |
|------|-------------|
| `apm-sequencing-report` | Clinical WES/WGS report |
| `apm-clinvar-record` | ClinVar entry |
| `apm-omim-record` | OMIM entry |
| `apm-gnomad-record` | Population frequency data |
| `apm-prediction-record` | In silico prediction |
| `apm-drug-record` | DrugBank/ChEMBL entry |
| `apm-pathway-record` | Pathway data |
| `apm-screening-result` | Drug screening results |

### Fragment Types

| Type | Description |
|------|-------------|
| `apm-phenotype-feature` | Phenotype mention from document |
| `apm-variant-call` | Variant from sequencing report |
| `apm-pathogenicity-evidence` | ACMG evidence item |
| `apm-drug-gene-interaction` | Drug-gene interaction |
| `apm-mechanism-claim` | Mechanism from literature |
| `apm-conservation-data` | Conservation/prediction data |

### Note Types

| Type | Purpose |
|------|---------|
| `apm-diagnosis-hypothesis-note` | Candidate diagnosis |
| `apm-variant-interpretation-note` | ACMG classification |
| `apm-mechanism-analysis-note` | Variant -> disease mechanism |
| `apm-therapeutic-strategy-note` | Treatment strategy |
| `apm-phenotype-genotype-note` | Symptom-gene links |
| `apm-reanalysis-note` | Re-analysis attempts |
| `apm-cross-case-synthesis-note` | Cross-case findings |
| `apm-screening-analysis-note` | Drug screening analysis |

### Key Relations

| Relation | Purpose |
|----------|---------|
| `apm-case-has-phenotype` | Patient presents symptom |
| `apm-case-has-variant` | Patient carries variant |
| `apm-case-has-diagnosis` | Working/confirmed diagnosis |
| `apm-variant-in-gene` | Variant location |
| `apm-variant-pathogenicity` | Variant causes disease |
| `apm-phenotype-gene-association` | Known phenotype-gene link |
| `apm-mechanism-of-harm` | How variant disrupts function |
| `apm-gene-encodes` | Gene -> protein |
| `apm-drug-target` | Drug acts on target |
| `apm-drug-indication` | Drug treats disease |
| `apm-pathway-membership` | Gene in pathway |
| `apm-model-for-disease` | Model recapitulates disease |
| `apm-assay-for-model` | Assay for model |

---

## Command Reference

| Command | Description | Key Args |
|---------|-------------|----------|
| `add-case` | Create investigation case | `--name`, `--diagnostic-status` |
| `add-gene` | Add gene | `--symbol`, `--entrez-id` |
| `add-variant` | Add variant | `--gene`, `--hgvs-c`, `--acmg-class` |
| `add-disease` | Add disease | `--name`, `--omim-id` |
| `add-phenotype` | Add HPO phenotype | `--hpo-id`, `--label` |
| `add-protein` | Add protein | `--name`, `--uniprot-id` |
| `add-drug` | Add drug | `--name`, `--drugbank-id` |
| `add-pathway` | Add pathway | `--name` |
| `add-model` | Add disease model | `--name`, `--model-type` |
| `ingest-report` | Ingest sequencing report | `--file`, `--name` |
| `ingest-record` | Ingest database record | `--type`, `--url` |
| `link-case-phenotype` | Link phenotype to case | `--case`, `--phenotype` |
| `link-case-variant` | Link variant to case | `--case`, `--variant` |
| `link-case-diagnosis` | Link diagnosis to case | `--case`, `--disease` |
| `link-variant-gene` | Link variant to gene | `--variant`, `--gene` |
| `link-variant-disease` | Variant pathogenicity | `--variant`, `--disease` |
| `link-mechanism` | Mechanism of harm | `--variant`, `--gene` |
| `link-gene-protein` | Gene encodes protein | `--gene`, `--protein` |
| `link-drug-target` | Drug targets gene/protein | `--drug`, `--gene` |
| `link-drug-indication` | Drug-disease link | `--drug`, `--disease` |
| `add-note` | Create any note type | `--about`, `--type`, `--content` |
| `show-case` | Full case details | `--id` |
| `show-diagnostic-chain` | Diagnostic reasoning chain | `--case` |
| `show-therapeutic-chain` | Therapeutic reasoning chain | `--case` |
| `list-cases` | List investigations | `--status` |
| `list-artifacts` | List artifacts | `--status` |
| `show-artifact` | Artifact content | `--id` |
| `list-genes` | List genes | |
| `list-variants` | List variants | |
| `list-diseases` | List diseases | |
| `list-phenotypes` | List phenotypes | |
| `list-drugs` | List drugs | |
| `tag` | Tag an entity | `--entity`, `--tag` |
| `search-tag` | Find by tag | `--tag` |

---

## Cross-Skill Integration

- **Literature**: Use `epmc-search` to find papers about genes/variants/diseases, stored as `scilit-paper`. Link to the investigation collection via `collection-membership`.
- **Collections**: Each investigation is a `Collection`. Use sub-collections for Phase 1 (Diagnostic) and Phase 2 (Therapeutic).

---

## TypeDB 2.x Reference

When writing custom TypeDB queries for APM data, consult:

- **Full Reference:** `.claude/skills/typedb-notebook/typedb-2x-documentation.md`
- **APM Schema:** `local_resources/typedb/namespaces/apm.tql`
- **Core Schema:** `local_resources/typedb/alhazen_notebook.tql`

### Quick TypeQL Examples

```typeql
# Find all phenotypes for a case
match
  $case isa apm-case, has id "<case-id>";
  (case: $case, phenotype: $p) isa apm-case-has-phenotype;
fetch $p: apm-hpo-id, apm-hpo-label;

# Full diagnostic chain
match
  $case isa apm-case;
  (case: $case, phenotype: $p) isa apm-case-has-phenotype;
  (case: $case, variant: $v) isa apm-case-has-variant;
  (variant: $v, gene: $g) isa apm-variant-in-gene;
  (case: $case, disease: $d) isa apm-case-has-diagnosis;
fetch $case: name; $p: apm-hpo-label; $g: apm-gene-symbol; $d: name;

# Find therapeutic targets for a mechanism
match
  $v isa apm-variant;
  (variant: $v, gene: $g) isa apm-mechanism-of-harm,
    has apm-functional-impact "absence";
fetch $g: apm-gene-symbol; $v: apm-hgvs-c;
```

### Common Pitfalls

- **No `optional` in fetch** - Use separate queries for optional attributes
- **Update = delete + insert** - Can't modify attributes in place
- **Use semicolons** between match patterns (implicit AND)
