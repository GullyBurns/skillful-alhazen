#!/usr/bin/env python3
"""
Job Forager - Automated job discovery via Greenhouse, Lever, LinkedIn, Remotive, and Adzuna.

Searches company job boards and aggregator platforms, filters by your skill profile,
deduplicates against existing positions/candidates, and optionally sends an email digest.

Platforms:
    Company boards:  greenhouse, lever (require --token, search one company)
    Aggregators:     linkedin, remotive, adzuna (require --query, search across companies)

Usage:
    python .claude/skills/jobhunt/job_forager.py <command> [options]

Commands:
    add-source          Add a search source (company board or aggregator)
    list-sources        List configured search sources
    remove-source       Remove a search source
    suggest-sources     Analyze profile + positions → suggest companies (JSON)
    search-source       Search a single source, store candidates
    heartbeat           Full cycle: all sources → filter → dedup → store → digest
    list-candidates     List discovered candidates (filterable)
    triage              Mark candidates as reviewed/dismissed
    promote             Promote a candidate to a jobhunt-position

Examples:
    # Company board sources (require --token)
    python .claude/skills/jobhunt/job_forager.py add-source \
        --name "Anthropic" --platform greenhouse --token anthropic
    python .claude/skills/jobhunt/job_forager.py add-source \
        --name "Netflix" --platform lever --token netflix

    # Aggregator sources (require --query)
    python .claude/skills/jobhunt/job_forager.py add-source \
        --name "ML Jobs" --platform linkedin --query "machine learning" --location "San Francisco"
    python .claude/skills/jobhunt/job_forager.py add-source \
        --name "Remote ML" --platform remotive --query "machine learning"
    python .claude/skills/jobhunt/job_forager.py add-source \
        --name "AI Jobs US" --platform adzuna --query "artificial intelligence" --location "San Francisco"

    # Search one source
    python .claude/skills/jobhunt/job_forager.py search-source --source "ML Jobs"

    # Full heartbeat
    python .claude/skills/jobhunt/job_forager.py heartbeat --min-relevance 0.1

    # List and triage candidates
    python .claude/skills/jobhunt/job_forager.py list-candidates --status new
    python .claude/skills/jobhunt/job_forager.py triage --id candidate-abc123 --action dismiss

    # Promote to full position
    python .claude/skills/jobhunt/job_forager.py promote --id candidate-abc123

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)

    # Optional: Adzuna API (free, 250 req/day)
    ADZUNA_APP_ID     Adzuna application ID
    ADZUNA_APP_KEY    Adzuna application key

    # Optional SMTP for email digest
    SMTP_HOST         SMTP server (default: smtp.gmail.com)
    SMTP_PORT         SMTP port (default: 587)
    SMTP_USER         SMTP username
    SMTP_PASSWORD     SMTP password / app-specific password
    DIGEST_TO         Recipient email
    DIGEST_FROM       Sender email
"""

import argparse
import json
import os
import re
import smtplib
import sys
import time
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as html_escape

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

# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")

# API endpoints — company boards
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
LEVER_API = "https://api.lever.co/v0/postings/{company}"
ASHBY_GRAPHQL = "https://jobs.ashbyhq.com/api/non-user-graphql"

# API endpoints — aggregators
LINKEDIN_GUEST_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
REMOTIVE_API = "https://remotive.com/api/remote-jobs"
ADZUNA_API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

LINKEDIN_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Adzuna credentials (optional — skips gracefully if not set)
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# Platform categories
COMPANY_PLATFORMS = ["greenhouse", "lever", "ashby"]
AGGREGATOR_PLATFORMS = ["linkedin", "remotive", "adzuna"]
ALL_PLATFORMS = COMPANY_PLATFORMS + AGGREGATOR_PLATFORMS

# Profile-based query generation
_GENERIC_SKILL_NAMES = {
    "python", "scientific writing", "nih/grant review",
    "scientific strategy & vision", "cell biology",
    "computational biology", "deep learning implementation",
}
_SKILL_SUFFIX_WORDS = {"systems", "domain", "concepts", "pipelines"}
_ROLE_PATTERNS = [
    "principal research scientist", "principal scientist",
    "senior research scientist", "senior scientist",
    "staff scientist", "research scientist", "research engineer",
    "applied ai engineer", "ai engineer", "ai scientist",
    "machine learning engineer", "ml engineer", "data scientist",
    "member of technical staff", "software engineer",
]

# SMTP config
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DIGEST_TO = os.getenv("DIGEST_TO", "")
DIGEST_FROM = os.getenv("DIGEST_FROM", "")

REQUEST_TIMEOUT = 30


# =============================================================================
# UTILITIES (shared patterns from jobhunt.py)
# =============================================================================


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
    """Safely extract attribute value from TypeDB fetch result."""
    attr_list = entity.get(attr_name, [])
    if attr_list and len(attr_list) > 0:
        return attr_list[0].get("value", default)
    return default


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# =============================================================================
# API CLIENTS
# =============================================================================


def search_greenhouse(board_token: str) -> list[dict]:
    """Query Greenhouse job board API, return normalized job list."""
    url = GREENHOUSE_API.format(board_token=board_token)
    print(f"  Querying Greenhouse: {board_token}...", file=sys.stderr)

    try:
        resp = requests.get(url, params={"content": "true"}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  Error querying Greenhouse {board_token}: {e}", file=sys.stderr)
        return []

    jobs = data.get("jobs", [])
    print(f"  Found {len(jobs)} jobs on Greenhouse/{board_token}", file=sys.stderr)

    normalized = []
    for job in jobs:
        # Extract location
        location = ""
        if job.get("location", {}).get("name"):
            location = job["location"]["name"]

        # Extract content snippet from HTML
        content_html = job.get("content", "")
        content_text = re.sub(r"<[^>]+>", " ", content_html)
        content_text = re.sub(r"\s+", " ", content_text).strip()
        snippet = content_text[:500] if content_text else ""

        # Department
        departments = job.get("departments", [])
        department = departments[0]["name"] if departments else ""

        # Posted date
        updated_at = job.get("updated_at", "")

        normalized.append({
            "external_id": str(job.get("id", "")),
            "title": job.get("title", ""),
            "location": location,
            "url": job.get("absolute_url", ""),
            "content_snippet": snippet,
            "content_full": content_text,
            "department": department,
            "posted_at": updated_at,
            "source_token": board_token,
            "platform": "greenhouse",
        })

    return normalized


def search_lever(company_slug: str) -> list[dict]:
    """Query Lever job board API, return normalized job list."""
    url = LEVER_API.format(company=company_slug)
    print(f"  Querying Lever: {company_slug}...", file=sys.stderr)

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  Error querying Lever {company_slug}: {e}", file=sys.stderr)
        return []

    if not isinstance(data, list):
        print(f"  Unexpected Lever response for {company_slug}", file=sys.stderr)
        return []

    print(f"  Found {len(data)} jobs on Lever/{company_slug}", file=sys.stderr)

    normalized = []
    for posting in data:
        # Extract text description
        desc_plain = posting.get("descriptionPlain", "")
        snippet = desc_plain[:500] if desc_plain else ""

        # Location
        categories = posting.get("categories", {})
        location = categories.get("location", "")

        # Department
        department = categories.get("department", "")

        # Posted date (epoch ms)
        created_at = posting.get("createdAt")
        posted_at = ""
        if created_at:
            try:
                posted_at = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat()
            except (ValueError, OSError):
                pass

        normalized.append({
            "external_id": posting.get("id", ""),
            "title": posting.get("text", ""),
            "location": location,
            "url": posting.get("hostedUrl", ""),
            "content_snippet": snippet,
            "content_full": desc_plain,
            "department": department,
            "posted_at": posted_at,
            "source_token": company_slug,
            "platform": "lever",
        })

    return normalized


def search_ashby(org_slug: str) -> list[dict]:
    """Query Ashby job board GraphQL API, return normalized job list.

    Uses the public GraphQL endpoint. The listing query returns basic fields
    (title, location, compensation). For richer scoring, individual posting
    details (with full description) can be fetched separately.
    """
    print(f"  Querying Ashby: {org_slug}...", file=sys.stderr)

    # Step 1: Get all postings (list view — no description available here)
    list_query = """query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
        jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
            teams { id name }
            jobPostings { id title locationName employmentType compensationTierSummary teamId }
        }
    }"""

    try:
        resp = requests.post(
            ASHBY_GRAPHQL,
            json={
                "operationName": "ApiJobBoardWithTeams",
                "variables": {"organizationHostedJobsPageName": org_slug},
                "query": list_query,
            },
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  Error querying Ashby {org_slug}: {e}", file=sys.stderr)
        return []

    if "errors" in data:
        print(f"  Ashby GraphQL errors for {org_slug}: {data['errors']}", file=sys.stderr)
        return []

    board = data.get("data", {}).get("jobBoard", {})
    postings = board.get("jobPostings", [])
    teams = {t["id"]: t["name"] for t in board.get("teams", [])}
    print(f"  Found {len(postings)} jobs on Ashby/{org_slug}", file=sys.stderr)

    normalized = []
    for p in postings:
        ashby_id = p.get("id", "")
        url = f"https://jobs.ashbyhq.com/{org_slug}/{ashby_id}" if ashby_id else ""
        department = teams.get(p.get("teamId", ""), "")

        normalized.append({
            "external_id": f"ashby-{ashby_id}" if ashby_id else "",
            "title": p.get("title", ""),
            "location": p.get("locationName", ""),
            "url": url,
            "content_snippet": "",  # Not available in list view
            "content_full": "",
            "department": department,
            "posted_at": "",
            "source_token": org_slug,
            "platform": "ashby",
        })

    return normalized


def search_linkedin(query: str, location: str = "") -> list[dict]:
    """Query LinkedIn guest jobs API, return normalized job list.

    Uses the public guest API (no auth required). Rate-limited to 3 pages
    with 2-second delays between requests.
    """
    print(f"  Querying LinkedIn: '{query}' in '{location or 'anywhere'}'...", file=sys.stderr)

    headers = {"User-Agent": LINKEDIN_USER_AGENT}
    normalized = []

    for page in range(3):  # Max 3 pages (75 jobs)
        params = {
            "keywords": query,
            "f_TPR": "r86400",  # Last 24 hours
            "sortBy": "DD",     # Date descending
            "start": page * 25,
        }
        if location:
            params["location"] = location

        try:
            resp = requests.get(
                LINKEDIN_GUEST_SEARCH,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                print("  LinkedIn rate limited, stopping pagination", file=sys.stderr)
                break
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Error querying LinkedIn page {page}: {e}", file=sys.stderr)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_="base-card")

        if not cards:
            break  # No more results

        for card in cards:
            # Title
            title_el = card.find("h3", class_="base-search-card__title")
            title = title_el.get_text(strip=True) if title_el else ""

            # Company
            company_el = card.find("h4", class_="base-search-card__subtitle")
            company = company_el.get_text(strip=True) if company_el else ""

            # Location
            loc_el = card.find("span", class_="job-search-card__location")
            job_location = loc_el.get_text(strip=True) if loc_el else ""

            # URL and job ID
            link_el = card.find("a", class_="base-card__full-link")
            url = link_el["href"].split("?")[0] if link_el and link_el.get("href") else ""
            # LinkedIn URLs: /jobs/view/{slug}-{id} or /jobs/view/{id}
            job_id_match = re.search(r"/jobs/view/(?:.*?-)?(\d+)/?$", url)
            job_id = job_id_match.group(1) if job_id_match else ""

            if not title or not job_id:
                continue

            display_title = f"{title} @ {company}" if company else title

            normalized.append({
                "external_id": f"linkedin-{job_id}",
                "title": display_title,
                "location": job_location,
                "url": url,
                "content_snippet": f"{display_title} - {job_location}",
                "content_full": "",
                "department": "",
                "posted_at": "",
                "source_token": "linkedin",
                "platform": "linkedin",
            })

        if page < 2:
            time.sleep(2)  # Rate-limit delay

    print(f"  Found {len(normalized)} jobs on LinkedIn", file=sys.stderr)
    return normalized


def search_remotive(query: str, location: str = "") -> list[dict]:
    """Query Remotive API for remote jobs, return normalized job list.

    No auth required. Returns JSON directly.
    """
    print(f"  Querying Remotive: '{query}'...", file=sys.stderr)

    try:
        resp = requests.get(
            REMOTIVE_API,
            params={"search": query, "limit": 50},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  Error querying Remotive: {e}", file=sys.stderr)
        return []

    jobs = data.get("jobs", [])

    # Client-side location filter
    if location:
        location_lower = location.lower()
        jobs = [
            j for j in jobs
            if location_lower in (j.get("candidate_required_location", "") or "").lower()
        ]

    print(f"  Found {len(jobs)} jobs on Remotive", file=sys.stderr)

    normalized = []
    for job in jobs:
        # Strip HTML tags from description
        desc_html = job.get("description", "")
        desc_text = re.sub(r"<[^>]+>", " ", desc_html)
        desc_text = re.sub(r"\s+", " ", desc_text).strip()
        snippet = desc_text[:500] if desc_text else ""

        company = job.get("company_name", "")
        title = job.get("title", "")
        display_title = f"{title} @ {company}" if company else title

        normalized.append({
            "external_id": f"remotive-{job.get('id', '')}",
            "title": display_title,
            "location": job.get("candidate_required_location", ""),
            "url": job.get("url", ""),
            "content_snippet": snippet,
            "content_full": desc_text,
            "department": job.get("category", ""),
            "posted_at": job.get("publication_date", ""),
            "source_token": "remotive",
            "platform": "remotive",
        })

    return normalized


def search_adzuna(query: str = "", location: str = "", country: str = "us",
                  what_or: str = "", what_exclude: str = "", title_only: str = "") -> list[dict]:
    """Query Adzuna API for jobs, return normalized job list.

    Requires ADZUNA_APP_ID and ADZUNA_APP_KEY env vars. Gracefully skips
    if not configured.

    Supports both simple mode (query as 'what') and structured mode
    (what_or, what_exclude, title_only for profile-based searches).
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("  Adzuna: skipping (ADZUNA_APP_ID/ADZUNA_APP_KEY not set)", file=sys.stderr)
        return []

    desc = query or what_or or "profile-based"
    print(f"  Querying Adzuna: '{desc}' in '{location or country}'...", file=sys.stderr)

    normalized = []

    for page in range(1, 3):  # Max 2 pages (100 results)
        url = ADZUNA_API.format(country=country, page=page)
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "max_days_old": 1,
            "sort_by": "date",
            "results_per_page": 50,
        }
        # Simple mode: single query string
        if query:
            params["what"] = query
        # Structured mode: separate boolean params
        else:
            if what_or:
                params["what_or"] = what_or
            if what_exclude:
                params["what_exclude"] = what_exclude
            if title_only:
                params["title_only"] = title_only
        if location:
            params["where"] = location

        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"  Error querying Adzuna page {page}: {e}", file=sys.stderr)
            break

        results = data.get("results", [])
        if not results:
            break

        for job in results:
            company = job.get("company", {}).get("display_name", "")
            title = job.get("title", "")
            # Clean HTML from title
            title = re.sub(r"<[^>]+>", "", title).strip()
            display_title = f"{title} @ {company}" if company else title

            desc = job.get("description", "")
            desc = re.sub(r"<[^>]+>", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            snippet = desc[:500] if desc else ""

            job_id = job.get("id", "")

            normalized.append({
                "external_id": f"adzuna-{job_id}",
                "title": display_title,
                "location": job.get("location", {}).get("display_name", ""),
                "url": job.get("redirect_url", ""),
                "content_snippet": snippet,
                "content_full": desc,
                "department": job.get("category", {}).get("label", ""),
                "posted_at": job.get("created", ""),
                "source_token": "adzuna",
                "platform": "adzuna",
            })

    print(f"  Found {len(normalized)} jobs on Adzuna", file=sys.stderr)
    return normalized


# =============================================================================
# PROFILE-BASED QUERY GENERATION
# =============================================================================


def load_position_titles() -> list[str]:
    """Load position titles from TypeDB for search term extraction."""
    titles = []
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match $p isa jobhunt-position;
                    fetch $p: name;"""
                results = list(tx.query.fetch(query))
                for r in results:
                    name = get_attr(r["p"], "name")
                    if name:
                        titles.append(name)
    return titles


def _clean_skill_for_search(name: str) -> str:
    """Clean a skill name into a search-friendly term."""
    # Split on & and take first part
    name = name.split("&")[0].strip()
    # Remove trailing generic words
    words = name.split()
    while words and words[-1].lower() in _SKILL_SUFFIX_WORDS:
        words.pop()
    return " ".join(words)


def _title_case_role(role: str) -> str:
    """Title-case a role, preserving AI/ML/NLP abbreviations."""
    return " ".join(
        p.upper() if p.upper() in ("AI", "ML", "NLP", "LLM") else p.title()
        for p in role.split()
    )


def extract_profile_search_terms(skills: list[dict], position_titles: list[str] = None) -> dict:
    """Extract search terms from user profile for building job search queries.

    Returns dict with:
        domain_terms: skill/domain phrases for search
        role_terms: job title/role phrases
        exclude_terms: terms to filter out
    """
    # Domain terms from strong/some skills
    domain_terms = []
    for s in skills:
        if s.get("level") not in ("strong", "some"):
            continue
        name = s.get("name", "")
        if name.lower() in _GENERIC_SKILL_NAMES:
            continue
        clean = _clean_skill_for_search(name)
        if clean:
            domain_terms.append(clean)

    # Role terms from position titles
    found_roles = set()
    if position_titles:
        for title in position_titles:
            title_lower = title.lower()
            for role in _ROLE_PATTERNS:
                if role in title_lower:
                    found_roles.add(_title_case_role(role))

    # Sensible defaults if no roles extracted
    if not found_roles:
        found_roles = {"Research Scientist", "AI Engineer"}

    return {
        "domain_terms": domain_terms,
        "role_terms": sorted(found_roles),
        "exclude_terms": ["intern", "junior", "entry level"],
    }


def build_linkedin_query(terms: dict) -> str:
    """Build LinkedIn boolean search query from profile terms.

    LinkedIn guest API supports: AND, OR, NOT, "phrases", () grouping.
    Strategy: combine top domain terms with OR for broad coverage.
    The relevance scorer handles precision after results come back.
    """
    # Pick the most distinctive domain terms (skip very broad ones)
    domain = terms.get("domain_terms", [])[:6]
    roles = terms.get("role_terms", [])[:3]

    # Combine domain and role terms with OR for broad recall
    all_phrases = [f'"{d}"' for d in domain] + [f'"{r}"' for r in roles]

    if not all_phrases:
        return ""

    query = " OR ".join(all_phrases)

    # Exclude terms
    for ex in terms.get("exclude_terms", []):
        query += f' NOT "{ex}"'

    return query


def build_remotive_queries(terms: dict) -> list[str]:
    """Build list of Remotive search terms (no boolean support).

    Remotive only does substring matching, so we make multiple calls
    with different terms and merge client-side.
    """
    queries = []
    # Top domain terms (most specific)
    for dt in terms["domain_terms"][:4]:
        queries.append(dt)
    # Top role terms
    for rt in terms["role_terms"][:2]:
        queries.append(rt)
    return queries


def build_adzuna_params(terms: dict) -> dict:
    """Build Adzuna structured search params from profile terms.

    Adzuna uses separate params: what_or, what_exclude, title_only.
    """
    params = {}
    if terms["domain_terms"]:
        params["what_or"] = " ".join(f'"{d}"' for d in terms["domain_terms"])
    if terms["role_terms"]:
        # Use top 3 roles for title filtering
        params["title_only"] = " ".join(terms["role_terms"][:3])
    if terms["exclude_terms"]:
        params["what_exclude"] = " ".join(terms["exclude_terms"])
    return params


def _search_remotive_multi(queries: list[str], location: str = "") -> list[dict]:
    """Search Remotive with multiple queries, merge and dedup results."""
    all_jobs = []
    seen_ids = set()
    for q in queries:
        results = search_remotive(q, location)
        for r in results:
            if r["external_id"] not in seen_ids:
                seen_ids.add(r["external_id"])
                all_jobs.append(r)
    return all_jobs


def search_platform(source: dict, profile_terms: dict = None) -> list[dict]:
    """Search a platform, auto-generating query from profile if source has no search_query.

    For aggregator sources without a stored search_query, builds a platform-appropriate
    query from the user's skill profile and position titles.
    """
    platform = source["platform"]
    location = source.get("search_location", "")
    query = source.get("search_query") or ""

    if platform == "greenhouse":
        return search_greenhouse(source.get("board_token", ""))
    elif platform == "lever":
        return search_lever(source.get("board_token", ""))
    elif platform == "ashby":
        return search_ashby(source.get("board_token", ""))
    elif platform == "linkedin":
        if not query and profile_terms:
            query = build_linkedin_query(profile_terms)
            print(f"  Auto-generated LinkedIn query: {query}", file=sys.stderr)
        return search_linkedin(query, location) if query else []
    elif platform == "remotive":
        if not query and profile_terms:
            queries = build_remotive_queries(profile_terms)
            print(f"  Auto-generated Remotive queries: {queries}", file=sys.stderr)
            return _search_remotive_multi(queries, location)
        return search_remotive(query, location) if query else []
    elif platform == "adzuna":
        if not query and profile_terms:
            adzuna_params = build_adzuna_params(profile_terms)
            print(f"  Auto-generated Adzuna params: {adzuna_params}", file=sys.stderr)
            return search_adzuna(
                "", location,
                what_or=adzuna_params.get("what_or", ""),
                what_exclude=adzuna_params.get("what_exclude", ""),
                title_only=adzuna_params.get("title_only", ""),
            )
        return search_adzuna(query, location)

    print(f"  Unknown platform: {platform}", file=sys.stderr)
    return []


# =============================================================================
# RELEVANCE SCORING
# =============================================================================


def load_user_skills() -> list[dict]:
    """Load your-skill entities from TypeDB."""
    skills = []
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match $s isa your-skill;
                    fetch $s: skill-name, skill-level;"""
                results = list(tx.query.fetch(query))
                for r in results:
                    skills.append({
                        "name": get_attr(r["s"], "skill-name", ""),
                        "level": get_attr(r["s"], "skill-level", "none"),
                    })
    return skills


def compute_relevance(job: dict, skills: list[dict]) -> float:
    """Compute relevance score for a job based on user skill profile.

    Score = weighted matches / total skills checked.
    strong=1.0, some=0.7, learning=0.4, none=0.1
    """
    if not skills:
        return 0.0

    level_weights = {"strong": 1.0, "some": 0.7, "learning": 0.4, "none": 0.1}

    text = (job.get("title", "") + " " + job.get("content_snippet", "")).lower()

    total_weight = 0.0
    matched_weight = 0.0

    for skill in skills:
        skill_name = skill["name"].lower()
        weight = level_weights.get(skill["level"], 0.1)
        total_weight += weight

        # Check for skill name in job text (word boundary aware)
        # Handle multi-word skills and common variations
        patterns = [re.escape(skill_name)]
        # Also check hyphenated version
        if " " in skill_name:
            patterns.append(re.escape(skill_name.replace(" ", "-")))

        for pattern in patterns:
            if re.search(r"\b" + pattern + r"\b", text, re.IGNORECASE):
                matched_weight += weight
                break

    if total_weight == 0:
        return 0.0

    return round(min(matched_weight / total_weight, 1.0), 3)


# =============================================================================
# PRE-STORAGE FILTERING
# =============================================================================

# Bay Area location patterns (case-insensitive matching)
_BAY_AREA_PATTERNS = [
    "san francisco", "san jose", "mountain view", "palo alto", "sunnyvale",
    "menlo park", "redwood city", "south san francisco", "san mateo",
    "oakland", "berkeley", "los gatos", "santa clara", "cupertino",
    "fremont", "san bruno", "foster city", "burlingame", "los altos",
    "milpitas", "bay area", "sf,", "sf ", "california",
]

# Title patterns to exclude (clearly irrelevant roles)
_EXCLUDE_TITLE_PATTERNS = [
    r"\baccount\s+(director|manager|executive)\b",
    r"\bsales\s+(director|manager|lead|representative)\b",
    r"\brecruit(er|ing\s+manager)\b",
    r"\b(general\s+)?counsel\b",
    r"\blegal\b",
    r"\bfacilities\b",
    r"\badministrative\b",
    r"\bexecutive\s+(assistant|business\s+partner)\b",
    r"\bcopywriter\b",
    r"\bpayroll\b",
    r"\bprocurement\b",
    r"\b(buyer|purchasing)\b",
    r"\btax\s+(manager|analyst|director)\b",
    r"\baccounting\b",
    r"\breal\s+estate\b",
    r"\boffice\s+manager\b",
    r"\bintern(ship)?\b",
    r"\bco-?op\b",
]
_EXCLUDE_TITLE_RE = [re.compile(p, re.IGNORECASE) for p in _EXCLUDE_TITLE_PATTERNS]


def is_bay_area_or_remote(location: str) -> bool:
    """Check if a job location is in the Bay Area or remote-friendly."""
    loc = location.lower()
    if not loc:
        return True  # Unknown location — keep it
    if "remote" in loc:
        return True
    return any(ba in loc for ba in _BAY_AREA_PATTERNS)


def is_relevant_title(title: str) -> bool:
    """Check if a job title is potentially relevant (not clearly irrelevant)."""
    return not any(p.search(title) for p in _EXCLUDE_TITLE_RE)


def filter_candidates(jobs: list[dict], location_filter: bool = True,
                      title_filter: bool = True) -> tuple[list[dict], int, int]:
    """Filter jobs by location and title relevance.

    Returns (filtered_jobs, location_excluded, title_excluded).
    """
    loc_excluded = 0
    title_excluded = 0
    kept = []

    for job in jobs:
        if location_filter and not is_bay_area_or_remote(job.get("location", "")):
            loc_excluded += 1
            continue
        if title_filter and not is_relevant_title(job.get("title", "")):
            title_excluded += 1
            continue
        kept.append(job)

    return kept, loc_excluded, title_excluded


# =============================================================================
# DEDUPLICATION
# =============================================================================


def load_existing_position_urls() -> set[str]:
    """Load all job-url values from existing jobhunt-position entities."""
    urls = set()
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match $p isa jobhunt-position, has job-url $url;
                    fetch $p: job-url;"""
                results = list(tx.query.fetch(query))
                for r in results:
                    url = get_attr(r["p"], "job-url")
                    if url:
                        urls.add(url)
    return urls


def load_existing_candidate_ext_ids() -> set[str]:
    """Load all external-job-id values from existing candidates."""
    ext_ids = set()
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match $c isa jobhunt-candidate, has external-job-id $eid;
                    fetch $c: external-job-id;"""
                results = list(tx.query.fetch(query))
                for r in results:
                    eid = get_attr(r["c"], "external-job-id")
                    if eid:
                        ext_ids.add(eid)
    return ext_ids


def deduplicate(candidates: list[dict], existing_urls: set[str], existing_ext_ids: set[str]) -> list[dict]:
    """Filter out candidates that already exist as positions or candidates."""
    new = []
    for c in candidates:
        if c["external_id"] in existing_ext_ids:
            continue
        if c["url"] in existing_urls:
            continue
        new.append(c)
    return new


# =============================================================================
# TYPEDB STORAGE
# =============================================================================


def load_search_sources() -> list[dict]:
    """Load all jobhunt-search-source entities."""
    sources = []
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match $s isa jobhunt-search-source;
                    fetch $s: id, name, board-token, board-platform, company-url,
                        search-query, search-location;"""
                results = list(tx.query.fetch(query))
                for r in results:
                    sources.append({
                        "id": get_attr(r["s"], "id"),
                        "name": get_attr(r["s"], "name"),
                        "board_token": get_attr(r["s"], "board-token"),
                        "platform": get_attr(r["s"], "board-platform"),
                        "company_url": get_attr(r["s"], "company-url"),
                        "search_query": get_attr(r["s"], "search-query"),
                        "search_location": get_attr(r["s"], "search-location"),
                    })
    return sources


def store_candidates(candidates: list[dict], source_id: str,
                     source_name: str = "") -> list[dict]:
    """Store candidate entities in TypeDB and link to source."""
    stored = []
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            for c in candidates:
                candidate_id = generate_id("candidate")

                # Truncate snippet for storage
                snippet = c.get("content_snippet", "")[:500]

                # Normalize title to "Role @ Company" format
                title = c['title']
                if ' @ ' not in title and source_name:
                    title = f"{title} @ {source_name}"

                insert_query = f'''insert $c isa jobhunt-candidate,
                    has id "{candidate_id}",
                    has name "{escape_string(title)}",
                    has job-url "{escape_string(c['url'])}",
                    has external-job-id "{escape_string(c['external_id'])}",
                    has candidate-status "new",
                    has relevance-score {c.get('relevance', 0.0)},
                    has discovered-at {timestamp},
                    has created-at {timestamp}'''

                if c.get("location"):
                    insert_query += f', has location "{escape_string(c["location"])}"'
                if snippet:
                    insert_query += f', has description "{escape_string(snippet)}"'

                insert_query += ";"

                try:
                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.insert(insert_query)
                        tx.commit()

                    # Link to source
                    with session.transaction(TransactionType.WRITE) as tx:
                        rel_query = f'''match
                            $s isa jobhunt-search-source, has id "{source_id}";
                            $c isa jobhunt-candidate, has id "{candidate_id}";
                        insert (source: $s, candidate: $c) isa source-provides;'''
                        tx.query.insert(rel_query)
                        tx.commit()

                    c["candidate_id"] = candidate_id
                    stored.append(c)
                except Exception as e:
                    print(f"  Error storing candidate '{c['title']}': {e}", file=sys.stderr)

    return stored


# =============================================================================
# EMAIL DIGEST
# =============================================================================


def smtp_configured() -> bool:
    """Check if SMTP settings are configured."""
    return bool(SMTP_USER and SMTP_PASSWORD and DIGEST_TO)


def send_email_digest(candidates: list[dict]) -> bool:
    """Send HTML email digest of new candidates."""
    if not smtp_configured():
        return False

    # Sort by relevance descending
    candidates_sorted = sorted(candidates, key=lambda c: c.get("relevance", 0), reverse=True)

    # Build HTML
    rows = []
    for c in candidates_sorted:
        score = c.get("relevance", 0)
        score_pct = f"{score * 100:.0f}%"
        title_escaped = html_escape(c.get("title", ""))
        url = html_escape(c.get("url", ""))
        location = html_escape(c.get("location", ""))
        source = html_escape(c.get("source_token", ""))
        platform = html_escape(c.get("platform", ""))

        rows.append(f"""<tr>
            <td style="padding:8px;border-bottom:1px solid #eee">
                <a href="{url}">{title_escaped}</a>
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee">{source} ({platform})</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{location}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:center">{score_pct}</td>
        </tr>""")

    html_body = f"""<html>
<body style="font-family:sans-serif;max-width:800px;margin:0 auto">
<h2>Job Forager Digest</h2>
<p>Found <strong>{len(candidates_sorted)}</strong> new candidates on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</p>
<table style="width:100%;border-collapse:collapse">
<thead>
<tr style="background:#f5f5f5">
    <th style="padding:8px;text-align:left">Title</th>
    <th style="padding:8px;text-align:left">Source</th>
    <th style="padding:8px;text-align:left">Location</th>
    <th style="padding:8px;text-align:center">Relevance</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
<p style="color:#888;font-size:12px;margin-top:20px">
    Generated by Alhazen Job Forager. Promote candidates via:
    <code>job_forager.py promote --id &lt;candidate-id&gt;</code>
</p>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Forager: {len(candidates_sorted)} new candidates ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
    msg["From"] = DIGEST_FROM or SMTP_USER
    msg["To"] = DIGEST_TO

    # Plain text fallback
    plain_lines = [f"Job Forager Digest - {len(candidates_sorted)} new candidates\n"]
    for c in candidates_sorted:
        score_pct = f"{c.get('relevance', 0) * 100:.0f}%"
        plain_lines.append(f"- [{score_pct}] {c.get('title', '')} @ {c.get('source_token', '')} - {c.get('url', '')}")
    plain_text = "\n".join(plain_lines)

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(msg["From"], [DIGEST_TO], msg.as_string())
        print(f"  Email digest sent to {DIGEST_TO}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"  Error sending email: {e}", file=sys.stderr)
        return False


# =============================================================================
# COMMAND IMPLEMENTATIONS
# =============================================================================


def cmd_add_source(args):
    """Add a search source (company board or aggregator)."""
    # Validate: company platforms need --token, aggregators need --query
    token = getattr(args, "token", None) or ""
    query_kw = getattr(args, "query", None) or ""
    location_kw = getattr(args, "location", None) or ""

    if args.platform in COMPANY_PLATFORMS and not token:
        print(json.dumps({
            "success": False,
            "error": f"Platform '{args.platform}' requires --token (company slug)",
        }))
        return

    if args.platform in AGGREGATOR_PLATFORMS and not query_kw:
        print(f"  Note: No --query provided for {args.platform}. "
              "Will auto-generate from your skill profile during heartbeat.", file=sys.stderr)

    source_id = generate_id("source")
    timestamp = get_timestamp()

    insert_query = f'''insert $s isa jobhunt-search-source,
        has id "{source_id}",
        has name "{escape_string(args.name)}",
        has board-platform "{args.platform}",
        has created-at {timestamp}'''

    if token:
        insert_query += f', has board-token "{escape_string(token)}"'
    if query_kw:
        insert_query += f', has search-query "{escape_string(query_kw)}"'
    if location_kw:
        insert_query += f', has search-location "{escape_string(location_kw)}"'
    if args.url:
        insert_query += f', has company-url "{escape_string(args.url)}"'

    insert_query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(insert_query)
                tx.commit()

    result = {
        "success": True,
        "source_id": source_id,
        "name": args.name,
        "platform": args.platform,
    }
    if token:
        result["board_token"] = token
    if query_kw:
        result["search_query"] = query_kw
    if location_kw:
        result["search_location"] = location_kw

    print(json.dumps(result))


def cmd_list_sources(args):
    """List all configured search sources."""
    sources = load_search_sources()
    print(json.dumps({
        "success": True,
        "sources": sources,
        "count": len(sources),
    }, indent=2))


def cmd_remove_source(args):
    """Remove a search source by id or token."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Find the source
            if args.id:
                match_clause = f'$s isa jobhunt-search-source, has id "{args.id}"'
            elif args.token:
                match_clause = f'$s isa jobhunt-search-source, has board-token "{escape_string(args.token)}"'
            elif args.name:
                match_clause = f'$s isa jobhunt-search-source, has name "{escape_string(args.name)}"'
            else:
                print(json.dumps({"success": False, "error": "Must provide --id, --token, or --name"}))
                return

            # Check existence
            with session.transaction(TransactionType.READ) as tx:
                check = f'match {match_clause}; fetch $s: id, name;'
                existing = list(tx.query.fetch(check))

            if not existing:
                print(json.dumps({"success": False, "error": "Source not found"}))
                return

            source_name = get_attr(existing[0]["s"], "name")
            source_id = get_attr(existing[0]["s"], "id")

            # Delete any source-provides relations first
            with session.transaction(TransactionType.WRITE) as tx:
                try:
                    del_rel = f'''match
                        $s isa jobhunt-search-source, has id "{source_id}";
                        $r (source: $s, candidate: $c) isa source-provides;
                    delete $r isa source-provides;'''
                    tx.query.delete(del_rel)
                    tx.commit()
                except Exception:
                    pass  # No relations to delete

            # Delete the source
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.delete(f'match {match_clause}; delete $s isa jobhunt-search-source;')
                tx.commit()

    print(json.dumps({
        "success": True,
        "removed": source_name,
        "source_id": source_id,
    }))


def cmd_suggest_sources(args):
    """Analyze profile + existing positions to suggest companies."""
    suggestions = []

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Get existing companies from positions
            with session.transaction(TransactionType.READ) as tx:
                query = """match
                    $p isa jobhunt-position, has job-url $url;
                    fetch $p: name, job-url;"""
                results = list(tx.query.fetch(query))

            # Get existing search sources to exclude
            with session.transaction(TransactionType.READ) as tx:
                src_query = """match $s isa jobhunt-search-source;
                    fetch $s: board-token, board-platform;"""
                existing_sources = list(tx.query.fetch(src_query))

            # Get user skills
            with session.transaction(TransactionType.READ) as tx:
                skill_query = """match $s isa your-skill;
                    fetch $s: skill-name, skill-level;"""
                skill_results = list(tx.query.fetch(skill_query))

    existing_tokens = set()
    for s in existing_sources:
        token = get_attr(s["s"], "board-token")
        if token:
            existing_tokens.add(token.lower())

    # Extract company slugs from position URLs
    seen_companies = set()
    for r in results:
        url = get_attr(r["p"], "job-url", "")
        name = get_attr(r["p"], "name", "")

        # Try to detect platform and slug from URL
        if "greenhouse.io" in url:
            # boards.greenhouse.io/{slug}/jobs/...
            match = re.search(r"greenhouse\.io/(\w+)/", url)
            if match:
                slug = match.group(1)
                if slug.lower() not in existing_tokens and slug not in seen_companies:
                    seen_companies.add(slug)
                    suggestions.append({
                        "name": slug.title(),
                        "platform": "greenhouse",
                        "token": slug,
                        "reason": f"Found in existing position: {name[:50]}",
                    })
        elif "lever.co" in url:
            # jobs.lever.co/{slug}/...
            match = re.search(r"lever\.co/(\w+)/", url)
            if match:
                slug = match.group(1)
                if slug.lower() not in existing_tokens and slug not in seen_companies:
                    seen_companies.add(slug)
                    suggestions.append({
                        "name": slug.title(),
                        "platform": "lever",
                        "token": slug,
                        "reason": f"Found in existing position: {name[:50]}",
                    })

    # Format skills for context
    skills = []
    for r in skill_results:
        skills.append({
            "name": get_attr(r["s"], "skill-name"),
            "level": get_attr(r["s"], "skill-level"),
        })

    print(json.dumps({
        "success": True,
        "suggestions": suggestions,
        "count": len(suggestions),
        "existing_sources": len(existing_tokens),
        "skills_for_context": skills,
        "message": "Claude: review these suggestions and call add-source for ones you approve. "
                   "Also consider adding companies from your domain knowledge that use Greenhouse or Lever. "
                   "For broad discovery, add aggregator sources: linkedin, remotive, or adzuna with --query.",
    }, indent=2))


def cmd_search_source(args):
    """Search a single source, score, dedup, and store candidates."""
    # Find the source by token, id, or name
    sources = load_search_sources()
    source = None
    for s in sources:
        if (s.get("board_token") == args.source
                or s["id"] == args.source
                or s.get("name") == args.source):
            source = s
            break

    if not source:
        print(json.dumps({"success": False, "error": f"Source not found: {args.source}"}))
        return

    # Build profile terms for auto-query generation (aggregator sources)
    profile_terms = None
    if source["platform"] in AGGREGATOR_PLATFORMS and not source.get("search_query"):
        skills = load_user_skills()
        position_titles = load_position_titles()
        profile_terms = extract_profile_search_terms(skills, position_titles)

    # Search the API
    jobs = search_platform(source, profile_terms)

    if not jobs:
        print(json.dumps({
            "success": True,
            "source": source["name"],
            "total_jobs": 0,
            "new_candidates": 0,
        }))
        return

    # Score by relevance
    skills = load_user_skills()
    for job in jobs:
        job["relevance"] = compute_relevance(job, skills)

    # Filter by minimum relevance
    min_rel = args.min_relevance if hasattr(args, "min_relevance") and args.min_relevance is not None else 0.0
    relevant = [j for j in jobs if j["relevance"] >= min_rel]

    # Dedup
    existing_urls = load_existing_position_urls()
    existing_ext_ids = load_existing_candidate_ext_ids()
    new_jobs = deduplicate(relevant, existing_urls, existing_ext_ids)

    # Store
    stored = store_candidates(new_jobs, source["id"], source_name=source["name"]) if new_jobs else []

    print(json.dumps({
        "success": True,
        "source": source["name"],
        "platform": source["platform"],
        "total_jobs": len(jobs),
        "above_threshold": len(relevant),
        "after_dedup": len(new_jobs),
        "stored": len(stored),
        "min_relevance": min_rel,
        "candidates": [
            {
                "id": c.get("candidate_id", ""),
                "title": c["title"],
                "relevance": c["relevance"],
                "location": c.get("location", ""),
                "url": c["url"],
            }
            for c in stored
        ],
    }, indent=2))


def cmd_heartbeat(args):
    """Run full heartbeat: all sources → filter → dedup → store → digest."""
    print("Starting heartbeat...", file=sys.stderr)

    # 1. Load profile
    skills = load_user_skills()
    print(f"  Loaded {len(skills)} skills from profile", file=sys.stderr)

    # 1b. Build profile search terms for aggregator auto-query
    position_titles = load_position_titles()
    profile_terms = extract_profile_search_terms(skills, position_titles)
    print(f"  Profile search terms: {len(profile_terms['domain_terms'])} domain, "
          f"{len(profile_terms['role_terms'])} role", file=sys.stderr)

    # 2. Load sources
    sources = load_search_sources()
    print(f"  Loaded {len(sources)} search sources", file=sys.stderr)

    if not sources:
        print(json.dumps({
            "success": True,
            "message": "No search sources configured. Use add-source first.",
            "total_new": 0,
        }))
        return

    # 3. Load existing IDs for dedup
    existing_urls = load_existing_position_urls()
    existing_ext_ids = load_existing_candidate_ext_ids()
    print(f"  Loaded {len(existing_urls)} existing position URLs and {len(existing_ext_ids)} candidate IDs for dedup", file=sys.stderr)

    # 4. Search each source
    all_candidates = []
    source_results = []
    min_rel = args.min_relevance if args.min_relevance is not None else 0.0

    for source in sources:
        print(f"\n  Searching {source['name']}...", file=sys.stderr)

        jobs = search_platform(source, profile_terms)

        # 5. Score and filter
        for job in jobs:
            job["relevance"] = compute_relevance(job, skills)
        relevant = [j for j in jobs if j["relevance"] >= min_rel]

        # 5b. Pre-storage filtering (location + title relevance)
        filtered, loc_excl, title_excl = filter_candidates(relevant)
        if loc_excl or title_excl:
            print(f"  Filtered: {loc_excl} non-Bay-Area, {title_excl} irrelevant titles "
                  f"({len(filtered)} kept of {len(relevant)})", file=sys.stderr)
        relevant = filtered

        # 6. Deduplicate
        new_jobs = deduplicate(relevant, existing_urls, existing_ext_ids)

        # Also deduplicate against candidates we've already collected in this run
        already_seen_ids = {c["external_id"] for c in all_candidates}
        new_jobs = [j for j in new_jobs if j["external_id"] not in already_seen_ids]

        # 7. Store in TypeDB
        stored = store_candidates(new_jobs, source["id"], source_name=source["name"]) if new_jobs else []

        # Update dedup set for subsequent sources
        for c in stored:
            existing_ext_ids.add(c["external_id"])

        all_candidates.extend(stored)

        source_results.append({
            "source": source["name"],
            "platform": source["platform"],
            "total_jobs": len(jobs),
            "above_threshold": len(relevant) + loc_excl + title_excl,
            "filtered_location": loc_excl,
            "filtered_title": title_excl,
            "after_filter": len(relevant),
            "new_stored": len(stored),
        })

    # 8. Email digest
    email_sent = False
    if all_candidates and smtp_configured():
        email_sent = send_email_digest(all_candidates)

    # 9. Output summary
    print(json.dumps({
        "success": True,
        "total_sources": len(sources),
        "total_new_candidates": len(all_candidates),
        "min_relevance": min_rel,
        "email_sent": email_sent,
        "source_results": source_results,
        "top_candidates": [
            {
                "id": c.get("candidate_id", ""),
                "title": c["title"],
                "relevance": c["relevance"],
                "location": c.get("location", ""),
                "source": c.get("source_token", ""),
                "url": c["url"],
            }
            for c in sorted(all_candidates, key=lambda x: x.get("relevance", 0), reverse=True)[:20]
        ],
    }, indent=2))


def cmd_list_candidates(args):
    """List discovered candidates, optionally filtered."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = "match $c isa jobhunt-candidate"

                if args.status:
                    query += f', has candidate-status "{args.status}"'

                query += """;
                    fetch $c: id, name, job-url, location, relevance-score,
                        candidate-status, external-job-id, discovered-at, triage-reason;"""

                results = list(tx.query.fetch(query))

                # If filtering by source, get source links
                if args.source:
                    src_query = f'''match
                        $s isa jobhunt-search-source, has board-token "{escape_string(args.source)}";
                        (source: $s, candidate: $c) isa source-provides;
                    fetch $c: id;'''
                    src_results = list(tx.query.fetch(src_query))
                    source_ids = {get_attr(r["c"], "id") for r in src_results}
                    results = [r for r in results if get_attr(r["c"], "id") in source_ids]

    candidates = []
    for r in results:
        candidates.append({
            "id": get_attr(r["c"], "id"),
            "title": get_attr(r["c"], "name"),
            "url": get_attr(r["c"], "job-url"),
            "location": get_attr(r["c"], "location"),
            "relevance": get_attr(r["c"], "relevance-score"),
            "status": get_attr(r["c"], "candidate-status"),
            "external_id": get_attr(r["c"], "external-job-id"),
            "discovered_at": get_attr(r["c"], "discovered-at"),
            "triage_reason": get_attr(r["c"], "triage-reason"),
        })

    # Sort by relevance descending
    candidates.sort(key=lambda x: x.get("relevance") or 0, reverse=True)

    total = len(candidates)

    # Apply limit/offset after sort
    offset = getattr(args, 'offset', None)
    limit = getattr(args, 'limit', None)
    if offset is not None and offset > 0:
        candidates = candidates[offset:]
    if limit is not None and limit > 0:
        candidates = candidates[:limit]

    print(json.dumps({
        "success": True,
        "candidates": candidates,
        "count": len(candidates),
        "total": total,
    }, indent=2))


def cmd_triage(args):
    """Mark a candidate as reviewed or dismissed."""
    valid_actions = ["reviewed", "dismissed"]
    if args.action not in valid_actions:
        print(json.dumps({"success": False, "error": f"Action must be one of: {valid_actions}"}))
        return

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Check existence
            with session.transaction(TransactionType.READ) as tx:
                check = f'''match $c isa jobhunt-candidate, has id "{args.id}";
                    fetch $c: id, name, candidate-status;'''
                existing = list(tx.query.fetch(check))

            if not existing:
                print(json.dumps({"success": False, "error": "Candidate not found"}))
                return

            # Delete old status, add new one
            with session.transaction(TransactionType.WRITE) as tx:
                update_query = f'''match
                    $c isa jobhunt-candidate, has id "{args.id}", has candidate-status $old;
                delete $c has $old;'''
                tx.query.delete(update_query)
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                insert_query = f'''match
                    $c isa jobhunt-candidate, has id "{args.id}";
                insert $c has candidate-status "{args.action}";'''
                tx.query.insert(insert_query)
                tx.commit()

    print(json.dumps({
        "success": True,
        "candidate_id": args.id,
        "new_status": args.action,
    }))


def cmd_promote(args):
    """Promote a candidate to a full jobhunt-position."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            # Load candidate
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match $c isa jobhunt-candidate, has id "{args.id}";
                    fetch $c: id, name, job-url, location, candidate-status;'''
                results = list(tx.query.fetch(query))

            if not results:
                print(json.dumps({"success": False, "error": "Candidate not found"}))
                return

            candidate = results[0]["c"]
            title = get_attr(candidate, "name", "Untitled")
            url = get_attr(candidate, "job-url", "")
            location = get_attr(candidate, "location")

            # Create position
            position_id = generate_id("position")
            timestamp = get_timestamp()

            pos_query = f'''insert $p isa jobhunt-position,
                has id "{position_id}",
                has name "{escape_string(title)}",
                has created-at {timestamp}'''

            if url:
                pos_query += f', has job-url "{escape_string(url)}"'
            if location:
                pos_query += f', has location "{escape_string(location)}"'

            pos_query += ";"

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(pos_query)
                tx.commit()

            # Create initial application note
            note_id = generate_id("note")
            with session.transaction(TransactionType.WRITE) as tx:
                note_query = f'''insert $n isa jobhunt-application-note,
                    has id "{note_id}",
                    has name "Application Status",
                    has application-status "researching",
                    has created-at {timestamp};'''
                tx.query.insert(note_query)
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                about_query = f'''match
                    $n isa note, has id "{note_id}";
                    $p isa jobhunt-position, has id "{position_id}";
                insert (note: $n, subject: $p) isa aboutness;'''
                tx.query.insert(about_query)
                tx.commit()

            # Update candidate status to "promoted"
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.delete(f'''match
                    $c isa jobhunt-candidate, has id "{args.id}", has candidate-status $old;
                delete $c has $old;''')
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'''match
                    $c isa jobhunt-candidate, has id "{args.id}";
                insert $c has candidate-status "promoted";''')
                tx.commit()

    print(json.dumps({
        "success": True,
        "candidate_id": args.id,
        "position_id": position_id,
        "title": title,
        "url": url,
        "message": f"Candidate promoted to position {position_id}. "
                   "Use 'ingest-job --url' or ask Claude to analyze it for full sensemaking.",
    }, indent=2))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Job Forager - Automated job discovery via Greenhouse, Lever, LinkedIn, Remotive, and Adzuna"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # add-source
    p = subparsers.add_parser("add-source", help="Add a search source (company board or aggregator)")
    p.add_argument("--name", required=True, help="Source name")
    p.add_argument("--platform", required=True, choices=ALL_PLATFORMS, help="Platform type")
    p.add_argument("--token", help="Board token / company slug (required for greenhouse/lever)")
    p.add_argument("--query", help="Search keywords (required for linkedin/remotive/adzuna)")
    p.add_argument("--location", help="Location filter (optional, for aggregators)")
    p.add_argument("--url", help="Company website URL")

    # list-sources
    subparsers.add_parser("list-sources", help="List configured search sources")

    # remove-source
    p = subparsers.add_parser("remove-source", help="Remove a search source")
    p.add_argument("--id", help="Source entity ID")
    p.add_argument("--token", help="Board token to remove")
    p.add_argument("--name", help="Source name to remove")

    # suggest-sources
    subparsers.add_parser("suggest-sources", help="Suggest companies from your profile/positions")

    # search-source
    p = subparsers.add_parser("search-source", help="Search a single source")
    p.add_argument("--source", required=True, help="Source board-token or entity ID")
    p.add_argument("--min-relevance", type=float, default=0.0, help="Minimum relevance score (0.0-1.0)")

    # heartbeat
    p = subparsers.add_parser("heartbeat", help="Full cycle: search all sources, filter, store, digest")
    p.add_argument("--min-relevance", type=float, default=0.0, help="Minimum relevance score (0.0-1.0)")

    # list-candidates
    p = subparsers.add_parser("list-candidates", help="List discovered candidates")
    p.add_argument("--status", choices=["new", "reviewed", "promoted", "dismissed"], help="Filter by status")
    p.add_argument("--source", help="Filter by source board-token")
    p.add_argument("--limit", type=int, default=None, help="Max candidates to return")
    p.add_argument("--offset", type=int, default=None, help="Skip first N candidates (after sort)")

    # triage
    p = subparsers.add_parser("triage", help="Mark candidate as reviewed/dismissed")
    p.add_argument("--id", required=True, help="Candidate entity ID")
    p.add_argument("--action", required=True, choices=["reviewed", "dismissed"], help="Triage action")

    # promote
    p = subparsers.add_parser("promote", help="Promote candidate to full position")
    p.add_argument("--id", required=True, help="Candidate entity ID")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not REQUESTS_AVAILABLE and args.command in ("search-source", "heartbeat"):
        print(json.dumps({"success": False, "error": "requests not installed"}))
        sys.exit(1)

    commands = {
        "add-source": cmd_add_source,
        "list-sources": cmd_list_sources,
        "remove-source": cmd_remove_source,
        "suggest-sources": cmd_suggest_sources,
        "search-source": cmd_search_source,
        "heartbeat": cmd_heartbeat,
        "list-candidates": cmd_list_candidates,
        "triage": cmd_triage,
        "promote": cmd_promote,
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
