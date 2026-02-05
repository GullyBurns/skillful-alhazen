# Europe PMC Search Skill

The `/epmc-search` skill searches Europe PMC's database of scientific papers and stores results in the knowledge graph.

## Overview

[Europe PMC](https://europepmc.org/) provides free access to over 40 million biomedical and life sciences publications. This skill lets you:

- Search by keyword, author, date, or complex queries
- Count results before fetching
- Add papers to collections
- Store metadata for analysis

## Quick Start

### Search for Papers

```
You: Search for papers about CRISPR delivery mechanisms

Claude: [Searches Europe PMC]

Found 1,247 papers matching "CRISPR delivery mechanisms".
Top 10 by citation count:

| Title | Authors | Year | Citations |
|-------|---------|------|-----------|
| Lipid nanoparticles for CRISPR... | Smith et al. | 2023 | 847 |
| Viral vectors in gene editing... | Jones et al. | 2022 | 612 |
...

Want me to add any of these to a collection?
```

### Count Results First

```
You: How many papers are there about single-cell RNA sequencing from 2023?

Claude: [Counts without fetching]

There are 4,821 papers matching:
- Query: "single-cell RNA sequencing"
- Year: 2023
- Source: Europe PMC

Want me to fetch the top results?
```

### Create Collections

```
You: Add the top 5 papers to a collection called "CRISPR Delivery Review"

Claude: [Creates collection, adds papers]

Created collection "CRISPR Delivery Review" with 5 papers.
Each paper has been stored with its metadata (authors, abstract, DOI, etc.)
```

### Advanced Queries

Europe PMC supports Boolean operators and field-specific searches:

```
You: Search for papers by "Jennifer Doudna" about Cas9 from 2020-2023

Claude: [Constructs query: AUTH:"Jennifer Doudna" AND Cas9 AND (FIRST_PDATE:[2020 TO 2023])]

Found 47 papers...
```

## Query Syntax

### Boolean Operators

| Operator | Example |
|----------|---------|
| AND | `CRISPR AND delivery` |
| OR | `lipid OR viral` |
| NOT | `CRISPR NOT Cas9` |

### Field-Specific Searches

| Field | Syntax | Example |
|-------|--------|---------|
| Author | `AUTH:"name"` | `AUTH:"Jennifer Doudna"` |
| Title | `TITLE:term` | `TITLE:CRISPR` |
| Abstract | `ABSTRACT:term` | `ABSTRACT:nanoparticle` |
| Journal | `JOURNAL:"name"` | `JOURNAL:"Nature"` |
| Year | `FIRST_PDATE:year` | `FIRST_PDATE:2023` |
| Year range | `FIRST_PDATE:[from TO to]` | `FIRST_PDATE:[2020 TO 2023]` |
| DOI | `DOI:value` | `DOI:10.1038/s41586-023-00000-0` |
| PMID | `EXT_ID:value` | `EXT_ID:12345678` |

### Open Access Filter

```
You: Search for open access papers about protein folding

Claude: [Adds OPEN_ACCESS:y to query]

Found 3,412 open access papers...
```

## What Gets Stored

When papers are added to a collection, Claude stores:

| Field | Description |
|-------|-------------|
| `title` | Paper title |
| `authors` | Author list |
| `journal` | Journal name |
| `year` | Publication year |
| `abstract` | Full abstract |
| `doi` | Digital Object Identifier |
| `pmid` | PubMed ID |
| `pmcid` | PubMed Central ID |
| `citation_count` | Number of citations |
| `source_url` | Link to Europe PMC |

## Use Cases

### Literature Review

```
You: I'm reviewing the field of spatial transcriptomics.
     Search for the most cited papers from 2021-2024.

Claude: [Searches, returns sorted by citations]
...

You: Add the top 20 to a "Spatial Transcriptomics Review" collection

Claude: [Creates collection with papers]

You: What methods are most commonly mentioned in these abstracts?

Claude: [Analyzes abstracts, extracts method mentions]

Based on the abstracts:
- Visium (mentioned in 14/20)
- MERFISH (mentioned in 8/20)
- Slide-seq (mentioned in 6/20)
...
```

### Author Tracking

```
You: Find all papers by our lab's collaborator, Dr. Jane Smith at MIT

Claude: [Searches AUTH:"Jane Smith" with affiliation filter]

Found 23 papers by Jane Smith with MIT affiliation...
```

### Finding Key Papers

```
You: What are the foundational papers on AlphaFold?

Claude: [Searches "AlphaFold" sorted by citation count]

The most cited AlphaFold papers are:
1. "Highly accurate protein structure prediction..." (Nature, 2021) - 12,847 citations
2. "AlphaFold Protein Structure Database..." (NAR, 2022) - 4,231 citations
...
```

## Data Model

Papers are stored as `scilit-paper` entities with:
- Metadata as attributes
- Collection membership via `in-collection` relation
- Notes for your annotations
