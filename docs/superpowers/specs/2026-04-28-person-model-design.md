# Unified Person & Organization Model — Design Spec

## Context

The current codebase has two disconnected person models:
- **Core schema**: `person` (sub agent) with minimal attributes (given-name, family-name, email), extended by `operator-user` in agentic-memory with 10 context domains
- **Jobhunt skill**: `jobhunt-contact` (sub agent — wrong parent!) with contact-role, email, linkedin-url, linked to `jobhunt-company` (sub domain-thing) via `works-at`

These don't connect. A recruiter tracked in jobhunt is invisible to agentic-memory's relationship tracking. The `jobhunt-company` duplicates the core `organization` entity. There's no way to track interactions (meetings, calls, interviews) as first-class entities, and no integration with email/calendar.

**Goal**: A single unified person hierarchy in the core schema that all skills specialize, with first-class interaction tracking and email/calendar artifact integration.

## Design Decisions

| Decision | Choice |
|----------|--------|
| Person model depth | Rich profiles for everyone (not just operator) |
| Interaction tracking | First-class interaction entity |
| Person research | Artifacts + notes with full provenance |
| Email/calendar | Design schema + plan MCP integration in this spec |
| Jobhunt alignment | jobhunt-contact → sub person, jobhunt-company → sub organization |
| Data migration | Yes, migrate existing contacts |

## Schema Changes

### 1. Enriched `person` (core schema: `alhazen_notebook.tql`)

**New attributes** (added to core schema):

```typeql
attribute linkedin-url, value string;     # already exists in jobhunt — promote to core
attribute title, value string;             # current role/title
attribute phone-number, value string;
attribute bio, value string;               # short text bio
attribute participant-role, value string;  # role in an interaction
attribute interaction-type, value string;  # meeting, call, email, interview, coffee, conference
attribute interaction-date, value datetime;
attribute outcome, value string;           # free-text interaction outcome
attribute follow-up-by, value datetime;    # when follow-up is needed
attribute follow-up-status, value string;  # pending, completed, overdue
attribute industry, value string;          # organization industry
attribute company-url, value string;       # already in jobhunt — promote to core
attribute location, value string;          # already in jobhunt — promote to core
```

Note: `linkedin-url`, `company-url`, and `location` already exist in the jobhunt schema. They will be promoted to core and removed from the jobhunt schema definition (jobhunt entities inherit them).

**New relation:**

```typeql
relation interaction-participation,
    owns participant-role,
    relates interaction,
    relates participant;
```

**New entity:**

```typeql
entity interaction sub domain-thing,
    owns interaction-type,
    owns interaction-date,
    owns outcome,
    owns follow-up-by,
    owns follow-up-status,
    plays interaction-participation:interaction;
```

**Modified entities:**

```typeql
# person gains new attributes and plays interaction + relationship roles
entity person sub agent,
    owns given-name,
    owns family-name,
    owns email-address,
    owns linkedin-url,
    owns title,
    owns phone-number,
    owns bio,
    plays interaction-participation:participant,
    plays relationship-context:from-person,
    plays relationship-context:to-person;

# organization gains new attributes and plays works-at employer role
entity organization sub domain-thing,
    owns linkedin-url,
    owns company-url,
    owns location,
    owns industry,
    plays affiliation:organization,
    plays works-at:employer;
```

**Moved to core from jobhunt:**

```typeql
# works-at relation (was in jobhunt schema, now core)
relation works-at,
    owns valid-from,
    owns valid-until,
    relates employee,
    relates employer;

# person plays employee role
entity person plays works-at:employee;
```

**Moved from operator-user only to all persons:**

The `relationship-context` relation's `from-person` and `to-person` roles move from `operator-user` plays declarations to `person` plays declarations. This means any person can have tracked relationships, not just the operator.

`operator-user` no longer needs to declare `plays relationship-context:from-person/to-person` since it inherits from person.

### 2. Agentic-Memory Schema Changes (`skills/agentic-memory/schema.tql`)

**Remove** from `operator-user` definition:
- `plays relationship-context:from-person` (now inherited from person)
- `plays relationship-context:to-person` (now inherited from person)

Everything else stays — the 10 context domains (identity-summary, role-description, etc.) remain operator-user-specific.

### 3. Jobhunt Schema Changes (`local_skills/jobhunt/schema.tql`)

**`jobhunt-contact`**: Change from `sub agent` to `sub person`:

```typeql
entity jobhunt-contact sub person,
    owns contact-role;
    # Inherits: given-name, family-name, email-address, linkedin-url, title, bio, phone-number
    # Inherits: plays works-at:employee, plays interaction-participation:participant
    # Inherits: plays relationship-context:from-person/to-person
    # No longer needs: owns contact-email (use inherited email-address)
    # No longer needs: owns linkedin-url (inherited from person)
```

**`jobhunt-company`**: Change from `sub domain-thing` to `sub organization`:

```typeql
entity jobhunt-company sub organization,
    owns board-token,
    owns board-platform,
    owns search-query,
    owns search-location,
    plays position-at-company:employer,
    plays opportunity-at-organization:organization;
    # Inherits: linkedin-url, company-url, location, industry from organization
    # No longer needs: owns company-url (inherited)
    # No longer needs: owns linkedin-url (inherited)
    # No longer needs: owns location (inherited)
    # No longer needs: plays works-at:employer (inherited from organization)
```

**Remove** from jobhunt schema:
- `relation works-at` definition (moved to core)
- `attribute contact-email` (replaced by inherited `email-address`)
- `attribute linkedin-url` definition (promoted to core)
- `attribute company-url` definition (promoted to core)
- `attribute location` definition (promoted to core)

### 4. Complete Entity Hierarchy (after changes)

```
identifiable-entity (abstract)
├── domain-thing
│   ├── agent (operational actor base)
│   │   ├── ai-agent (Claude, GPT-4, etc.)
│   │   └── person (enriched: name, email, linkedin, title, bio, phone)
│   │       ├── operator-user (10 context domains)
│   │       ├── author (publication authorship)
│   │       ├── application-user (other system users)
│   │       └── jobhunt-contact (contact-role: recruiter/hiring-manager/etc.)
│   ├── organization (enriched: linkedin, website, location, industry)
│   │   └── jobhunt-company (board-token, search config)
│   └── interaction (type, date, outcome, follow-up)
├── collection
└── information-content-entity (abstract)
    ├── artifact (email threads, calendar events, LinkedIn pages)
    ├── fragment
    ├── note (debrief notes, research findings, profile notes)
    └── episode
```

### 5. Provenance Chains

**Person research:**
```
person ←(aboutness)→ note (research findings, profile summary)
person ←(aboutness)→ artifact (LinkedIn page, company bio)
note ←(fact-evidence)→ artifact (provenance: note derived from artifact)
```

**Interaction tracking:**
```
interaction ←(representation)→ artifact (email thread, calendar event)
interaction ←(interaction-participation)→ person (with participant-role)
interaction ←(aboutness)→ note (debrief, takeaways, action items)
interaction ←(aboutness)→ jobhunt-position (if interview-related)
```

**Relationship context:**
```
person ←(relationship-context)→ person (with description: "recruiter at Anthropic")
person ←(works-at)→ organization (with valid-from/valid-until)
```

## Email/Calendar Integration

### Gmail MCP Integration

The agent uses existing Gmail MCP tools to create interaction + artifact entities:

1. **Search**: `mcp__claude_ai_Gmail__search_threads` — find threads mentioning a person/company
2. **Read**: `mcp__claude_ai_Gmail__get_thread` — get full thread content
3. **Store**: Create `artifact` entity with:
   - `source-uri`: Gmail thread URL
   - `format`: "email"
   - `content`: thread summary (< 50KB inline, else cache-path)
4. **Track**: Create `interaction` entity with:
   - `interaction-type`: "email"
   - `interaction-date`: thread date
   - Link to artifact via `representation`
5. **Link participants**: Match `email-address` to existing persons, create new persons if needed
6. **Analyze**: Create notes with key takeaways linked to the interaction

### Google Calendar MCP Integration

1. **List**: `mcp__claude_ai_Google_Calendar__list_events` — upcoming/past meetings
2. **Read**: `mcp__claude_ai_Google_Calendar__get_event` — event details + attendees
3. **Store**: Create `artifact` entity with:
   - `source-uri`: Calendar event URL
   - `format`: "calendar-event"
   - `content`: event description + attendee list
4. **Track**: Create `interaction` entity with:
   - `interaction-type`: "meeting" or "interview"
   - `interaction-date`: event start time
   - Link to artifact via `representation`
5. **Link participants**: Match attendee emails to persons
6. **Prep/Debrief**: Before meeting — create prep notes. After — create debrief notes.

### Person Matching Logic

When encountering an email/calendar participant:
1. Query TypeDB for `person` with matching `email-address`
2. If found → use existing entity
3. If not found → create new `person` with `given-name`, `family-name`, `email-address` from message/event metadata
4. Agent can later enrich the person via web research (LinkedIn, company page)

## Data Migration

Existing `jobhunt-contact` entities (sub agent) need to be migrated to `sub person`. Steps:

1. Export all jobhunt-contact data (id, name, contact-role, contact-email, linkedin-url)
2. Export all works-at relations
3. Update schema (core + jobhunt)
4. Re-insert contacts as `person` entities with enriched attributes
5. Re-insert contacts as `jobhunt-contact` (now sub person) with contact-role
6. Re-create works-at relations

Similarly for `jobhunt-company` → `sub organization`.

## Files to Modify

| File | Change |
|------|--------|
| `local_resources/typedb/alhazen_notebook.tql` | Add attributes (linkedin-url, title, phone-number, bio, interaction-type, interaction-date, outcome, follow-up-by, follow-up-status, industry, company-url, location, participant-role). Add interaction entity, interaction-participation relation, works-at relation. Enrich person and organization. |
| `skills/agentic-memory/schema.tql` | Remove relationship-context plays from operator-user (now inherited from person) |
| `local_skills/jobhunt/schema.tql` (upstream: sciknow-io/alhazen-skill-examples) | Change jobhunt-contact to sub person, jobhunt-company to sub organization. Remove duplicate attribute definitions and works-at relation. |
| `skills/agentic-memory/agentic_memory.py` | Update link-person to use enriched person attributes. Add interaction commands. |
| `local_skills/jobhunt/jobhunt.py` | Update contact creation to use new person hierarchy. Map contact-email → email-address. |

## Verification

1. `make db-init` succeeds with updated schemas (no TypeQL errors)
2. Create a person with full attributes: name, email, linkedin, title, bio
3. Create a jobhunt-contact (now sub person) — verify it inherits person attributes
4. Create an interaction with participants — verify the full chain works
5. Create an artifact (email source) linked to the interaction
6. Query "all interactions with person X" — returns correct results
7. Query "all people at organization Y" via works-at — returns correct results
8. Existing jobhunt pipeline data still works after migration
