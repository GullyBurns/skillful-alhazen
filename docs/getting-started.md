# Getting Started

This guide walks you through setting up Skillful-Alhazen and using it for the first time.

## Prerequisites

Before you begin, ensure you have:

1. **[Claude Code](https://claude.ai/code)** installed and configured
2. **[Docker](https://www.docker.com/)** for running TypeDB
3. **[uv](https://docs.astral.sh/uv/)** for Python dependency management

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/gullyburns/skillful-alhazen
cd skillful-alhazen
```

### 2. Install Python Dependencies

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies
uv sync --all-extras
```

### 3. Start TypeDB

```bash
docker compose -f docker-compose-typedb.yml up -d
```

This starts TypeDB on port 1729. The database schema will be initialized automatically when you first use the system.

### 4. Verify Installation

Open Claude Code in the project directory:

```bash
claude
```

Try a simple command:

```
You: What skills are available?
Claude: [Lists available skills: /jobhunt, /epmc-search, /typedb-notebook, /domain-modeling]
```

## Your First Session

### Example 1: Job Hunting

```
You: I'm looking for ML engineering jobs. Here's one I found:
     https://boards.greenhouse.io/company/jobs/12345

Claude: I'll ingest and analyze this posting...

[Claude fetches the job description, extracts requirements,
and creates a fit analysis based on your profile]
```

### Example 2: Literature Research

```
You: Search for papers about CRISPR delivery mechanisms

Claude: [Searches Europe PMC, returns results]

Found 1,247 papers. Here are the top 10 by citation count...

You: Add the top 5 to a collection called "CRISPR Delivery Review"

Claude: [Creates collection, adds papers with metadata]
```

### Example 3: Knowledge Notes

```
You: Remember that the Smith et al. 2024 paper found lipid nanoparticles
     were 3x more effective than viral vectors for liver targeting

Claude: [Stores this finding in the knowledge graph with provenance]

Noted. I've stored this finding linked to the Smith et al. paper.
```

## Dashboard

The project includes a Next.js dashboard for visualizing your knowledge graph:

```bash
cd dashboard
npm install
npm run dev
```

Visit `http://localhost:3000` to see:
- **Pipeline Board**: Kanban view of job applications
- **Skills Matrix**: Gap analysis across positions
- **Learning Plan**: Resources linked to skill gaps

## Environment Variables

You can customize TypeDB connection settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `TYPEDB_HOST` | localhost | TypeDB server hostname |
| `TYPEDB_PORT` | 1729 | TypeDB server port |
| `TYPEDB_DATABASE` | alhazen_notebook | Database name |

## Next Steps

- Read about [Design Concepts](concepts.md) to understand the architecture
- Explore individual [Skills](skills/) for detailed usage
- Learn about the [History](history.md) behind the project name
