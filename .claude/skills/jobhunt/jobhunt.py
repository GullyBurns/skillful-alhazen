#!/usr/bin/env python3
"""
Job Hunting Notebook CLI - Track job applications and analyze career opportunities.

This script handles INGESTION and QUERIES. Claude handles SENSEMAKING via the SKILL.md.

Usage:
    python .claude/skills/jobhunt/jobhunt.py <command> [options]

Commands:
    # Ingestion (script fetches, stores raw content)
    ingest-job          Fetch job posting URL and store raw content as artifact
    add-company         Add a company to track
    add-position        Add a position manually

    # Your Skill Profile
    add-skill           Add/update a skill in your profile
    list-skills         Show your skill profile

    # Artifacts (for Claude's sensemaking)
    list-artifacts      List artifacts pending analysis
    show-artifact       Get artifact content for Claude to read

    # Application Tracking
    update-status       Update application status
    add-note            Create a note about any entity
    add-resource        Add a learning resource
    add-requirement     Add a requirement to a position
    link-resource       Link resource to a skill requirement
    link-collection     Link paper collection to skill requirement(s)
    link-paper          Link learning resource to a paper

    # Queries
    list-pipeline       Show your application pipeline
    show-position       Get position details with all notes
    show-company        Get company details
    show-gaps           Identify skill gaps across applications
    learning-plan       Show prioritized learning resources
    tag                 Tag an entity
    search-tag          Search by tag

    # Cache
    cache-stats         Show cache statistics

Examples:
    # Ingest a job posting (stores raw content for Claude to analyze)
    python .claude/skills/jobhunt/jobhunt.py ingest-job --url "https://example.com/jobs/123"

    # Add your skills for gap analysis
    python .claude/skills/jobhunt/jobhunt.py add-skill --name "Python" --level "strong"
    python .claude/skills/jobhunt/jobhunt.py add-skill --name "Distributed Systems" --level "some"

    # List artifacts needing analysis
    python .claude/skills/jobhunt/jobhunt.py list-artifacts --status raw

    # Show artifact content (for Claude to read and extract)
    python .claude/skills/jobhunt/jobhunt.py show-artifact --id "artifact-abc123"

    # Show pipeline
    python .claude/skills/jobhunt/jobhunt.py list-pipeline --status interviewing

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    ALHAZEN_CACHE_DIR File cache directory (default: ~/.alhazen/cache)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print(
        "Warning: requests/beautifulsoup4 not installed. Install with: pip install requests beautifulsoup4",
        file=sys.stderr,
    )

try:
    from typedb.driver import SessionType, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=2.25.0,<3.0.0'",
        file=sys.stderr,
    )

# Cache utilities
try:
    from skillful_alhazen.utils.cache import (
        get_cache_dir,
        save_to_cache,
        load_from_cache_text,
        should_cache,
        get_cache_stats,
        format_size,
    )

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    # Fallback: define minimal versions if cache module not available
    def should_cache(content):
        return False

    def get_cache_stats():
        return {"error": "Cache module not available"}

    def format_size(size):
        return f"{size} bytes"


# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def get_attr(entity: dict, attr_name: str, default=None):
    """Safely extract attribute value from TypeDB fetch result.

    TypeDB fetch returns attributes as arrays, e.g.:
    {'id': [{'value': 'abc', 'type': {...}}], 'name': [...]}

    This helper extracts the first value or returns default.
    """
    attr_list = entity.get(attr_name, [])
    if attr_list and len(attr_list) > 0:
        return attr_list[0].get("value", default)
    return default


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def parse_date(date_str: str) -> str:
    """Parse various date formats to TypeDB datetime."""
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    # If no format works, assume it's already in correct format
    return date_str


def fetch_url_content(url: str) -> tuple[str, str]:
    """
    Fetch URL and return (title, text_content).

    Returns basic parsed content - Claude will do the intelligent extraction.
    """
    if not REQUESTS_AVAILABLE:
        return "", ""

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        title = soup.title.string if soup.title else ""

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        # Limit content size
        if len(text) > 50000:
            text = text[:50000] + "\n... [truncated]"

        return title, text

    except Exception as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return "", ""


def extract_company_from_url(url: str) -> str:
    """Try to extract company name from URL domain."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Remove common prefixes
    for prefix in ["www.", "jobs.", "careers.", "boards.greenhouse.io", "jobs.lever.co"]:
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]

    # Extract main domain part
    parts = domain.split(".")
    if len(parts) >= 2:
        return parts[0].title()
    return domain.title()


# =============================================================================
# COMMAND IMPLEMENTATIONS
# =============================================================================


def cmd_ingest_job(args):
    """
    Fetch job posting URL and store raw content as artifact.

    This implements the INGESTION phase of the curation pattern:
    - Fetches URL content (raw, unedited)
    - Stores as artifact with provenance
    - Creates placeholder position entity
    - Claude does the SENSEMAKING (extraction, analysis) separately

    NO parsing, NO extraction - just raw capture with provenance.
    """
    if not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests/beautifulsoup4 not installed"}))
        return

    url = args.url
    title, content = fetch_url_content(url)

    if not content:
        print(json.dumps({"success": False, "error": "Could not fetch URL content"}))
        return

    # Generate IDs
    position_id = generate_id("position")
    artifact_id = generate_id("artifact")
    timestamp = get_timestamp()

    # Use a placeholder name - Claude will extract the real title during sensemaking
    placeholder_name = title if title else f"Job posting from {url[:50]}"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Create position placeholder (Claude will update with extracted info)
            with session.transaction(TransactionType.WRITE) as tx:
                position_query = f'''insert $p isa jobhunt-position,
                    has id "{position_id}",
                    has name "{escape_string(placeholder_name)}",
                    has job-url "{escape_string(url)}",
                    has created-at {timestamp}'''

                if args.priority:
                    position_query += f', has priority-level "{args.priority}"'

                position_query += ";"
                tx.query.insert(position_query)
                tx.commit()

            # Create job description artifact with content (inline or cached)
            with session.transaction(TransactionType.WRITE) as tx:
                # Check if content should be cached externally
                if CACHE_AVAILABLE and should_cache(content):
                    # Store in cache
                    cache_result = save_to_cache(
                        artifact_id=artifact_id,
                        content=content,
                        mime_type="text/html",
                    )
                    artifact_query = f'''insert $a isa jobhunt-job-description,
                        has id "{artifact_id}",
                        has name "Job Description: {escape_string(placeholder_name)}",
                        has cache-path "{cache_result['cache_path']}",
                        has mime-type "text/html",
                        has file-size {cache_result['file_size']},
                        has content-hash "{cache_result['content_hash']}",
                        has source-uri "{escape_string(url)}",
                        has created-at {timestamp};'''
                else:
                    # Store inline
                    artifact_query = f'''insert $a isa jobhunt-job-description,
                        has id "{artifact_id}",
                        has name "Job Description: {escape_string(placeholder_name)}",
                        has content "{escape_string(content)}",
                        has source-uri "{escape_string(url)}",
                        has created-at {timestamp};'''
                tx.query.insert(artifact_query)
                tx.commit()

            # Link artifact to position
            with session.transaction(TransactionType.WRITE) as tx:
                rep_query = f'''match
                    $a isa jobhunt-job-description, has id "{artifact_id}";
                    $p isa jobhunt-position, has id "{position_id}";
                insert (artifact: $a, referent: $p) isa representation;'''
                tx.query.insert(rep_query)
                tx.commit()

            # Create initial application note with researching status
            app_note_id = generate_id("note")
            with session.transaction(TransactionType.WRITE) as tx:
                note_query = f'''insert $n isa jobhunt-application-note,
                    has id "{app_note_id}",
                    has name "Application Status",
                    has application-status "researching",
                    has created-at {timestamp};'''
                tx.query.insert(note_query)
                tx.commit()

            # Link note to position
            with session.transaction(TransactionType.WRITE) as tx:
                about_query = f'''match
                    $n isa note, has id "{app_note_id}";
                    $p isa jobhunt-position, has id "{position_id}";
                insert (note: $n, subject: $p) isa aboutness;'''
                tx.query.insert(about_query)
                tx.commit()

            # Add tags if specified
            if args.tags:
                for tag_name in args.tags:
                    tag_id = generate_id("tag")
                    with session.transaction(TransactionType.READ) as tx:
                        tag_check = f'match $t isa tag, has name "{tag_name}"; fetch $t: id;'
                        existing_tag = list(tx.query.fetch(tag_check))

                    if not existing_tag:
                        with session.transaction(TransactionType.WRITE) as tx:
                            tx.query.insert(
                                f'insert $t isa tag, has id "{tag_id}", has name "{tag_name}";'
                            )
                            tx.commit()

                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.insert(f'''match
                            $p isa jobhunt-position, has id "{position_id}";
                            $t isa tag, has name "{tag_name}";
                        insert (tagged-entity: $p, tag: $t) isa tagging;''')
                        tx.commit()

    # Prepare output
    output = {
        "success": True,
        "position_id": position_id,
        "artifact_id": artifact_id,
        "url": url,
        "content_length": len(content),
        "status": "raw",
        "message": "Job posting ingested. Artifact stored - ask Claude to 'analyze this job posting' for sensemaking.",
    }

    # Add cache info if applicable
    if CACHE_AVAILABLE and should_cache(content):
        output["storage"] = "cache"
        output["cache_path"] = cache_result["cache_path"]
    else:
        output["storage"] = "inline"

    print(json.dumps(output, indent=2))


def cmd_add_company(args):
    """Add a company to track."""
    company_id = args.id or generate_id("company")
    timestamp = get_timestamp()

    query = f'''insert $c isa jobhunt-company,
        has id "{company_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.url:
        query += f', has company-url "{escape_string(args.url)}"'
    if args.linkedin:
        query += f', has linkedin-url "{escape_string(args.linkedin)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    if args.location:
        query += f', has location "{escape_string(args.location)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "company_id": company_id, "name": args.name}))


def cmd_add_position(args):
    """Add a position manually."""
    position_id = args.id or generate_id("position")
    timestamp = get_timestamp()

    query = f'''insert $p isa jobhunt-position,
        has id "{position_id}",
        has name "{escape_string(args.title)}",
        has created-at {timestamp}'''

    if args.url:
        query += f', has job-url "{escape_string(args.url)}"'
    if args.location:
        query += f', has location "{escape_string(args.location)}"'
    if args.remote_policy:
        query += f', has remote-policy "{args.remote_policy}"'
    if args.salary:
        query += f', has salary-range "{escape_string(args.salary)}"'
    if args.team_size:
        query += f', has team-size "{escape_string(args.team_size)}"'
    if args.priority:
        query += f', has priority-level "{args.priority}"'
    if args.deadline:
        query += f", has deadline {parse_date(args.deadline)}"

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to company
            if args.company:
                with session.transaction(TransactionType.WRITE) as tx:
                    rel_query = f'''match
                        $p isa jobhunt-position, has id "{position_id}";
                        $c isa jobhunt-company, has id "{args.company}";
                    insert (position: $p, employer: $c) isa position-at-company;'''
                    tx.query.insert(rel_query)
                    tx.commit()

            # Create initial application note
            app_note_id = generate_id("note")
            with session.transaction(TransactionType.WRITE) as tx:
                note_query = f'''insert $n isa jobhunt-application-note,
                    has id "{app_note_id}",
                    has name "Application Status",
                    has application-status "researching",
                    has created-at {timestamp};'''
                tx.query.insert(note_query)
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                about_query = f'''match
                    $n isa note, has id "{app_note_id}";
                    $p isa jobhunt-position, has id "{position_id}";
                insert (note: $n, subject: $p) isa aboutness;'''
                tx.query.insert(about_query)
                tx.commit()

    print(json.dumps({"success": True, "position_id": position_id, "title": args.title}))


def cmd_update_status(args):
    """Update application status for a position."""
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Find or create application note
            with session.transaction(TransactionType.READ) as tx:
                find_query = f'''match
                    $p isa jobhunt-position, has id "{args.position}";
                    (note: $n, subject: $p) isa aboutness;
                    $n isa jobhunt-application-note;
                fetch $n: id, application-status;'''
                existing = list(tx.query.fetch(find_query))

            if existing:
                # Update existing note - delete old and create new with updated status
                old_note_id = existing[0]["n"]["id"][0]["value"]

                # Delete old note
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.delete(
                        f'match $n isa note, has id "{old_note_id}"; delete $n isa note;'
                    )
                    tx.commit()

            # Create new application note with updated status
            note_id = generate_id("note")
            note_query = f'''insert $n isa jobhunt-application-note,
                has id "{note_id}",
                has name "Application Status",
                has application-status "{args.status}",
                has created-at {timestamp}'''

            if args.date:
                note_query += f", has applied-date {parse_date(args.date)}"

            note_query += ";"

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(note_query)
                tx.commit()

            # Link to position
            with session.transaction(TransactionType.WRITE) as tx:
                about_query = f'''match
                    $n isa note, has id "{note_id}";
                    $p isa jobhunt-position, has id "{args.position}";
                insert (note: $n, subject: $p) isa aboutness;'''
                tx.query.insert(about_query)
                tx.commit()

    print(
        json.dumps(
            {
                "success": True,
                "position_id": args.position,
                "status": args.status,
                "note_id": note_id,
            }
        )
    )


def cmd_set_short_name(args):
    """Set short display name for a position."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Check if position exists and if it already has a short-name
            with session.transaction(TransactionType.READ) as tx:
                check_query = f'''match
                    $p isa jobhunt-position, has id "{args.position}";
                fetch $p: short-name;'''
                existing = list(tx.query.fetch(check_query))

                if not existing:
                    print(json.dumps({"success": False, "error": "Position not found"}))
                    return

                has_existing = bool(get_attr(existing[0]["p"], "short-name"))

            if has_existing:
                # Delete old short-name and add new one
                with session.transaction(TransactionType.WRITE) as tx:
                    delete_query = f'''match
                        $p isa jobhunt-position, has id "{args.position}", has short-name $sn;
                    delete $p has $sn;'''
                    tx.query.delete(delete_query)
                    tx.commit()

            # Add new short-name
            with session.transaction(TransactionType.WRITE) as tx:
                insert_query = f'''match
                    $p isa jobhunt-position, has id "{args.position}";
                insert $p has short-name "{escape_string(args.name)}";'''
                tx.query.insert(insert_query)
                tx.commit()

    print(
        json.dumps(
            {
                "success": True,
                "position_id": args.position,
                "short_name": args.name,
            }
        )
    )


def cmd_add_note(args):
    """Create a note about any entity."""
    note_id = args.id or generate_id("note")
    timestamp = get_timestamp()

    # Map note type to TypeDB type
    type_map = {
        "research": "jobhunt-research-note",
        "interview": "jobhunt-interview-note",
        "strategy": "jobhunt-strategy-note",
        "skill-gap": "jobhunt-skill-gap-note",
        "fit-analysis": "jobhunt-fit-analysis-note",
        "interaction": "jobhunt-interaction-note",
        "application": "jobhunt-application-note",
        "general": "note",
    }

    note_type = type_map.get(args.type, "note")

    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(args.content)}",
        has created-at {timestamp}'''

    if args.name:
        query += f', has name "{escape_string(args.name)}"'
    if args.confidence:
        query += f", has confidence {args.confidence}"

    # Type-specific attributes
    if args.type == "interaction":
        if args.interaction_type:
            query += f', has interaction-type "{args.interaction_type}"'
        if args.interaction_date:
            query += f", has interaction-date {parse_date(args.interaction_date)}"

    if args.type == "interview" and args.interview_date:
        query += f", has interview-date {parse_date(args.interview_date)}"

    if args.type == "fit-analysis":
        if args.fit_score:
            query += f", has fit-score {args.fit_score}"
        if args.fit_summary:
            query += f', has fit-summary "{escape_string(args.fit_summary)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to subject
            with session.transaction(TransactionType.WRITE) as tx:
                about_query = f'''match
                    $n isa note, has id "{note_id}";
                    $s isa entity, has id "{args.about}";
                insert (note: $n, subject: $s) isa aboutness;'''
                tx.query.insert(about_query)
                tx.commit()

            # Add tags
            if args.tags:
                for tag_name in args.tags:
                    tag_id = generate_id("tag")
                    with session.transaction(TransactionType.READ) as tx:
                        tag_check = f'match $t isa tag, has name "{tag_name}"; fetch $t: id;'
                        existing_tag = list(tx.query.fetch(tag_check))

                    if not existing_tag:
                        with session.transaction(TransactionType.WRITE) as tx:
                            tx.query.insert(
                                f'insert $t isa tag, has id "{tag_id}", has name "{tag_name}";'
                            )
                            tx.commit()

                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.insert(f'''match
                            $n isa note, has id "{note_id}";
                            $t isa tag, has name "{tag_name}";
                        insert (tagged-entity: $n, tag: $t) isa tagging;''')
                        tx.commit()

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about, "type": args.type}))


def cmd_add_resource(args):
    """Add a learning resource."""
    resource_id = args.id or generate_id("resource")
    timestamp = get_timestamp()

    query = f'''insert $r isa jobhunt-learning-resource,
        has id "{resource_id}",
        has name "{escape_string(args.name)}",
        has resource-type "{args.type}",
        has completion-status "not-started",
        has created-at {timestamp}'''

    if args.url:
        query += f', has resource-url "{escape_string(args.url)}"'
    if args.hours:
        query += f", has estimated-hours {args.hours}"
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Tag with skills
            if args.skills:
                for skill in args.skills:
                    tag_id = generate_id("tag")
                    tag_name = f"skill:{skill}"

                    with session.transaction(TransactionType.READ) as tx:
                        tag_check = f'match $t isa tag, has name "{tag_name}"; fetch $t: id;'
                        existing_tag = list(tx.query.fetch(tag_check))

                    if not existing_tag:
                        with session.transaction(TransactionType.WRITE) as tx:
                            tx.query.insert(
                                f'insert $t isa tag, has id "{tag_id}", has name "{tag_name}";'
                            )
                            tx.commit()

                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.insert(f'''match
                            $r isa jobhunt-learning-resource, has id "{resource_id}";
                            $t isa tag, has name "{tag_name}";
                        insert (tagged-entity: $r, tag: $t) isa tagging;''')
                        tx.commit()

    print(
        json.dumps(
            {"success": True, "resource_id": resource_id, "name": args.name, "type": args.type}
        )
    )


def cmd_link_resource(args):
    """Link a learning resource to a skill requirement."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                link_query = f'''match
                    $r isa jobhunt-learning-resource, has id "{args.resource}";
                    $req isa jobhunt-requirement, has id "{args.requirement}";
                insert (resource: $r, requirement: $req) isa addresses-requirement;'''
                tx.query.insert(link_query)
                tx.commit()

    print(json.dumps({"success": True, "resource": args.resource, "requirement": args.requirement}))


def cmd_link_collection(args):
    """Link a paper collection to skill requirement(s).

    Bridges scilit collections to jobhunt skill gaps via addresses-requirement.
    Use --requirement for a specific requirement, or --skill to link to all
    matching requirements across positions.
    """
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            if args.requirement:
                # Link to specific requirement
                with session.transaction(TransactionType.WRITE) as tx:
                    link_query = f'''match
                        $c isa collection, has id "{args.collection}";
                        $req isa jobhunt-requirement, has id "{args.requirement}";
                    insert (resource: $c, requirement: $req) isa addresses-requirement;'''
                    tx.query.insert(link_query)
                    tx.commit()
                print(json.dumps({
                    "success": True,
                    "collection": args.collection,
                    "requirement": args.requirement,
                }))

            elif args.skill:
                # Link to all requirements matching skill name
                with session.transaction(TransactionType.READ) as tx:
                    find_query = f'''match
                        $req isa jobhunt-requirement, has skill-name "{escape_string(args.skill)}";
                    fetch $req: id;'''
                    reqs = list(tx.query.fetch(find_query))

                if not reqs:
                    print(json.dumps({
                        "success": False,
                        "error": f"No requirements found with skill-name '{args.skill}'",
                    }))
                    return

                linked = []
                for r in reqs:
                    req_id = get_attr(r["req"], "id")
                    with session.transaction(TransactionType.WRITE) as tx:
                        link_query = f'''match
                            $c isa collection, has id "{args.collection}";
                            $req isa jobhunt-requirement, has id "{req_id}";
                        insert (resource: $c, requirement: $req) isa addresses-requirement;'''
                        tx.query.insert(link_query)
                        tx.commit()
                    linked.append(req_id)

                print(json.dumps({
                    "success": True,
                    "collection": args.collection,
                    "skill": args.skill,
                    "linked_requirements": linked,
                    "count": len(linked),
                }))
            else:
                print(json.dumps({
                    "success": False,
                    "error": "Must specify either --requirement or --skill",
                }))


def cmd_link_paper(args):
    """Link a learning resource to a paper via citation-reference.

    Creates a citation-reference relation where the learning resource
    cites the paper. Both types inherit from domain-thing so they
    can already play citing-item/cited-item roles.
    """
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            timestamp = get_timestamp()
            with session.transaction(TransactionType.WRITE) as tx:
                link_query = f'''match
                    $res isa jobhunt-learning-resource, has id "{args.resource}";
                    $paper isa scilit-paper, has id "{args.paper}";
                insert (citing-item: $res, cited-item: $paper) isa citation-reference,
                    has created-at {timestamp};'''
                tx.query.insert(link_query)
                tx.commit()

    print(json.dumps({
        "success": True,
        "resource": args.resource,
        "paper": args.paper,
    }))


def cmd_list_pipeline(args):
    """List positions in the pipeline."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Build query - fetch positions with their application status
                query = """match
                    $p isa jobhunt-position;
                    (note: $n, subject: $p) isa aboutness;
                    $n isa jobhunt-application-note, has application-status $status;"""

                if args.status:
                    query = query.replace(
                        "has application-status $status", f'has application-status "{args.status}"'
                    )

                if args.priority:
                    query += f'\n                    $p has priority-level "{args.priority}";'

                query += """
                fetch $p: id, name, short-name, job-url, location, remote-policy, salary-range, priority-level;
                    $n: application-status;"""

                results = list(tx.query.fetch(query))

                # Separately fetch company info for each position
                # Note: TypeDB fetch returns arrays for attributes
                for r in results:
                    id_list = r["p"].get("id", [])
                    pos_id = id_list[0]["value"] if id_list else None
                    if pos_id:
                        company_query = f'''match
                            $p isa jobhunt-position, has id "{pos_id}";
                            (position: $p, employer: $c) isa position-at-company;
                        fetch $c: name;'''
                        try:
                            company_results = list(tx.query.fetch(company_query))
                            if company_results:
                                name_list = company_results[0]["c"].get("name", [])
                                r["company_name"] = name_list[0]["value"] if name_list else ""
                        except Exception:
                            r["company_name"] = ""

                # If filtering by tag, we need a separate query
                if args.tag:
                    tag_query = f'''match
                        $p isa jobhunt-position;
                        $t isa tag, has name "{args.tag}";
                        (tagged-entity: $p, tag: $t) isa tagging;
                    fetch $p: id;'''
                    tagged = list(tx.query.fetch(tag_query))
                    tagged_ids = {get_attr(r["p"], "id") for r in tagged}
                    results = [r for r in results if get_attr(r["p"], "id") in tagged_ids]

    # Format output
    positions = []
    for r in results:
        pos = {
            "id": get_attr(r["p"], "id"),
            "title": get_attr(r["p"], "name"),
            "short_name": get_attr(r["p"], "short-name"),
            "url": get_attr(r["p"], "job-url"),
            "location": get_attr(r["p"], "location"),
            "remote_policy": get_attr(r["p"], "remote-policy"),
            "salary": get_attr(r["p"], "salary-range"),
            "priority": get_attr(r["p"], "priority-level"),
            "status": get_attr(r["n"], "application-status"),
            "company": r.get("company_name", ""),
        }
        positions.append(pos)

    print(json.dumps({"success": True, "positions": positions, "count": len(positions)}, indent=2))


def cmd_show_position(args):
    """Get full details for a position."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get position details
                pos_query = f'''match
                    $p isa jobhunt-position, has id "{args.id}";
                fetch $p: id, name, job-url, location, remote-policy, salary-range,
                    team-size, priority-level, deadline;'''
                pos_result = list(tx.query.fetch(pos_query))

                if not pos_result:
                    print(json.dumps({"success": False, "error": "Position not found"}))
                    return

                # Get company
                company_query = f'''match
                    $p isa jobhunt-position, has id "{args.id}";
                    (position: $p, employer: $c) isa position-at-company;
                fetch $c: id, name, company-url, location;'''
                company_result = list(tx.query.fetch(company_query))

                # Get all notes (only fetch common attributes - specific ones like
                # application-status are only on subtypes)
                notes_query = f'''match
                    $p isa jobhunt-position, has id "{args.id}";
                    (note: $n, subject: $p) isa aboutness;
                fetch $n: id, name, content;'''
                notes_result = list(tx.query.fetch(notes_query))

                # Get requirements
                req_query = f'''match
                    $p isa jobhunt-position, has id "{args.id}";
                    (requirement: $r, position: $p) isa requirement-for;
                fetch $r: id, skill-name, skill-level, your-level, content;'''
                req_result = list(tx.query.fetch(req_query))

                # Get job description artifact
                artifact_query = f'''match
                    $p isa jobhunt-position, has id "{args.id}";
                    (artifact: $a, referent: $p) isa representation;
                    $a isa jobhunt-job-description;
                fetch $a: id, content;'''
                artifact_result = list(tx.query.fetch(artifact_query))

                # Get tags
                tags_query = f'''match
                    $p isa jobhunt-position, has id "{args.id}";
                    (tagged-entity: $p, tag: $t) isa tagging;
                fetch $t: name;'''
                tags_result = list(tx.query.fetch(tags_query))

    output = {
        "success": True,
        "position": pos_result[0]["p"] if pos_result else None,
        "company": company_result[0]["c"] if company_result else None,
        "notes": [n["n"] for n in notes_result],
        "requirements": [r["r"] for r in req_result],
        "job_description": artifact_result[0]["a"] if artifact_result else None,
        "tags": [t["t"]["name"][0]["value"] for t in tags_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_company(args):
    """Get company details and positions."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get company
                company_query = f'''match
                    $c isa jobhunt-company, has id "{args.id}";
                fetch $c: id, name, company-url, linkedin-url, description, location;'''
                company_result = list(tx.query.fetch(company_query))

                if not company_result:
                    print(json.dumps({"success": False, "error": "Company not found"}))
                    return

                # Get positions at company
                pos_query = f'''match
                    $c isa jobhunt-company, has id "{args.id}";
                    (position: $p, employer: $c) isa position-at-company;
                fetch $p: id, name, job-url, priority-level;'''
                pos_result = list(tx.query.fetch(pos_query))

                # Get notes about company
                notes_query = f'''match
                    $c isa jobhunt-company, has id "{args.id}";
                    (note: $n, subject: $c) isa aboutness;
                fetch $n: id, name, content;'''
                notes_result = list(tx.query.fetch(notes_query))

    output = {
        "success": True,
        "company": company_result[0]["c"] if company_result else None,
        "positions": [p["p"] for p in pos_result],
        "notes": [n["n"] for n in notes_result],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_gaps(args):
    """Show skill gaps across active applications."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get all requirements with their positions
                query = """match
                    $r isa jobhunt-requirement, has skill-name $skill;
                    (requirement: $r, position: $p) isa requirement-for;
                    (note: $n, subject: $p) isa aboutness;
                    $n isa jobhunt-application-note, has application-status $status;
                    not { $status = "rejected"; };
                    not { $status = "withdrawn"; };
                fetch $r: skill-name, skill-level, your-level;
                    $p: id, name;"""

                results = list(tx.query.fetch(query))

                # Get learning resources
                resources_query = """match
                    $res isa jobhunt-learning-resource;
                fetch $res: id, name, resource-type, resource-url, estimated-hours, completion-status;"""
                resources = list(tx.query.fetch(resources_query))

                # Get collections linked to requirements via addresses-requirement
                coll_query = """match
                    $c isa collection;
                    (resource: $c, requirement: $req) isa addresses-requirement;
                fetch $c: id, name, description;
                    $req: id, skill-name;"""
                coll_results = list(tx.query.fetch(coll_query))

    # Aggregate skills
    skill_map = {}
    for r in results:
        skill = get_attr(r["r"], "skill-name")
        if not skill:
            continue

        if skill not in skill_map:
            skill_map[skill] = {
                "skill": skill,
                "level": get_attr(r["r"], "skill-level"),
                "your_level": get_attr(r["r"], "your-level"),
                "positions": [],
            }

        skill_map[skill]["positions"].append(
            {"id": get_attr(r["p"], "id"), "title": get_attr(r["p"], "name")}
        )

    # Filter to gaps (where your_level is not 'strong')
    gaps = [s for s in skill_map.values() if s.get("your_level") in [None, "none", "some", ""]]

    # Sort by number of positions needing this skill
    gaps.sort(key=lambda x: len(x["positions"]), reverse=True)

    # Format collections linked to requirements
    collections = []
    for cr in coll_results:
        collections.append({
            "id": get_attr(cr["c"], "id"),
            "name": get_attr(cr["c"], "name"),
            "description": get_attr(cr["c"], "description"),
            "requirement_id": get_attr(cr["req"], "id"),
            "skill_name": get_attr(cr["req"], "skill-name"),
        })

    print(
        json.dumps(
            {
                "success": True,
                "skill_gaps": gaps,
                "total_gaps": len(gaps),
                "resources": [r["res"] for r in resources],
                "collections": collections,
            },
            indent=2,
            default=str,
        )
    )


def cmd_learning_plan(args):
    """Generate a prioritized learning plan based on skill gaps."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get all learning resources
                # Note: TypeDB 2.x doesn't support 'optional' - use separate queries if needed
                query = """match
                    $res isa jobhunt-learning-resource;
                fetch $res: id, name, resource-type, resource-url, estimated-hours, completion-status;"""

                results = list(tx.query.fetch(query))

                # Get collections linked to skill requirements
                coll_query = """match
                    $c isa collection;
                    (resource: $c, requirement: $req) isa addresses-requirement;
                    $req has skill-name $skill;
                fetch $c: id, name, description;
                    $req: skill-name;"""
                coll_results = list(tx.query.fetch(coll_query))

                # Get papers referenced by learning resources via citation-reference
                paper_query = """match
                    $res isa jobhunt-learning-resource;
                    (citing-item: $res, cited-item: $paper) isa citation-reference;
                fetch $res: id, name;
                    $paper: id, name;"""
                paper_results = list(tx.query.fetch(paper_query))

    # Format resources
    resources = []
    for r in results:
        res = {
            "id": get_attr(r["res"], "id"),
            "name": get_attr(r["res"], "name"),
            "type": get_attr(r["res"], "resource-type"),
            "url": get_attr(r["res"], "resource-url"),
            "hours": get_attr(r["res"], "estimated-hours"),
            "status": get_attr(r["res"], "completion-status"),
        }
        resources.append(res)

    # Remove duplicates
    seen = set()
    unique_resources = []
    for r in resources:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique_resources.append(r)

    # Format collections
    collections = []
    seen_colls = set()
    for cr in coll_results:
        coll_id = get_attr(cr["c"], "id")
        skill = get_attr(cr["req"], "skill-name")
        key = f"{coll_id}:{skill}"
        if key not in seen_colls:
            seen_colls.add(key)
            collections.append({
                "id": coll_id,
                "name": get_attr(cr["c"], "name"),
                "description": get_attr(cr["c"], "description"),
                "skill_name": skill,
            })

    # Format referenced papers
    referenced_papers = []
    for pr in paper_results:
        referenced_papers.append({
            "resource_id": get_attr(pr["res"], "id"),
            "resource_name": get_attr(pr["res"], "name"),
            "paper_id": get_attr(pr["paper"], "id"),
            "paper_name": get_attr(pr["paper"], "name"),
        })

    print(
        json.dumps(
            {
                "success": True,
                "learning_plan": unique_resources,
                "total_resources": len(unique_resources),
                "collections": collections,
                "referenced_papers": referenced_papers,
            },
            indent=2,
        )
    )


def cmd_tag(args):
    """Tag an entity."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Create tag if not exists
            tag_id = generate_id("tag")
            with session.transaction(TransactionType.READ) as tx:
                tag_check = f'match $t isa tag, has name "{args.tag}"; fetch $t: id;'
                existing_tag = list(tx.query.fetch(tag_check))

            if not existing_tag:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(f'insert $t isa tag, has id "{tag_id}", has name "{args.tag}";')
                    tx.commit()

            # Create tagging relation
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'''match
                    $e isa entity, has id "{args.entity}";
                    $t isa tag, has name "{args.tag}";
                insert (tagged-entity: $e, tag: $t) isa tagging;''')
                tx.commit()

    print(json.dumps({"success": True, "entity": args.entity, "tag": args.tag}))


def cmd_search_tag(args):
    """Search entities by tag."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match
                    $t isa tag, has name "{args.tag}";
                    (tagged-entity: $e, tag: $t) isa tagging;
                fetch $e: id, name;'''
                results = list(tx.query.fetch(query))

    print(
        json.dumps(
            {
                "success": True,
                "tag": args.tag,
                "entities": [r["e"] for r in results],
                "count": len(results),
            },
            indent=2,
            default=str,
        )
    )


def cmd_add_requirement(args):
    """Add a requirement to a position."""
    req_id = args.id or generate_id("requirement")
    timestamp = get_timestamp()

    query = f'''insert $r isa jobhunt-requirement,
        has id "{req_id}",
        has skill-name "{escape_string(args.skill)}",
        has created-at {timestamp}'''

    if args.level:
        query += f', has skill-level "{args.level}"'
    if args.your_level:
        query += f', has your-level "{args.your_level}"'
    if args.content:
        query += f', has content "{escape_string(args.content)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to position
            with session.transaction(TransactionType.WRITE) as tx:
                rel_query = f'''match
                    $r isa jobhunt-requirement, has id "{req_id}";
                    $p isa jobhunt-position, has id "{args.position}";
                insert (requirement: $r, position: $p) isa requirement-for;'''
                tx.query.insert(rel_query)
                tx.commit()

    print(
        json.dumps(
            {
                "success": True,
                "requirement_id": req_id,
                "skill": args.skill,
                "position": args.position,
            }
        )
    )


# =============================================================================
# YOUR SKILL PROFILE COMMANDS
# =============================================================================


def cmd_add_skill(args):
    """
    Add or update a skill in your profile.

    Your skill profile is used during sensemaking to compare
    position requirements against your capabilities for gap analysis.
    """
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Check if skill already exists
            with session.transaction(TransactionType.READ) as tx:
                check_query = f'''match
                    $s isa your-skill, has skill-name "{escape_string(args.name)}";
                fetch $s: skill-name, skill-level;'''
                existing = list(tx.query.fetch(check_query))

            if existing:
                # Update existing skill - delete and recreate
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.delete(f'''match
                        $s isa your-skill, has skill-name "{escape_string(args.name)}";
                    delete $s isa your-skill;''')
                    tx.commit()

            # Create skill
            with session.transaction(TransactionType.WRITE) as tx:
                skill_id = generate_id("skill")
                skill_query = f'''insert $s isa your-skill,
                    has id "{skill_id}",
                    has skill-name "{escape_string(args.name)}",
                    has skill-level "{args.level}",
                    has last-updated {timestamp}'''

                if args.description:
                    skill_query += f', has description "{escape_string(args.description)}"'

                skill_query += ";"
                tx.query.insert(skill_query)
                tx.commit()

    action = "updated" if existing else "added"
    print(
        json.dumps(
            {
                "success": True,
                "action": action,
                "skill_name": args.name,
                "skill_level": args.level,
                "message": f"Skill '{args.name}' {action} as '{args.level}'",
            }
        )
    )


def cmd_list_skills(args):
    """List your skill profile."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match
                    $s isa your-skill;
                fetch $s: skill-name, skill-level, description, last-updated;"""
                results = list(tx.query.fetch(query))

    # Format output
    skills = []
    for r in results:
        skill = {
            "name": get_attr(r["s"], "skill-name"),
            "level": get_attr(r["s"], "skill-level"),
            "description": get_attr(r["s"], "description"),
            "last_updated": get_attr(r["s"], "last-updated"),
        }
        skills.append(skill)

    # Sort by level (strong first, then some, then learning, then none)
    level_order = {"strong": 0, "some": 1, "learning": 2, "none": 3}
    skills.sort(key=lambda x: (level_order.get(x["level"], 4), x["name"]))

    print(
        json.dumps(
            {
                "success": True,
                "skills": skills,
                "count": len(skills),
                "by_level": {
                    "strong": len([s for s in skills if s["level"] == "strong"]),
                    "some": len([s for s in skills if s["level"] == "some"]),
                    "learning": len([s for s in skills if s["level"] == "learning"]),
                    "none": len([s for s in skills if s["level"] == "none"]),
                },
            },
            indent=2,
        )
    )


# =============================================================================
# ARTIFACT COMMANDS (for Claude's sensemaking)
# =============================================================================


def cmd_list_artifacts(args):
    """
    List artifacts, optionally filtered by analysis status.

    Status:
    - 'raw': Artifacts with no notes (need sensemaking)
    - 'analyzed': Artifacts with at least one note
    - 'all': All artifacts
    """
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get all job description artifacts
                artifacts_query = """match
                    $a isa jobhunt-job-description;
                fetch $a: id, name, source-uri, created-at;"""
                artifacts = list(tx.query.fetch(artifacts_query))

                # For each artifact, check if it has associated notes
                # (via position -> aboutness -> note)
                results = []
                for art in artifacts:
                    artifact_id = get_attr(art["a"], "id")

                    # Check for notes on the linked position
                    notes_query = f'''match
                        $a isa jobhunt-job-description, has id "{artifact_id}";
                        (artifact: $a, referent: $p) isa representation;
                        (note: $n, subject: $p) isa aboutness;
                        not {{ $n isa jobhunt-application-note; }};
                    fetch $n: id;'''

                    try:
                        notes = list(tx.query.fetch(notes_query))
                        has_notes = len(notes) > 0
                    except Exception:
                        has_notes = False

                    status = "analyzed" if has_notes else "raw"

                    # Apply filter
                    if args.status and args.status != "all":
                        if args.status != status:
                            continue

                    results.append(
                        {
                            "id": artifact_id,
                            "name": get_attr(art["a"], "name"),
                            "source_url": get_attr(art["a"], "source-uri"),
                            "created_at": get_attr(art["a"], "created-at"),
                            "status": status,
                            "note_count": len(notes) if has_notes else 0,
                        }
                    )

    print(
        json.dumps(
            {
                "success": True,
                "artifacts": results,
                "count": len(results),
                "filter": args.status or "all",
            },
            indent=2,
        )
    )


def cmd_show_artifact(args):
    """
    Get full artifact content for Claude to read during sensemaking.

    Returns the raw content stored during ingestion, along with
    metadata about the linked position. Content is loaded from cache
    if the artifact was stored externally.
    """
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get artifact - include cache-path and other cache attributes
                artifact_query = f'''match
                    $a isa jobhunt-job-description, has id "{args.id}";
                fetch $a: id, name, content, cache-path, mime-type, file-size, source-uri, created-at;'''
                artifact_result = list(tx.query.fetch(artifact_query))

                if not artifact_result:
                    print(json.dumps({"success": False, "error": "Artifact not found"}))
                    return

                # Get linked position (specifically jobhunt-position)
                position_query = f'''match
                    $a isa jobhunt-job-description, has id "{args.id}";
                    (artifact: $a, referent: $p) isa representation;
                    $p isa jobhunt-position;
                fetch $p: id, name, job-url, location, remote-policy, salary-range, priority-level;'''
                position_result = list(tx.query.fetch(position_query))

                # Get linked company (if any)
                company_result = []
                if position_result:
                    pos_id = get_attr(position_result[0]["p"], "id")
                    company_query = f'''match
                        $p isa jobhunt-position, has id "{pos_id}";
                        (position: $p, employer: $c) isa position-at-company;
                    fetch $c: id, name;'''
                    try:
                        company_result = list(tx.query.fetch(company_query))
                    except Exception:
                        pass

    art = artifact_result[0]["a"]

    # Get content - either from inline content or from cache
    cache_path = get_attr(art, "cache-path")
    if cache_path and CACHE_AVAILABLE:
        # Load from cache
        try:
            content = load_from_cache_text(cache_path)
            storage = "cache"
        except FileNotFoundError:
            content = f"[ERROR: Cache file not found: {cache_path}]"
            storage = "cache_missing"
    else:
        # Get inline content
        content = get_attr(art, "content")
        storage = "inline"

    output = {
        "success": True,
        "artifact": {
            "id": get_attr(art, "id"),
            "name": get_attr(art, "name"),
            "source_url": get_attr(art, "source-uri"),
            "created_at": get_attr(art, "created-at"),
            "content": content,
            "storage": storage,
            "cache_path": cache_path,
            "mime_type": get_attr(art, "mime-type"),
            "file_size": get_attr(art, "file-size"),
        },
        "position": None,
        "company": None,
    }

    if position_result:
        pos = position_result[0]["p"]
        output["position"] = {
            "id": get_attr(pos, "id"),
            "name": get_attr(pos, "name"),
            "url": get_attr(pos, "job-url"),
            "location": get_attr(pos, "location"),
            "remote_policy": get_attr(pos, "remote-policy"),
            "salary": get_attr(pos, "salary-range"),
            "priority": get_attr(pos, "priority-level"),
        }

    if company_result:
        comp = company_result[0]["c"]
        output["company"] = {
            "id": get_attr(comp, "id"),
            "name": get_attr(comp, "name"),
        }

    print(json.dumps(output, indent=2))


def cmd_cache_stats(args):
    """Show cache statistics."""
    stats = get_cache_stats()

    if "error" in stats:
        print(json.dumps({"success": False, "error": stats["error"]}))
        return

    # Format sizes for readability
    output = {
        "success": True,
        "cache_dir": stats["cache_dir"],
        "total_files": stats["total_files"],
        "total_size": stats["total_size"],
        "total_size_human": format_size(stats["total_size"]),
        "by_type": {},
    }

    for type_name, type_stats in stats["by_type"].items():
        output["by_type"][type_name] = {
            "count": type_stats["count"],
            "size": type_stats["size"],
            "size_human": format_size(type_stats["size"]),
        }

    print(json.dumps(output, indent=2))


# =============================================================================
# REPORT COMMANDS (Markdown output for messaging apps)
# =============================================================================


STATUS_EMOJI = {
    "researching": "🔍",
    "applied": "📨",
    "phone-screen": "📞",
    "interviewing": "🎯",
    "offer": "🎉",
    "rejected": "❌",
    "withdrawn": "⏸️",
}

PRIORITY_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}


def _fetch_pipeline_data():
    """Fetch all pipeline data: positions with status from application notes."""
    client = TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")
    session = client.session(TYPEDB_DATABASE, SessionType.DATA)

    try:
        tx = session.transaction(TransactionType.READ)

        # Get positions with status from application notes
        query = """
            match
            $p isa jobhunt-position;
            (note: $n, subject: $p) isa aboutness;
            $n isa jobhunt-application-note, has application-status $status;
            fetch $p: id, name, short-name, job-url, priority-level;
                $n: application-status;
        """
        results = list(tx.query.fetch(query))

        # Also get positions WITHOUT application notes (still researching)
        all_pos_query = """
            match $p isa jobhunt-position;
            fetch $p: id, name, short-name, job-url, priority-level;
        """
        all_positions = list(tx.query.fetch(all_pos_query))

        tx.close()
    finally:
        session.close()
        client.close()

    # Extract positions with status
    tracked = {}
    for r in results:
        p = r["p"]
        pid = p.get("id", [{}])[0].get("value", "") if p.get("id") else ""
        if not pid:
            continue
        tracked[pid] = {
            "id": pid,
            "name": p.get("name", [{}])[0].get("value", "") if p.get("name") else "",
            "short_name": p.get("short-name", [{}])[0].get("value", "") if p.get("short-name") else "",
            "priority": p.get("priority-level", [{}])[0].get("value", "") if p.get("priority-level") else "",
            "url": p.get("job-url", [{}])[0].get("value", "") if p.get("job-url") else "",
            "status": r["n"].get("application-status", [{}])[0].get("value", "researching") if r.get("n") else "researching",
        }

    # Add untracked positions as "researching"
    for r in all_positions:
        p = r["p"]
        pid = p.get("id", [{}])[0].get("value", "") if p.get("id") else ""
        if not pid or pid in tracked:
            continue
        tracked[pid] = {
            "id": pid,
            "name": p.get("name", [{}])[0].get("value", "") if p.get("name") else "",
            "short_name": p.get("short-name", [{}])[0].get("value", "") if p.get("short-name") else "",
            "priority": p.get("priority-level", [{}])[0].get("value", "") if p.get("priority-level") else "",
            "url": p.get("job-url", [{}])[0].get("value", "") if p.get("job-url") else "",
            "status": "researching",
        }

    return list(tracked.values())


def cmd_report_pipeline(args):
    """Generate pipeline report as formatted Markdown."""
    positions = _fetch_pipeline_data()

    # Group by status
    by_status = {}
    for p in positions:
        s = p["status"]
        by_status.setdefault(s, []).append(p)

    # Count stats
    total = len(positions)
    active = sum(1 for p in positions if p["status"] not in ("rejected", "withdrawn", "offer"))
    applied = sum(1 for p in positions if p["status"] == "applied")
    interviewing = sum(1 for p in positions if p["status"] in ("phone-screen", "interviewing"))

    # Build markdown
    lines = ["**📊 Job Search Pipeline**", ""]
    lines.append(f"Total: {total} | Active: {active} | Applied: {applied} | Interviewing: {interviewing}")
    lines.append("")

    status_order = ["interviewing", "phone-screen", "applied", "researching", "offer", "rejected", "withdrawn"]

    for status in status_order:
        group = by_status.get(status, [])
        if not group:
            continue
        emoji = STATUS_EMOJI.get(status, "•")
        lines.append(f"**{emoji} {status.replace('-', ' ').title()}** ({len(group)})")
        for p in group:
            display = p["short_name"] or p["name"][:40]
            pri = PRIORITY_EMOJI.get(p["priority"], "") + " " if p["priority"] else ""
            lines.append(f"  • {pri}{display}")
        lines.append("")

    print("\n".join(lines))


def cmd_report_position(args):
    """Generate position detail report as formatted Markdown."""
    client = TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")
    session = client.session(TYPEDB_DATABASE, SessionType.DATA)

    try:
        tx = session.transaction(TransactionType.READ)

        pid = args.id

        # Get position attributes
        query = f"""
            match $p isa jobhunt-position, has id "{pid}", has $a;
            get $a;
        """
        results = list(tx.query.get(query))
        if not results:
            print(f"Position `{pid}` not found.")
            return

        attrs = {}
        for r in results:
            a = r.get("a")
            label = a.get_type().get_label().name
            attrs[label] = a.get_value()

        # Get notes
        note_query = f"""
            match
            $p isa jobhunt-position, has id "{pid}";
            $note isa note, has content $c;
            (subject: $p, note: $note) isa aboutness;
            $note has name $nname;
            get $c, $nname;
        """
        try:
            notes = list(tx.query.get(note_query))
        except Exception:
            notes = []

        # Get notes without names
        note_query2 = f"""
            match
            $p isa jobhunt-position, has id "{pid}";
            $note isa note, has content $c;
            (subject: $p, note: $note) isa aboutness;
            get $c;
        """
        try:
            all_notes = list(tx.query.get(note_query2))
        except Exception:
            all_notes = []

        # Get application status from application note
        status_query = f"""
            match
            $p isa jobhunt-position, has id "{pid}";
            $n isa jobhunt-application-note, has application-status $s;
            (subject: $p, note: $n) isa aboutness;
            get $s;
        """
        try:
            status_results = list(tx.query.get(status_query))
            if status_results:
                attrs["application-status"] = status_results[0].get("s").get_value()
        except Exception:
            pass

        tx.close()
    finally:
        session.close()
        client.close()

    # Build markdown
    title = attrs.get("short-name") or attrs.get("name", pid)
    status = attrs.get("application-status", "unknown")
    status_emoji = STATUS_EMOJI.get(status, "•")

    lines = [f"**{title}**", ""]
    lines.append(f"Status: {status_emoji} {status}")
    if attrs.get("priority-level"):
        lines.append(f"Priority: {PRIORITY_EMOJI.get(attrs['priority-level'], '')} {attrs['priority-level']}")
    if attrs.get("job-url"):
        lines.append(f"URL: {attrs['job-url']}")
    if attrs.get("salary-range"):
        lines.append(f"Salary: {attrs['salary-range']}")
    if attrs.get("location"):
        lines.append(f"Location: {attrs['location']}")
    if attrs.get("remote-policy"):
        lines.append(f"Remote: {attrs['remote-policy']}")
    lines.append("")

    if all_notes:
        lines.append(f"**Notes** ({len(all_notes)})")
        lines.append("")
        for n in all_notes:
            content = n.get("c").get_value()
            # Unescape literal \n sequences
            content = content.replace("\\n", "\n").replace("\\'", "'")
            # Truncate long notes for messaging
            if len(content) > 500:
                content = content[:497] + "..."
            lines.append(f"{content}")
            lines.append("")
            lines.append("---")
            lines.append("")

    print("\n".join(lines))


def cmd_report_gaps(args):
    """Generate skill gaps report as formatted Markdown."""
    client = TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")
    session = client.session(TYPEDB_DATABASE, SessionType.DATA)

    try:
        tx = session.transaction(TransactionType.READ)

        # Get all requirements with your skill levels
        query = """
            match
            $req isa jobhunt-requirement, has skill-name $skill, has skill-level $level;
            $p isa jobhunt-position, has name $pname, has id $pid;
            (position: $p, requirement: $req) isa requirement-for;
            get $skill, $level, $pname, $pid;
        """
        results = list(tx.query.get(query))

        # Get your skills
        skill_query = """
            match $s isa your-skill, has skill-name $name, has skill-level $level;
            get $name, $level;
        """
        try:
            skill_results = list(tx.query.get(skill_query))
        except Exception:
            skill_results = []

        tx.close()
    finally:
        session.close()
        client.close()

    my_skills = {}
    for s in skill_results:
        my_skills[s.get("name").get_value()] = s.get("level").get_value()

    # Group by skill
    gaps = {}
    for r in results:
        skill = r.get("skill").get_value()
        level = r.get("level").get_value()
        pos_name = r.get("pname").get_value()
        my_level = my_skills.get(skill, "none")

        if my_level in ("strong",):
            continue  # No gap

        gaps.setdefault(skill, {
            "required_level": level,
            "your_level": my_level,
            "positions": [],
        })
        gaps[skill]["positions"].append(pos_name[:30])

    # Build markdown
    lines = ["**🎯 Skill Gaps Analysis**", ""]

    if not gaps:
        lines.append("No significant skill gaps found! ✅")
    else:
        # Sort: required gaps first, then by number of positions
        sorted_gaps = sorted(
            gaps.items(),
            key=lambda x: (0 if x[1]["required_level"] == "required" else 1, -len(x[1]["positions"]))
        )

        LEVEL_EMOJI = {"none": "⬜", "some": "🟨", "learning": "🟧", "strong": "🟩"}

        for skill, info in sorted_gaps:
            level_e = LEVEL_EMOJI.get(info["your_level"], "⬜")
            req_marker = "❗" if info["required_level"] == "required" else "💡"
            count = len(info["positions"])
            lines.append(f"{req_marker} **{skill}** {level_e} ({info['your_level']}) → needed by {count} position(s)")

    lines.append("")
    lines.append("Legend: ❗required 💡preferred | ⬜none 🟧learning 🟨some 🟩strong")

    print("\n".join(lines))


def cmd_report_stats(args):
    """Generate stats overview as formatted Markdown."""
    positions = _fetch_pipeline_data()

    total = len(positions)
    statuses = [p["status"] for p in positions]
    priorities = [p["priority"] for p in positions]

    active = sum(1 for s in statuses if s not in ("rejected", "withdrawn", "offer"))
    by_status = {}
    for s in statuses:
        by_status[s] = by_status.get(s, 0) + 1
    high_pri = sum(1 for p in priorities if p == "high")

    lines = ["**📈 Job Search Stats**", ""]
    lines.append(f"📋 **{total}** total positions")
    lines.append(f"🚀 **{active}** active applications")
    lines.append(f"🔴 **{high_pri}** high priority")
    lines.append("")
    lines.append("**By Status:**")

    status_order = ["interviewing", "phone-screen", "applied", "researching", "offer", "rejected", "withdrawn"]
    for s in status_order:
        count = by_status.get(s, 0)
        if count > 0:
            emoji = STATUS_EMOJI.get(s, "•")
            lines.append(f"  {emoji} {s.replace('-', ' ').title()}: {count}")

    print("\n".join(lines))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Job Hunting Notebook CLI - Track applications and analyze opportunities"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ingest-job
    p = subparsers.add_parser("ingest-job", help="Fetch and parse a job posting URL")
    p.add_argument("--url", required=True, help="Job posting URL")
    p.add_argument("--company", help="Override company name")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--tags", nargs="+", help="Tags to apply")

    # add-company
    p = subparsers.add_parser("add-company", help="Add a company")
    p.add_argument("--name", required=True, help="Company name")
    p.add_argument("--url", help="Company website")
    p.add_argument("--linkedin", help="LinkedIn company page")
    p.add_argument("--description", help="Brief description")
    p.add_argument("--location", help="Headquarters location")
    p.add_argument("--id", help="Specific ID")

    # add-position
    p = subparsers.add_parser("add-position", help="Add a position manually")
    p.add_argument("--title", required=True, help="Position title")
    p.add_argument("--company", help="Company ID")
    p.add_argument("--url", help="Job posting URL")
    p.add_argument("--location", help="Job location")
    p.add_argument("--remote-policy", choices=["remote", "hybrid", "onsite"], help="Remote policy")
    p.add_argument("--salary", help="Salary range")
    p.add_argument("--team-size", help="Team size")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--deadline", help="Application deadline (YYYY-MM-DD)")
    p.add_argument("--id", help="Specific ID")

    # update-status
    p = subparsers.add_parser("update-status", help="Update application status")
    p.add_argument("--position", required=True, help="Position ID")
    p.add_argument(
        "--status",
        required=True,
        choices=[
            "researching",
            "applied",
            "phone-screen",
            "interviewing",
            "offer",
            "rejected",
            "withdrawn",
        ],
        help="New status",
    )
    p.add_argument("--date", help="Date of status change (YYYY-MM-DD)")

    # set-short-name
    p = subparsers.add_parser("set-short-name", help="Set short display name for a position")
    p.add_argument("--position", required=True, help="Position ID")
    p.add_argument("--name", required=True, help="Short name (e.g., 'anthropic', 'langchain')")

    # add-note
    p = subparsers.add_parser("add-note", help="Create a note")
    p.add_argument("--about", required=True, help="Entity ID this note is about")
    p.add_argument(
        "--type",
        required=True,
        choices=[
            "research",
            "interview",
            "strategy",
            "skill-gap",
            "fit-analysis",
            "interaction",
            "application",
            "general",
        ],
        help="Note type",
    )
    p.add_argument("--content", required=True, help="Note content")
    p.add_argument("--name", help="Note title")
    p.add_argument("--confidence", type=float, help="Confidence score (0.0-1.0)")
    p.add_argument("--tags", nargs="+", help="Tags to apply")
    p.add_argument("--interaction-type", help="Type of interaction (for interaction notes)")
    p.add_argument("--interaction-date", help="Date of interaction")
    p.add_argument("--interview-date", help="Date of interview")
    p.add_argument("--fit-score", type=float, help="Fit score (for fit-analysis notes)")
    p.add_argument("--fit-summary", help="Fit summary")
    p.add_argument("--id", help="Specific ID")

    # add-resource
    p = subparsers.add_parser("add-resource", help="Add a learning resource")
    p.add_argument("--name", required=True, help="Resource name")
    p.add_argument(
        "--type",
        required=True,
        choices=["course", "book", "tutorial", "project", "video"],
        help="Resource type",
    )
    p.add_argument("--url", help="Resource URL")
    p.add_argument("--hours", type=int, help="Estimated hours to complete")
    p.add_argument("--description", help="Description")
    p.add_argument("--skills", nargs="+", help="Skills this addresses")
    p.add_argument("--id", help="Specific ID")

    # link-resource
    p = subparsers.add_parser("link-resource", help="Link resource to requirement")
    p.add_argument("--resource", required=True, help="Resource ID")
    p.add_argument("--requirement", required=True, help="Requirement ID")

    # link-collection
    p = subparsers.add_parser("link-collection", help="Link paper collection to skill requirement(s)")
    p.add_argument("--collection", required=True, help="Collection ID")
    p.add_argument("--requirement", help="Specific requirement ID")
    p.add_argument("--skill", help="Skill name (links to all matching requirements)")

    # link-paper
    p = subparsers.add_parser("link-paper", help="Link learning resource to a paper via citation-reference")
    p.add_argument("--resource", required=True, help="Learning resource ID")
    p.add_argument("--paper", required=True, help="Paper ID (scilit-paper)")

    # add-requirement
    p = subparsers.add_parser("add-requirement", help="Add a requirement to a position")
    p.add_argument("--position", required=True, help="Position ID")
    p.add_argument("--skill", required=True, help="Skill name")
    p.add_argument(
        "--level", choices=["required", "preferred", "nice-to-have"], help="Requirement level"
    )
    p.add_argument("--your-level", choices=["strong", "some", "none"], help="Your skill level")
    p.add_argument("--content", help="Full requirement text")
    p.add_argument("--id", help="Specific ID")

    # add-skill (your profile)
    p = subparsers.add_parser("add-skill", help="Add/update a skill in your profile")
    p.add_argument(
        "--name", required=True, help="Skill name (e.g., 'Python', 'Distributed Systems')"
    )
    p.add_argument(
        "--level",
        required=True,
        choices=["strong", "some", "learning", "none"],
        help="Your skill level",
    )
    p.add_argument("--description", help="Optional description or evidence of this skill")

    # list-skills
    subparsers.add_parser("list-skills", help="Show your skill profile")

    # list-artifacts
    p = subparsers.add_parser(
        "list-artifacts", help="List artifacts (job descriptions) with analysis status"
    )
    p.add_argument(
        "--status",
        choices=["raw", "analyzed", "all"],
        help="Filter: raw (needs sensemaking), analyzed (has notes), all",
    )

    # show-artifact
    p = subparsers.add_parser("show-artifact", help="Get artifact content for Claude to read")
    p.add_argument("--id", required=True, help="Artifact ID")

    # list-pipeline
    p = subparsers.add_parser("list-pipeline", help="Show application pipeline")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Filter by priority")
    p.add_argument("--tag", help="Filter by tag")

    # show-position
    p = subparsers.add_parser("show-position", help="Get position details")
    p.add_argument("--id", required=True, help="Position ID")

    # show-company
    p = subparsers.add_parser("show-company", help="Get company details")
    p.add_argument("--id", required=True, help="Company ID")

    # show-gaps
    p = subparsers.add_parser("show-gaps", help="Show skill gaps")
    p.add_argument(
        "--priority", choices=["high", "medium", "low"], help="Filter by position priority"
    )

    # learning-plan
    subparsers.add_parser("learning-plan", help="Show prioritized learning plan")

    # tag
    p = subparsers.add_parser("tag", help="Tag an entity")
    p.add_argument("--entity", required=True, help="Entity ID")
    p.add_argument("--tag", required=True, help="Tag name")

    # search-tag
    p = subparsers.add_parser("search-tag", help="Search by tag")
    p.add_argument("--tag", required=True, help="Tag to search for")

    # cache-stats
    subparsers.add_parser("cache-stats", help="Show cache statistics")

    # report commands (Markdown output for messaging apps)
    p = subparsers.add_parser("report-pipeline", help="Pipeline report (Markdown)")
    p = subparsers.add_parser("report-stats", help="Stats overview (Markdown)")
    p = subparsers.add_parser("report-gaps", help="Skill gaps report (Markdown)")
    p = subparsers.add_parser("report-position", help="Position detail report (Markdown)")
    p.add_argument("--id", required=True, help="Position ID")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        # Ingestion
        "ingest-job": cmd_ingest_job,
        "add-company": cmd_add_company,
        "add-position": cmd_add_position,
        # Your skill profile
        "add-skill": cmd_add_skill,
        "list-skills": cmd_list_skills,
        # Artifacts (for sensemaking)
        "list-artifacts": cmd_list_artifacts,
        "show-artifact": cmd_show_artifact,
        # Application tracking
        "update-status": cmd_update_status,
        "set-short-name": cmd_set_short_name,
        "add-note": cmd_add_note,
        "add-resource": cmd_add_resource,
        "link-resource": cmd_link_resource,
        "link-collection": cmd_link_collection,
        "link-paper": cmd_link_paper,
        "add-requirement": cmd_add_requirement,
        # Queries
        "list-pipeline": cmd_list_pipeline,
        "show-position": cmd_show_position,
        "show-company": cmd_show_company,
        "show-gaps": cmd_show_gaps,
        "learning-plan": cmd_learning_plan,
        "tag": cmd_tag,
        "search-tag": cmd_search_tag,
        # Cache
        "cache-stats": cmd_cache_stats,
        # Reports (Markdown)
        "report-pipeline": cmd_report_pipeline,
        "report-stats": cmd_report_stats,
        "report-gaps": cmd_report_gaps,
        "report-position": cmd_report_position,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
