---
name: single-paper-deep-dive
description: Deep analysis of a single research paper — extracts primary, secondary, and peripheral claims, traces all evidence back to primary experimental data, and maps how subsequent papers have engaged with the original claims.
triggers:
  - analyze this paper
  - deep dive
  - paper deep dive
  - single paper deep dive
  - analyze paper claims
  - trace evidence
  - what does this paper actually claim
  - review the evidence in this paper
  - analyze the claims in this paper
prerequisites:
  - TypeDB running (make db-start)
  - At least one of: paper DOI, arXiv ID, PubMed ID, file path to PDF, or URL
read_strategy:
  starting_analysis: "Read Overview, Input Handling, Claim Taxonomy, Evidence Protocol"
  review_paper: "Read Overview, Claim Taxonomy, Evidence Protocol, Review Protocol"
  citation_impact: "Read Citation Impact Protocol, Scope Management"
  storing_results: "Read Storage Pattern, Command Output Pattern"
---

## Overview

Single Paper Deep Dive performs a structured, exhaustive analysis of one research paper. It systematically extracts and classifies every claim the paper makes, traces each claim's evidence back to the original experimental data (even through multiple layers of citation), and maps how the paper's claims have been received by subsequent work.

**This is a research-intensive task.** A thorough deep dive involves reading the focal paper, fetching and reading dozens of cited papers and citing papers, and carefully recording experimental designs and raw data. Begin by storing the analysis skeleton in TypeDB early, then fill it in claim by claim. Save progress frequently.

The analysis is scoped to a maximum of 100 external sources. At that limit, compile a "Further Investigation Map" of sources identified but not read, and mark the analysis complete.

## Quick Start

```bash
# Start a new analysis (do this first — creates the TypeDB record)
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py new-analysis \
  --doi "10.1038/s41586-023-XXXXX" --title "Paper Title" --year 2023 2>/dev/null

# Add a primary claim
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py add-claim \
  --analysis-doi "10.1038/..." \
  --type primary \
  --statement "Transformer architectures achieve 28.4 BLEU on WMT En-De, surpassing all prior RNN-based models" 2>/dev/null

# Add evidence for that claim
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py add-evidence \
  --analysis-doi "10.1038/..." \
  --claim-statement "Transformer architectures achieve 28.4 BLEU on WMT En-De, surpassing all prior RNN-based models" \
  --evidence-type experimental \
  --source-doi "10.48550/arXiv.1706.03762" \
  --source-title "Attention Is All You Need" \
  --experimental-design "WMT 2014 English-German translation, 4.5M sentence pairs, trained on 8 P100 GPUs for 3.5 days, compared against best prior LSTM ensemble (26.0 BLEU)" \
  --data-summary "Transformer big: 28.4 BLEU (new state of the art). Prior best: 26.0 BLEU ensemble. Single model: 27.3 BLEU." 2>/dev/null

# Record citation impact
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py add-citation-impact \
  --analysis-doi "10.1038/..." \
  --citing-doi "10.48550/arXiv.1810.04805" \
  --citing-title "BERT: Pre-training of Deep Bidirectional Transformers" \
  --impact-type extends \
  --impact-summary "Adopts transformer encoder architecture and scales to 340M parameters; demonstrates generalization to 11 NLP tasks, extending beyond the translation setting." 2>/dev/null

# Retrieve stored analysis
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py get-analysis \
  --doi "10.1038/..." 2>/dev/null

# Export as markdown
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py export-analysis \
  --doi "10.1038/..." 2>/dev/null
```

## Input Handling

Accept the paper in any of these forms:

| Input type | Examples | Resolution |
|---|---|---|
| DOI | `10.1038/s41586-023-12345-6`, `https://doi.org/10.xxxx` | Use `mcp__get_article_metadata` + `mcp__get_full_text_article` |
| arXiv ID | `2303.12345`, `arXiv:2303.12345`, `https://arxiv.org/abs/2303.12345` | Use `mcp__convert_article_ids` to get DOI, then fetch |
| PMID | Numeric ID | Use `mcp__convert_article_ids` to get DOI, then fetch |
| Local PDF | `/path/to/paper.pdf` | Use the PDF skill to read the document |
| URL | Paper landing page or direct PDF | Use `WebFetch` |

**Always normalize to a DOI** for TypeDB storage. If a DOI cannot be found, use the arXiv ID (prefixed `arxiv:`) or a URL as the identifier.

**Resolution order:**
1. Try `mcp__get_full_text_article` with the DOI — this often returns full text directly
2. Try `WebFetch` on the DOI redirect URL (`https://doi.org/<doi>`)
3. Try the arXiv PDF URL if it's an arXiv paper
4. Use `WebSearch` for "[author] [title] PDF" as a last resort

## Claim Taxonomy

Every claim the paper makes belongs to exactly one tier. Read the whole paper before finalizing classifications — a claim that looks peripheral in the abstract may be central to the argument in the results.

### Primary Claims
The paper's core contributions to knowledge. What the authors are arguing the field should now believe or do differently as a result of this paper. Usually 1–4 per paper.

**Hallmarks**: in the abstract, restated in the conclusion, would make the paper non-publishable if false.

**Write as**: a precise, falsifiable statement with specific quantities where possible.
- ❌ "The method performs well"
- ✓ "Method X achieves 94.2% F1 on dataset Y, a 3.1-point improvement over the prior SOTA baseline Z"

### Secondary Claims
Claims made to justify, support, or contextualize the primary claims. Often methodological ("this experimental design is valid because..."), comparative ("our method is faster than X"), or intermediate results. Usually 5–20 per paper.

**Hallmarks**: in Results or Methods; removing them would weaken but not destroy the primary claims.

### Peripheral Claims
Scientific assertions made in passing — background statements treated as established, brief mentions of related work findings, or minor observations in Discussion. Often highly important if they turn out to be contested.

**Hallmarks**: "it is known that...", "previous work has shown...", citations to established facts, or speculative discussion points.

**Do not skip peripheral claims.** They often contain the most interesting unexamined assumptions.

## Evidence Protocol

For each claim, identify and record all evidence the paper uses to support it.

### Step 1: Identify the evidence type

| Type | Definition |
|---|---|
| experimental | Controlled manipulation; comparison between conditions |
| observational | Measurement without intervention |
| computational | In silico analysis, model output, simulation |
| review | Synthesized evidence from other studies (must be traced further) |
| theoretical | Mathematical proof, formal argument |
| anecdotal | Single case, expert opinion, qualitative example |

### Step 2: For experimental and observational evidence, record all of:

1. **What was the study system?** (Cell line, animal model, patient cohort, dataset, benchmark...)
2. **What was the intervention or variable?** (Drug dose, model architecture, training regime...)
3. **What was measured?** (Accuracy, survival, expression level, BLEU score...)
4. **What was the comparison?** (Control group, baseline model, prior SOTA...)
5. **What was the sample size?** (n=?, number of runs, replicate structure...)
6. **What statistical approach was used?** (p-values, confidence intervals, Bayesian posteriors...)
7. **What were the key numbers?** (The actual results, not just "improved")

### Step 3: Trace citations to primary data

If the evidence for a claim comes from a cited paper:
1. Retrieve that paper: `mcp__get_article_metadata` + `mcp__get_full_text_article`
2. Find the specific result being cited in that paper
3. Record the experimental design and data FROM THAT PAPER
4. Count it toward your source budget

**If the cited paper is itself a review** — keep tracing until you reach a primary experimental study (max 3 hops). Flag any chain that ends in a review with no primary study as "evidence chain unresolved."

**Stop tracing when**:
- You reach a primary experimental study with original data
- The source is not publicly accessible after two retrieval attempts
- You hit 80 sources (begin compiling Further Investigation Map instead)

### Step 4: Record the evidence

```bash
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py add-evidence \
  --analysis-doi "DOI" \
  --claim-statement "EXACT CLAIM TEXT" \
  --evidence-type experimental \
  --source-doi "SOURCE DOI" \
  --source-title "Source paper title" \
  --experimental-design "What system? What manipulation? What measured? What compared? n=? Statistics?" \
  --data-summary "The actual numbers: e.g. 94.2% F1 vs 91.1% baseline, p<0.001, 95% CI [93.1, 95.3]" 2>/dev/null
```

**The `--claim-statement` must match exactly** what was stored with `add-claim`. Copy it precisely.

## Review Paper Protocol

If the focal paper is a review (systematic review, meta-analysis, narrative review, scoping review):

1. **Identify the review's methodology**: systematic with defined inclusion/exclusion criteria? Narrative? Meta-analysis with pooled statistics?
2. **All primary claims must cite primary studies** — a review cannot generate its own evidence
3. **For each primary claim**, identify the 3–5 most important supporting studies and retrieve them
4. **For meta-analyses**: record inclusion/exclusion criteria, number of included studies, heterogeneity (I²), pooled effect size with CI
5. **Flag unsupported claims**: if a review makes a claim with only narrative citations or no citation, mark the evidence as `anecdotal`

For nested reviews (review citing review):
- Hop 1: Read the first-level cited review
- Hop 2: Find its primary study citations for the relevant claim
- Hop 3: Retrieve and read those primary studies
- **Maximum depth: 3 hops**. If you cannot reach primary data in 3 hops, note this explicitly.

## Citation Impact Protocol

After completing the evidence analysis, survey how the paper's claims have been received by subsequent work. This answers: "Has the field accepted these claims? Disputed them? Extended them?"

**Target**: 5–10 citing papers per primary claim, up to 30 citing papers total.

**How to find citing papers**:
1. Use `mcp__find_related_articles` with the focal DOI
2. Use `WebSearch` for "cites:<doi>" or "[title] cited by"
3. Check Semantic Scholar, Google Scholar, or OpenCitations for the paper's citation list

**For each citing paper you examine**:

| Impact type | When to use |
|---|---|
| supports | Cites the claim approvingly; provides corroborating evidence |
| refutes | Directly contradicts or fails to replicate the claim |
| extends | Builds on the claim to reach a new result |
| nuances | Qualifies the claim (e.g., "true in context X but not Y") |
| uses | Uses the method/tool without evaluating the claim |
| unrelated | Cites the paper for something unrelated to its primary claims |

**Prioritize** citing papers that: (a) are themselves highly cited, (b) explicitly discuss the focal paper's methods/conclusions, or (c) are replication studies.

## Scope Management

**Hard limit: 100 sources total** (focal paper + cited papers examined + citing papers examined + supplementary materials).

Budget allocation (approximate):
- Focal paper: 1
- Evidence sources (cited papers): up to 60
- Citation impact (citing papers): up to 30
- Supplementary materials: up to 9

**Priority order for the evidence budget**:
1. Papers cited to directly support a primary claim → always read these
2. Papers cited to directly support a secondary claim → read as many as budget allows
3. Papers cited for peripheral background → sample selectively
4. Second-hop citations → only if necessary to resolve a primary claim's evidence chain

**At 80 sources**: Stop fetching new papers. Begin writing the Further Investigation Map (see Output Format). Use the remaining budget only to finish evidence you've already started tracing.

**At 100 sources**: Mark the analysis complete with status `scope-exhausted`:
```bash
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py complete-analysis \
  --doi "DOI" --status scope-exhausted --source-count 100 \
  --scope-note "Budget exhausted. [N] primary claim sources fully traced. [N] citing papers examined. See Further Investigation Map." 2>/dev/null
```

## Supplementary Materials

Before closing the analysis, check for:
- **Supplementary files**: linked from the paper's landing page (usually HTML, PDF, or ZIP)
- **Data repositories**: GEO (genomics), NCBI SRA (sequencing), Zenodo, OSF, Dryad, figshare
- **Code**: GitHub/GitLab/Bitbucket links in the paper; check for reproducibility issues
- **Clinical trial registry**: ClinicalTrials.gov, ISRCTN — compare registered endpoints with published results
- **Preprint versions**: bioRxiv/medRxiv/arXiv — earlier drafts sometimes show analyses omitted from the final paper
- **Replication studies**: Search "[paper title] replication" or "[paper title] failed to replicate"
- **Data/code availability statements**: note if data is unavailable (a quality signal)
- **Corrections/retractions**: check PubPeer and Retraction Watch

Use `WebFetch` or `WebSearch` for these. Each external resource counts toward the source budget.

## Storage Pattern

**Save progress frequently** — store each claim and its evidence as you go, not all at once at the end.

```bash
# 1. Start the analysis (first thing you do)
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py new-analysis \
  --doi "$DOI" --title "$TITLE" --year $YEAR --paper-type research 2>/dev/null

# 2. Store each claim as you identify it
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py add-claim \
  --analysis-doi "$DOI" \
  --type primary|secondary|peripheral \
  --statement "$PRECISE_FALSIFIABLE_CLAIM" 2>/dev/null

# 3. Store evidence for each claim
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py add-evidence \
  --analysis-doi "$DOI" \
  --claim-statement "$EXACT_CLAIM_TEXT" \
  --evidence-type experimental \
  --source-doi "$SOURCE_DOI" \
  --source-title "$SOURCE_TITLE" \
  --experimental-design "$DESIGN" \
  --data-summary "$DATA" 2>/dev/null

# 4. Store citation impacts as you find them
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py add-citation-impact \
  --analysis-doi "$DOI" \
  --citing-doi "$CITING_DOI" --citing-title "$CITING_TITLE" \
  --impact-type supports|refutes|extends|nuances|uses|unrelated \
  --impact-summary "$SUMMARY" 2>/dev/null

# 5. Mark complete when done (or at budget limit)
uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py complete-analysis \
  --doi "$DOI" --source-count $N --status complete 2>/dev/null
```

## Command Output Pattern

All commands return JSON to stdout. TypeDB driver warnings go to stderr.

**Use `2>/dev/null`** when parsing results:
```bash
result=$(uv run python .claude/skills/single-paper-deep-dive/single_paper_deep_dive.py get-analysis \
  --doi "10.1038/..." 2>/dev/null)
echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['analysis']['claims']), 'claims stored')"
```

**Use `2>&1`** when debugging to see TypeDB errors.

## Output Format

Present the final analysis in this structure:

```
## Deep Dive: [Paper Title]

**DOI:** [doi]  |  **Year:** [year]  |  **Type:** [research/review/...]
**Sources examined:** [n]/100  |  **Status:** [complete/scope-exhausted]

---

### Primary Claims

1. [Precise, falsifiable claim statement]

   **Evidence:**
   - [experimental] **[Source Paper Title]** ([doi])
     - Design: [what system, what manipulation, what measured, what compared, n=, statistics]
     - Data: [actual numbers / results]
   - [observational] **[Source]**
     - Design: [...]
     - Data: [...]

   **Citation impact** (from [n] citing papers): [n] supports, [n] extends, [n] nuances, [n] refutes

   [If any citing papers refute or nuance the claim, list them explicitly here]

2. [Next primary claim...]

---

### Secondary Claims

[Same structure, but evidence may be summarized more briefly]

---

### Peripheral Claims

[List with source citations; only expand evidence for contested or surprising peripheral claims]

---

### Contested Claims

Claims where evidence is weak, contradictory, or where replication has failed:

- **[Claim]**: [Why contested — who failed to replicate, what the counter-evidence is]

---

### Further Investigation Map

Sources identified but not examined (budget exhausted at [n]/100):

**High priority** (would materially affect the analysis):
- [Paper title] ([doi]): [Why important — which claim it bears on]

**Medium priority** (would add nuance):
- [Paper title] ([doi]): [Brief rationale]

**Citing papers not yet examined**: [n] total; [n] most-cited listed below:
- [...]
```

## References

See USAGE.md for full command reference. Read `docs/typedb.md` for TypeQL patterns.
