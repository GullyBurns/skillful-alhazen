# Notes on Evaluation

Design notes for evaluating tech-recon investigations. The core idea: instead of measuring whether tech-recon found the same information as a human curator, measure whether **the thing tech-recon produced actually does what it's supposed to do**.

---

## Outcome-based evaluation

Every investigation type produces an artifact. The evaluation question is: **does that artifact work?**

### Three levels of "does it work?"

1. **Structural validity** -- Does the output have the right shape? Did the landscape produce a matrix covering all criteria? Did the question investigation produce an answer with cited evidence? Checkable automatically against the type prompt's completion criteria.

2. **Factual accuracy** -- Are the claims correct? Are system descriptions accurate? Are cited papers real and relevant? Requires a gold standard or a verifier (LLM-as-judge, human reviewer, automated fact-checking against source material).

3. **Functional success** -- Does the produced artifact work when you act on it? The landscape recommended Framework X -- can you build a prototype with it? The question says "use approach Y" -- does it solve the problem? This is the real test.

---

## Investigation type to PoC artifact mapping

### Landscape --> Benchmark harness

The investigation surveyed a space and recommended a tool. The PoC: build a minimal benchmark that runs the same task on the top 2-3 candidates and confirms the recommendation holds.

- **Example**: Investigation recommends CrewAI over LangGraph for multi-agent orchestration.
- **PoC**: Python script implementing the same agent task in both frameworks.
- **Test**: Does CrewAI actually perform better on the criteria from the investigation?
- **Output**: Comparison table with real measurements, not just claims from docs.
- **Automatable**: Yes.

The PoC doesn't just validate the recommendation -- it *is* the deliverable. The investigation produced a hypothesis, the benchmark tests it.

### Evaluation --> Integration prototype

The investigation assessed one tool for fit. The PoC: build the minimal integration that proves it works in your stack.

- **Example**: Investigation says "Mem0 can serve as our memory layer, but graph-mode requires custom adapters."
- **PoC**: Script that connects Mem0 to TypeDB, stores a memory, retrieves it, verifies round-trip.
- **Test**: Does the integration actually work? What breaks? How long did it take vs. the effort estimate?
- **Output**: Working integration code + discrepancy report (investigation said X, reality was Y).
- **Automatable**: Yes.

This is the most natural PoC -- evaluations are *about* deciding whether to build something, so the PoC *is* the next step.

### Question --> Worked example

The investigation found approaches to a technical problem. The PoC: implement the recommended approach on a concrete example and verify it solves the problem.

- **Example**: Investigation says "For schema migration in graph DBs, use blue-green deployment with shadow writes."
- **PoC**: Script that performs a schema migration on a test TypeDB database using the recommended approach.
- **Test**: Does the migration complete without data loss? Does the app continue working during migration?
- **Output**: Working migration script + test results.
- **Automatable**: Yes.

The PoC is literally "does this advice work when you follow it?"

### Survey --> Coverage dataset + gap detector

The investigation built understanding of a field. The PoC is fuzzier -- there's no single "thing to build":

- **Option A: Structured dataset** -- Turn the survey into a structured dataset (papers x themes x methods x findings) and validate coverage against a known review.
- **Option B: Gap analysis tool** -- Build a query that surfaces papers the survey missed, using the survey's own theme taxonomy as search terms.
- **Option C: Teaching artifact** -- Generate a study guide from the survey and have it reviewed.

- **Example**: Investigation surveys "agentic AI in drug development."
- **PoC**: TypeDB query retrieving all papers by theme, plus a gap-detection query searching PubMed for recent papers in each theme.
- **Test**: Does the theme taxonomy cover the field? Are there obvious papers the survey missed?
- **Output**: Coverage report + gap list.
- **Automatable**: Partially.

### Monitor --> Alert pipeline

The investigation tracks a field over time. The PoC: build an automated check that detects the signals you defined.

- **Example**: Investigation monitors "open-weight reasoning models" with signals: new model releases, benchmark results, paper counts.
- **PoC**: Script querying GitHub releases, arXiv, and PwC for defined signals, producing a delta summary.
- **Test**: Run on a known time period where you already know what happened. Does it catch the same developments?
- **Output**: Working monitor script + validation against a known delta.
- **Automatable**: Yes.

The PoC becomes a *real tool* -- if the monitor pipeline works, the investigation becomes self-sustaining.

### Brief --> Document + reader test

The investigation produced a document for an audience. The PoC tests: does the document serve its purpose?

- **Option A: Comprehension test** -- Generate quiz questions from the brief, have the target audience answer them.
- **Option B: Decision simulation** -- Present the brief to an LLM role-playing the target audience, see if they make the expected decision.
- **Option C: Format compliance** -- Check the document against its format specification.

- **Automatable**: Partially (LLM-as-judge for Options A and B).

---

## Summary

| Type | PoC artifact | What it tests | Automatable? |
|------|-------------|---------------|-------------|
| Landscape | Benchmark harness | Does the recommendation hold under real comparison? | Yes |
| Evaluation | Integration prototype | Does the tool actually work in your stack? | Yes |
| Question | Worked example | Does the recommended approach solve the problem? | Yes |
| Survey | Coverage dataset + gap detector | Is the field coverage complete and accurate? | Partially |
| Monitor | Alert pipeline | Do the defined signals actually detect changes? | Yes |
| Brief | Document + reader test | Does the audience get what they need? | Partially |

**Key observation**: Four out of six produce a reusable tool as the PoC. The benchmark harness, integration prototype, worked example, and alert pipeline aren't throwaway test artifacts -- they're things you'd actually want to keep. The evaluation harness doesn't just score the investigation, it produces the *next deliverable*.

---

## Evaluation harness architecture

### Claim extraction pipeline

```
Investigation output (TypeDB)
    |
    v
Claim extractor (parse notes/synthesis into testable claims)
    |
    v
Claim verifier (per claim type):
    - "X exists" --> check URL, check GitHub, check API
    - "X has feature Y" --> read docs, grep source code
    - "X outperforms Z on metric M" --> find benchmark data
    - "Use X for task T" --> generate a minimal PoC and run it
    |
    v
Scorecard: { verified, refuted, unverifiable, untested }
```

### Gold standard datasets (from investigation tri-b0fc5973d6e9)

| Investigation type | Best gold standard | Source |
|---|---|---|
| Landscape | Awesome Lists (curated tool inventories) | GitHub, parseable markdown |
| Evaluation | FAIRsharing (structured DB registry) | REST API |
| Question | TREC tracks (CDS, RAG) | NIST, registration required |
| Survey | SR Screening Benchmarks (SYNERGY, CLEF TAR) | Open datasets |
| Monitor | State-of Annual Reports (Stanford AI Index) | PDFs + Kaggle data |
| Brief | (Weak -- no strong benchmark) | Gap to fill |

### Recommended starting points

1. **SYNERGY benchmark** for survey-type evaluation (26 reviews, 169K records)
2. **awesome-ai-agents-2026** for landscape pilot (340+ entries, 20 categories)
3. **TREC CDS 2016** for question-type pilot (30 clinical topics with qrels)

### Key gap

No existing benchmark evaluates **sensemaking quality** -- the quality of synthesized analysis notes. All benchmarks evaluate retrieval or classification, not the quality of the analysis itself. This may be the most valuable benchmark to build.
