# Bioskills Index — Full Reference

## Architecture

EDAM ontology terms (`bio-operation`, `bio-topic`) and custom extension terms
live in the same TypeDB entity types. TypeDB inference rules propagate
`bsi-implements` and `bsi-covers-topic` annotations transitively up the
hierarchy so querying `operation_2403` (Sequence analysis) returns all skills
tagged with any subtype.

```
[EDAM.tsv] --import-edam--> [bio-operation / bio-topic in TypeDB]
                                      |
                             [bio-subtype hierarchy]
                                      |
[bioskill]  --annotate-skill-->  [bsi-implements / bsi-covers-topic]
                                      |
                             [TypeDB inference rules]
                                      |
                             [Transitive EDAM queries]
```

---

## 1. One-Time Setup

```bash
# Create an index
uv run python .claude/skills/bioskills-index/bioskills_index.py create-index \
    --name "Bio AI Skills v1" --description "Global bioskills index"

# Import EDAM Operation and Topic terms
uv run python .claude/skills/bioskills-index/bioskills_index.py import-edam \
    --namespace operation   # ~1000 terms
uv run python .claude/skills/bioskills-index/bioskills_index.py import-edam \
    --namespace topic       # ~200 terms
```

---

## 2. Ontology Commands

### Browse EDAM hierarchy
```bash
uv run python .claude/skills/bioskills-index/bioskills_index.py list-operations \
    --parent operation_0004 --limit 20
# -> top-level EDAM operations

uv run python .claude/skills/bioskills-index/bioskills_index.py list-operations \
    --source bioskills-index
# -> custom extension terms only

uv run python .claude/skills/bioskills-index/bioskills_index.py show-operation \
    --edam-id operation_2403
# -> Sequence analysis term with implementing skill count
```

### Add custom extension terms (not in EDAM)
```bash
# Create a new operation subtyping an EDAM term
uv run python .claude/skills/bioskills-index/bioskills_index.py add-operation \
    --name "AI-Assisted Target Identification" \
    --definition "Use ML/LLM to identify therapeutic targets from omics data" \
    --parent-edam operation_0478    # parent: Molecular docking
# -> creates bio-operation with bsi-term-id, edam-source="bioskills-index"
# -> inference rules immediately propagate skills tagged with this term
#    to the parent when querying operation_0478

uv run python .claude/skills/bioskills-index/bioskills_index.py add-topic \
    --name "AI Drug Discovery" \
    --parent-edam topic_3336        # Drug discovery
```

---

## 3. Index + Skill Commands

```bash
# List indices
uv run python .claude/skills/bioskills-index/bioskills_index.py list-indices

# Add a skill manually
uv run python .claude/skills/bioskills-index/bioskills_index.py add-skill \
    --index <id> \
    --name "ESM-2 protein embedder" \
    --description "Embed protein sequences with Meta ESM-2" \
    --type python-api \
    --source-repo https://github.com/facebookresearch/esm \
    --ops operation_2479            # Protein feature detection
    --topics topic_2814             # Protein structure

# Add EDAM annotations to existing skill
uv run python .claude/skills/bioskills-index/bioskills_index.py annotate-skill \
    --skill <skill-id> \
    --op operation_2403,operation_0292 \
    --topic topic_0080

# Show skill details
uv run python .claude/skills/bioskills-index/bioskills_index.py show-skill --id <id>

# List skills with EDAM filter (uses inference)
uv run python .claude/skills/bioskills-index/bioskills_index.py list-skills \
    --index <id> --op operation_2403
# -> returns ALL skills tagged with Sequence analysis or any subtype

# Add code snippet
uv run python .claude/skills/bioskills-index/bioskills_index.py add-snippet \
    --skill <id> \
    --name "embed_sequence function" \
    --content "def embed_sequence(seq): ..." \
    --type function --language python
```

---

## 4. Semantic Search + Composition

Requires `VOYAGE_API_KEY` from https://dash.voyageai.com/

```bash
# Embed all skills in the index (voyage-4-large -> UMAP -> HDBSCAN)
VOYAGE_API_KEY=<key> uv run python .claude/skills/bioskills-index/bioskills_index.py \
    embed-and-project --index <id>

# Search by natural language query
VOYAGE_API_KEY=<key> uv run python .claude/skills/bioskills-index/bioskills_index.py \
    search --index <id> --query "protein structure prediction" --top-k 10

# Compose a workflow playlist
VOYAGE_API_KEY=<key> uv run python .claude/skills/bioskills-index/bioskills_index.py \
    compose --index <id> \
    --task "analyze single-cell RNA from IPF lung samples" \
    --max-skills 8 --min-clusters 3
```

---

## 5. Discovery + Update

```bash
# Discover new skills from all configured sources (discovery-sources.yaml)
uv run python .claude/skills/bioskills-index/bioskills_index.py update \
    --index <id>

# Dry run (see what would be added)
uv run python .claude/skills/bioskills-index/bioskills_index.py update \
    --index <id> --dry-run

# Use a custom sources file
uv run python .claude/skills/bioskills-index/bioskills_index.py update \
    --index <id> --sources-file my-sources.yaml
```

---

## 6. TypeDB Schema Summary

| Entity | Subtype of | Purpose |
|--------|-----------|---------|
| `bio-operation` | `domain-thing` | EDAM Operation term or custom extension |
| `bio-topic` | `domain-thing` | EDAM Topic term or custom extension |
| `bioskill-index` | `collection` | Versioned container for bioskills |
| `bioskill` | `domain-thing` | A bioskill entry |
| `bioskill-snippet` | `fragment` | Code snippet from a bioskill |

| Relation | Roles | Purpose |
|----------|-------|---------|
| `bio-subtype` | `bio-child`, `bio-parent` | EDAM + custom term hierarchy |
| `bsi-indexed-in` | `bsi-skill`, `bsi-index` | Skill belongs to index |
| `bsi-implements` | `bsi-skill`, `bsi-bio-op` | Skill implements operation |
| `bsi-covers-topic` | `bsi-skill`, `bsi-bio-topic` | Skill covers topic |
| `bsi-snippet-of` | `bsi-snippet`, `bsi-parent-skill` | Snippet is part of skill |

| Inference Rule | What it infers |
|---------------|----------------|
| `bsi-transitively-implements-bio-op` | If skill implements op X and X subtypes Y, skill also implements Y |
| `bsi-transitively-covers-bio-topic` | Same for topics |

---

## 7. Dashboard

Available at **http://localhost:3001/bioskills-index** when dashboard is running.

| Route | Content |
|-------|---------|
| `/bioskills-index` | Card grid of all indices |
| `/bioskills-index/[id]` | UMAP scatter + EDAM browser + search/compose |
| `/bioskills-index/[id]/skill/[sid]` | Skill detail: EDAM tags + snippets |
| `/bioskills-index/[id]/edam/[eid]` | EDAM term: definition + implementing skills |
