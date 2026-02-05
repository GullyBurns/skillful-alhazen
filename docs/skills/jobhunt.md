# Job Hunt Skill

The `/jobhunt` skill helps you manage your job search as a knowledge graph. Claude acts as your career coach, building understanding of positions, companies, and your fit over time.

## Overview

This skill follows the curation pattern:

1. **Foraging** - You discover job postings (URLs)
2. **Ingestion** - Script fetches raw content, stores as artifact
3. **Sensemaking** - Claude reads artifact, extracts entities, creates notes
4. **Analysis** - Query across notes to answer questions
5. **Reporting** - Dashboard views of pipeline and skills

## Quick Start

### Add a Job Posting

```
You: I found an interesting job at https://boards.greenhouse.io/company/jobs/12345

Claude: I'll ingest and analyze this posting...

[Fetches job description]
[Extracts company info, requirements, qualifications]
[Compares against your skill profile]
[Creates fit analysis]

## Analysis: Senior Software Engineer at ExampleCorp

**Your Fit: 82%**

| Requirement | Level | You | Match |
|-------------|-------|-----|-------|
| Python | Required | Strong | ✓ |
| ML Systems | Required | Strong | ✓ |
| Kubernetes | Required | Some | △ |
| Rust | Preferred | None | ✗ |

**Key Gap:** Kubernetes is required but you only have some experience.

Want me to set a priority level?
```

### Build Your Skill Profile

Before analyzing jobs, set up your skills:

```
You: My skills are:
     - Python: strong (5 years production)
     - Machine Learning: strong (built models at CZI)
     - Kubernetes: some (deployed but not configured)
     - Rust: learning (started last month)

Claude: [Creates skill profile with levels and descriptions]

Added 4 skills to your profile. I'll use these for gap analysis.
```

### Track Application Status

```
You: I applied to the ExampleCorp position yesterday

Claude: [Updates status to "applied" with date]

Updated. The position is now in your "applied" pipeline stage.
```

### Analyze Gaps Across Positions

```
You: What skill gaps do I have across my high-priority positions?

Claude: [Queries positions, aggregates gaps]

Across 3 high-priority positions:

| Skill | Frequency | Your Level | Priority |
|-------|-----------|------------|----------|
| Distributed Systems | 3/3 | None | Critical |
| Kubernetes | 2/3 | Some | High |
| Rust | 1/3 | Learning | Medium |

I recommend focusing on Distributed Systems first.
Want me to find learning resources?
```

## Skill Levels

When adding skills to your profile, use these levels:

| Level | Description |
|-------|-------------|
| `strong` | Confident, production experience |
| `some` | Working knowledge, need to brush up |
| `learning` | Currently studying |
| `none` | No experience yet |

## Application Status Values

| Status | Description |
|--------|-------------|
| `researching` | Evaluating the position |
| `applied` | Application submitted |
| `phone-screen` | Initial phone conversation |
| `interviewing` | In interview process |
| `offer` | Received offer |
| `rejected` | Not moving forward |
| `withdrawn` | You withdrew |

## Note Types

Claude creates different types of notes:

| Type | Purpose |
|------|---------|
| `fit-analysis` | Overall fit assessment with score |
| `research` | Company or industry research |
| `strategy` | Talking points, approach |
| `skill-gap` | Learning needs for specific gaps |
| `interview` | Interview prep or feedback |
| `interaction` | Contact logs and meetings |

## Learning Resources

Link learning resources to skill gaps:

```
You: I found a good Kubernetes course: https://example.com/k8s-course

Claude: [Adds resource, links to K8s requirement]

Added. This is now linked to your Kubernetes gap across 2 positions.
```

## Dashboard

The Next.js dashboard provides visual views:

- **Pipeline Board**: Kanban view of applications by status
- **Skills Matrix**: Your skills vs. requirements across positions
- **Learning Plan**: Resources prioritized by gap frequency
- **Position Detail**: Full analysis, notes, and requirements

## Data Model

### Entities

| Type | Description |
|------|-------------|
| `your-skill` | Skills in your profile |
| `jobhunt-company` | Employer organizations |
| `jobhunt-position` | Specific job postings |
| `jobhunt-learning-resource` | Courses, books, tutorials |
| `jobhunt-contact` | People at companies |

### Artifacts

| Type | Description |
|------|-------------|
| `jobhunt-job-description` | Full JD text (raw) |
| `jobhunt-resume` | Your resume versions |
| `jobhunt-cover-letter` | Tailored cover letters |

### Fragments

| Type | Description |
|------|-------------|
| `jobhunt-requirement` | Single skill requirement |
| `jobhunt-responsibility` | Job responsibility |
| `jobhunt-qualification` | Qualification |
