---
type: question
label: Question
short: QUES
icon: circle
color: blue
---

# Question Investigation

## When to use

The user has a specific technical question — "how do people solve X?", "is there a way to do Y?", "what's the best practice for Z?" The goal is to find approaches that address the question, compare them, and synthesize an answer. The unit of analysis is "approach" or "solution pattern," not "product."

## Interview adjustments

Replace the 8-question interview with a focused question refinement:
1. What is the question? (Get the exact formulation)
2. What have you already tried or considered?
3. What constraints matter? (language, performance, licensing, etc.)
4. What would a good answer look like? (a single recommendation? a trade-off analysis? a how-to guide?)
5. How confident do you need to be? (quick survey vs. exhaustive review)

After Q5, restate the question precisely and confirm with the user.

## Discovery phase

Search broadly across heterogeneous sources:
- Academic papers (via scientific-literature skill)
- Blog posts and technical articles (web search)
- Stack Overflow / GitHub discussions
- Tool documentation that addresses the problem
- Conference talks and tutorials

The unit is "source that addresses the question," not "system." Use `add-system` to represent distinct approaches/solutions rather than products. For example, if the question is "how to do schema migration in graph DBs?", approaches might be: "blue-green deployment", "incremental migration", "schema versioning."

## Sensemaking strategy

Organize findings by approach, not by source. Each approach gets its own set of notes:

### Expected note topics
- `approach-summary` — What is this approach? How does it work?
- `evidence` — What sources support this approach? What's the evidence quality?
- `trade-offs` — Pros, cons, and conditions where this approach works best/worst
- `implementation-notes` — Practical details for applying this approach
- `synthesis` — Cross-approach comparison and recommendation

Notes should cite their sources explicitly.

## Analysis phase

Visualizations should support understanding:
- Approach comparison table (approach x dimensions)
- Evidence quality assessment (source type, recency, relevance)
- Decision tree (if conditions → then approach)
- Trade-off radar chart

## Output expectations

**Synthesis report** should contain:
1. The question, precisely stated
2. Summary of approaches found (3-7 typically)
3. Per-approach assessment with evidence
4. Trade-off analysis: when to use which approach
5. Recommended approach for the user's specific context
6. Confidence assessment: how well-supported is this answer?
7. Open questions that remain

**Completion assessment** should confirm the question has been answered with cited evidence.

## Completion criteria

The investigation is complete when:
- At least 3 distinct approaches have been identified and assessed
- Each approach has evidence from at least 2 independent sources
- A trade-off analysis explains when each approach is appropriate
- A recommendation is made for the user's specific context
- The user confirms the answer addresses their question
