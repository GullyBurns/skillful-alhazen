# Domain Modeling Skill

The `/domain-modeling` skill is a meta-skill for designing new domain-specific skills. Use it when you want to track a new type of information systematically.

## Overview

When you find yourself repeatedly tracking a certain kind of information, it's time to create a dedicated skill. This skill guides you through:

1. Defining the entity types for your domain
2. Designing the TypeDB schema
3. Writing the SKILL.md documentation
4. Creating transaction scripts

## When to Create a New Skill

You should create a new skill when:

- You're tracking the same type of information repeatedly
- The information has consistent structure
- You want to query across instances
- You need specialized analysis

Examples:
- Grant applications you're writing
- Conference talks you're preparing
- Research projects you're managing
- Datasets you're curating

## The Curation Pattern

All skills should follow the curation workflow:

```
FORAGING → INGESTION → SENSEMAKING → ANALYSIS → REPORTING
```

When designing a new skill, consider each stage:

| Stage | Questions to Answer |
|-------|---------------------|
| **Foraging** | Where does the information come from? URLs? APIs? Manual entry? |
| **Ingestion** | What's the raw form? How do you capture it? |
| **Sensemaking** | What entities should Claude extract? What relationships? |
| **Analysis** | What questions do you want to answer across instances? |
| **Reporting** | What views or dashboards would be useful? |

## Example: Conference Talks Skill

Let's design a skill for managing conference talks.

### Step 1: Define the Domain

```
You: I want to track conference talks I'm giving. For each talk I need:
     - The conference name, date, location
     - Talk title and abstract
     - Submission deadlines and status
     - Slides and materials
     - Audience feedback

Claude: Let me help you design a schema for this...
```

### Step 2: Identify Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| `conference` | A conference event | name, date, location, url |
| `talk` | A talk submission | title, abstract, status, format |
| `deadline` | Important dates | type (submit, camera-ready, etc.), date |
| `material` | Associated files | type (slides, paper, demo), url |
| `feedback` | Audience responses | score, comments, source |

### Step 3: Define Relationships

| Relationship | Description |
|--------------|-------------|
| `at-conference` | Links talk to conference |
| `has-deadline` | Links conference/talk to deadline |
| `has-material` | Links talk to materials |
| `has-feedback` | Links talk to feedback |

### Step 4: Design Workflow

**Foraging:**
- Conference CFPs from email, Twitter, websites
- Add by URL or manual entry

**Ingestion:**
- Script fetches CFP details
- Stores raw CFP as artifact

**Sensemaking:**
- Claude extracts deadlines, topics, requirements
- You add your talk details

**Analysis:**
- What talks are due this month?
- What's my acceptance rate?
- Which topics get best feedback?

**Reporting:**
- Calendar view of deadlines
- Status pipeline (submitted → accepted → presented)
- Feedback trends

## Skill File Structure

A complete skill has:

```
.claude/skills/conference-talks/
├── SKILL.md              # Instructions for Claude
├── conference_talks.py   # TypeDB transaction scripts
└── README.md            # Developer documentation
```

### SKILL.md Template

```markdown
# Conference Talks Skill

Use this skill to manage conference talks you're preparing and giving.

## Commands

### Add a Conference
\`\`\`
You: Add NeurIPS 2025 to my conference list
Claude: [Creates conference entity, fetches deadlines if URL provided]
\`\`\`

### Submit a Talk
\`\`\`
You: I'm submitting "AI for Science" to NeurIPS 2025
Claude: [Creates talk, links to conference, notes deadline]
\`\`\`

### Update Status
\`\`\`
You: My NeurIPS talk was accepted!
Claude: [Updates status, creates preparation timeline]
\`\`\`

## Status Values
- `idea` - Not yet submitted
- `submitted` - Awaiting decision
- `accepted` - Will present
- `rejected` - Not accepted
- `presented` - Completed
```

### Schema Extension

Add to `local_resources/typedb/namespaces/`:

```typeql
# conference-talks.tql

conference-talk sub thing,
    owns title,
    owns abstract,
    owns status,
    owns format;

conference sub thing,
    owns name,
    owns location,
    owns conference-date,
    owns url;

at-conference sub relation,
    relates talk,
    relates conference;

# ... etc
```

## Best Practices

### Separation of Concerns

- **Scripts handle I/O**: API calls, database transactions, file operations
- **Claude handles thinking**: Extraction, analysis, recommendations

### Consistent Naming

- Entity types: `domain-entity` (e.g., `conference-talk`)
- Relations: `verb-noun` (e.g., `at-conference`)
- Attributes: `noun` or `adjective-noun` (e.g., `status`, `submission-deadline`)

### Provenance

Always link back to sources:
- Artifacts store raw content
- Fragments store extracted portions
- Notes store your annotations

### Progressive Enhancement

Start simple, add complexity as needed:
1. Basic entities and relationships
2. Status tracking
3. Analysis queries
4. Dashboard views

## Getting Help

```
You: I want to create a new skill for tracking [domain]

Claude: [Uses /domain-modeling to guide you through the design process]
```

Claude will help you:
- Identify entities and relationships
- Design the schema
- Write SKILL.md
- Create initial scripts
