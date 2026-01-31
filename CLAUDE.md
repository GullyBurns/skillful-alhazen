# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Skillful-Alhazen is an AI agent framework for scientific knowledge analysis, built on LangChain. It helps researchers build digital libraries from papers, webpages, and database records while providing AI-powered analysis and synthesis tools. Named after Ibn al-Haytham (965-1039 AD), an early pioneer of the scientific method.

Forked from the CZI [alhazen](https://github.com/chanzuckerberg/alhazen) project.

## Development Commands

**Installation:**
```bash
conda create -n alhazen python=3.11
conda activate alhazen
pip install -e .
```

**Docker (preferred):**
```bash
docker compose build
docker compose up
```

**With Huridocs PDF extraction:**
```bash
docker compose -f docker-compose-huridocs.yml up
```

**Running tests:**
```bash
pytest
pytest tests/test_specific.py -v  # single test file
```

**Running Marimo dashboards:**
```bash
marimo run marimo/002_corpora_map.py
marimo run marimo/001_chat.py
```

**Running the chat application:**
```bash
python -m alhazen.apps.chat --loc <path> --db_name <database_name>
```

## Architecture

### Core Components

- **Agent System** (`src/skillful_alhazen/agent.py`): `AlhazenAgent` class using LangChain's agent executor with custom JSON parsing fixes
- **Database Layer** (`src/skillful_alhazen/utils/ceifns_db.py`, `src/skillful_alhazen/schema_sqla.py`): CEIFNS model (Collection-Expression-Item-Fragment-Note-Summary) using PostgreSQL with pgvector
- **Toolkit System** (`src/skillful_alhazen/toolkit.py`): Manages tools including `AlhazenToolkit` and `MetadataExtractionToolkit`
- **Core Module** (`src/skillful_alhazen/core.py`): Prompt templates, LLM factory functions, `OllamaRunner` for local models

### Tools (`src/skillful_alhazen/tools/`)

- `basic.py` - Core tool implementations
- `metadata_extraction_tool.py` - Structured data extraction from papers
- `paperqa_emulation_tool.py` - Paper Q&A functionality
- `protocol_extraction_tool.py` - Experimental protocol extraction
- `tiab_*.py` - Title/Abstract analysis tools (extraction, classification, mapping)

### Utilities (`src/skillful_alhazen/utils/`)

- `ceifns_db.py` - Database ORM for the CEIFNS document model
- `searchEngineUtils.py` - Search and query tools
- `jats_text_extractor.py` - XML/JATS article parsing
- `pdf_research_article_text_extractor.py` - PDF processing
- `web_robot.py` - Web scraping with Selenium/Splinter

## Key Dependencies

- **LLM Integration**: langchain, langchain-openai, langchain-groq, langchain-google-vertexai
- **Database**: sqlalchemy, psycopg2-binary, pgvector
- **Document Processing**: pymupdf, trafilatura, beautifulsoup4, lxml
- **Ontologies**: owlready2, linkml
- **Web Automation**: selenium, splinter

## Environment Variables

**Required:**
- `LOCAL_FILE_PATH` - Directory for storing full-text files

**Optional (for LLM providers):**
- `OPENAI_API_KEY`
- `GROQ_API_KEY`
- `DATABRICKS_API_KEY`
- `VERTEXAI_PROJECT_NAME`
- `NCBI_API_KEY`

## Infrastructure Requirements

- PostgreSQL 14 with pgvector extension
- Optional: Huridocs Docker container for advanced PDF extraction
- For local LLMs via Ollama: Apple Mac with 48GB+ memory recommended

## Directory Structure

```
src/skillful_alhazen/   # Main package (import as skillful_alhazen)
├── agent.py            # Agent orchestration
├── core.py             # Prompt templates, LLM configs
├── toolkit.py          # Tool collection management
├── schema_sqla.py      # SQLAlchemy ORM models
├── schema_python.py    # Pydantic data models
├── tools/              # Tool implementations
└── utils/              # Utility modules

scripts/                # Standalone scripts
tests/                  # Test files
marimo/                 # Interactive dashboards
local_resources/
├── prompts/            # YAML prompt templates
└── linkml/             # LinkML schemas
archive/                # Archived nbdev notebooks (historical reference)
```
