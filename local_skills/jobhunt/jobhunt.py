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
    link-background     Link paper collection to opportunity as background reading
    list-background     List paper collections linked to an opportunity
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
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# Cache utilities (inlined — no external package needed)
# ---------------------------------------------------------------------------

_CACHE_THRESHOLD = 50 * 1024  # 50KB

_MIME_TYPE_MAP = {
    "text/html": ("html", "html"),
    "application/xhtml+xml": ("html", "html"),
    "application/pdf": ("pdf", "pdf"),
    "image/png": ("image", "png"),
    "image/jpeg": ("image", "jpg"),
    "image/gif": ("image", "gif"),
    "image/webp": ("image", "webp"),
    "image/svg+xml": ("image", "svg"),
    "application/json": ("json", "json"),
    "text/plain": ("text", "txt"),
    "text/markdown": ("text", "md"),
    "text/csv": ("text", "csv"),
    "application/xml": ("text", "xml"),
    "text/xml": ("text", "xml"),
}


def get_cache_dir():
    cache_env = os.getenv("ALHAZEN_CACHE_DIR")
    cache_dir = Path(cache_env).expanduser() if cache_env else Path.home() / ".alhazen" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def should_cache(content):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return len(content) >= _CACHE_THRESHOLD


def save_to_cache(artifact_id, content, mime_type):
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content
    type_dir, ext = _MIME_TYPE_MAP.get(mime_type, ("other", "bin"))
    cache_dir = get_cache_dir()
    type_path = cache_dir / type_dir
    type_path.mkdir(parents=True, exist_ok=True)
    filename = f"{artifact_id}.{ext}"
    full_path = type_path / filename
    full_path.write_bytes(content_bytes)
    return {
        "cache_path": f"{type_dir}/{filename}",
        "file_size": len(content_bytes),
        "content_hash": hashlib.sha256(content_bytes).hexdigest(),
        "full_path": str(full_path),
    }


def load_from_cache_text(cache_path, encoding="utf-8"):
    return (get_cache_dir() / cache_path).read_bytes().decode(encoding)


def get_cache_stats():
    cache_dir = get_cache_dir()
    stats = {"cache_dir": str(cache_dir), "total_files": 0, "total_size": 0, "by_type": {}}
    if not cache_dir.exists():
        return stats
    for type_dir in cache_dir.iterdir():
        if type_dir.is_dir():
            type_stats = {"count": 0, "size": 0}
            for f in type_dir.iterdir():
                if f.is_file():
                    type_stats["count"] += 1
                    type_stats["size"] += f.stat().st_size
            if type_stats["count"] > 0:
                stats["by_type"][type_dir.name] = type_stats
                stats["total_files"] += type_stats["count"]
                stats["total_size"] += type_stats["size"]
    return stats


def format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


CACHE_AVAILABLE = True


# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def get_attr(entity: dict, attr_name: str, default=None):
    """Safely extract attribute value from TypeDB 3.x fetch result.

    TypeDB 3.x fetch returns plain Python dicts directly.
    """
    return entity.get(attr_name, default)


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
        # Create position placeholder (Claude will update with extracted info)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            position_query = f'''insert $p isa jhunt-position,
                has id "{position_id}",
                has name "{escape_string(placeholder_name)}",
                has jhunt-job-url "{escape_string(url)}",
                has created-at {timestamp}'''

            if args.priority:
                position_query += f', has jhunt-priority-level "{args.priority}"'

            position_query += ";"
            tx.query(position_query).resolve()
            tx.commit()

        # Create job description artifact with content (inline or cached)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            if CACHE_AVAILABLE and should_cache(content):
                cache_result = save_to_cache(
                    artifact_id=artifact_id,
                    content=content,
                    mime_type="text/html",
                )
                artifact_query = f'''insert $a isa jhunt-job-description,
                    has id "{artifact_id}",
                    has name "Job Description: {escape_string(placeholder_name)}",
                    has cache-path "{cache_result['cache_path']}",
                    has mime-type "text/html",
                    has file-size {cache_result['file_size']},
                    has content-hash "{cache_result['content_hash']}",
                    has source-uri "{escape_string(url)}",
                    has created-at {timestamp};'''
            else:
                artifact_query = f'''insert $a isa jhunt-job-description,
                    has id "{artifact_id}",
                    has name "Job Description: {escape_string(placeholder_name)}",
                    has content "{escape_string(content)}",
                    has source-uri "{escape_string(url)}",
                    has created-at {timestamp};'''
            tx.query(artifact_query).resolve()
            tx.commit()

        # Link artifact to position
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            rep_query = f'''match
                $a isa jhunt-job-description, has id "{artifact_id}";
                $p isa jhunt-position, has id "{position_id}";
            insert (alh-artifact: $a, referent: $p) isa alh-representation;'''
            tx.query(rep_query).resolve()
            tx.commit()

        # Create initial application note with researching status
        app_note_id = generate_id("note")
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            note_query = f'''insert $n isa jhunt-application-note,
                has id "{app_note_id}",
                has name "Application Status",
                has jhunt-application-status "researching",
                has created-at {timestamp};'''
            tx.query(note_query).resolve()
            tx.commit()

        # Link note to position
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            about_query = f'''match
                $n isa alh-note, has id "{app_note_id}";
                $p isa jhunt-position, has id "{position_id}";
            insert (note: $n, subject: $p) isa alh-aboutness;'''
            tx.query(about_query).resolve()
            tx.commit()

        # Add tags if specified
        if args.tags:
            for tag_name in args.tags:
                tag_id = generate_id("tag")
                with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                    tag_check = f'match $t isa alh-tag, has name "{tag_name}"; fetch {{ "id": $t.id }};' 
                    existing_tag = list(tx.query(tag_check).resolve())

                if not existing_tag:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(
                            f'insert $t isa alh-tag, has id "{tag_id}", has name "{tag_name}";'
                        ).resolve()
                        tx.commit()

                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $p isa jhunt-position, has id "{position_id}";
                        $t isa alh-tag, has name "{tag_name}";
                    insert (tagged-entity: $p, tag: $t) isa alh-tagging;''').resolve()
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

    # Link to active job-seeker role
    try:
        with get_driver() as d:
            _link_opportunity_to_seeker(d, position_id)
    except Exception:
        pass  # seeker role may not exist yet

    print(json.dumps(output, indent=2))


def cmd_add_company(args):
    """Add a company to track."""
    company_id = args.id or generate_id("company")
    timestamp = get_timestamp()

    query = f'''insert $c isa jhunt-company,
        has id "{company_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.url:
        query += f', has alh-company-url "{escape_string(args.url)}"'
    if args.linkedin:
        query += f', has alh-linkedin-url "{escape_string(args.linkedin)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    if args.location:
        query += f', has alh-location "{escape_string(args.location)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "company_id": company_id, "name": args.name}))


def cmd_add_position(args):
    """Add a position manually."""
    position_id = args.id or generate_id("position")
    timestamp = get_timestamp()

    query = f'''insert $p isa jhunt-position,
        has id "{position_id}",
        has name "{escape_string(args.title)}",
        has created-at {timestamp}'''

    if args.url:
        query += f', has jhunt-job-url "{escape_string(args.url)}"'
    if args.location:
        query += f', has alh-location "{escape_string(args.location)}"'
    if args.jhunt_remote_policy:
        query += f', has jhunt-remote-policy "{args.jhunt_remote_policy}"'
    if args.salary:
        query += f', has jhunt-salary-range "{escape_string(args.salary)}"'
    if args.jhunt_team_size:
        query += f', has jhunt-team-size "{escape_string(args.jhunt_team_size)}"'
    if args.priority:
        query += f', has jhunt-priority-level "{args.priority}"'
    if args.deadline:
        query += f", has jhunt-deadline {parse_date(args.deadline)}"

    query += ";"

    app_note_id = generate_id("note")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to company (match by name, create if not found)
        if args.company:
            company_name = args.company.strip()
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                # Look up existing company by name
                existing = list(tx.query(f'''match
                    $c isa jhunt-company, has id $cid, has name $cn;
                fetch {{ "id": $cid, "name": $cn }};''').resolve())

                # Case-insensitive exact match
                company_id_linked = None
                for co in existing:
                    if co["name"].lower() == company_name.lower():
                        company_id_linked = co["id"]
                        break

                if not company_id_linked:
                    # Create new company
                    company_id_linked = generate_id("company")
                    tx.query(f'''insert $c isa jhunt-company,
                        has id "{company_id_linked}",
                        has name "{escape_string(company_name)}",
                        has created-at {timestamp};''').resolve()

                # Create jhunt-position-at-company relation
                tx.query(f'''match
                    $p isa jhunt-position, has id "{position_id}";
                    $c isa jhunt-company, has id "{company_id_linked}";
                insert (position: $p, employer: $c) isa jhunt-position-at-company;''').resolve()
                tx.commit()

        # Create initial application note
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            note_query = f'''insert $n isa jhunt-application-note,
                has id "{app_note_id}",
                has name "Application Status",
                has jhunt-application-status "researching",
                has created-at {timestamp};'''
            tx.query(note_query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            about_query = f'''match
                $n isa alh-note, has id "{app_note_id}";
                $p isa jhunt-position, has id "{position_id}";
            insert (note: $n, subject: $p) isa alh-aboutness;'''
            tx.query(about_query).resolve()
            tx.commit()

    # Link to active job-seeker role
    try:
        _link_opportunity_to_seeker(driver, position_id)
    except Exception:
        pass

    print(json.dumps({"success": True, "position_id": position_id, "title": args.title}))


def cmd_update_status(args):
    """Update application status for a position."""
    timestamp = get_timestamp()
    note_id = generate_id("note")

    with get_driver() as driver:
        # Find existing application note
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            find_query = f'''match
                $p isa jhunt-position, has id "{args.position}";
                (note: $n, subject: $p) isa alh-aboutness;
                $n isa jhunt-application-note;
            fetch {{ "id": $n.id }};'''
            existing = list(tx.query(find_query).resolve())

        if existing:
            # Delete old application note
            old_note_id = existing[0].get("id", "")
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'match $n isa alh-note, has id "{old_note_id}"; delete $n;'
                ).resolve()
                tx.commit()

        # Create new application note with updated status
        note_query = f'''insert $n isa jhunt-application-note,
            has id "{note_id}",
            has name "Application Status",
            has jhunt-application-status "{args.status}",
            has created-at {timestamp}'''

        if args.date:
            note_query += f", has jhunt-applied-date {parse_date(args.date)}"

        note_query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(note_query).resolve()
            tx.commit()

        # Link to position
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            about_query = f'''match
                $n isa alh-note, has id "{note_id}";
                $p isa jhunt-position, has id "{args.position}";
            insert (note: $n, subject: $p) isa alh-aboutness;'''
            tx.query(about_query).resolve()
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
        # Check if position exists and if it already has a jhunt-short-name
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check_query = f'''match
                $p isa jhunt-position, has id "{args.position}";
            fetch {{ "jhunt-short-name": $p.jhunt-short-name }};'''
            existing = list(tx.query(check_query).resolve())

        if not existing:
            print(json.dumps({"success": False, "error": "Position not found"}))
            return

        has_existing = bool(existing[0].get("jhunt-short-name"))

        if has_existing:
            # Delete old jhunt-short-name and add new one
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                delete_query = f'''match
                    $p isa jhunt-position, has id "{args.position}", has jhunt-short-name $sn;
                delete $p has $sn;'''
                tx.query(delete_query).resolve()
                tx.commit()

        # Add new jhunt-short-name
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_query = f'''match
                $p isa jhunt-position, has id "{args.position}";
            insert $p has jhunt-short-name "{escape_string(args.name)}";'''
            tx.query(insert_query).resolve()
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
        "research": "jhunt-research-note",
        "interview": "jhunt-interview-note",
        "strategy": "jhunt-strategy-note",
        "skill-gap": "jhunt-skill-gap-note",
        "fit-analysis": "jhunt-fit-analysis-note",
        "interaction": "jhunt-interaction-note",
        "application": "jhunt-application-note",
        "opp-summary": "jhunt-opp-summary-note",
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
            query += f', has alh-interaction-type "{args.interaction_type}"'
        if args.interaction_date:
            query += f", has alh-interaction-date {parse_date(args.interaction_date)}"

    if args.type == "interview" and args.interview_date:
        query += f", has jhunt-interview-date {parse_date(args.interview_date)}"

    if args.type == "fit-analysis":
        if args.fit_score:
            query += f", has jhunt-fit-score {args.fit_score}"
        if args.fit_summary:
            query += f', has jhunt-fit-summary "{escape_string(args.fit_summary)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to subject
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            about_query = f'''match
                $n isa alh-note, has id "{note_id}";
                $s isa alh-identifiable-entity, has id "{args.about}";
            insert (note: $n, subject: $s) isa alh-aboutness;'''
            tx.query(about_query).resolve()
            tx.commit()

        # Add tags
        if args.tags:
            for tag_name in args.tags:
                tag_id = generate_id("tag")
                with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                    tag_check = f'match $t isa alh-tag, has name "{tag_name}"; fetch {{ "id": $t.id }};'
                    existing_tag = list(tx.query(tag_check).resolve())

                if not existing_tag:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(
                            f'insert $t isa alh-tag, has id "{tag_id}", has name "{tag_name}";'
                        ).resolve()
                        tx.commit()

                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $n isa alh-note, has id "{note_id}";
                        $t isa alh-tag, has name "{tag_name}";
                    insert (tagged-entity: $n, tag: $t) isa alh-tagging;''').resolve()
                    tx.commit()

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about, "type": args.type}))


def cmd_upsert_summary(args):
    """Create or overwrite the opportunity summary."""
    timestamp = get_timestamp()
    content = args.content

    # If content is a file path, read it
    if content.startswith("@"):
        filepath = content[1:]
        with open(filepath, "r") as f:
            content = f.read()

    with get_driver() as driver:
        # Check for existing brief
        existing_id = None
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            r = list(tx.query(f'''match
                $s isa alh-identifiable-entity, has id "{args.about}";
                (note: $n, subject: $s) isa alh-aboutness;
                $n isa jhunt-opp-summary-note, has id $nid;
            fetch {{ "nid": $nid }};''').resolve())
            if r:
                existing_id = r[0]["nid"]

        if existing_id:
            # Delete old content, insert new
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $n isa jhunt-opp-summary-note, has id "{existing_id}", has content $c;
                delete has $c of $n;''').resolve()
                tx.commit()
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match $n isa jhunt-opp-summary-note, has id "{existing_id}";
                insert $n has content "{escape_string(content)}";''').resolve()
                tx.commit()
            # Update created-at to track last update
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $n isa jhunt-opp-summary-note, has id "{existing_id}", has created-at $t;
                delete has $t of $n;''').resolve()
                tx.commit()
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match $n isa jhunt-opp-summary-note, has id "{existing_id}";
                insert $n has created-at {timestamp};''').resolve()
                tx.commit()
            note_id = existing_id
            action = "updated"
        else:
            # Create new brief
            note_id = generate_id("oppsummary")
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''insert $n isa jhunt-opp-summary-note,
                    has id "{note_id}",
                    has name "brief",
                    has content "{escape_string(content)}",
                    has created-at {timestamp};''').resolve()
                tx.commit()
            # Link to subject
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $n isa jhunt-opp-summary-note, has id "{note_id}";
                    $s isa alh-identifiable-entity, has id "{args.about}";
                insert (note: $n, subject: $s) isa alh-aboutness;''').resolve()
                tx.commit()
            action = "created"

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about, "action": action}))


def cmd_regenerate_summary(args):
    """Fetch all notes + metadata for an opportunity so the agent can write a summary."""
    opp_id = args.about

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Determine opportunity type
            opp_meta = None
            for otype in ["jhunt-position", "jhunt-engagement", "jhunt-venture", "jhunt-lead"]:
                r = list(tx.query(f'''match $o isa {otype}, has id "{opp_id}", has name $n;
                    fetch {{ "name": $n }};''').resolve())
                if r:
                    opp_meta = {"id": opp_id, "type": otype.replace("jhunt-", ""), "name": r[0]["name"]}
                    break

            if not opp_meta:
                print(json.dumps({"success": False, "error": f"Opportunity {opp_id} not found"}))
                return

            otype_full = f"jhunt-{opp_meta['type']}"

            # Fetch optional attributes
            for attr, key in [("jhunt-short-name", "short_name"), ("jhunt-priority-level", "priority"),
                              ("created-at", "created_at"), ("jhunt-job-url", "job_url"),
                              ("jhunt-salary-range", "salary"), ("location", "location"),
                              ("jhunt-remote-policy", "remote_policy")]:
                try:
                    r = list(tx.query(f'match $o isa {otype_full}, has id "{opp_id}", has {attr} $v; fetch {{ "v": $v }};').resolve())
                    if r:
                        opp_meta[key] = str(r[0]["v"])
                except:
                    pass

            # Status
            if opp_meta["type"] == "position":
                try:
                    s = list(tx.query(f'''match $o isa {otype_full}, has id "{opp_id}";
                        (note: $n, subject: $o) isa alh-aboutness;
                        $n isa jhunt-application-note, has jhunt-application-status $s;
                    fetch {{ "s": $s }};''').resolve())
                    if s:
                        opp_meta["status"] = s[0]["s"]
                except:
                    pass
            else:
                try:
                    s = list(tx.query(f'match $o isa {otype_full}, has id "{opp_id}", has jhunt-opportunity-status $s; fetch {{ "s": $s }};').resolve())
                    if s:
                        opp_meta["status"] = s[0]["s"]
                except:
                    pass

            # Company
            try:
                for rel in ["jhunt-position-at-company", "jhunt-opportunity-at-organization"]:
                    role = "employer" if "position" in rel else "organization"
                    co = list(tx.query(f'''match $o isa {otype_full}, has id "{opp_id}";
                        ({rel.split("-")[0]}: $o, {role}: $c) isa {rel};
                    fetch {{ "name": $c.name }};''').resolve())
                    if co:
                        opp_meta["company"] = co[0]["name"]
                        break
            except:
                pass

            # All notes (grouped by type)
            notes = {}
            note_types = [
                ("jhunt-research-note", "research"),
                ("jhunt-fit-analysis-note", "fit-analysis"),
                ("jhunt-strategy-note", "strategy"),
                ("jhunt-skill-gap-note", "skill-gap"),
                ("jhunt-application-note", "application"),
                ("jhunt-interview-note", "interview"),
                ("jhunt-interaction-note", "interaction"),
                ("jhunt-opp-summary-note", "current-summary"),
                ("note", "general"),
            ]
            for ntype, label in note_types:
                try:
                    results = list(tx.query(f'''match
                        $o isa {otype_full}, has id "{opp_id}";
                        (note: $n, subject: $o) isa alh-aboutness;
                        $n isa {ntype}, has content $c;
                    fetch {{ "content": $c }};''').resolve())
                    if results:
                        notes[label] = [r["content"] for r in results]
                except:
                    pass

            # Contacts linked to this opportunity
            contacts = []
            try:
                contact_r = list(tx.query(f'''match
                    $o isa {otype_full}, has id "{opp_id}";
                    (note: $n, subject: $o) isa alh-aboutness;
                    $n isa jhunt-interaction-note, has content $c;
                fetch {{ "content": $c }};''').resolve())
                # Also try direct interaction links
            except:
                pass

    result = {
        "success": True,
        "opportunity": opp_meta,
        "notes": notes,
        "note_count": sum(len(v) for v in notes.values()),
    }
    print(json.dumps(result, default=str))


def cmd_add_resource(args):
    """Add a learning resource."""
    resource_id = args.id or generate_id("resource")
    timestamp = get_timestamp()

    query = f'''insert $r isa jhunt-learning-resource,
        has id "{resource_id}",
        has name "{escape_string(args.name)}",
        has jhunt-resource-type "{args.type}",
        has jhunt-completion-status "not-started",
        has created-at {timestamp}'''

    if args.url:
        query += f', has jhunt-resource-url "{escape_string(args.url)}"'
    if args.hours:
        query += f", has jhunt-estimated-hours {args.hours}"
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Tag with skills
        if args.skills:
            for skill in args.skills:
                tag_id = generate_id("tag")
                tag_name = f"skill:{skill}"

                with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                    tag_check = f'match $t isa alh-tag, has name "{tag_name}"; fetch {{ "id": $t.id }};'
                    existing_tag = list(tx.query(tag_check).resolve())

                if not existing_tag:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(
                            f'insert $t isa alh-tag, has id "{tag_id}", has name "{tag_name}";'
                        ).resolve()
                        tx.commit()

                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $r isa jhunt-learning-resource, has id "{resource_id}";
                        $t isa alh-tag, has name "{tag_name}";
                    insert (tagged-entity: $r, tag: $t) isa alh-tagging;''').resolve()
                    tx.commit()

    print(
        json.dumps(
            {"success": True, "resource_id": resource_id, "name": args.name, "type": args.type}
        )
    )


def cmd_link_resource(args):
    """Link a learning resource to a skill requirement."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            link_query = f'''match
                $r isa jhunt-learning-resource, has id "{args.resource}";
                $req isa jhunt-requirement, has id "{args.requirement}";
            insert (resource: $r, requirement: $req) isa jhunt-addresses-requirement;'''
            tx.query(link_query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "resource": args.resource, "requirement": args.requirement}))


def cmd_link_collection(args):
    """Link a paper collection to skill requirement(s).

    Bridges scilit collections to jobhunt skill gaps via jhunt-addresses-requirement.
    Use --requirement for a specific requirement, or --skill to link to all
    matching requirements across positions.
    """
    with get_driver() as driver:
        if args.requirement:
            # Link to specific requirement
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                link_query = f'''match
                    $c isa alh-collection, has id "{args.collection}";
                    $req isa jhunt-requirement, has id "{args.requirement}";
                insert (resource: $c, requirement: $req) isa jhunt-addresses-requirement;'''
                tx.query(link_query).resolve()
                tx.commit()
            print(json.dumps({
                "success": True,
                "collection": args.collection,
                "requirement": args.requirement,
            }))

        elif args.skill:
            # Link to all requirements matching skill name
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                find_query = f'''match
                    $req isa jhunt-requirement, has jhunt-skill-name "{escape_string(args.skill)}";
                fetch {{ "id": $req.id }};'''
                reqs = list(tx.query(find_query).resolve())

            if not reqs:
                print(json.dumps({
                    "success": False,
                    "error": f"No requirements found with jhunt-skill-name '{args.skill}'",
                }))
                return

            linked = []
            for r in reqs:
                req_id = r.get("id", "")
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    link_query = f'''match
                        $c isa alh-collection, has id "{args.collection}";
                        $req isa jhunt-requirement, has id "{req_id}";
                    insert (resource: $c, requirement: $req) isa jhunt-addresses-requirement;'''
                    tx.query(link_query).resolve()
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


def cmd_link_background(args):
    """Link a paper collection to a job opportunity as background reading."""
    collection_id = args.collection
    opportunity_id = args.opportunity
    description = getattr(args, "description", "") or ""

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            cols = list(tx.query(f'''
                match $c isa alh-collection, has id "{collection_id}";
                fetch {{ "id": $c.id, "name": $c.name }};
            ''').resolve())
            if not cols:
                print(json.dumps({"success": False, "error": f"Collection '{collection_id}' not found"}))
                return

            opps = list(tx.query(f'''
                match $o isa jhunt-opportunity, has id "{opportunity_id}";
                fetch {{ "id": $o.id, "name": $o.name }};
            ''').resolve())
            if not opps:
                print(json.dumps({"success": False, "error": f"Opportunity '{opportunity_id}' not found"}))
                return

        ts = get_timestamp()
        desc_clause = f', has description "{escape_string(description)}"' if description else ""
        prov_clause = ', has provenance "link-background"'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
                match $o isa jhunt-opportunity, has id "{opportunity_id}";
                      $c isa alh-collection, has id "{collection_id}";
                insert (opportunity: $o, reading-material: $c) isa jhunt-background-reading,
                    has created-at {ts}{desc_clause}{prov_clause};
            ''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "opportunity_id": opportunity_id,
        "collection_id": collection_id,
        "description": description,
        "message": f"Linked collection '{cols[0]['name']}' to opportunity '{opps[0]['name']}' as background reading",
    }))


def cmd_list_background(args):
    """List paper collections linked to a job opportunity as background reading."""
    opportunity_id = args.opportunity

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $o isa jhunt-opportunity, has id "{opportunity_id}";
                      $c isa alh-collection;
                      (opportunity: $o, reading-material: $c) isa jhunt-background-reading;
                fetch {{
                    "collection-id": $c.id,
                    "collection-name": $c.name
                }};
            ''').resolve())

    print(json.dumps({
        "success": True,
        "opportunity_id": opportunity_id,
        "collections": results,
        "count": len(results),
    }))


def cmd_link_paper(args):
    """Link a learning resource to a paper via alh-citation-reference.

    Creates a alh-citation-reference relation where the learning resource
    cites the paper. Both types inherit from alh-domain-thing so they
    can already play citing-item/cited-item roles.
    """
    timestamp = get_timestamp()
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            link_query = f'''match
                $res isa jhunt-learning-resource, has id "{args.resource}";
                $paper isa scilit-paper, has id "{args.paper}";
            insert (citing-item: $res, cited-item: $paper) isa alh-citation-reference,
                has created-at {timestamp};'''
            tx.query(link_query).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "resource": args.resource,
        "paper": args.paper,
    }))


def cmd_delete_position(args):
    """Delete a position and all its related data."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(f'''match $p isa jhunt-position, has id "{args.id}";
            fetch {{ "name": $p.name }};''').resolve())
        if not check:
            print(json.dumps({"success": False, "error": "Position not found"}))
            return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Delete the position entity (TypeDB cascades owned attributes)
            tx.query(f'''match $p isa jhunt-position, has id "{args.id}";
            delete $p;''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "deleted": args.id}))


# =============================================================================
# OPPORTUNITY MODEL COMMANDS
# =============================================================================


def _link_opportunity_to_company(driver, opportunity_id, company_id):
    """Link an opportunity to a company via jhunt-opportunity-at-organization."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        rel_query = f'''match
            $o isa jhunt-opportunity, has id "{opportunity_id}";
            $c isa jhunt-company, has id "{company_id}";
        insert (opportunity: $o, organization: $c) isa jhunt-opportunity-at-organization;'''
        tx.query(rel_query).resolve()
        tx.commit()


def _link_opportunity_to_seeker(driver, opportunity_id):
    """Link an opportunity to the active job-seeker role via jhunt-seeker-pipeline."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'''match
            $role isa jhunt-job-seeker-role, has alh-role-status "active";
            $opp isa jhunt-opportunity, has id "{escape_string(opportunity_id)}";
        insert (seeker: $role, opportunity: $opp) isa jhunt-seeker-pipeline;''').resolve()
        tx.commit()


def cmd_add_engagement(args):
    """Add a consulting/service engagement opportunity."""
    engagement_id = args.id or generate_id("engagement")
    timestamp = get_timestamp()

    query = f'''insert $e isa jhunt-engagement,
        has id "{engagement_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.type:
        query += f', has jhunt-engagement-type "{args.type}"'
    if args.rate:
        query += f', has jhunt-rate-info "{escape_string(args.rate)}"'
    if args.status:
        query += f', has jhunt-opportunity-status "{args.status}"'
    if args.priority:
        query += f', has jhunt-priority-level "{args.priority}"'
    if args.deadline:
        query += f', has jhunt-deadline {parse_date(args.deadline)}'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if args.company_id:
            _link_opportunity_to_company(driver, engagement_id, args.company_id)

        try:
            _link_opportunity_to_seeker(driver, engagement_id)
        except Exception:
            pass

    print(json.dumps({"success": True, "engagement_id": engagement_id, "name": args.name}))


def cmd_add_venture(args):
    """Add a startup/advisory/equity venture opportunity."""
    venture_id = args.id or generate_id("venture")
    timestamp = get_timestamp()

    query = f'''insert $v isa jhunt-venture,
        has id "{venture_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.stage:
        query += f', has jhunt-venture-stage "{args.stage}"'
    if args.equity_type:
        query += f', has jhunt-equity-type "{args.equity_type}"'
    if args.status:
        query += f', has jhunt-opportunity-status "{args.status}"'
    if args.priority:
        query += f', has jhunt-priority-level "{args.priority}"'
    if args.deadline:
        query += f', has jhunt-deadline {parse_date(args.deadline)}'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if args.company_id:
            _link_opportunity_to_company(driver, venture_id, args.company_id)

        try:
            _link_opportunity_to_seeker(driver, venture_id)
        except Exception:
            pass

    print(json.dumps({"success": True, "venture_id": venture_id, "name": args.name}))


def cmd_add_lead(args):
    """Add an early-stage networking lead."""
    lead_id = args.id or generate_id("lead")
    timestamp = get_timestamp()

    query = f'''insert $l isa jhunt-lead,
        has id "{lead_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.status:
        query += f', has jhunt-opportunity-status "{args.status}"'
    if args.priority:
        query += f', has jhunt-priority-level "{args.priority}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        try:
            _link_opportunity_to_seeker(driver, lead_id)
        except Exception:
            pass

    print(json.dumps({"success": True, "lead_id": lead_id, "name": args.name}))


def cmd_update_opportunity(args):
    """Update status, stage, or priority of any opportunity."""
    updates = []
    if args.status:
        updates.append(("jhunt-opportunity-status", args.status))
    if args.stage:
        updates.append(("jhunt-venture-stage", args.stage))
    if args.priority:
        updates.append(("jhunt-priority-level", args.priority))

    if not updates:
        print(json.dumps({"success": False, "error": "No updates specified"}))
        return

    with get_driver() as driver:
        for attr, value in updates:
            # Check if attribute already exists
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                check = list(tx.query(f'''match
                    $o isa jhunt-opportunity, has id "{args.id}", has {attr} $v;
                fetch {{ "v": $v.{attr} }};''').resolve())

            if check:
                # Delete old value then insert new
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $o isa jhunt-opportunity, has id "{args.id}", has {attr} $v;
                    delete has $v of $o;''').resolve()
                    tx.commit()

            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $o isa jhunt-opportunity, has id "{args.id}";
                insert $o has {attr} "{value}";''').resolve()
                tx.commit()

    print(json.dumps({"success": True, "id": args.id, "updates": dict(updates)}))


def cmd_show_opportunity(args):
    """Show details for any opportunity subtype."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Try each subtype in order
            opp = None
            opp_type = None
            for otype in ["jhunt-position", "jhunt-engagement", "jhunt-venture", "jhunt-lead"]:
                q = f'''match $o isa {otype}, has id "{args.id}";
                fetch {{
                    "id": $o.id,
                    "name": $o.name,
                    "description": $o.description,
                    "jhunt-opportunity-status": $o.jhunt-opportunity-status,
                    "jhunt-priority-level": $o.jhunt-priority-level,
                    "deadline": $o.jhunt-deadline
                }};'''
                results = list(tx.query(q).resolve())
                if results:
                    opp = results[0]
                    opp_type = otype
                    break

            if not opp:
                print(json.dumps({"success": False, "error": "Opportunity not found"}))
                return

            # Type-specific attributes
            if opp_type == "jhunt-position":
                extra_q = f'''match $o isa jhunt-position, has id "{args.id}";
                fetch {{
                    "jhunt-job-url": $o.jhunt-job-url,
                    "jhunt-short-name": $o.jhunt-short-name,
                    "jhunt-salary-range": $o.jhunt-salary-range,
                    "location": $o.alh-location,
                    "jhunt-remote-policy": $o.jhunt-remote-policy
                }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            elif opp_type == "jhunt-engagement":
                extra_q = f'''match $o isa jhunt-engagement, has id "{args.id}";
                fetch {{
                    "jhunt-short-name": $o.jhunt-short-name,
                    "jhunt-engagement-type": $o.jhunt-engagement-type,
                    "jhunt-rate-info": $o.jhunt-rate-info
                }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            elif opp_type == "jhunt-venture":
                extra_q = f'''match $o isa jhunt-venture, has id "{args.id}";
                fetch {{
                    "jhunt-short-name": $o.jhunt-short-name,
                    "jhunt-venture-stage": $o.jhunt-venture-stage,
                    "jhunt-equity-type": $o.jhunt-equity-type
                }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            elif opp_type == "jhunt-lead":
                extra_q = f'''match $o isa jhunt-lead, has id "{args.id}";
                fetch {{ "jhunt-short-name": $o.jhunt-short-name }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            # Get linked company via jhunt-opportunity-at-organization
            company_results = []
            # Try opportunity-at-organization first
            try:
                company_q = f'''match
                    $o isa jhunt-opportunity, has id "{args.id}";
                    (opportunity: $o, organization: $c) isa jhunt-opportunity-at-organization;
                fetch {{ "id": $c.id, "name": $c.name }};'''
                company_results = list(tx.query(company_q).resolve())
            except Exception:
                pass
            # Fall back to position-at-company
            if not company_results:
                try:
                    company_q = f'''match
                        $p isa jhunt-position, has id "{args.id}";
                        (position: $p, employer: $c) isa jhunt-position-at-company;
                    fetch {{ "id": $c.id, "name": $c.name }};'''
                    company_results = list(tx.query(company_q).resolve())
                except Exception:
                    pass

            # Get notes
            notes_q = f'''match
                $o isa jhunt-opportunity, has id "{args.id}";
                (note: $n, subject: $o) isa alh-aboutness;
            fetch {{ "id": $n.id, "name": $n.name, "content": $n.content }};'''
            notes_results = list(tx.query(notes_q).resolve())

            # Get background reading collections
            bg_cols = list(tx.query(f'''
                match $o isa jhunt-opportunity, has id "{args.id}";
                      $c isa alh-collection;
                      (opportunity: $o, reading-material: $c) isa jhunt-background-reading;
                fetch {{ "collection-id": $c.id, "collection-name": $c.name }};
            ''').resolve())

            # Fetch descriptions — anon relation + has avoids $var naming issues
            bg_descs = {r["collection-id"]: r["description"]
                        for r in tx.query(f'''
                match $o isa jhunt-opportunity, has id "{args.id}";
                      $c isa alh-collection, has id $cid;
                      (opportunity: $o, reading-material: $c) isa jhunt-background-reading,
                          has description $desc;
                fetch {{ "collection-id": $cid, "description": $desc }};
            ''').resolve()}

            background_reading = []
            for col in bg_cols:
                cid = col["collection-id"]
                item = {"collection-id": cid, "collection-name": col["collection-name"]}
                if cid in bg_descs:
                    item["description"] = bg_descs[cid]
                background_reading.append(item)

    print(json.dumps({
        "success": True,
        "type": opp_type,
        "opportunity": opp,
        "company": company_results[0] if company_results else None,
        "notes": notes_results,
        "background_reading": background_reading,
    }, indent=2, default=str))


def cmd_list_opportunities(args):
    """List opportunities, optionally filtered by type and status."""
    opp_type = args.type or "all"

    type_map = {
        "position": ["jhunt-position"],
        "engagement": ["jhunt-engagement"],
        "venture": ["jhunt-venture"],
        "lead": ["jhunt-lead"],
        "all": ["jhunt-position", "jhunt-engagement", "jhunt-venture", "jhunt-lead"],
    }
    types_to_query = type_map.get(opp_type, ["jhunt-position"])

    results = []
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for otype in types_to_query:
                match_clause = f"match $o isa {otype};"
                if hasattr(args, 'person') and args.person:
                    match_clause += f'''
                    (seeker: $seeker, opportunity: $o) isa jhunt-seeker-pipeline;
                    (bearer: $person, borne-role: $seeker) isa alh-role-bearing;
                    $person has id "{escape_string(args.person)}";'''
                if args.status:
                    match_clause += f'\n$o has jhunt-opportunity-status "{args.status}";'
                if args.priority:
                    match_clause += f'\n$o has jhunt-priority-level "{args.priority}";'

                q = match_clause + """
                fetch {
                    "id": $o.id,
                    "name": $o.name,
                    "jhunt-short-name": $o.jhunt-short-name,
                    "jhunt-opportunity-status": $o.jhunt-opportunity-status,
                    "jhunt-priority-level": $o.jhunt-priority-level
                };"""
                rows = list(tx.query(q).resolve())
                for r in rows:
                    r["_type"] = otype
                results.extend(rows)

            # Get company links for all
            for r in results:
                oid = r.get("id", "")
                if not oid:
                    continue
                company_q = f'''match
                    $o isa jhunt-opportunity, has id "{oid}";
                    (opportunity: $o, organization: $c) isa jhunt-opportunity-at-organization;
                fetch {{ "name": $c.name }};'''
                try:
                    company_results = list(tx.query(company_q).resolve())
                    r["company"] = company_results[0].get("name", "") if company_results else ""
                except Exception:
                    r["company"] = ""

    opportunities = []
    for r in results:
        opportunities.append({
            "id": r.get("id", ""),
            "type": r.get("_type", "").replace("jhunt-", ""),
            "name": r.get("name", ""),
            "short_name": r.get("jhunt-short-name", ""),
            "status": r.get("jhunt-opportunity-status", ""),
            "priority": r.get("jhunt-priority-level", ""),
            "company": r.get("company", ""),
        })

    print(json.dumps({
        "success": True,
        "opportunities": opportunities,
        "count": len(opportunities),
    }, indent=2))


def cmd_list_pipeline(args):
    """List positions in the pipeline."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Build query - fetch positions with their application status
            match_clause = """match
                    $p isa jhunt-position;
                    (note: $n, subject: $p) isa alh-aboutness;
                    $n isa jhunt-application-note, has jhunt-application-status $status;"""

            if hasattr(args, 'person') and args.person:
                match_clause += f'''
                    (seeker: $seeker, opportunity: $p) isa jhunt-seeker-pipeline;
                    (bearer: $person, borne-role: $seeker) isa alh-role-bearing;
                    $person has id "{escape_string(args.person)}";'''

            if args.status:
                match_clause = match_clause.replace(
                    "has jhunt-application-status $status", f'has jhunt-application-status "{args.status}"'
                )

            if args.priority:
                match_clause += f'\n                    $p has jhunt-priority-level "{args.priority}";'

            query = match_clause + """
                fetch {
                    "id": $p.id,
                    "name": $p.name,
                    "jhunt-short-name": $p.jhunt-short-name,
                    "jhunt-job-url": $p.jhunt-job-url,
                    "location": $p.alh-location,
                    "jhunt-remote-policy": $p.jhunt-remote-policy,
                    "jhunt-salary-range": $p.jhunt-salary-range,
                    "jhunt-priority-level": $p.jhunt-priority-level,
                    "status": $n.jhunt-application-status
                };"""

            results = list(tx.query(query).resolve())

            # Separately fetch company info for each position
            for r in results:
                pos_id = r.get("id")
                if pos_id:
                    company_query = f'''match
                        $p isa jhunt-position, has id "{pos_id}";
                        (position: $p, employer: $c) isa jhunt-position-at-company;
                    fetch {{ "name": $c.name }};'''
                    try:
                        company_results = list(tx.query(company_query).resolve())
                        if company_results:
                            r["company_name"] = company_results[0].get("name", "")
                    except Exception:
                        r["company_name"] = ""

            # If filtering by tag, we need a separate query
            if args.tag:
                tag_query = f'''match
                    $p isa jhunt-position;
                    $t isa alh-tag, has name "{args.tag}";
                    (tagged-entity: $p, tag: $t) isa alh-tagging;
                fetch {{ "id": $p.id }};'''
                tagged = list(tx.query(tag_query).resolve())
                tagged_ids = {r.get("id") for r in tagged}
                results = [r for r in results if r.get("id") in tagged_ids]

    # Format output
    positions = []
    for r in results:
        pos = {
            "id": r.get("id"),
            "title": r.get("name"),
            "short_name": r.get("jhunt-short-name"),
            "url": r.get("jhunt-job-url"),
            "location": r.get("location"),
            "remote_policy": r.get("jhunt-remote-policy"),
            "salary": r.get("jhunt-salary-range"),
            "priority": r.get("jhunt-priority-level"),
            "status": r.get("status"),
            "company": r.get("company_name", ""),
        }
        positions.append(pos)

    print(json.dumps({"success": True, "positions": positions, "count": len(positions)}, indent=2))
def cmd_show_position(args):
    """Get full details for a position."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get position details
            pos_query = f'''match
                $p isa jhunt-position, has id "{args.id}";
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "jhunt-job-url": $p.jhunt-job-url,
                "location": $p.alh-location,
                "jhunt-remote-policy": $p.jhunt-remote-policy,
                "jhunt-salary-range": $p.jhunt-salary-range,
                "jhunt-team-size": $p.jhunt-team-size,
                "jhunt-priority-level": $p.jhunt-priority-level,
                "deadline": $p.jhunt-deadline
            }};'''
            pos_result = list(tx.query(pos_query).resolve())

            if not pos_result:
                print(json.dumps({"success": False, "error": "Position not found"}))
                return

            # Get company
            company_query = f'''match
                $p isa jhunt-position, has id "{args.id}";
                (position: $p, employer: $c) isa jhunt-position-at-company;
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "alh-company-url": $c.alh-company-url,
                "location": $c.alh-location
            }};'''
            company_result = list(tx.query(company_query).resolve())

            # Query each note subtype separately so we can return type
            # labels and type-specific attributes for the dashboard
            NOTE_TYPE_ATTRS = {
                "jhunt-application-note": ["id", "name", "content", "jhunt-application-status", "jhunt-applied-date", "jhunt-response-date"],
                "jhunt-fit-analysis-note": ["id", "name", "content", "jhunt-fit-score", "jhunt-fit-summary"],
                "jhunt-interview-note": ["id", "name", "content", "jhunt-interview-date"],
                "jhunt-interaction-note": ["id", "name", "content", "alh-interaction-type", "alh-interaction-date"],
                "jhunt-research-note": ["id", "name", "content"],
                "jhunt-strategy-note": ["id", "name", "content"],
                "jhunt-skill-gap-note": ["id", "name", "content"],
            }
            notes_result = []
            for ntype, attr_list in NOTE_TYPE_ATTRS.items():
                attr_fetch = ", ".join(f'"{a}": $n.{a}' for a in attr_list)
                q = f'''match
                    $p isa jhunt-position, has id "{args.id}";
                    (note: $n, subject: $p) isa alh-aboutness;
                    $n isa {ntype};
                fetch {{ {attr_fetch} }};'''
                for r in tx.query(q).resolve():
                    r["type"] = ntype
                    notes_result.append(r)

            # Get requirements
            req_query = f'''match
                $p isa jhunt-position, has id "{args.id}";
                (requirement: $r, position: $p) isa jhunt-requirement-for;
            fetch {{
                "id": $r.id,
                "jhunt-skill-name": $r.jhunt-skill-name,
                "jhunt-skill-level": $r.jhunt-skill-level,
                "jhunt-your-level": $r.jhunt-your-level,
                "content": $r.content
            }};'''
            req_result = list(tx.query(req_query).resolve())

            # Get job description artifact
            artifact_query = f'''match
                $p isa jhunt-position, has id "{args.id}";
                (alh-artifact: $a, referent: $p) isa alh-representation;
                $a isa jhunt-job-description;
            fetch {{ "id": $a.id, "content": $a.content }};'''
            artifact_result = list(tx.query(artifact_query).resolve())

            # Get tags
            tags_query = f'''match
                $p isa jhunt-position, has id "{args.id}";
                (tagged-entity: $p, tag: $t) isa alh-tagging;
            fetch {{ "name": $t.name }};'''
            tags_result = list(tx.query(tags_query).resolve())

            # Get background reading collections
            bg_cols = list(tx.query(f'''
                match $p isa jhunt-position, has id "{args.id}";
                      $c isa alh-collection;
                      (opportunity: $p, reading-material: $c) isa jhunt-background-reading;
                fetch {{ "collection-id": $c.id, "collection-name": $c.name }};
            ''').resolve())

            # Fetch descriptions — anon relation + has avoids $var naming issues
            bg_descs = {r["collection-id"]: r["description"]
                        for r in tx.query(f'''
                match $p isa jhunt-position, has id "{args.id}";
                      $c isa alh-collection, has id $cid;
                      (opportunity: $p, reading-material: $c) isa jhunt-background-reading,
                          has description $desc;
                fetch {{ "collection-id": $cid, "description": $desc }};
            ''').resolve()}

            background_reading = []
            for col in bg_cols:
                cid = col["collection-id"]
                item = {"collection-id": cid, "collection-name": col["collection-name"]}
                if cid in bg_descs:
                    item["description"] = bg_descs[cid]
                background_reading.append(item)

    output = {
        "success": True,
        "position": pos_result[0] if pos_result else None,
        "company": company_result[0] if company_result else None,
        "notes": notes_result,
        "requirements": req_result,
        "job_description": artifact_result[0] if artifact_result else None,
        "tags": [t.get("name") for t in tags_result],
        "background_reading": background_reading,
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_company(args):
    """Get company details and positions."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get company
            company_query = f'''match
                $c isa jhunt-company, has id "{args.id}";
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "alh-company-url": $c.alh-company-url,
                "alh-linkedin-url": $c.alh-linkedin-url,
                "description": $c.description,
                "location": $c.alh-location
            }};'''
            company_result = list(tx.query(company_query).resolve())

            if not company_result:
                print(json.dumps({"success": False, "error": "Company not found"}))
                return

            # Get positions at company
            pos_query = f'''match
                $c isa jhunt-company, has id "{args.id}";
                (position: $p, employer: $c) isa jhunt-position-at-company;
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "jhunt-job-url": $p.jhunt-job-url,
                "jhunt-priority-level": $p.jhunt-priority-level
            }};'''
            pos_result = list(tx.query(pos_query).resolve())

            # Get notes about company
            notes_query = f'''match
                $c isa jhunt-company, has id "{args.id}";
                (note: $n, subject: $c) isa alh-aboutness;
            fetch {{
                "id": $n.id,
                "name": $n.name,
                "content": $n.content
            }};'''
            notes_result = list(tx.query(notes_query).resolve())

    output = {
        "success": True,
        "company": company_result[0] if company_result else None,
        "positions": pos_result,
        "notes": notes_result,
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_gaps(args):
    """Compute candidate-to-market fit: seeker skills vs position requirements."""
    level_value = {"none": 0, "aware": 1, "learning": 1, "practiced": 2, "some": 2, "expert": 3, "strong": 3}
    req_threshold = {"required": 2, "preferred": 1, "nice-to-have": 0}
    req_weight = {"required": 2.0, "preferred": 1.0, "nice-to-have": 0.5}

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # 1. Get all seeker skills
            skills_query = """match $s isa jhunt-your-skill, has jhunt-skill-name $sn, has jhunt-skill-level $sl;
                fetch { "name": $sn, "level": $sl };"""
            skill_results = list(tx.query(skills_query).resolve())

            # 2. Get all requirements (optionally filter by status)
            # Default: show all positions that progressed past "researching"
            # --all: include researching too
            include_all = hasattr(args, 'all') and args.all
            status_filter = '' if include_all else '''
                not { $status == "researching"; };'''
            req_query = f"""match
                $r isa jhunt-requirement, has jhunt-skill-name $sn, has jhunt-skill-level $sl;
                (requirement: $r, position: $p) isa jhunt-requirement-for;
                (note: $n, subject: $p) isa alh-aboutness;
                $n isa jhunt-application-note, has jhunt-application-status $status;{status_filter}
            fetch {{
                "skill": $sn, "level": $sl,
                "pos-id": $p.id, "pos-name": $p.name
            }};"""
            req_results = list(tx.query(req_query).resolve())

            # 3. Get alt-labels for concept matching
            alt_query = """match $c isa jhunt-skill-concept, has name $cn, has jhunt-alt-label $alt;
                fetch { "name": $cn, "alt": $alt };"""
            try:
                alt_results = list(tx.query(alt_query).resolve())
            except Exception:
                alt_results = []

    # Build skill lookup (lowercase name -> level)
    my_skills = {}
    for s in skill_results:
        my_skills[s["name"].lower()] = s["level"]

    # Build alt-label -> canonical name lookup
    alt_to_canonical = {}
    for a in alt_results:
        canonical = a["name"].lower()
        alt = a["alt"].lower()
        alt_to_canonical[alt] = canonical

    def lookup_my_level(skill_name):
        """Find seeker's level for a skill, checking alt-labels."""
        key = skill_name.lower()
        # Direct match
        if key in my_skills:
            return my_skills[key]
        # Alt-label match: look up canonical name, then check skills
        canonical = alt_to_canonical.get(key)
        if canonical and canonical in my_skills:
            return my_skills[canonical]
        # Check if skill_name IS a canonical name for which we have alt matches
        for alt, canon in alt_to_canonical.items():
            if canon == key and alt in my_skills:
                return my_skills[alt]
        return "none"

    # Group requirements by position
    positions = {}
    for r in req_results:
        pid = r["pos-id"]
        if pid not in positions:
            positions[pid] = {"id": pid, "name": r["pos-name"], "requirements": []}
        positions[pid]["requirements"].append({
            "skill": r["skill"],
            "level": r["level"],
        })

    # Compute per-position fit scores
    position_fits = []
    all_gaps = {}  # skill -> {gap_impact, positions}

    for pid, pos in positions.items():
        total_weight = 0
        total_coverage = 0
        reqs_detail = []

        for req in pos["requirements"]:
            my_level = lookup_my_level(req["skill"])
            my_val = level_value.get(my_level, 0)
            threshold = req_threshold.get(req["level"], 1)
            weight = req_weight.get(req["level"], 1.0)

            coverage = min(1.0, my_val / max(threshold, 1))
            total_weight += weight
            total_coverage += coverage * weight

            reqs_detail.append({
                "skill": req["skill"],
                "required_level": req["level"],
                "my_level": my_level,
                "coverage": round(coverage, 2),
            })

            # Track gaps for learning priority
            if coverage < 1.0:
                gap_size = max(threshold - my_val, 0)
                skill_key = req["skill"]
                if skill_key not in all_gaps:
                    all_gaps[skill_key] = {"skill": skill_key, "current_level": my_level, "gap_impact": 0, "positions": []}
                all_gaps[skill_key]["gap_impact"] += gap_size * weight
                all_gaps[skill_key]["positions"].append(pos["name"][:40])

        fit_score = round(total_coverage / max(total_weight, 1), 2)
        covered = len([r for r in reqs_detail if r["coverage"] >= 1.0])
        gaps_count = len([r for r in reqs_detail if r["coverage"] < 1.0])

        position_fits.append({
            "id": pid,
            "name": pos["name"],
            "fit_score": fit_score,
            "total_requirements": len(reqs_detail),
            "covered": covered,
            "gaps": gaps_count,
            "requirements": reqs_detail,
        })

    # Sort positions by number of gaps (fewest gaps first)
    position_fits.sort(key=lambda x: (x["gaps"], -x["covered"]))

    # Learning priorities sorted by gap impact
    learning_priorities = sorted(all_gaps.values(), key=lambda x: x["gap_impact"], reverse=True)
    for lp in learning_priorities:
        lp["needed_for"] = len(lp["positions"])
        lp["gap_impact"] = round(lp["gap_impact"], 1)

    # Also include legacy skill_gaps format for backward compatibility
    legacy_gaps = []
    for lp in learning_priorities:
        legacy_gaps.append({
            "skill": lp["skill"],
            "level": "required",
            "your_level": lp["current_level"],
            "positions": [{"id": "", "title": p} for p in lp["positions"]],
        })

    print(json.dumps({
        "success": True,
        "seeker_skills": len(my_skills),
        "positions_analyzed": len(position_fits),
        "positions": position_fits,
        "learning_priorities": learning_priorities,
        "skill_gaps": legacy_gaps,
    }, indent=2, default=str))


def cmd_learning_plan(args):
    """Generate a prioritized learning plan based on skill gaps."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all learning resources
            query = """match
                $res isa jhunt-learning-resource;
            fetch {
                "id": $res.id,
                "name": $res.name,
                "jhunt-resource-type": $res.jhunt-resource-type,
                "jhunt-resource-url": $res.jhunt-resource-url,
                "jhunt-estimated-hours": $res.jhunt-estimated-hours,
                "jhunt-completion-status": $res.jhunt-completion-status
            };"""
            results = list(tx.query(query).resolve())

            # Get collections linked to skill requirements
            coll_query = """match
                $c isa alh-collection;
                (resource: $c, requirement: $req) isa jhunt-addresses-requirement;
            fetch {
                "id": $c.id,
                "name": $c.name,
                "description": $c.description,
                "jhunt-skill-name": $req.jhunt-skill-name
            };"""
            coll_results = list(tx.query(coll_query).resolve())

            # Get papers referenced by learning resources via alh-citation-reference
            paper_query = """match
                $res isa jhunt-learning-resource;
                (citing-item: $res, cited-item: $paper) isa alh-citation-reference;
            fetch {
                "res-id": $res.id,
                "res-name": $res.name,
                "paper-id": $paper.id,
                "paper-name": $paper.name
            };"""
            paper_results = list(tx.query(paper_query).resolve())

    # Format resources
    resources = []
    for r in results:
        res = {
            "id": r.get("id", ""),
            "name": r.get("name", ""),
            "type": r.get("jhunt-resource-type", ""),
            "url": r.get("jhunt-resource-url", ""),
            "hours": r.get("jhunt-estimated-hours", ""),
            "status": r.get("jhunt-completion-status", ""),
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
        coll_id = cr.get("id", "")
        skill = cr.get("jhunt-skill-name", "")
        key = f"{coll_id}:{skill}"
        if key not in seen_colls:
            seen_colls.add(key)
            collections.append({
                "id": coll_id,
                "name": cr.get("name", ""),
                "description": cr.get("description", ""),
                "skill_name": skill,
            })

    # Format referenced papers
    referenced_papers = []
    for pr in paper_results:
        referenced_papers.append({
            "resource_id": pr.get("res-id", ""),
            "resource_name": pr.get("res-name", ""),
            "paper_id": pr.get("paper-id", ""),
            "paper_name": pr.get("paper-name", ""),
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
    tag_id = generate_id("tag")
    with get_driver() as driver:
        # Create tag if not exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            tag_check = f'match $t isa alh-tag, has name "{args.tag}"; fetch {{ "id": $t.id }};'
            existing_tag = list(tx.query(tag_check).resolve())

        if not existing_tag:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'insert $t isa alh-tag, has id "{tag_id}", has name "{args.tag}";').resolve()
                tx.commit()

        # Create tagging relation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $e isa alh-identifiable-entity, has id "{args.entity}";
                $t isa alh-tag, has name "{args.tag}";
            insert (tagged-entity: $e, tag: $t) isa alh-tagging;''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "entity": args.entity, "tag": args.tag}))


def cmd_search_tag(args):
    """Search entities by tag."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = f'''match
                $t isa alh-tag, has name "{args.tag}";
                (tagged-entity: $e, tag: $t) isa alh-tagging;
            fetch {{
                "id": $e.id,
                "name": $e.name
            }};'''
            results = list(tx.query(query).resolve())

    print(
        json.dumps(
            {
                "success": True,
                "tag": args.tag,
                "entities": results,
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

    query = f'''insert $r isa jhunt-requirement,
        has id "{req_id}",
        has jhunt-skill-name "{escape_string(args.skill)}",
        has created-at {timestamp}'''

    if args.level:
        query += f', has jhunt-skill-level "{args.level}"'
    if args.jhunt_your_level:
        query += f', has jhunt-your-level "{args.jhunt_your_level}"'
    if args.content:
        query += f', has content "{escape_string(args.content)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to position
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            rel_query = f'''match
                $r isa jhunt-requirement, has id "{req_id}";
                $p isa jhunt-position, has id "{args.position}";
            insert (requirement: $r, position: $p) isa jhunt-requirement-for;'''
            tx.query(rel_query).resolve()
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


def cmd_create_seeker_profile(args):
    """Create a job-seeker role for a person (BFO/UFO role pattern)."""
    role_id = args.id or generate_id("jhunt-seeker")
    timestamp = get_timestamp()

    query = f'''insert $role isa jhunt-job-seeker-role,
        has id "{role_id}",
        has name "{escape_string(args.name or 'Job Search')}",
        has created-at {timestamp},
        has alh-role-status "active",
        has alh-role-started-on {timestamp}'''

    if args.target_role:
        query += f', has jhunt-target-role "{escape_string(args.target_role)}"'
    if args.industries:
        query += f', has jhunt-target-industries "{escape_string(args.industries)}"'
    if args.salary:
        query += f', has jhunt-salary-expectations "{escape_string(args.salary)}"'
    if args.location:
        query += f', has jhunt-location-preference "{escape_string(args.location)}"'
    if args.focus:
        query += f', has jhunt-search-focus "{escape_string(args.focus)}"'

    query += ";"

    with get_driver() as driver:
        # Create the role entity
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link role to person via alh-role-bearing
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $person isa alh-person, has id "{escape_string(args.person)}";
                $role isa jhunt-job-seeker-role, has id "{role_id}";
            insert (bearer: $person, borne-role: $role) isa alh-role-bearing;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "role_id": role_id,
        "person_id": args.person,
        "message": f"Job-seeker profile created for {args.person}",
    }))


def cmd_add_skill(args):
    """
    Add or update a skill in your profile.

    Your skill profile is used during sensemaking to compare
    position requirements against your capabilities for gap analysis.
    """
    timestamp = get_timestamp()
    existing = []

    with get_driver() as driver:
        # Check if skill already exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check_query = f'''match
                $s isa jhunt-your-skill, has jhunt-skill-name "{escape_string(args.name)}";
            fetch {{
                "jhunt-skill-name": $s.jhunt-skill-name,
                "jhunt-skill-level": $s.jhunt-skill-level
            }};'''
            existing = list(tx.query(check_query).resolve())

        if existing:
            # Update existing skill - delete and recreate
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $s isa jhunt-your-skill, has jhunt-skill-name "{escape_string(args.name)}";
                delete $s;''').resolve()
                tx.commit()

        # Create skill
        skill_id = generate_id("skill")
        skill_query = f'''insert $s isa jhunt-your-skill,
            has id "{skill_id}",
            has jhunt-skill-name "{escape_string(args.name)}",
            has jhunt-skill-level "{args.level}",
            has jhunt-last-updated {timestamp}'''

        if args.evidence:
            skill_query += f', has jhunt-skill-evidence "{escape_string(args.evidence)}"'
        if args.recency:
            skill_query += f', has jhunt-skill-recency "{escape_string(args.recency)}"'
        if args.description:
            skill_query += f', has description "{escape_string(args.description)}"'

        skill_query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(skill_query).resolve()
            tx.commit()

        # Link skill to active job-seeker role
        try:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $role isa jhunt-job-seeker-role, has alh-role-status "active";
                    $skill isa jhunt-your-skill, has id "{skill_id}";
                insert (seeker: $role, skill: $skill) isa jhunt-seeker-has-skill;''').resolve()
                tx.commit()
        except Exception:
            pass  # seeker role may not exist

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


def cmd_add_concept(args):
    """Add a skill concept to the controlled vocabulary."""
    concept_id = args.id or generate_id("concept")
    timestamp = get_timestamp()

    query = f'''insert $c isa jhunt-skill-concept,
        has id "{concept_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    # Add alt-labels
    alt_labels = []
    if args.alt_labels:
        for label in args.alt_labels.split(","):
            label = label.strip()
            if label:
                query += f', has jhunt-alt-label "{escape_string(label)}"'
                alt_labels.append(label)

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to broader concept if specified
        if args.broader:
            try:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $broader isa jhunt-skill-concept, has name "{escape_string(args.broader)}";
                        $narrower isa jhunt-skill-concept, has id "{concept_id}";
                    insert (broader-skill: $broader, narrower-skill: $narrower) isa jhunt-skill-hierarchy;''').resolve()
                    tx.commit()
            except Exception:
                pass  # broader concept may not exist

    print(json.dumps({
        "success": True,
        "concept_id": concept_id,
        "name": args.name,
        "alt_labels": alt_labels,
        "broader": args.broader,
    }))


def cmd_list_concepts(args):
    """List skill concepts with seeker proficiency levels (prompt-friendly format)."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all concepts
            concept_query = """match $c isa jhunt-skill-concept;
                fetch { "id": $c.id, "name": $c.name, "description": $c.description };"""
            concepts = list(tx.query(concept_query).resolve())

            # Get alt-labels per concept
            alt_query = """match $c isa jhunt-skill-concept, has id $cid, has jhunt-alt-label $alt;
                fetch { "id": $cid, "alt": $alt };"""
            alt_results = list(tx.query(alt_query).resolve())

            # Get seeker skills linked to concepts via skill-definition
            skill_query = """match
                $s isa jhunt-your-skill, has jhunt-skill-name $sn, has jhunt-skill-level $sl;
                (concept: $c, defined-skill: $s) isa jhunt-skill-definition;
                $c has id $cid;
                fetch { "concept_id": $cid, "skill_name": $sn, "level": $sl };"""
            try:
                skill_links = list(tx.query(skill_query).resolve())
            except Exception:
                skill_links = []

            # Get hierarchy
            hier_query = """match
                (broader-skill: $b, narrower-skill: $n) isa jhunt-skill-hierarchy;
                $b has name $bn; $n has id $nid;
                fetch { "narrower_id": $nid, "broader": $bn };"""
            try:
                hier_results = list(tx.query(hier_query).resolve())
            except Exception:
                hier_results = []

    # Build lookup maps
    alt_map = {}
    for a in alt_results:
        cid = a.get("id", "")
        if cid not in alt_map:
            alt_map[cid] = []
        alt_map[cid].append(a.get("alt", ""))

    skill_level_map = {}
    for sl in skill_links:
        skill_level_map[sl.get("concept_id", "")] = sl.get("level", "")

    hier_map = {}
    for h in hier_results:
        hier_map[h.get("narrower_id", "")] = h.get("broader", "")

    # If no skill links exist, fall back to matching by name
    if not skill_links:
        # Get all seeker skills for name-based matching
        all_skills_query = """match $s isa jhunt-your-skill, has jhunt-skill-name $sn, has jhunt-skill-level $sl;
            fetch { "name": $sn, "level": $sl };"""
        with get_driver() as driver:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                all_skills = list(tx.query(all_skills_query).resolve())
        skills_by_name = {s["name"].lower(): s["level"] for s in all_skills}
    else:
        skills_by_name = {}

    # Build output
    concept_list = []
    for c in concepts:
        cid = c.get("id", "")
        name = c.get("name", "")
        level = skill_level_map.get(cid, "")

        # Fallback: match by name if no concept link
        if not level and skills_by_name:
            level = skills_by_name.get(name.lower(), "")

        alts = alt_map.get(cid, [])
        broader = hier_map.get(cid, "")

        concept_list.append({
            "id": cid,
            "name": name,
            "description": c.get("description", ""),
            "level": level,
            "alt_labels": alts,
            "broader": broader,
        })

    # Sort by level then name
    level_order = {"expert": 0, "strong": 0, "practiced": 1, "some": 1,
                   "aware": 2, "learning": 2, "none": 3, "": 4}
    concept_list.sort(key=lambda x: (level_order.get(x["level"], 5), x["name"]))

    # Build compact prompt-friendly output
    level_icons = {"expert": "★", "strong": "★", "practiced": "●", "some": "●",
                   "aware": "○", "learning": "○", "none": "·", "": "?"}
    lines = []
    current_level = None
    level_labels = {"expert": "EXPERT", "strong": "EXPERT", "practiced": "PRACTICED",
                    "some": "PRACTICED", "aware": "AWARE", "learning": "AWARE",
                    "none": "NONE", "": "NOT IN PROFILE"}

    for c in concept_list:
        lvl = c["level"] or ""
        label = level_labels.get(lvl, "UNKNOWN")
        if label != current_level:
            current_level = label
            lines.append(f"\n{label}:")

        icon = level_icons.get(lvl, "?")
        alt_str = f" [alt: {', '.join(c['alt_labels'])}]" if c["alt_labels"] else ""
        broader_str = f" > {c['broader']}" if c["broader"] else ""
        lines.append(f"  {icon} {c['name']}{alt_str}{broader_str}")

    print(json.dumps({
        "success": True,
        "concepts": concept_list,
        "count": len(concept_list),
        "prompt_view": "\n".join(lines),
    }, indent=2))


def cmd_list_skills(args):
    """List your skill profile."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = """match
                $s isa jhunt-your-skill;
            fetch {
                "jhunt-skill-name": $s.jhunt-skill-name,
                "jhunt-skill-level": $s.jhunt-skill-level,
                "jhunt-skill-evidence": $s.jhunt-skill-evidence,
                "jhunt-skill-recency": $s.jhunt-skill-recency,
                "description": $s.description,
                "jhunt-last-updated": $s.jhunt-last-updated
            };"""
            results = list(tx.query(query).resolve())

    # Format output
    skills = []
    for r in results:
        skill = {
            "name": r.get("jhunt-skill-name", ""),
            "level": r.get("jhunt-skill-level", ""),
            "evidence": r.get("jhunt-skill-evidence", ""),
            "recency": r.get("jhunt-skill-recency", ""),
            "description": r.get("description", ""),
            "last_updated": r.get("jhunt-last-updated", ""),
        }
        skills.append(skill)

    # Sort by level (expert first, then practiced, aware, none)
    level_order = {"expert": 0, "practiced": 1, "aware": 2, "none": 3,
                   "strong": 0, "some": 1, "learning": 2}  # backward compat
    skills.sort(key=lambda x: (level_order.get(x["level"], 4), x["name"]))

    print(
        json.dumps(
            {
                "success": True,
                "skills": skills,
                "count": len(skills),
                "by_level": {
                    "expert": len([s for s in skills if s["level"] in ("expert", "strong")]),
                    "practiced": len([s for s in skills if s["level"] in ("practiced", "some")]),
                    "aware": len([s for s in skills if s["level"] in ("aware", "learning")]),
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
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all job description artifacts
            artifacts_query = """match
                $a isa jhunt-job-description;
            fetch {
                "id": $a.id,
                "name": $a.name,
                "source-uri": $a.source-uri,
                "created-at": $a.created-at
            };"""
            artifacts = list(tx.query(artifacts_query).resolve())

            # For each artifact, check if it has associated notes
            # (via position -> aboutness -> note)
            results = []
            for art in artifacts:
                artifact_id = art.get("id", "")

                # Check for notes on the linked position
                notes_query = f'''match
                    $a isa jhunt-job-description, has id "{artifact_id}";
                    (alh-artifact: $a, referent: $p) isa alh-representation;
                    (note: $n, subject: $p) isa alh-aboutness;
                    not {{ $n isa jhunt-application-note; }};
                fetch {{ "id": $n.id }};'''

                try:
                    notes = list(tx.query(notes_query).resolve())
                    has_notes = len(notes) > 0
                except Exception:
                    has_notes = False
                    notes = []

                status = "analyzed" if has_notes else "raw"

                # Apply filter
                if args.status and args.status != "all":
                    if args.status != status:
                        continue

                results.append(
                    {
                        "id": artifact_id,
                        "name": art.get("name", ""),
                        "source_url": art.get("source-uri", ""),
                        "created_at": art.get("created-at", ""),
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
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get artifact - include cache-path and other cache attributes
            artifact_query = f'''match
                $a isa jhunt-job-description, has id "{args.id}";
            fetch {{
                "id": $a.id,
                "name": $a.name,
                "content": $a.content,
                "cache-path": $a.cache-path,
                "mime-type": $a.mime-type,
                "file-size": $a.file-size,
                "source-uri": $a.source-uri,
                "created-at": $a.created-at
            }};'''
            artifact_result = list(tx.query(artifact_query).resolve())

            if not artifact_result:
                print(json.dumps({"success": False, "error": "Artifact not found"}))
                return

            # Get linked position (specifically jhunt-position)
            position_query = f'''match
                $a isa jhunt-job-description, has id "{args.id}";
                (alh-artifact: $a, referent: $p) isa alh-representation;
                $p isa jhunt-position;
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "jhunt-job-url": $p.jhunt-job-url,
                "location": $p.alh-location,
                "jhunt-remote-policy": $p.jhunt-remote-policy,
                "jhunt-salary-range": $p.jhunt-salary-range,
                "jhunt-priority-level": $p.jhunt-priority-level
            }};'''
            position_result = list(tx.query(position_query).resolve())

            # Get linked company (if any)
            company_result = []
            if position_result:
                pos_id = position_result[0].get("id", "")
                company_query = f'''match
                    $p isa jhunt-position, has id "{pos_id}";
                    (position: $p, employer: $c) isa jhunt-position-at-company;
                fetch {{
                    "id": $c.id,
                    "name": $c.name
                }};'''
                try:
                    company_result = list(tx.query(company_query).resolve())
                except Exception:
                    pass

    art = artifact_result[0]

    # Get content - either from inline content or from cache
    cache_path = art.get("cache-path", "")
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
        content = art.get("content", "")
        storage = "inline"

    output = {
        "success": True,
        "artifact": {
            "id": art.get("id", ""),
            "name": art.get("name", ""),
            "source_url": art.get("source-uri", ""),
            "created_at": art.get("created-at", ""),
            "content": content,
            "storage": storage,
            "cache_path": cache_path,
            "mime_type": art.get("mime-type", ""),
            "file_size": art.get("file-size", ""),
        },
        "position": None,
        "company": None,
    }

    if position_result:
        pos = position_result[0]
        output["position"] = {
            "id": pos.get("id", ""),
            "name": pos.get("name", ""),
            "url": pos.get("jhunt-job-url", ""),
            "location": pos.get("location", ""),
            "remote_policy": pos.get("jhunt-remote-policy", ""),
            "salary": pos.get("jhunt-salary-range", ""),
            "priority": pos.get("jhunt-priority-level", ""),
        }

    if company_result:
        comp = company_result[0]
        output["company"] = {
            "id": comp.get("id", ""),
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
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get positions with status from application notes
            query = """
                match
                $p isa jhunt-position;
                (note: $n, subject: $p) isa alh-aboutness;
                $n isa jhunt-application-note, has jhunt-application-status $status;
                fetch {
                    "id": $p.id,
                    "name": $p.name,
                    "jhunt-short-name": $p.jhunt-short-name,
                    "jhunt-job-url": $p.jhunt-job-url,
                    "jhunt-priority-level": $p.jhunt-priority-level,
                    "status": $n.jhunt-application-status
                };
            """
            results = list(tx.query(query).resolve())

            # Also get positions WITHOUT application notes (still researching)
            all_pos_query = """
                match $p isa jhunt-position;
                fetch {
                    "id": $p.id,
                    "name": $p.name,
                    "jhunt-short-name": $p.jhunt-short-name,
                    "jhunt-job-url": $p.jhunt-job-url,
                    "jhunt-priority-level": $p.jhunt-priority-level
                };
            """
            all_positions = list(tx.query(all_pos_query).resolve())

    # Extract positions with status (3.x returns plain dicts)
    tracked = {}
    for r in results:
        pid = r.get("id", "")
        if not pid:
            continue
        tracked[pid] = {
            "id": pid,
            "name": r.get("name", ""),
            "short_name": r.get("jhunt-short-name", ""),
            "priority": r.get("jhunt-priority-level", ""),
            "url": r.get("jhunt-job-url", ""),
            "status": r.get("status", "researching"),
        }

    # Add untracked positions as "researching"
    for r in all_positions:
        pid = r.get("id", "")
        if not pid or pid in tracked:
            continue
        tracked[pid] = {
            "id": pid,
            "name": r.get("name", ""),
            "short_name": r.get("jhunt-short-name", ""),
            "priority": r.get("jhunt-priority-level", ""),
            "url": r.get("jhunt-job-url", ""),
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
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            pid = args.id

            # Get position attributes
            pos_query = f"""
                match $p isa jhunt-position, has id "{pid}";
                fetch {{
                    "id": $p.id,
                    "name": $p.name,
                    "jhunt-short-name": $p.jhunt-short-name,
                    "jhunt-job-url": $p.jhunt-job-url,
                    "jhunt-salary-range": $p.jhunt-salary-range,
                    "location": $p.alh-location,
                    "jhunt-remote-policy": $p.jhunt-remote-policy,
                    "jhunt-priority-level": $p.jhunt-priority-level
                }};
            """
            pos_results = list(tx.query(pos_query).resolve())
            if not pos_results:
                print(f"Position `{pid}` not found.")
                return

            attrs = pos_results[0]

            # Get notes content
            note_query = f"""
                match
                $p isa jhunt-position, has id "{pid}";
                $note isa alh-note;
                (subject: $p, note: $note) isa alh-aboutness;
                fetch {{ "content": $note.content }};
            """
            try:
                all_notes = list(tx.query(note_query).resolve())
            except Exception:
                all_notes = []

            # Get application status from application note
            status_query = f"""
                match
                $p isa jhunt-position, has id "{pid}";
                $n isa jhunt-application-note;
                (subject: $p, note: $n) isa alh-aboutness;
                fetch {{ "status": $n.jhunt-application-status }};
            """
            try:
                status_results = list(tx.query(status_query).resolve())
                if status_results:
                    attrs["jhunt-application-status"] = status_results[0].get("status")
            except Exception:
                pass

    # Build markdown
    title = attrs.get("jhunt-short-name") or attrs.get("name", pid)
    status = attrs.get("jhunt-application-status", "unknown")
    status_emoji = STATUS_EMOJI.get(status, "•")

    lines = [f"**{title}**", ""]
    lines.append(f"Status: {status_emoji} {status}")
    if attrs.get("jhunt-priority-level"):
        lines.append(f"Priority: {PRIORITY_EMOJI.get(attrs['jhunt-priority-level'], '')} {attrs['jhunt-priority-level']}")
    if attrs.get("jhunt-job-url"):
        lines.append(f"URL: {attrs['jhunt-job-url']}")
    if attrs.get("jhunt-salary-range"):
        lines.append(f"Salary: {attrs['jhunt-salary-range']}")
    if attrs.get("location"):
        lines.append(f"Location: {attrs['location']}")
    if attrs.get("jhunt-remote-policy"):
        lines.append(f"Remote: {attrs['jhunt-remote-policy']}")
    lines.append("")

    if all_notes:
        lines.append(f"**Notes** ({len(all_notes)})")
        lines.append("")
        for n in all_notes:
            note_content = n.get("content", "")
            if note_content:
                # Unescape literal \n sequences
                note_content = note_content.replace("\\n", "\n").replace("\\'", "'")
                # Truncate long notes for messaging
                if len(note_content) > 500:
                    note_content = note_content[:497] + "..."
                lines.append(f"{note_content}")
                lines.append("")
                lines.append("---")
                lines.append("")

    print("\n".join(lines))

def cmd_report_gaps(args):
    """Generate skill gaps report as formatted Markdown."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all requirements with your skill levels
            query = """
                match
                $req isa jhunt-requirement;
                $p isa jhunt-position;
                (position: $p, requirement: $req) isa jhunt-requirement-for;
                fetch {
                    "skill": $req.jhunt-skill-name,
                    "level": $req.jhunt-skill-level,
                    "pos_name": $p.name
                };
            """
            results = list(tx.query(query).resolve())

            # Get your skills
            skill_query = """
                match $s isa jhunt-your-skill;
                fetch { "name": $s.jhunt-skill-name, "level": $s.jhunt-skill-level };
            """
            try:
                skill_results = list(tx.query(skill_query).resolve())
            except Exception:
                skill_results = []

    my_skills = {}
    for s in skill_results:
        my_skills[s.get("name", "")] = s.get("level", "")

    # Group by skill
    gaps = {}
    for r in results:
        skill = r.get("skill", "")
        level = r.get("level", "")
        pos_name = r.get("pos_name", "")
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
    lines = ["**Skill Gaps Analysis**", ""]

    if not gaps:
        lines.append("No significant skill gaps found!")
    else:
        # Sort: required gaps first, then by number of positions
        sorted_gaps = sorted(
            gaps.items(),
            key=lambda x: (0 if x[1]["required_level"] == "required" else 1, -len(x[1]["positions"]))
        )

        LEVEL_EMOJI = {"none": "[ ]", "some": "[~]", "learning": "[o]", "strong": "[x]"}

        for skill, info in sorted_gaps:
            level_e = LEVEL_EMOJI.get(info["your_level"], "[ ]")
            req_marker = "!" if info["required_level"] == "required" else "?"
            count = len(info["positions"])
            lines.append(f"{req_marker} **{skill}** {level_e} ({info['your_level']}) -> needed by {count} position(s)")

    lines.append("")
    lines.append("Legend: ! required ? preferred | [ ] none [o] learning [~] some [x] strong")

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
    p.add_argument("--company", help="Company name (matched to existing or created)")
    p.add_argument("--url", help="Job posting URL")
    p.add_argument("--location", help="Job location")
    p.add_argument("--jhunt-remote-policy", choices=["remote", "hybrid", "onsite"], help="Remote policy")
    p.add_argument("--salary", help="Salary range")
    p.add_argument("--jhunt-team-size", help="Team size")
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

    # set-jhunt-short-name
    p = subparsers.add_parser("set-jhunt-short-name", help="Set short display name for a position")
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
    p.add_argument("--alh-interaction-type", help="Type of interaction (for interaction notes)")
    p.add_argument("--alh-interaction-date", help="Date of interaction")
    p.add_argument("--jhunt-interview-date", help="Date of interview")
    p.add_argument("--jhunt-fit-score", type=float, help="Fit score (for fit-analysis notes)")
    p.add_argument("--jhunt-fit-summary", help="Fit summary")
    p.add_argument("--id", help="Specific ID")

    # upsert-summary
    p = subparsers.add_parser("upsert-summary", help="Create or overwrite the opportunity summary")
    p.add_argument("--about", required=True, help="Opportunity ID")
    p.add_argument("--content", required=True, help="Summary content (markdown). Prefix with @ to read from file")

    # regenerate-summary
    p = subparsers.add_parser("regenerate-summary", help="Fetch all notes for an opportunity (agent synthesizes summary)")
    p.add_argument("--about", required=True, help="Opportunity ID")

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

    # link-background
    p = subparsers.add_parser("link-background", help="Link paper collection to opportunity as background reading")
    p.add_argument("--opportunity", required=True, help="Opportunity ID (position, engagement, venture, lead)")
    p.add_argument("--collection", required=True, help="Collection ID (scilit-corpus, sltrend-thread, etc.)")
    p.add_argument("--description", help="Why this collection is relevant to the opportunity")

    # list-background
    p = subparsers.add_parser("list-background", help="List paper collections linked to an opportunity")
    p.add_argument("--opportunity", required=True, help="Opportunity ID")

    # link-paper
    p = subparsers.add_parser("link-paper", help="Link learning resource to a paper via alh-citation-reference")
    p.add_argument("--resource", required=True, help="Learning resource ID")
    p.add_argument("--paper", required=True, help="Paper ID (scilit-paper)")

    # add-requirement
    p = subparsers.add_parser("add-requirement", help="Add a requirement to a position")
    p.add_argument("--position", required=True, help="Position ID")
    p.add_argument("--skill", required=True, help="Skill name")
    p.add_argument(
        "--level", choices=["required", "preferred", "nice-to-have"], help="Requirement level"
    )
    p.add_argument("--jhunt-your-level", choices=["expert", "practiced", "aware", "none"], help="Your skill level (Bloom's: expert/practiced/aware/none)")
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
        choices=["expert", "practiced", "aware", "none"],
        help="Proficiency level (Bloom's): expert=can design/teach, practiced=hands-on, aware=conceptual, none=unknown",
    )
    p.add_argument("--evidence", help="What proves this level (project URL, publication, years)")
    p.add_argument("--recency", help="When last used (e.g., 'daily 2026', 'used 2019-2022')")
    p.add_argument("--description", help="Free text context about your experience")

    # list-skills
    subparsers.add_parser("list-skills", help="Show your skill profile")

    # add-concept
    p = subparsers.add_parser("add-concept", help="Add a skill concept to the vocabulary")
    p.add_argument("--name", required=True, help="Preferred label (canonical name)")
    p.add_argument("--alt-labels", dest="alt_labels", help="Comma-separated alternative labels")
    p.add_argument("--description", help="What this skill covers")
    p.add_argument("--broader", help="Name of broader concept (parent in hierarchy)")
    p.add_argument("--id", help="Specific ID")

    # list-concepts
    subparsers.add_parser("list-concepts", help="List skill concepts with proficiency levels (prompt-friendly)")

    # create-seeker-profile
    p = subparsers.add_parser("create-seeker-profile", help="Create a job-seeker role for a person")
    p.add_argument("--person", required=True, help="Person ID (e.g., op-f25ab4b15b0f)")
    p.add_argument("--name", help="Profile name (default: 'Job Search')")
    p.add_argument("--id", help="Custom role ID")
    p.add_argument("--target-role", dest="target_role", help="Target role title")
    p.add_argument("--industries", help="Target industries (comma-separated)")
    p.add_argument("--salary", help="Salary expectations (e.g., '180k-220k')")
    p.add_argument("--location", help="Location preference (e.g., 'Remote')")
    p.add_argument("--focus", help="Search focus (free text)")

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

    # delete-position
    p = subparsers.add_parser("delete-position", help="Delete a position and all its related data")
    p.add_argument("--id", required=True, help="Position ID")

    # add-engagement
    p = subparsers.add_parser("add-engagement", help="Add a consulting/service engagement")
    p.add_argument("--name", required=True, help="Engagement name")
    p.add_argument("--company-id", dest="company_id", help="Company ID to link")
    p.add_argument("--type", choices=["hourly", "project", "retainer", "advisory"], help="Engagement type")
    p.add_argument("--rate", help="Rate info (e.g. '$200/hr', 'TBD', 'equity only')")
    p.add_argument("--status", choices=["proposal", "active", "paused", "closed"], help="Engagement status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # add-venture
    p = subparsers.add_parser("add-venture", help="Add a startup/advisory/equity venture")
    p.add_argument("--name", required=True, help="Venture name")
    p.add_argument("--company-id", dest="company_id", help="Company ID to link")
    p.add_argument("--stage", choices=["seed", "series-a", "series-b", "growth", "closed"], help="Venture stage")
    p.add_argument("--jhunt-equity-type", dest="equity_type", choices=["none", "advisor", "cofounder", "investor"], help="Equity type")
    p.add_argument("--status", choices=["seed", "series-a", "series-b", "growth", "closed"], help="Venture status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # add-lead
    p = subparsers.add_parser("add-lead", help="Add an early-stage networking lead")
    p.add_argument("--name", required=True, help="Lead name/description")
    p.add_argument("--status", choices=["first-contact", "active", "inactive", "closed"], help="Lead status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # update-opportunity
    p = subparsers.add_parser("update-opportunity", help="Update status/stage/priority of any opportunity")
    p.add_argument("--id", required=True, help="Opportunity ID")
    p.add_argument("--status", help="New opportunity status")
    p.add_argument("--stage", help="New venture stage")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="New priority")

    # show-opportunity
    p = subparsers.add_parser("show-opportunity", help="Show details for any opportunity")
    p.add_argument("--id", required=True, help="Opportunity ID")

    # list-opportunities
    p = subparsers.add_parser("list-opportunities", help="List opportunities by type/status")
    p.add_argument("--type", choices=["position", "engagement", "venture", "lead", "all"], default="all", help="Opportunity type filter")
    p.add_argument("--status", help="Filter by opportunity status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Filter by priority")
    p.add_argument("--person", help="Filter by person ID (via seeker-pipeline)")

    # list-pipeline
    p = subparsers.add_parser("list-pipeline", help="Show application pipeline")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Filter by priority")
    p.add_argument("--tag", help="Filter by tag")
    p.add_argument("--person", help="Filter by person ID (via seeker-pipeline)")

    # show-position
    p = subparsers.add_parser("show-position", help="Get position details")
    p.add_argument("--id", required=True, help="Position ID")

    # show-company
    p = subparsers.add_parser("show-company", help="Get company details")
    p.add_argument("--id", required=True, help="Company ID")

    # show-gaps
    p = subparsers.add_parser("show-gaps", help="Show skill gaps and candidate-to-market fit")
    p.add_argument("--all", action="store_true", help="Include rejected/withdrawn positions (market-wide analysis)")
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
        "add-concept": cmd_add_concept,
        "list-concepts": cmd_list_concepts,
        "list-skills": cmd_list_skills,
        "create-seeker-profile": cmd_create_seeker_profile,
        # Artifacts (for sensemaking)
        "list-artifacts": cmd_list_artifacts,
        "show-artifact": cmd_show_artifact,
        # Application tracking
        "update-status": cmd_update_status,
        "set-jhunt-short-name": cmd_set_short_name,
        "add-note": cmd_add_note,
        "upsert-summary": cmd_upsert_summary,
        "regenerate-summary": cmd_regenerate_summary,
        "add-resource": cmd_add_resource,
        "link-resource": cmd_link_resource,
        "link-collection": cmd_link_collection,
        "link-background": cmd_link_background,
        "list-background": cmd_list_background,
        "link-paper": cmd_link_paper,
        "add-requirement": cmd_add_requirement,
        # Delete
        "delete-position": cmd_delete_position,
        # Opportunity model
        "add-engagement": cmd_add_engagement,
        "add-venture": cmd_add_venture,
        "add-lead": cmd_add_lead,
        "update-opportunity": cmd_update_opportunity,
        "show-opportunity": cmd_show_opportunity,
        "list-opportunities": cmd_list_opportunities,
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
