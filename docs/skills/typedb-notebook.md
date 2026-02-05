# TypeDB Notebook Skill

The `/typedb-notebook` skill provides core knowledge operations for the Alhazen system. It's the foundational skill that other skills build upon.

## Overview

This skill handles the fundamental operations:
- **Remember** - Store findings with provenance
- **Recall** - Query what you know about topics
- **Organize** - Manage collections and relationships

## Quick Start

### Remember a Finding

```
You: Remember that the Smith et al. paper found lipid nanoparticles
     were 3x more effective than viral vectors for liver targeting

Claude: [Creates note with provenance]

Noted. I've stored this finding and linked it to the Smith et al. paper.
The note includes:
- Content: Your finding about 3x effectiveness
- Source: Smith et al. paper
- Timestamp: Now
- Type: Research finding
```

### Recall Knowledge

```
You: What do I know about lipid nanoparticles?

Claude: [Queries notes, papers, fragments]

From your knowledge graph:

**Notes:**
- LNPs are 3x more effective than viral vectors for liver (Smith et al.)
- Ionizable lipids are key component for endosomal escape (Chen et al.)

**Papers in collections:**
- 5 papers in "CRISPR Delivery Review" mention LNPs

**Related topics:**
- mRNA delivery
- Gene therapy
- Liver targeting
```

### Organize Collections

```
You: Create a collection called "PhD Literature Review"

Claude: [Creates collection]

Created collection "PhD Literature Review".

You: Add the paper with DOI 10.1038/s41586-023-00001-1 to it

Claude: [Adds paper to collection]

Added to "PhD Literature Review".
```

## Note Types

You can create different types of notes:

| Type | Purpose | Example |
|------|---------|---------|
| `finding` | Key result or claim | "LNPs are 3x more effective..." |
| `question` | Open research question | "Why do LNPs work better in liver?" |
| `critique` | Critical analysis | "Small sample size in Table 2..." |
| `connection` | Link between ideas | "This relates to Chen's work on..." |
| `summary` | Synthesis of sources | "Three papers agree that..." |
| `todo` | Action item | "Read the methods section" |

## Core Entities

### Collections

Named groups for organizing knowledge:

```
You: What collections do I have?

Claude: [Lists collections with counts]

Your collections:
- PhD Literature Review (23 papers, 12 notes)
- CRISPR Delivery (5 papers, 8 notes)
- Job Hunt Q1 (handled by /jobhunt skill)
```

### Things

Any item you're tracking:
- Papers
- Datasets
- Tools
- People
- Organizations

### Artifacts

Raw captured content with provenance:
- PDF documents
- Web page snapshots
- API responses
- Email threads

### Fragments

Extracted portions of artifacts:
- Quotes
- Figures
- Tables
- Key sentences

### Notes

Your annotations about any entity:
- Findings
- Questions
- Critiques
- Summaries

## Provenance Chain

Every piece of knowledge traces back to its source:

```
Artifact (PDF of Smith et al. paper)
    ↓
Fragment (quote from Results section)
    ↓
Note (your finding about 3x effectiveness)
```

You can always ask: "Where did this come from?"

```
You: Where did the 3x effectiveness finding come from?

Claude: [Traces provenance]

This finding comes from:
- Your note created on 2024-02-01
- Based on fragment from Smith et al. Results section (page 7)
- Original artifact: PDF downloaded from Nature.com
```

## Search and Query

### Text Search

```
You: Search my notes for "effectiveness"

Claude: [Full-text search across notes]

Found 3 notes mentioning "effectiveness":
1. LNPs 3x more effective for liver... (Smith et al.)
2. AAV shows higher effectiveness in CNS... (Jones et al.)
3. Comparison of effectiveness across tissues... (your synthesis)
```

### By Entity Type

```
You: List all papers I have notes about

Claude: [Queries papers with linked notes]

Papers with your notes:
- Smith et al. 2023 - 4 notes
- Jones et al. 2022 - 2 notes
- Chen et al. 2024 - 1 note
```

### By Time

```
You: What did I add last week?

Claude: [Queries by timestamp]

Last week you added:
- 3 papers to "CRISPR Delivery"
- 5 notes about delivery mechanisms
- 1 new collection "Vaccine Development"
```

## Integration with Other Skills

The typedb-notebook skill underlies other skills:

- **/jobhunt** uses it for companies, positions, and notes
- **/epmc-search** uses it for papers and collections
- **/domain-modeling** extends its schema for new domains

Think of it as the operating system for your knowledge graph.
