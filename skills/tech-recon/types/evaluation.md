---
type: evaluation
label: Evaluation
short: EVAL
icon: target
color: mint
---

# Evaluation Investigation

## When to use

The user already knows the system and wants to assess whether it fits their specific context — "should we use X?", "is X right for our use case?", "what would it take to adopt X?" The goal is depth on one system (or a small fixed set of 2-3), measured against the user's requirements.

## Interview adjustments

Modify the 8-question interview:
- Q1 (problem) — Focus on the specific decision: what are you trying to decide?
- Q2 (success criteria) — Frame as requirements: what must the system do for you?
- Q3 (known tools) — This IS the system under evaluation. Ask: "What specifically do you want to evaluate about it?"
- Q5 (scale) — Critical: what are your actual load/performance requirements?
- Q7 (timeline) — Is this a decision with a deadline?
- **Add**: "What's your fallback if this doesn't work?" (identifies the build-vs-buy dimension)

After Q8, synthesize as a requirements checklist, not a comparison matrix.

## Discovery phase

Discovery is minimal or skipped — the user already knows the system. Focus on:
- Ingest the system's documentation deeply (not just landing page)
- Clone the repo and explore the source code
- Find real-world adoption examples, case studies, post-mortems
- Search for known issues, limitations, failure modes

Create 1-3 systems max. The emphasis is depth, not breadth.

## Sensemaking strategy

Single-system deep dive. Notes are organized around your requirements, not the system's features:

### Expected note topics
- `requirements-gap` — For each requirement, does the system meet it? Evidence?
- `risk-assessment` — Technical risks, vendor risks, community risks, lock-in risks
- `effort-estimate` — What's the integration effort? What would need to change in your stack?
- `integration-feasibility` — Can it connect to your existing systems? What are the friction points?
- `architecture` — Deep dive on internals relevant to your use case
- `assessment` — Overall go/no-go recommendation with rationale

Each note should explicitly reference the user's requirements and provide evidence.

## Analysis phase

Visualizations should support decision-making:
- Requirements heatmap (requirement x status: met/partial/unmet)
- Risk matrix (likelihood x impact)
- Effort breakdown (components x estimated effort)
- Comparison with fallback option (if identified)

## Output expectations

**Synthesis report** should contain:
1. Go/no-go recommendation with explicit rationale
2. Requirements checklist with pass/partial/fail per requirement
3. Risk register with mitigation strategies
4. Effort estimate with timeline
5. Key caveats and assumptions

**Completion assessment** should confirm all requirements were evaluated with evidence.

## Completion criteria

The investigation is complete when:
- Every stated requirement has a pass/partial/fail assessment with evidence
- A risk register exists with at least the top 3 risks
- An effort estimate exists (even if rough)
- A clear go/no-go recommendation is made with rationale
- The user has reviewed the recommendation
