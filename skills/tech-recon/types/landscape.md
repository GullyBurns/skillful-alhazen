---
type: landscape
label: Landscape
short: LAND
icon: grid
color: teal
---

# Landscape Investigation

## When to use

The user wants to map a space — "what tools exist for X?", "compare frameworks for Y", "what are the options for Z?" The goal is breadth first, then selective depth, ending with a ranked comparison and recommendation.

## Interview adjustments

Run all 8 questions from USAGE.md. Emphasize:
- Q2 (success criteria) — these become the columns of your comparison matrix
- Q3 (known tools) — seeds the discovery phase
- Q8 (non-negotiables) — these are hard filters, not scored criteria

After Q8, synthesize success criteria as a bullet list where each bullet is a scorable dimension.

## Discovery phase

Search broadly — web search, GitHub topics, Hugging Face, academic papers. Target 5-10 candidates initially, then narrow to 4-7 for deep ingestion after user approval. Aim for coverage: include obvious leaders AND underdog/emerging options.

For each candidate, create a system with `add-system` and present a summary table to the user for approval before ingestion.

## Sensemaking strategy

Dispatch parallel subagents — one per approved system. Each subagent ingests sources, then writes structured notes covering the standard topics:

### Expected note topics
- `architecture` — High-level design, components, data flow
- `api` — Key APIs, interfaces, entry points
- `data-model` — Schema, types, data structures
- `integration` — How to embed or connect to other systems
- `assessment` — Overall fit against success criteria (score each criterion)
- `context-storage` — How the system stores and retrieves context (if applicable)

Each note should explicitly reference the success criteria and score the system against them.

## Analysis phase

Visualizations should support comparison:
- Comparison matrix (systems x criteria, scored)
- Feature gap chart (which criteria are met by how many systems)
- Language/ecosystem distribution
- Community health indicators (stars, commits, contributors over time)

Use `plan-analyses` to generate a visualization plan, then implement with Observable Plot.

## Output expectations

**Synthesis report** should contain:
1. Executive summary: recommended system + runner-up with rationale
2. Comparison matrix with scores
3. Per-system assessment summaries
4. Gaps and caveats
5. Quarterly monitoring checklist (repos/sources to watch)

**Completion assessment** should confirm all success criteria were scored for all systems.

## Completion criteria

The investigation is complete when:
- Every approved system has notes for architecture, api/data-model, and assessment
- A comparison matrix exists covering all success criteria
- A synthesis report names a winner with explicit rationale
- The user has reviewed and accepted the recommendation
