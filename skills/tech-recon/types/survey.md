---
type: survey
label: Survey
short: SURV
icon: book
color: olive
---

# Survey Investigation

## When to use

The user wants to build understanding of a field — "what's the state of the art in X?", "survey the literature on Y", "I need a related works section on Z." The goal is comprehensive domain knowledge organized thematically. Sources are primarily academic papers and preprints.

## Interview adjustments

Replace the 8-question interview with scope definition:
1. What field or topic are you surveying?
2. What's the scope? (narrow subtopic vs. broad area)
3. What time period matters? (last 2 years? historical evolution? specific milestone onward?)
4. Are there seed papers or key authors you already know?
5. What's the output for? (related works section? self-education? teaching material?)
6. What themes or sub-questions should the survey address?

After Q6, define 3-5 initial themes to organize the survey around.

## Discovery phase

Use the scientific-literature skill for systematic paper search:
- PubMed for biomedical topics
- arXiv/OpenAlex for CS/ML topics
- Semantic Scholar for citation graph exploration
- Start from seed papers and expand via citations (both citing and cited-by)

Create systems to represent **themes/subtopics**, not individual papers. For example, a survey of "agentic AI in drug development" might have themes: "target identification", "molecule generation", "clinical trial design", "regulatory AI."

Papers are first-class artifacts — use `ingest-pdf` and `ingest-page` to capture them.

## Sensemaking strategy

Organize by theme. Each theme gets notes that synthesize across papers:

### Expected note topics
- `theme-summary` — What is this theme about? What are the key developments?
- `key-findings` — The 3-5 most important results or insights in this theme
- `methodology-notes` — Common methods, benchmarks, datasets used
- `citation-clusters` — Groups of papers that cite each other heavily (intellectual communities)
- `timeline` — Chronological evolution of ideas within this theme
- `gaps` — What questions remain unanswered? What's missing from the literature?

Notes should use proper citations (author, year, title) and be written in a style suitable for academic prose.

## Analysis phase

Visualizations should support understanding:
- Theme map (themes and their relationships)
- Publication timeline (papers by year, colored by theme)
- Citation network (which papers cite which)
- Author collaboration map
- Methodology comparison table

## Output expectations

**Synthesis report** should contain:
1. Scope statement and methodology (what was searched, how)
2. Per-theme narrative (2-4 paragraphs each)
3. Cross-cutting observations
4. Timeline of key developments
5. Open questions and future directions
6. Complete reference list

The report should be written in a style appropriate for the stated purpose (related works section = academic; self-education = tutorial; teaching = explainer).

**Completion assessment** should confirm coverage across defined themes.

## Completion criteria

The investigation is complete when:
- Each defined theme has at least 3-5 papers and a narrative summary
- Cross-theme connections have been identified
- A timeline of key developments exists
- Open questions have been articulated
- The user confirms the coverage is sufficient for their purpose
