#!/usr/bin/env python3
"""
Europe PMC Search CLI - Query EPMC and store results in TypeDB.

Usage:
    python scripts/epmc_search.py <command> [options]

Commands:
    search              Search EPMC and store results in TypeDB
    count               Count results for a query (without storing)
    fetch-paper         Fetch a single paper by DOI/PMID and store it
    list-collections    List all EPMC search collections

Examples:
    # Search for CRISPR papers and create a collection
    python scripts/epmc_search.py search --query "CRISPR AND gene editing" --collection "CRISPR Papers"

    # Count results without storing
    python scripts/epmc_search.py count --query "COVID-19 AND vaccine"

    # Fetch a single paper by DOI
    python scripts/epmc_search.py fetch-paper --doi "10.1038/s41586-020-2008-3"

    # Limit results
    python scripts/epmc_search.py search --query "machine learning" --max-results 100

Environment:
    TYPEDB_HOST     TypeDB server host (default: localhost)
    TYPEDB_PORT     TypeDB server port (default: 1729)
    TYPEDB_DATABASE Database name (default: alhazen)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from time import sleep

import requests
from tqdm import tqdm

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen")

# EPMC API Configuration
EPMC_API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DEFAULT_PAGE_SIZE = 1000
REQUEST_TIMEOUT = 60


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


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def map_publication_type(pub_types: list[str]) -> tuple[str, str]:
    """
    Map EPMC publication types to TypeDB entity types.

    Returns:
        Tuple of (typedb_type, human_readable_type)
    """
    pub_types_lower = [t.lower() for t in pub_types]

    if "patent" in pub_types_lower:
        return None, None  # Skip patents
    elif "clinical trial" in pub_types_lower:
        return "scilit-paper", "ClinicalTrial"
    elif any(
        t in pub_types_lower
        for t in [
            "review",
            "systematic review",
            "systematic-review",
            "meta-analysis",
            "review-article",
        ]
    ):
        return "scilit-review", "ScientificReviewArticle"
    elif "preprint" in pub_types_lower:
        return "scilit-preprint", "ScientificPrimaryResearchPreprint"
    elif any(t in pub_types_lower for t in ["journal article", "research-article"]):
        return "scilit-paper", "ScientificPrimaryResearchArticle"
    elif any(t in pub_types_lower for t in ["case-report", "case reports"]):
        return "scilit-paper", "ClinicalCaseReport"
    elif "practice guideline" in pub_types_lower:
        return "scilit-paper", "ClinicalGuidelines"
    elif any(t in pub_types_lower for t in ["letter", "comment", "editorial"]):
        return "scilit-paper", "ScientificComment"
    elif any(
        t in pub_types_lower
        for t in ["published erratum", "correction", "retraction of publication"]
    ):
        return "scilit-paper", "ScientificErrata"
    else:
        return None, None  # Skip unknown types


def run_epmc_query(
    query: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_results: int | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> tuple[int, list[dict]]:
    """
    Execute a search query against Europe PMC API.

    Args:
        query: The search query string
        page_size: Number of results per page
        max_results: Maximum total results to fetch (None for all)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (total_count, list of publication records)
    """
    params = {
        "format": "JSON",
        "pageSize": page_size,
        "synonym": "TRUE",
        "resultType": "core",
        "query": query,
    }

    # Initial request to get count
    response = requests.get(EPMC_API_URL, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    total_count = data["hitCount"]
    print(f"Found {total_count} results for query: {query}", file=sys.stderr)

    if total_count == 0:
        return 0, []

    # Determine how many to fetch
    fetch_count = min(total_count, max_results) if max_results else total_count

    publications = []
    cursor_mark = "*"

    for _i in tqdm(range(0, fetch_count, page_size), desc="Fetching", file=sys.stderr):
        params["cursorMark"] = cursor_mark

        response = requests.get(EPMC_API_URL, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if data.get("nextCursorMark"):
            cursor_mark = data["nextCursorMark"]

        for record in data.get("resultList", {}).get("result", []):
            if len(publications) >= fetch_count:
                break
            publications.append(record)

        # Rate limiting
        sleep(0.1)

    return total_count, publications


def parse_epmc_record(record: dict) -> dict | None:
    """
    Parse an EPMC record into a structured format for TypeDB.

    Args:
        record: Raw EPMC API record

    Returns:
        Parsed record dict or None if should be skipped
    """
    # Get publication types
    pub_types = record.get("pubTypeList", {}).get("pubType", [])
    typedb_type, pub_type_label = map_publication_type(pub_types)

    if typedb_type is None:
        return None

    # Must have DOI
    doi = record.get("doi")
    if not doi:
        return None

    # Parse date
    date_format = "%Y-%m-%d"
    pub_date = None
    if record.get("firstPublicationDate"):
        try:
            pub_date = datetime.strptime(record["firstPublicationDate"], date_format)
        except ValueError:
            pass
    elif record.get("dateOfCreation"):
        try:
            pub_date = datetime.strptime(record["dateOfCreation"], date_format)
        except ValueError:
            pass

    # Build author string for content field
    author_string = record.get("authorString", "")
    title = record.get("title", "")
    year = pub_date.year if pub_date else ""
    content = f"{author_string} ({year}) {title}" if author_string and year else title

    return {
        "doi": doi,
        "pmid": record.get("pmid"),
        "pmcid": record.get("pmcid"),
        "epmc_id": record.get("id"),
        "source": record.get("source"),
        "title": title,
        "abstract": record.get("abstractText", ""),
        "publication_date": pub_date,
        "publication_year": pub_date.year if pub_date else None,
        "journal_name": record.get("journalTitle"),
        "journal_volume": record.get("journalVolume"),
        "journal_issue": record.get("issue"),
        "page_range": record.get("pageInfo"),
        "typedb_type": typedb_type,
        "pub_type_label": pub_type_label,
        "content": content,
        "keywords": record.get("keywordList", {}).get("keyword", []),
        "pub_types": pub_types,
    }


def insert_paper_to_typedb(driver, paper: dict, collection_id: str | None = None) -> str:
    """
    Insert a parsed paper record into TypeDB.

    Args:
        driver: TypeDB driver
        paper: Parsed paper dict
        collection_id: Optional collection to add paper to

    Returns:
        The paper ID
    """
    paper_id = f"doi-{paper['doi'].replace('/', '-').replace('.', '_')}"
    timestamp = get_timestamp()

    # Build insert query for the paper
    query = f'''insert $p isa {paper["typedb_type"]},
        has id "{paper_id}",
        has name "{escape_string(paper["title"])}",
        has doi "{paper["doi"]}",
        has created-at {timestamp}'''

    if paper.get("pmid"):
        query += f', has pmid "{paper["pmid"]}"'
    if paper.get("pmcid"):
        query += f', has pmcid "{paper["pmcid"]}"'
    if paper.get("abstract"):
        query += f', has abstract-text "{escape_string(paper["abstract"])}"'
    if paper.get("publication_year"):
        query += f", has publication-year {paper['publication_year']}"
    if paper.get("journal_name"):
        query += f', has journal-name "{escape_string(paper["journal_name"])}"'
    if paper.get("journal_volume"):
        query += f', has journal-volume "{escape_string(paper["journal_volume"])}"'
    if paper.get("journal_issue"):
        query += f', has journal-issue "{escape_string(paper["journal_issue"])}"'
    if paper.get("page_range"):
        query += f', has page-range "{escape_string(paper["page_range"])}"'
    if paper.get("content"):
        query += f', has content "{escape_string(paper["content"])}"'

    # Add keywords
    for kw in paper.get("keywords", []):
        query += f', has keyword "{escape_string(kw)}"'

    query += ";"

    with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
        # Check if paper already exists
        with session.transaction(TransactionType.READ) as tx:
            check_query = f'match $p isa scilit-paper, has doi "{paper["doi"]}"; fetch $p: id;'
            existing = list(tx.query.fetch(check_query))
            if existing:
                # Paper already exists, return existing ID
                return paper_id

        # Insert paper
        with session.transaction(TransactionType.WRITE) as tx:
            tx.query.insert(query)
            tx.commit()

        # Create citation record artifact
        artifact_id = generate_id("artifact")
        artifact_query = f'''insert $a isa scilit-citation-record,
            has id "{artifact_id}",
            has format "epmc-citation",
            has source-uri "https://europepmc.org/article/{paper.get("source", "MED")}/{paper.get("epmc_id", paper["doi"])}",
            has created-at {timestamp};'''

        with session.transaction(TransactionType.WRITE) as tx:
            tx.query.insert(artifact_query)
            tx.commit()

        # Link artifact to paper
        with session.transaction(TransactionType.WRITE) as tx:
            rel_query = f'''match
                $p isa scilit-paper, has id "{paper_id}";
                $a isa artifact, has id "{artifact_id}";
            insert (artifact: $a, referent: $p) isa representation;'''
            tx.query.insert(rel_query)
            tx.commit()

        # Create title fragment
        if paper.get("title"):
            title_frag_id = generate_id("fragment")
            title_frag_query = f'''insert $f isa scilit-section,
                has id "{title_frag_id}",
                has content "{escape_string(paper["title"])}",
                has section-type "title",
                has offset 0,
                has length {len(paper["title"])},
                has created-at {timestamp};'''

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(title_frag_query)
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                frag_rel_query = f'''match
                    $a isa artifact, has id "{artifact_id}";
                    $f isa fragment, has id "{title_frag_id}";
                insert (whole: $a, part: $f) isa fragmentation;'''
                tx.query.insert(frag_rel_query)
                tx.commit()

        # Create abstract fragment
        if paper.get("abstract"):
            abs_frag_id = generate_id("fragment")
            title_len = len(paper.get("title", "")) + 1
            abs_frag_query = f'''insert $f isa scilit-section,
                has id "{abs_frag_id}",
                has content "{escape_string(paper["abstract"])}",
                has section-type "abstract",
                has offset {title_len},
                has length {len(paper["abstract"])},
                has created-at {timestamp};'''

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(abs_frag_query)
                tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                frag_rel_query = f'''match
                    $a isa artifact, has id "{artifact_id}";
                    $f isa fragment, has id "{abs_frag_id}";
                insert (whole: $a, part: $f) isa fragmentation;'''
                tx.query.insert(frag_rel_query)
                tx.commit()

        # Add to collection if specified
        if collection_id:
            with session.transaction(TransactionType.WRITE) as tx:
                coll_query = f'''match
                    $c isa collection, has id "{collection_id}";
                    $p isa scilit-paper, has id "{paper_id}";
                insert (collection: $c, member: $p) isa collection-membership,
                    has created-at {timestamp};'''
                tx.query.insert(coll_query)
                tx.commit()

        # Tag with publication type
        if paper.get("pub_type_label"):
            tag_id = generate_id("tag")
            tag_name = paper["pub_type_label"]

            # Check if tag exists
            with session.transaction(TransactionType.READ) as tx:
                tag_check = f'match $t isa tag, has name "{tag_name}"; fetch $t: id;'
                existing_tag = list(tx.query.fetch(tag_check))

            if not existing_tag:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(f'insert $t isa tag, has id "{tag_id}", has name "{tag_name}";')
                    tx.commit()

            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(f'''match
                    $p isa scilit-paper, has id "{paper_id}";
                    $t isa tag, has name "{tag_name}";
                insert (tagged-entity: $p, tag: $t) isa tagging,
                    has created-at {timestamp};''')
                tx.commit()

    return paper_id


def cmd_search(args):
    """Execute search and store results."""
    # Run the EPMC query
    total_count, publications = run_epmc_query(
        args.query, page_size=args.page_size, max_results=args.max_results
    )

    if not publications:
        print(
            json.dumps(
                {
                    "success": True,
                    "total_count": total_count,
                    "stored_count": 0,
                    "message": "No results found",
                }
            )
        )
        return

    # Create collection
    collection_id = args.collection_id or generate_id("collection")
    collection_name = args.collection or f"EPMC Search: {args.query[:50]}"
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                coll_query = f'''insert $c isa collection,
                    has id "{collection_id}",
                    has name "{escape_string(collection_name)}",
                    has description "EPMC search results for: {escape_string(args.query)}",
                    has logical-query "{escape_string(args.query)}",
                    has is-extensional true,
                    has created-at {timestamp};'''
                tx.query.insert(coll_query)
                tx.commit()

        # Process and store papers
        stored_count = 0
        skipped_count = 0
        paper_ids = []

        for record in tqdm(publications, desc="Storing papers", file=sys.stderr):
            paper = parse_epmc_record(record)
            if paper:
                try:
                    paper_id = insert_paper_to_typedb(driver, paper, collection_id)
                    paper_ids.append(paper_id)
                    stored_count += 1
                except Exception as e:
                    print(f"Error storing paper {paper.get('doi')}: {e}", file=sys.stderr)
                    skipped_count += 1
            else:
                skipped_count += 1

    print(
        json.dumps(
            {
                "success": True,
                "collection_id": collection_id,
                "collection_name": collection_name,
                "query": args.query,
                "total_count": total_count,
                "fetched_count": len(publications),
                "stored_count": stored_count,
                "skipped_count": skipped_count,
            },
            indent=2,
        )
    )


def cmd_count(args):
    """Count results for a query without storing."""
    params = {"format": "JSON", "pageSize": 1, "query": args.query}

    response = requests.get(EPMC_API_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    print(json.dumps({"success": True, "query": args.query, "count": data["hitCount"]}))


def cmd_fetch_paper(args):
    """Fetch a single paper by DOI or PMID."""
    if args.doi:
        query = f'DOI:"{args.doi}"'
    elif args.pmid:
        query = f"EXT_ID:{args.pmid}"
    else:
        print(json.dumps({"success": False, "error": "Must provide --doi or --pmid"}))
        return

    _, publications = run_epmc_query(query, page_size=10, max_results=1)

    if not publications:
        print(json.dumps({"success": False, "error": "Paper not found"}))
        return

    paper = parse_epmc_record(publications[0])
    if not paper:
        print(json.dumps({"success": False, "error": "Paper type not supported"}))
        return

    with get_driver() as driver:
        paper_id = insert_paper_to_typedb(driver, paper, args.collection)

    print(
        json.dumps(
            {
                "success": True,
                "paper_id": paper_id,
                "doi": paper["doi"],
                "title": paper["title"],
                "type": paper["pub_type_label"],
            },
            indent=2,
        )
    )


def cmd_list_collections(args):
    """List all collections created from EPMC searches."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = """match $c isa collection, has logical-query $q;
                    fetch $c: id, name, description, logical-query;"""
                results = list(tx.query.fetch(query))

    print(json.dumps({"success": True, "collections": results, "count": len(results)}, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Europe PMC Search CLI - Query EPMC and store results in TypeDB"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # search command
    p = subparsers.add_parser("search", help="Search EPMC and store results")
    p.add_argument("--query", "-q", required=True, help="EPMC search query")
    p.add_argument("--collection", "-c", help="Collection name for results")
    p.add_argument("--collection-id", help="Specific collection ID")
    p.add_argument("--max-results", "-m", type=int, help="Maximum results to fetch")
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Results per page")

    # count command
    p = subparsers.add_parser("count", help="Count results for a query")
    p.add_argument("--query", "-q", required=True, help="EPMC search query")

    # fetch-paper command
    p = subparsers.add_parser("fetch-paper", help="Fetch a single paper")
    p.add_argument("--doi", help="Paper DOI")
    p.add_argument("--pmid", help="PubMed ID")
    p.add_argument("--collection", help="Collection ID to add paper to")

    # list-collections command
    subparsers.add_parser("list-collections", help="List EPMC search collections")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE and args.command not in ["count", None]:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "search": cmd_search,
        "count": cmd_count,
        "fetch-paper": cmd_fetch_paper,
        "list-collections": cmd_list_collections,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
