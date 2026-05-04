---
name: agentic-memory
description: TypeDB-backed ontological memory with schema-driven retrieval. Introspects the live knowledge graph schema, composes TypeQL queries dynamically, and combines graph traversal with embedding-based semantic search for three-stage retrieval (plan, execute, organize with provenance).
triggers:
  - remember this / record this decision / consolidate
  - what do I know about... / recall facts about... / tell me about...
  - who is... / what organizations... / cross-domain questions
  - create an episode / anchor this session / what did we do
  - create operator user / set up personal context
  - search for... / find papers about... / semantic search
  - describe the schema / what types exist / how is X connected to Y
prerequisites:
  - TypeDB running: make db-start
  - make build-skills
  - For semantic search: Qdrant running (make qdrant-start) + VOYAGE_API_KEY set
read_strategy:
  always: Quick Start, Three-Stage Retrieval Pipeline, Command Output Pattern
  when_writing: Write Operations
  when_searching: Semantic Search, Schema Navigation Patterns
  when_exploring_schema: Schema Navigation Patterns, TypeQL Patterns Cheat Sheet
---

# Agentic Memory Skill

Ontological memory for Alhazen: the agent understands the schema, composes queries dynamically, and navigates the full knowledge graph across all skill namespaces.

**Core capability:** Three-stage retrieval — plan queries from schema understanding, execute multi-step graph + vector searches, organize results with provenance.

**Write-side entities:**
- **operator-user** — person running Alhazen; 10-domain personal context
- **memory-claim-note** — crystallized proposition (fact-type: knowledge | decision | goal | preference | schema-gap)
- **episode** — process account of a work session with operation tracking (what was created/modified and why)
- **entity-alias** — cross-skill resolution (same real-world entity as multiple TypeDB entities)

## Quick Start

```bash
# Understand the schema
uv run python .claude/skills/agentic-memory/agentic_memory.py describe-schema 2>/dev/null

# Run any TypeQL query
uv run python .claude/skills/agentic-memory/agentic_memory.py query \
  --typeql 'match $p isa person, has name $n; $n contains "Burns"; fetch { "id": $p.id, "name": $n };' 2>/dev/null

# Semantic search across all embedded collections
uv run python .claude/skills/agentic-memory/agentic_memory.py search \
  --query "CRISPR delivery mechanisms" --limit 5 2>/dev/null

# Create operator profile
uv run python .claude/skills/agentic-memory/agentic_memory.py create-operator \
  --name "Gully Burns" --identity "Principal AI Architect" --role "Building knowledge graphs" 2>/dev/null

# Consolidate a fact into long-term memory
uv run python .claude/skills/agentic-memory/agentic_memory.py consolidate \
  --content "TypeDB 3.x sub! operator returns direct parent only" \
  --subject <entity-id> --fact-type knowledge --confidence 0.9 2>/dev/null

# Create episode with operation tracking
uv run python .claude/skills/agentic-memory/agentic_memory.py create-episode \
  --skill agentic-memory --summary "Fixed schema hierarchy" 2>/dev/null
uv run python .claude/skills/agentic-memory/agentic_memory.py link-episode \
  --episode <ep-id> --entities <id1>,<id2> \
  --operation-type created --rationale "Created during schema fix session" 2>/dev/null
```

## Three-Stage Retrieval Pipeline

When answering questions about the knowledge graph, follow this three-stage pattern:

### Stage A: Plan Retrieval

1. **Understand the schema**: Call `describe-schema` to see what entity types, relations, and embedding indexes exist
2. **Identify relevant types**: Map the user's question to TypeDB types (e.g., "who works at Altos Labs?" involves `person`, `organization`, `works-at`)
3. **Choose strategy**:
   - **Graph-only** — known entity by name/ID, structural question ("who works at X?"), relation traversal
   - **Embedding-only** — semantic/fuzzy query ("papers about CRISPR delivery"), no specific entity known
   - **Hybrid** — embedding search to find candidates, then graph traversal for context

### Stage B: Execute Plan

Compose and execute queries dynamically using `query` and `search` commands:

1. **Semantic search** (if needed): `search --query "..." [--collection <name>]`
   - Returns entity IDs + scores from Qdrant
   - Cross-collection search (omit --collection) searches ALL embedded collections
2. **Entity lookup**: `query --typeql 'match $e isa <type>, has id "<id>"; fetch { ... };'`
3. **Relation traversal**: Follow connections from entities
   ```
   match (employee: $p, employer: $o) isa works-at; $o has name "Altos Labs";
   fetch { "person": $p.name, "person-id": $p.id };
   ```
4. **Notes/claims about entity**: `match (note: $n, subject: $e) isa aboutness; $e has id "<id>"; fetch { "content": $n.content };`
5. **Episode history**: `match (session: $ep, subject: $e) isa episode-mention; $e has id "<id>"; fetch { "episode": $ep.content };`
6. **Alias resolution**: Check `entity-alias` for cross-skill duplicates

### Stage C: Organize Response with Provenance

Synthesize results into a structured answer:
- **Direct answer** — facts addressing the question
- **Supporting evidence** — which notes, artifacts, papers support each fact
- **Provenance** — how each piece was obtained (skill, timestamp, source)
- **Confidence** — from memory-claim-notes and evidence-chain attributes
- **Cross-domain connections** — related entities from other namespaces

## Schema Navigation Patterns

### Understanding the type hierarchy

`describe-schema` returns the full entity/relation hierarchy with:
- **parent**: direct supertype (e.g., person's parent is agent)
- **owns**: all attributes including inherited
- **plays**: roles this type can play in relations
- **subtypes**: types that inherit from this type
- **embedding_index**: which Qdrant collections have embedded vectors for which types

TypeDB's **subtype polymorphism** is key: `match $p isa person` returns ALL person subtypes (operator-user, author, jobhunt-contact, etc.). Use the broadest useful supertype for queries.

### Finding connections between entities

1. Check what **relations** the entity's type plays (from `describe-schema`)
2. Query each relevant relation:
   ```typeql
   match $e isa person, has id "<id>"; (employee: $e, employer: $o) isa works-at;
   fetch { "org-id": $o.id, "org-name": $o.name };
   ```
3. For notes/analysis: use `aboutness` relation
4. For episodes: use `episode-mention` relation
5. For collections: use `collection-membership` relation

### Cross-skill entity visibility

The same real-world entity may exist as different TypeDB types across skills. Use `entity-alias` to link them, and check aliases when building unified views.

## TypeQL Patterns Cheat Sheet

```typeql
-- Polymorphic match (catches all subtypes)
match $p isa person; fetch { "id": $p.id, "name": $p.name };

-- Relation traversal
match (employee: $p, employer: $o) isa works-at;
fetch { "person": $p.name, "org": $o.name };

-- Multi-hop: person -> org -> collection
match
    (employee: $p, employer: $o) isa works-at;
    (collection: $c, member: $o) isa collection-membership;
fetch { "person": $p.name, "collection": $c.name };

-- Notes about an entity
match
    $e isa identifiable-entity, has id "<id>";
    (note: $n, subject: $e) isa aboutness;
fetch { "note-id": $n.id, "content": $n.content, "confidence": $n.confidence };

-- Text search (substring match)
match $e isa person, has name $n; $n contains "Burns";
fetch { "id": $e.id, "name": $n };

-- Temporal filtering
match $r (employee: $p, employer: $o) isa works-at, has valid-from $vf;
fetch { "person": $p.name, "org": $o.name, "since": $vf };
```

## Semantic Search

The `search` command embeds query text with Voyage AI and searches Qdrant collections.

**Available collections** (check `describe-schema` for current list + point counts):
- `alhazen_papers` — scientific papers (title + abstract)
- `apt-notes` — disease mechanism evidence notes
- `jobhunt-opportunities` — job positions with sensemaking notes
- `dismech_benchmark` — disease mechanism corpus (25K+ points)

**Cross-collection search** (omit `--collection`) searches ALL collections and merges results by score. This is the "search everything" capability.

Results include entity IDs that bridge back to TypeDB for graph follow-up.

## Write Operations

### Memory Claims
```bash
# Consolidate a fact
agentic_memory.py consolidate --content "..." --subject <entity-id> --fact-type knowledge --confidence 0.9

# Recall claims about an entity
agentic_memory.py recall --subject <entity-id>

# Invalidate (soft delete with timestamp)
agentic_memory.py invalidate <claim-id>
```

### Episodes
```bash
# Create with skill attribution
agentic_memory.py create-episode --skill <name> --summary "What happened"

# Link entities with operation tracking
agentic_memory.py link-episode --episode <ep-id> --entities <id1>,<id2> \
  --operation-type created --rationale "Why this was done"

# View structured session history
agentic_memory.py show-episode <ep-id>
```

### Entity Aliases
```bash
# Link two entities as the same real-world thing
agentic_memory.py merge-entities --canonical <id1> --alias <id2> --description "Same person"

# Remove alias
agentic_memory.py unmerge-entities --canonical <id1> --alias <id2>

# List all aliases (or for a specific entity)
agentic_memory.py list-aliases [--id <entity-id>]
```

### Operator Context
```bash
agentic_memory.py create-operator --name "..." --identity "..." --role "..."
agentic_memory.py update-context-domain --person <id> --domain goals --content "..."
agentic_memory.py get-context --person <id>
agentic_memory.py link-project --person <id> --collection <id>
agentic_memory.py link-tool --person <id> --entity <id>
agentic_memory.py link-person --from-person <id> --to-person <id> --context "..."
```

## Command Output Pattern

All commands return JSON to stdout. `uv run` emits a `VIRTUAL_ENV` warning to stderr. Always use `2>/dev/null` when piping to a JSON parser.

**Read USAGE.md for full command reference.**
