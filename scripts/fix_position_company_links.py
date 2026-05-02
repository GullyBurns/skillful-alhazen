#!/usr/bin/env python3
"""One-time data repair: link positions to companies via position-at-company.

Fixes audit finding #7 (position-company-link): 35/48 positions missing company link.

Strategy:
1. Find all positions without position-at-company relation
2. Extract company name from title patterns or job-url domain
3. Match to existing company entities (case-insensitive)
4. Create position-at-company relations

Usage:
    uv run python scripts/fix_position_company_links.py [--dry-run]
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")

# Known URL domain → company name mappings
URL_COMPANY_MAP = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "deepmind": "DeepMind",
    "altoslabs": "Altos Labs",
    "xairatherapeutics": "Xaira Therapeutics",
    "scaleai": "Scale AI",
    "wikimedia": "Wikimedia Foundation",
    "komodohealth": "Komodo Health",
    "lilasciences": "Lila Sciences",
    "nvidia": "NVIDIA",
    "genbio": "GenBio AI",
    "thealleninstitute": "Allen Institute for AI",
    "alleninstitute": "Allen Institute",
    "edisonscientific": "Edison Scientific",
}


def get_driver():
    from typedb.driver import Credentials, DriverOptions, TypeDB
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials("admin", "password"),
        DriverOptions(is_tls_enabled=False),
    )


def escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"') if s else ""


def extract_company_from_title(title):
    """Extract company name from common job board title patterns."""
    if not title:
        return None

    # "Job Application for X at Y"
    m = re.match(r"Job Application for .+ at (.+)$", title)
    if m:
        return m.group(1).strip()

    # "Company hiring X in Location | LinkedIn"
    m = re.match(r"(.+?) hiring .+", title)
    if m:
        return m.group(1).strip()

    # "X at Company" (but not "X at Location")
    # Skip if after "at" looks like a location (contains ", " or state abbreviation)
    m = re.search(r" at (.+?)(?:\s*\|.*)?$", title)
    if m:
        candidate = m.group(1).strip()
        # Filter out locations
        if not re.search(r"\b[A-Z]{2}\b", candidate) and ", " not in candidate:
            return candidate

    # "X | LinkedIn" — strip the LinkedIn suffix but no company info
    # "X @ Company"
    m = re.search(r" @ (.+)$", title)
    if m:
        return m.group(1).strip()

    return None


def extract_company_from_url(url):
    """Extract company name from job board URL patterns."""
    if not url:
        return None

    parsed = urlparse(url)
    path = parsed.path.lower()

    # greenhouse.io/company/jobs/...
    m = re.search(r"greenhouse\.io/(\w+)/", path)
    if m:
        key = m.group(1)
        return URL_COMPANY_MAP.get(key, key.title())

    # ashbyhq.com/company/...
    m = re.search(r"ashbyhq\.com/(\w+)/", path)
    if m:
        key = m.group(1)
        return URL_COMPANY_MAP.get(key, key.title())

    # lever.co/company/...
    m = re.search(r"lever\.co/(\w+)/", path)
    if m:
        key = m.group(1)
        return URL_COMPANY_MAP.get(key, key.title())

    # eightfold.ai — check subdomain
    if "eightfold.ai" in parsed.hostname:
        subdomain = parsed.hostname.split(".")[0]
        return URL_COMPANY_MAP.get(subdomain, subdomain.title())

    # linkedin.com — can't extract company reliably
    return None


def main():
    parser = argparse.ArgumentParser(description="Fix position-company links")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    from typedb.driver import TransactionType

    driver = get_driver()

    # 1. Find unlinked positions
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        unlinked = list(tx.query('''match
            $p isa jobhunt-position, has id $id, has name $n;
            not { (position: $p, employer: $c) isa position-at-company; };
        fetch { "id": $id, "name": $n };''').resolve())

        # Also get job-url for each
        for pos in unlinked:
            try:
                urls = list(tx.query(f'''match
                    $p isa jobhunt-position, has id "{pos["id"]}";
                    $p has job-url $u;
                fetch {{ "url": $u }};''').resolve())
                pos["url"] = urls[0]["url"] if urls else None
            except:
                pos["url"] = None

    print(f"Unlinked positions: {len(unlinked)}", file=sys.stderr)

    # 2. Load existing companies for matching
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        companies = list(tx.query('''match
            $c isa jobhunt-company, has id $cid, has name $cn;
        fetch { "id": $cid, "name": $cn };''').resolve())

    company_by_name = {}
    for co in companies:
        company_by_name[co["name"].lower()] = co

    print(f"Existing companies: {len(companies)}", file=sys.stderr)

    # 3. Match and link
    linked = 0
    created = 0
    failed = []

    for pos in unlinked:
        # Try title extraction first, then URL
        company_name = extract_company_from_title(pos["name"])
        if not company_name:
            company_name = extract_company_from_url(pos.get("url"))

        if not company_name:
            failed.append(pos)
            continue

        # Match to existing company
        match = company_by_name.get(company_name.lower())

        if args.dry_run:
            if match:
                print(f"  LINK {pos['id']}: '{pos['name'][:50]}' → {match['name']} ({match['id']})")
            else:
                print(f"  CREATE+LINK {pos['id']}: '{pos['name'][:50]}' → new company '{company_name}'")
            linked += 1
            continue

        if match:
            company_id = match["id"]
        else:
            # Create new company
            import uuid
            company_id = f"company-{uuid.uuid4().hex[:12]}"
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''insert $c isa jobhunt-company,
                    has id "{company_id}",
                    has name "{escape(company_name)}";''').resolve()
                tx.commit()
            company_by_name[company_name.lower()] = {"id": company_id, "name": company_name}
            created += 1
            print(f"  Created company: {company_name} ({company_id})", file=sys.stderr)

        # Create relation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $p isa jobhunt-position, has id "{pos['id']}";
                $c isa jobhunt-company, has id "{company_id}";
            insert (position: $p, employer: $c) isa position-at-company;''').resolve()
            tx.commit()
        linked += 1
        print(f"  Linked: {pos['name'][:50]} → {company_name}", file=sys.stderr)

    print(f"\nResults: {linked} linked, {created} companies created, {len(failed)} unresolved",
          file=sys.stderr)

    if failed:
        print("\nCould not auto-link (need manual company assignment):", file=sys.stderr)
        for pos in failed:
            print(f"  {pos['id']}: {pos['name'][:70]}", file=sys.stderr)

    # Output summary as JSON
    print(json.dumps({
        "linked": linked,
        "created": created,
        "unresolved": len(failed),
        "unresolved_ids": [p["id"] for p in failed],
    }))

    driver.close()


if __name__ == "__main__":
    main()
