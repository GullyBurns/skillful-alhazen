# Agent Memory Framework: A TypeDB Schema

## Overview

This document describes a general-purpose ontological framework for agent memory systems, implemented in TypeDB. The framework provides four core structural types while treating external vocabularies (like schema.org) as pluggable classification systems rather than rigid inheritance hierarchies.

### Design Principles

1. **Structural vs. Descriptive Separation**: The core ontology handles *how information is organized*; external vocabularies handle *what things are called*
2. **Multiple Classification**: Entities can be classified under multiple schema.org types simultaneously
3. **Aboutness as First-Class**: The `is_about` relation (IAO:0000136) is central to connecting information artifacts to their referents
4. **Agent-Native**: Designed for AI agents to create, retrieve, and reason over knowledge

### Core Ontological Distinctions

| Concept | Role | Description |
|---------|------|-------------|
| **Thing** | Referent | Entities in the world that information can be *about* |
| **Collection** | Organization | Sets of entities, defined extensionally or intensionally |
| **Artifact** | Representation | Information objects that represent or describe things |
| **Note** | Annotation | Agent-generated information *about* other information entities |

---

## TypeDB Schema

```typeql
# =============================================================================
# AGENT MEMORY FRAMEWORK - TypeDB Schema
# =============================================================================
# A general-purpose ontological framework for agent memory systems.
# Treats schema.org and other vocabularies as classification facets.
# =============================================================================

define

# -----------------------------------------------------------------------------
# ATTRIBUTE TYPES - Core Properties
# -----------------------------------------------------------------------------

# Identity and naming
attribute id, value string;
attribute name, value string;
attribute description, value string;
attribute iri, value string;          # External identifier (URI/IRI)

# Content and representation
attribute content, value string;       # The actual content/text
attribute content-hash, value string;  # For deduplication
attribute format, value string;        # MIME type or format identifier
attribute token-count, value long;     # For LLM context management

# Temporal
attribute created-at, value datetime;
attribute updated-at, value datetime;
attribute valid-from, value datetime;  # Temporal validity start
attribute valid-until, value datetime; # Temporal validity end

# Provenance
attribute provenance, value string;    # How this was created/obtained
attribute source-uri, value string;    # Original source location
attribute confidence, value double;    # Epistemic confidence (0.0-1.0)

# Fragment positioning
attribute offset, value long;          # Start position in parent
attribute length, value long;          # Length of fragment

# Collection semantics
attribute logical-query, value string; # Intensional definition
attribute is-extensional, value boolean; # Whether membership is enumerated

# Classification metadata
attribute schema-org-uri, value string;   # e.g., "https://schema.org/Person"
attribute wikidata-qid, value string;     # e.g., "Q5" for human
attribute vocabulary-source, value string; # Which vocabulary this comes from


# -----------------------------------------------------------------------------
# ENTITY TYPES - Core Ontology
# -----------------------------------------------------------------------------

# Root type for all information-bearing entities
entity information-content-entity,
    abstract,
    owns id @key,
    owns name,
    owns description,
    owns iri,
    owns content,
    owns content-hash,
    owns format,
    owns token-count,
    owns created-at,
    owns updated-at,
    owns provenance,
    owns source-uri,
    plays authorship:work,
    plays classification:classified-entity,
    plays tagging:tagged-entity,
    plays aboutness:subject,
    plays collection-membership:member,
    plays derivation:derived-from-source,
    plays derivation:derivative;


# THING - Referents in the world
# Things are what information can be "about". They represent entities
# in the domain of discourse - people, places, concepts, events, etc.
entity thing,
    sub information-content-entity,
    plays representation:referent,
    plays participation:participant;


# COLLECTION - Organized groupings
# Collections can be extensional (enumerated members) or intensional
# (defined by a logical query/criteria).
entity collection,
    sub information-content-entity,
    owns logical-query,
    owns is-extensional,
    plays collection-membership:collection,
    plays collection-nesting:parent-collection,
    plays collection-nesting:child-collection;


# ARTIFACT - Specific representations
# An artifact is a concrete information object - a document, a record,
# a data file. It represents or describes things.
entity artifact,
    sub information-content-entity,
    plays representation:artifact,
    plays fragmentation:whole,
    plays citation:citing-work,
    plays citation:cited-work;


# FRAGMENT - Parts of artifacts
# A fragment is a selected portion of an artifact, located by offset/length
# or other selectors. Fragments can themselves be subjects of notes.
entity fragment,
    sub information-content-entity,
    owns offset,
    owns length,
    plays fragmentation:part,
    plays quotation:quoted-fragment;


# NOTE - Agent-generated annotations
# Notes are information artifacts created by agents about other
# information entities. They are the primary unit of agent memory.
entity note,
    sub information-content-entity,
    owns confidence,
    plays aboutness:note,
    plays note-threading:parent-note,
    plays note-threading:child-note;


# -----------------------------------------------------------------------------
# ENTITY TYPES - Agents and Actors
# -----------------------------------------------------------------------------

# AGENT - Creator of notes and other content
# Can be human users, AI agents, or automated processes
entity agent,
    owns id @key,
    owns name,
    owns iri,
    plays authorship:author,
    plays classification:classified-entity;


# ORGANIZATION - Groups of agents
entity organization,
    owns id @key,
    owns name,
    owns iri,
    plays affiliation:organization,
    plays classification:classified-entity;


# -----------------------------------------------------------------------------
# ENTITY TYPES - External Vocabulary Classification
# -----------------------------------------------------------------------------

# VOCABULARY - A classification system (schema.org, Wikidata, UMLS, etc.)
entity vocabulary,
    owns id @key,
    owns name,
    owns iri,
    owns description;


# VOCABULARY-TYPE - A type from an external vocabulary
# Instead of inheriting from schema.org types, entities are *classified* by them
entity vocabulary-type,
    owns id @key,
    owns name,
    owns schema-org-uri,
    owns wikidata-qid,
    owns description,
    plays vocabulary-membership:vocab-type,
    plays vocabulary-membership:vocab,
    plays type-hierarchy:subtype,
    plays type-hierarchy:supertype,
    plays classification:type-facet;


# VOCABULARY-PROPERTY - A property from an external vocabulary
entity vocabulary-property,
    owns id @key,
    owns name,
    owns schema-org-uri,
    owns description,
    plays vocabulary-membership:vocab-type,
    plays property-assertion:property-definition,
    plays domain-range:property-def,
    plays domain-range:domain-type,
    plays domain-range:range-type;


# TAG - Lightweight classification without full vocabulary structure
entity tag,
    owns id @key,
    owns name,
    plays tagging:tag;


# -----------------------------------------------------------------------------
# RELATION TYPES - Core Relations
# -----------------------------------------------------------------------------

# ABOUTNESS - The fundamental "is about" relation (IAO:0000136)
# Connects notes to what they describe
relation aboutness,
    relates note,
    relates subject;


# REPRESENTATION - Connects artifacts to the things they represent
relation representation,
    relates artifact,
    relates referent;


# COLLECTION-MEMBERSHIP - Things belonging to collections
relation collection-membership,
    owns created-at,
    owns provenance,
    relates collection,
    relates member;


# COLLECTION-NESTING - Hierarchical collection organization
relation collection-nesting,
    relates parent-collection,
    relates child-collection;


# FRAGMENTATION - Parts of artifacts
relation fragmentation,
    relates whole,
    relates part;


# AUTHORSHIP - Who created what
relation authorship,
    owns created-at,
    relates author,
    relates work;


# AFFILIATION - Agent membership in organizations
relation affiliation,
    owns valid-from,
    owns valid-until,
    relates agent,
    relates organization;


# CITATION - References between artifacts
relation citation,
    owns provenance,
    relates citing-work,
    relates cited-work;


# QUOTATION - When a fragment quotes another
relation quotation,
    relates quoting-fragment,
    relates quoted-fragment;


# DERIVATION - Provenance chain for derived content
relation derivation,
    owns provenance,
    owns created-at,
    relates derivative,
    relates derived-from-source;


# NOTE-THREADING - Hierarchical note organization
relation note-threading,
    relates parent-note,
    relates child-note;


# PARTICIPATION - Things participating in events/situations
relation participation,
    owns role,
    relates participant,
    relates situation;

attribute role, value string;


# -----------------------------------------------------------------------------
# RELATION TYPES - Classification System
# -----------------------------------------------------------------------------

# CLASSIFICATION - Assigning vocabulary types to entities
# This is the key relation that allows multiple schema.org types per entity
relation classification,
    owns confidence,
    owns provenance,
    owns created-at,
    relates classified-entity,
    relates type-facet;


# VOCABULARY-MEMBERSHIP - Types belonging to vocabularies
relation vocabulary-membership,
    relates vocab,
    relates vocab-type;


# TYPE-HIERARCHY - Subtype relationships within vocabularies
relation type-hierarchy,
    relates subtype,
    relates supertype;


# DOMAIN-RANGE - Property constraints from vocabularies
relation domain-range,
    relates property-def,
    relates domain-type,
    relates range-type;


# TAGGING - Lightweight classification
relation tagging,
    owns created-at,
    relates tagged-entity,
    relates tag;


# PROPERTY-ASSERTION - Dynamic property assignment
# Allows attaching vocabulary-defined properties to entities
relation property-assertion,
    owns created-at,
    owns provenance,
    relates subject-entity,
    relates property-definition,
    relates value-string,
    relates value-entity;

attribute value-string, value string;

# Extend participation for property assertions
entity information-content-entity,
    plays property-assertion:subject-entity,
    plays property-assertion:value-entity;

entity vocabulary-property,
    plays property-assertion:property-definition;


# -----------------------------------------------------------------------------
# RELATION TYPES - N-ary Relations for Complex Assertions
# -----------------------------------------------------------------------------

# SEMANTIC-TRIPLE - For RDF-style assertions with provenance
relation semantic-triple,
    owns confidence,
    owns provenance,
    owns created-at,
    owns source-uri,
    relates triple-subject,
    relates triple-predicate,
    relates triple-object;

entity information-content-entity,
    plays semantic-triple:triple-subject,
    plays semantic-triple:triple-object;

entity vocabulary-property,
    plays semantic-triple:triple-predicate;


# EVIDENCE-CHAIN - Linking claims to supporting evidence
relation evidence-chain,
    owns confidence,
    relates claim,
    relates evidence,
    relates evidence-type;

entity note,
    plays evidence-chain:claim,
    plays evidence-chain:evidence;

attribute evidence-type, value string;

entity note,
    plays evidence-chain:evidence-type-holder;

# Simple workaround - use attribute for evidence type
relation evidence-chain,
    owns evidence-type;


# =============================================================================
# END SCHEMA
# =============================================================================
```

---

## Usage Examples

### 1. Creating a Thing with Multiple Schema.org Classifications

```typeql
# Insert a hospital that is both a MedicalOrganization and a CivicStructure
insert
    $hospital isa thing,
        has id "thing-hospital-001",
        has name "Massachusetts General Hospital",
        has description "A major teaching hospital in Boston";
    
    $med-org isa vocabulary-type,
        has id "schema-MedicalOrganization",
        has name "MedicalOrganization",
        has schema-org-uri "https://schema.org/MedicalOrganization";
    
    $civic isa vocabulary-type,
        has id "schema-CivicStructure",
        has name "CivicStructure",
        has schema-org-uri "https://schema.org/CivicStructure";
    
    # Multiple classifications - no inheritance conflict!
    (classified-entity: $hospital, type-facet: $med-org) isa classification,
        has confidence 1.0;
    
    (classified-entity: $hospital, type-facet: $civic) isa classification,
        has confidence 1.0;
```

### 2. Creating an Artifact about a Thing

```typeql
insert
    $paper isa artifact,
        has id "artifact-paper-001",
        has name "Clinical Outcomes Study 2024",
        has content "Full text of the paper...",
        has format "application/pdf",
        has source-uri "https://doi.org/10.1234/example";
    
    $hospital isa thing,
        has id "thing-hospital-001";
    
    # The paper represents/describes the hospital
    (artifact: $paper, referent: $hospital) isa representation;
```

### 3. Creating an Agent Note about an Artifact

```typeql
insert
    $agent isa agent,
        has id "agent-claude-001",
        has name "Claude Research Assistant";
    
    $paper isa artifact,
        has id "artifact-paper-001";
    
    $note isa note,
        has id "note-001",
        has name "Key Findings Summary",
        has content "This paper demonstrates a 23% improvement in patient outcomes...",
        has confidence 0.85,
        has created-at 2025-02-01T10:30:00;
    
    # The note is about the paper
    (note: $note, subject: $paper) isa aboutness;
    
    # The agent authored the note
    (author: $agent, work: $note) isa authorship;
```

### 4. Creating a Collection with Members

```typeql
insert
    $collection isa collection,
        has id "collection-covid-research",
        has name "COVID-19 Research Papers",
        has logical-query "papers about coronavirus published 2020-2024",
        has is-extensional false;
    
    $paper1 isa artifact, has id "artifact-paper-001";
    $paper2 isa artifact, has id "artifact-paper-002";
    
    (collection: $collection, member: $paper1) isa collection-membership;
    (collection: $collection, member: $paper2) isa collection-membership;
```

### 5. Creating Fragments of an Artifact

```typeql
insert
    $paper isa artifact,
        has id "artifact-paper-001";
    
    $abstract isa fragment,
        has id "fragment-abstract-001",
        has name "Abstract",
        has content "Background: This study examines...",
        has offset 0,
        has length 1500;
    
    $methods isa fragment,
        has id "fragment-methods-001",
        has name "Methods Section",
        has content "We conducted a randomized...",
        has offset 1500,
        has length 3000;
    
    (whole: $paper, part: $abstract) isa fragmentation;
    (whole: $paper, part: $methods) isa fragmentation;
```

### 6. Querying: Find All Notes About Things Classified as "Person"

```typeql
match
    $person-type isa vocabulary-type,
        has schema-org-uri "https://schema.org/Person";
    
    (classified-entity: $thing, type-facet: $person-type) isa classification;
    
    # Find artifacts about this person
    (artifact: $artifact, referent: $thing) isa representation;
    
    # Find notes about those artifacts
    (note: $note, subject: $artifact) isa aboutness;
    
fetch
    $thing: name;
    $note: name, content, confidence;
```

### 7. Querying: Get All Classifications for an Entity

```typeql
match
    $entity isa thing, has id "thing-hospital-001";
    (classified-entity: $entity, type-facet: $type) isa classification,
        has confidence $conf;
    $type has schema-org-uri $uri, has name $type-name;
    
fetch
    $type-name;
    $uri;
    $conf;
```

### 8. Using Functions (TypeDB 3.0) for Transitive Collection Membership

```typeql
# Define a function to get all nested collection members
define
fun get_all_members(collection: collection) -> { information-content-entity }:
    match
        (collection: $collection, member: $member) isa collection-membership;
    return { $member };

fun get_nested_members(collection: collection) -> { information-content-entity }:
    match
        # Direct members
        { (collection: $collection, member: $member) isa collection-membership; }
        or
        # Members of child collections
        {
            (parent-collection: $collection, child-collection: $child) isa collection-nesting;
            $member in get_nested_members($child);
        };
    return { $member };
```

---

## Schema.org Integration Strategy

### Importing Schema.org Types

To bootstrap the vocabulary types, you can parse schema.org's JSON-LD and generate insert statements:

```python
# Pseudocode for schema.org import
import json
from rdflib import Graph

# Load schema.org
g = Graph()
g.parse("https://schema.org/version/latest/schemaorg-current-https.jsonld", format="json-ld")

# Generate TypeQL inserts
for s, p, o in g.triples((None, RDFS.subClassOf, None)):
    subtype_uri = str(s)
    supertype_uri = str(o)
    
    print(f"""
    insert
        $sub isa vocabulary-type,
            has schema-org-uri "{subtype_uri}",
            has name "{subtype_uri.split('/')[-1]}";
        $super isa vocabulary-type,
            has schema-org-uri "{supertype_uri}";
        (subtype: $sub, supertype: $super) isa type-hierarchy;
    """)
```

### Multiple Inheritance Handling

Since schema.org uses multiple inheritance but TypeDB uses single inheritance, we handle this through multiple `type-hierarchy` relations:

```typeql
# Hospital has multiple parents in schema.org
insert
    $hospital-type isa vocabulary-type,
        has id "schema-Hospital",
        has schema-org-uri "https://schema.org/Hospital";
    
    $med-org isa vocabulary-type,
        has schema-org-uri "https://schema.org/MedicalOrganization";
    
    $civic isa vocabulary-type,
        has schema-org-uri "https://schema.org/CivicStructure";
    
    $emergency isa vocabulary-type,
        has schema-org-uri "https://schema.org/EmergencyService";
    
    # All three inheritance paths preserved as relations
    (subtype: $hospital-type, supertype: $med-org) isa type-hierarchy;
    (subtype: $hospital-type, supertype: $civic) isa type-hierarchy;
    (subtype: $hospital-type, supertype: $emergency) isa type-hierarchy;
```

---

## Implementation Notes

### Prerequisites

- TypeDB 3.0+ (for functions support)
- TypeDB Studio or Console for schema loading
- Python/Rust/Java driver for application integration

### Loading the Schema

```bash
# Start TypeDB
typedb server

# In another terminal, use console
typedb console

# Create database and load schema
> database create agent-memory
> transaction agent-memory schema write
> source /path/to/schema.tql
> commit
```

### Recommended Indexes

TypeDB automatically indexes `@key` attributes. For additional performance, consider:

1. Frequently queried attributes like `schema-org-uri`
2. Temporal attributes for time-range queries
3. The `content-hash` attribute for deduplication

### Vector Search Integration

TypeDB doesn't natively support vector search. For semantic retrieval, consider:

1. **Hybrid Architecture**: Store embeddings in pgvector/Qdrant, use TypeDB for structured queries
2. **Synchronized IDs**: Use the same `id` values across both systems
3. **Query Pipeline**: Vector search → retrieve IDs → TypeDB graph traversal

---

## Extending the Framework

### Adding New Vocabularies

To add support for Wikidata, UMLS, or domain-specific ontologies:

```typeql
insert
    $wikidata isa vocabulary,
        has id "vocab-wikidata",
        has name "Wikidata",
        has iri "https://www.wikidata.org/";
    
    $human isa vocabulary-type,
        has id "wd-Q5",
        has name "human",
        has wikidata-qid "Q5";
    
    (vocab: $wikidata, vocab-type: $human) isa vocabulary-membership;
```

### Custom Note Types

Extend the note entity for domain-specific annotations:

```typeql
define
    entity extraction-note,
        sub note,
        owns extraction-method,
        owns extraction-model;
    
    attribute extraction-method, value string;
    attribute extraction-model, value string;
```

---

## Comparison with Alhazen Notebook Model

| Alhazen Concept | This Framework | Notes |
|-----------------|----------------|-------|
| `Entity` | `information-content-entity` | Abstract root |
| `Thing` | `thing` | Same concept |
| `Collection` | `collection` | Added intensional support |
| `Artifact` | `artifact` | Same concept |
| `Fragment` | `fragment` | Same concept |
| `Note` | `note` | Same concept |
| `NAryRelation` | `semantic-triple`, `evidence-chain` | More specific relation types |
| `is about` | `aboutness` | Relation, not slot |
| `has representation` | `representation` | Relation, not slot |

Key differences:
1. Schema.org types are classifications, not inheritance
2. Relations are first-class (TypeDB native)
3. Temporal validity built into attributes
4. Confidence scores on classifications and notes

---

## License

This schema is released under the MIT License. Use freely for research and commercial applications.

---

## References

- [TypeDB Documentation](https://typedb.com/docs)
- [Schema.org](https://schema.org)
- [Information Artifact Ontology](http://www.obofoundry.org/ontology/iao.html)
- [LinkML](https://linkml.io/)
