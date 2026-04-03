# Domain Spec: [Domain Name]

> Fill out this template, then ingest it as the canonical starting document for your domain:
>
>     uv run python .claude/skills/skill-builder/skill_builder.py \
>       ingest-source-doc --domain-id $DOMAIN \
>       --file domain-spec.md --doc-type template \
>       --title "[Domain Name] spec"

---

## 1. Domain Name & Purpose

**Name:** (e.g. `jobhunt`, `sci-lit-review`, `rare-disease`)

**What problem does this skill solve?**
(Describe the information problem. What does the user need to know/track that they can't easily answer today?)

**What curation goal does this serve?**
(What decision, question, or task is this knowledge graph FOR? Be specific.)

---

## 2. Primary Users & Use Cases

**Who will use this skill?**
(Researcher, clinician, job seeker, analyst, etc.)

**Primary use case:**
(The main workflow the skill supports — one paragraph.)

**Secondary use cases:**
(Other workflows this skill might support.)

---

## 3. Key Entities

What real-world things does the domain track? List them as bullets with a brief description.

- **[EntityName]** — (what it is, e.g. "A published scientific paper")
- **[EntityName]** — (what it is, e.g. "A gene associated with a disease")
- **[EntityName]** — (what it is)

**Key relationships between entities:**
(How do these entities connect? e.g. "A paper is authored-by an Author; a gene is implicated-in a Disease")

---

## 4. Data Sources

Where does data come from? List each source with its type.

| Source | Type | Notes |
|--------|------|-------|
| (e.g. PubMed API) | API | Free text query, returns JSON |
| (e.g. PDF uploads) | File | User-provided documents |
| (e.g. Manual entry) | Manual | Via CLI flags |

**Access constraints:** (authentication needed? rate limits? paywalls?)

---

## 5. Key Workflows

Describe the main curation workflows step by step. For each workflow:

### Workflow 1: [Name]
1. (Step one — e.g. "Search for papers matching a topic")
2. (Step two — e.g. "Ingest full text of each paper")
3. (Step three — e.g. "Claude extracts key claims and entities")
4. (Step four — e.g. "Synthesize findings across papers")

### Workflow 2: [Name]
1. ...

---

## 6. Success Criteria

How would you know the skill is working well? List measurable criteria.

- **Coverage:** (e.g. "90% of relevant papers on topic X are captured")
- **Accuracy:** (e.g. "Entity extraction correct for 85% of test cases")
- **Usability:** (e.g. "Can answer 'what are the top 5 genes for X?' without manual lookup")
- **Completeness:** (e.g. "No important entity types missing from schema")

---

## 7. Constraints & Non-Goals

What is explicitly out of scope for this skill?

- (e.g. "Does not handle full-text PDF parsing — only abstracts")
- (e.g. "Does not integrate with external lab systems")
- (e.g. "Single user only — no multi-user collaboration")

---

## 8. Reference Documents

Papers, specs, emails, or other documents that should be ingested alongside this template.
After filling this out, ingest each one:

    uv run python .claude/skills/skill-builder/skill_builder.py \
      ingest-source-doc --domain-id $DOMAIN \
      --file path/to/doc.pdf --doc-type paper \
      --title "Author Year -- Title"

| Title | Type | Location |
|-------|------|----------|
| (e.g. "Might 2017 -- Undiagnosed Diseases Algorithm") | paper | path/or/url |
| (e.g. "Internal spec email 2024-03-01") | email | paste inline |
