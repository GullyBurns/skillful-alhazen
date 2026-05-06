#!/usr/bin/env python3
"""
Scientific Literature CLI - Multi-source paper search and ingestion for TypeDB.

Sources: Europe PMC (epmc), PubMed (pubmed), OpenAlex (openalex), bioRxiv/medRxiv

Usage:
    python scientific_literature.py search --source epmc --query "CRISPR" --collection "CRISPR Papers"
    python scientific_literature.py count --query "COVID-19 AND vaccine"
    python scientific_literature.py ingest --doi "10.1038/s41587-020-0700-8"
    python scientific_literature.py show --id "scilit-paper-abc123"
    python scientific_literature.py list [--collection "collection-abc123"]
    python scientific_literature.py list-collections
    python scientific_literature.py embed --collection "collection-abc123"
    python scientific_literature.py search-semantic --query "CDK8 stress response" --collection "col-abc"
    python scientific_literature.py cluster --collection "collection-abc123" --min-cluster-size 15 --dry-run

Environment:
    TYPEDB_HOST         TypeDB host (default: localhost)
    TYPEDB_PORT         TypeDB port (default: 1729)
    TYPEDB_DATABASE     Database name (default: alhazen_notebook)
    NCBI_API_KEY        NCBI Entrez API key (optional; raises rate limit to 10 req/s)
    OPENALEX_API_KEY    OpenAlex API key (optional; free at openalex.org/settings/api)
    VOYAGE_API_KEY      Voyage AI API key (required for embed/search-semantic/cluster)
    QDRANT_HOST         Qdrant host (default: localhost)
    QDRANT_PORT         Qdrant port (default: 6333)
"""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print("Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
          file=sys.stderr)

try:
    from skillful_alhazen.utils.skill_helpers import escape_string, generate_id, get_timestamp
except ImportError:
    def escape_string(s):
        if s is None:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")

    def generate_id(prefix):
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def get_timestamp():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: requests not installed. Run: uv add requests", file=sys.stderr)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

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


def _get_cache_dir():
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
    cache_dir = _get_cache_dir()
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
    return (_get_cache_dir() / cache_path).read_bytes().decode(encoding)


CACHE_AVAILABLE = True

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    def tqdm(iterable, **kwargs):
        return iterable


# =============================================================================
# CONFIGURATION
# =============================================================================

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")

APT_SECTIONS_COLLECTION = "apt-sections"
APT_NOTES_COLLECTION = "apt-notes"
VECTOR_DIM_SECTIONS = 1024  # voyage-3 output dimension

EPMC_API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OPENALEX_BASE = "https://api.openalex.org"
BIORXIV_BASE = "https://api.biorxiv.org/pubs"
MEDRXIV_BASE = "https://api.medrxiv.org/pubs"

DEFAULT_PAGE_SIZE = 1000
REQUEST_TIMEOUT = 60
HEADERS = {"User-Agent": "skillful-alhazen/0.1 (mailto:alhazen@example.com)"}

ESEARCH_PAGE_SIZE = 500   # PMIDs per esearch pagination page
EFETCH_BATCH_SIZE = 200   # PMIDs per efetch POST batch (avoids GET URL length limits)
NCBI_RATE_LIMIT   = 0.34  # minimum seconds between NCBI requests (3 req/sec without key)


# =============================================================================
# TYPEDB HELPERS
# =============================================================================

def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def paper_exists(driver, doi=None, pmid=None):
    """Check if a paper already exists by DOI or PMID. Returns existing ID or None."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        if doi:
            result = list(tx.query(
                f'match $p isa scilit-paper, has scilit-doi "{escape_string(doi)}"; fetch {{ "id": $p.id }};'
            ).resolve())
            if result:
                return result[0]["id"]
        if pmid:
            result = list(tx.query(
                f'match $p isa scilit-paper, has scilit-pmid "{escape_string(pmid)}"; fetch {{ "id": $p.id }};'
            ).resolve())
            if result:
                return result[0]["id"]
    return None


def insert_paper(driver, paper: dict) -> str:
    """Insert a normalized paper dict into TypeDB. Returns paper_id."""
    pid = paper.get("id") or generate_id("scilit-paper")
    timestamp = get_timestamp()

    q = f'insert $p isa scilit-paper, has id "{pid}", has name "{escape_string(paper.get("title", ""))}"'
    if paper.get("abstract"):
        q += f', has abstract-text "{escape_string(paper["abstract"])}"'
    if paper.get("doi"):
        q += f', has scilit-doi "{escape_string(paper["doi"])}"'
    if paper.get("pmid"):
        q += f', has scilit-pmid "{escape_string(str(paper["pmid"]))}"'
    if paper.get("pmcid"):
        q += f', has scilit-pmcid "{escape_string(paper["pmcid"])}"'
    if paper.get("arxiv_id"):
        q += f', has scilit-arxiv-id "{escape_string(paper["arxiv_id"])}"'
    if paper.get("year"):
        q += f', has scilit-publication-year {int(paper["year"])}'
    if paper.get("journal"):
        q += f', has scilit-journal-name "{escape_string(paper["journal"])}"'
    if paper.get("journal_volume"):
        q += f', has scilit-journal-volume "{escape_string(paper["journal_volume"])}"'
    if paper.get("journal_issue"):
        q += f', has scilit-journal-issue "{escape_string(paper["journal_issue"])}"'
    if paper.get("page_range"):
        q += f', has scilit-page-range "{escape_string(paper["page_range"])}"'
    if paper.get("source_uri"):
        q += f', has source-uri "{escape_string(paper["source_uri"])}"'
    for kw in paper.get("keywords", []):
        q += f', has scilit-keyword "{escape_string(kw)}"'
    q += f', has created-at {timestamp};'

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(q).resolve()
        tx.commit()

    return pid


def add_to_collection(driver, paper_id: str, collection_id: str):
    """Add a paper to a collection."""
    timestamp = get_timestamp()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(
            f'match $c isa alh-collection, has id "{collection_id}"; '
            f'$p isa scilit-paper, has id "{paper_id}"; '
            f'insert (collection: $c, member: $p) isa alh-collection-membership, '
            f'has created-at {timestamp};'
        ).resolve()
        tx.commit()


# =============================================================================
# EPMC CONNECTOR
# =============================================================================

def map_publication_type(pub_types: list) -> tuple:
    """Map EPMC publication types to TypeDB entity types."""
    pub_types_lower = [t.lower() for t in pub_types]

    if "patent" in pub_types_lower:
        return None, None
    elif "clinical trial" in pub_types_lower:
        return "scilit-paper", "ClinicalTrial"
    elif any(t in pub_types_lower for t in [
        "review", "systematic review", "systematic-review", "meta-analysis", "review-article",
    ]):
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
    elif any(t in pub_types_lower for t in [
        "published erratum", "correction", "retraction of publication",
    ]):
        return "scilit-paper", "ScientificErrata"
    else:
        return None, None


def run_epmc_query(query, page_size=DEFAULT_PAGE_SIZE, max_results=None, timeout=REQUEST_TIMEOUT):
    """Execute a search query against Europe PMC API."""
    params = {
        "format": "JSON",
        "pageSize": page_size,
        "synonym": "TRUE",
        "resultType": "core",
        "query": query,
    }

    response = requests.get(EPMC_API_URL, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    total_count = data["hitCount"]
    print(f"Found {total_count} results for query: {query}", file=sys.stderr)

    if total_count == 0:
        return 0, []

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

        sleep(0.1)

    return total_count, publications


def parse_epmc_record(record: dict):
    """Parse an EPMC record into a normalized paper dict for TypeDB."""
    pub_types = record.get("pubTypeList", {}).get("pubType", [])
    typedb_type, pub_type_label = map_publication_type(pub_types)

    if typedb_type is None:
        return None

    doi = record.get("doi")
    if not doi:
        return None

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

    author_string = record.get("authorString", "")
    title = record.get("title", "")
    year = pub_date.year if pub_date else ""

    return {
        "doi": doi,
        "pmid": record.get("pmid"),
        "pmcid": record.get("pmcid"),
        "epmc_id": record.get("id"),
        "source": record.get("source"),
        "title": title,
        "abstract": record.get("abstractText", ""),
        "publication_date": pub_date,
        "year": pub_date.year if pub_date else None,
        "journal": record.get("journalTitle"),
        "journal_volume": record.get("journalVolume"),
        "journal_issue": record.get("issue"),
        "page_range": record.get("pageInfo"),
        "typedb_type": typedb_type,
        "pub_type_label": pub_type_label,
        "keywords": record.get("keywordList", {}).get("keyword", []),
        "pub_types": pub_types,
        "source_uri": f"https://europepmc.org/article/{record.get('source', 'MED')}/{record.get('id', doi)}",
    }


def insert_epmc_paper(driver, paper: dict, collection_id=None) -> str:
    """Insert an EPMC paper with full citation record and fragments. Returns paper_id."""
    paper_id = f"doi-{paper['doi'].replace('/', '-').replace('.', '_')}"
    timestamp = get_timestamp()

    # Build insert query
    query = f'insert $p isa {paper["typedb_type"]}, has id "{paper_id}", has name "{escape_string(paper["title"])}", has scilit-doi "{paper["doi"]}", has created-at {timestamp}'

    if paper.get("pmid"):
        query += f', has scilit-pmid "{paper["pmid"]}"'
    if paper.get("pmcid"):
        query += f', has scilit-pmcid "{paper["pmcid"]}"'
    if paper.get("abstract"):
        query += f', has abstract-text "{escape_string(paper["abstract"])}"'
    if paper.get("year") and paper.get("typedb_type") != "scilit-preprint":
        query += f', has scilit-publication-year {paper["year"]}'
    if paper.get("journal"):
        query += f', has scilit-journal-name "{escape_string(paper["journal"])}"'
    if paper.get("journal_volume"):
        query += f', has scilit-journal-volume "{escape_string(paper["journal_volume"])}"'
    if paper.get("journal_issue"):
        query += f', has scilit-journal-issue "{escape_string(paper["journal_issue"])}"'
    if paper.get("page_range"):
        query += f', has scilit-page-range "{escape_string(paper["page_range"])}"'
    for kw in paper.get("keywords", []):
        query += f', has scilit-keyword "{escape_string(kw)}"'
    query += ";"

    # Check if paper already exists
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        check = f'match $p isa scilit-paper, has scilit-doi "{paper["doi"]}"; fetch {{ "id": $p.id }};'
        if list(tx.query(check).resolve()):
            return paper_id

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(query).resolve()
        tx.commit()

    # Create citation record artifact
    artifact_id = generate_id("artifact")
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'insert $a isa scilit-citation-record, has id "{artifact_id}", has format "epmc-citation", has source-uri "{escape_string(paper["source_uri"])}", has created-at {timestamp};').resolve()
        tx.commit()

    # Link artifact to paper
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'match $p isa scilit-paper, has id "{paper_id}"; $a isa alh-artifact, has id "{artifact_id}"; insert (artifact: $a, referent: $p) isa alh-representation;').resolve()
        tx.commit()

    # Create title fragment
    if paper.get("title"):
        title_frag_id = generate_id("fragment")
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'insert $f isa scilit-section, has id "{title_frag_id}", has content "{escape_string(paper["title"])}", has scilit-section-type "title", has offset 0, has length {len(paper["title"])}, has created-at {timestamp};').resolve()
            tx.commit()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'match $a isa alh-artifact, has id "{artifact_id}"; $f isa alh-fragment, has id "{title_frag_id}"; insert (whole: $a, part: $f) isa alh-fragmentation;').resolve()
            tx.commit()

    # Create abstract fragment
    if paper.get("abstract"):
        abs_frag_id = generate_id("fragment")
        title_len = len(paper.get("title", "")) + 1
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'insert $f isa scilit-section, has id "{abs_frag_id}", has content "{escape_string(paper["abstract"])}", has scilit-section-type "abstract", has offset {title_len}, has length {len(paper["abstract"])}, has created-at {timestamp};').resolve()
            tx.commit()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'match $a isa alh-artifact, has id "{artifact_id}"; $f isa alh-fragment, has id "{abs_frag_id}"; insert (whole: $a, part: $f) isa alh-fragmentation;').resolve()
            tx.commit()

    # Add to collection if specified
    if collection_id:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'match $c isa alh-collection, has id "{collection_id}"; $p isa scilit-paper, has id "{paper_id}"; insert (collection: $c, member: $p) isa alh-collection-membership, has created-at {timestamp};').resolve()
            tx.commit()

    # Tag with publication type
    if paper.get("pub_type_label"):
        tag_name = paper["pub_type_label"]
        tag_id = generate_id("tag")
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing_tag = list(tx.query(f'match $t isa alh-tag, has name "{tag_name}"; fetch {{ "id": $t.id }};').resolve())
        if not existing_tag:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'insert $t isa alh-tag, has id "{tag_id}", has name "{tag_name}";').resolve()
                tx.commit()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'match $p isa scilit-paper, has id "{paper_id}"; $t isa alh-tag, has name "{tag_name}"; insert (tagged-entity: $p, tag: $t) isa alh-tagging, has created-at {timestamp};').resolve()
            tx.commit()

    return paper_id


# =============================================================================
# PUBMED CONNECTOR
# =============================================================================

def _ncbi_params(**kwargs):
    params = {"retmode": "json", **kwargs}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    return params


def _esearch_paginated(query: str, max_results: int) -> list:
    """Collect PubMed IDs via paginated esearch (retstart/retmax chunks).

    Mirrors ESearchQuery.execute_query() from alhazen searchEngineUtils:
    - Gets total count first, then pages through results in ESEARCH_PAGE_SIZE chunks
    - Respects NCBI rate limit between pages
    - Returns up to max_results PMIDs
    """
    # First: get total hit count
    r = requests.get(
        f"{NCBI_BASE}/esearch.fcgi",
        params=_ncbi_params(db="pubmed", term=query, retmax=0),
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    total = int(r.json().get("esearchresult", {}).get("count", 0))
    to_fetch = min(total, max_results)
    if to_fetch == 0:
        return []

    ids = []
    for start in range(0, to_fetch, ESEARCH_PAGE_SIZE):
        batch_size = min(ESEARCH_PAGE_SIZE, to_fetch - start)
        time.sleep(NCBI_RATE_LIMIT)
        r = requests.get(
            f"{NCBI_BASE}/esearch.fcgi",
            params=_ncbi_params(db="pubmed", term=query, retmax=batch_size, retstart=start),
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        ids.extend(r.json().get("esearchresult", {}).get("idlist", []))

    return ids[:to_fetch]


def _efetch_batched(pmids: list) -> list:
    """Fetch PubMed records for a list of PMIDs using batched POST requests.

    Mirrors EFetchQuery.generate_data_frame_from_id_list() from alhazen searchEngineUtils:
    - Sends IDs as POST form data in EFETCH_BATCH_SIZE chunks
    - POST avoids HTTP 414 (Request-URI Too Long) from large ID lists in GET params
    - Respects NCBI rate limit between batches
    """
    papers = []
    for i in range(0, len(pmids), EFETCH_BATCH_SIZE):
        batch = pmids[i:i + EFETCH_BATCH_SIZE]
        data = {"db": "pubmed", "retmode": "xml", "rettype": "abstract", "id": ",".join(batch)}
        if NCBI_API_KEY:
            data["api_key"] = NCBI_API_KEY
        r = requests.post(
            f"{NCBI_BASE}/efetch.fcgi",
            data=data,
            headers=HEADERS,
            timeout=60,
        )
        r.raise_for_status()
        papers.extend(_parse_pubmed_xml(r.text))
        if i + EFETCH_BATCH_SIZE < len(pmids):
            time.sleep(NCBI_RATE_LIMIT)
    return papers


def search_pubmed(query: str, max_results: int = 20) -> list:
    """Search PubMed using paginated esearch + batched POST efetch.

    Handles queries returning any number of results:
    - esearch is paginated (ESEARCH_PAGE_SIZE per page with retstart/retmax)
    - efetch uses POST in batches of EFETCH_BATCH_SIZE, avoiding URL length limits
    Both patterns adapted from alhazen.utils.searchEngineUtils (ESearchQuery /
    EFetchQuery classes).
    """
    pmids = _esearch_paginated(query, max_results)
    if not pmids:
        return []
    time.sleep(NCBI_RATE_LIMIT)
    return _efetch_batched(pmids)


def _parse_pubmed_xml(xml_text: str) -> list:
    """Parse PubMed efetch XML into normalized dicts."""
    papers = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for article in root.findall(".//PubmedArticle"):
        medline = article.find(".//MedlineCitation")
        if medline is None:
            continue

        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else None

        art = medline.find("Article")
        if art is None:
            continue

        title_el = art.find("ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_el = art.find(".//AbstractText")
        abstract = "".join(abstract_el.itertext()) if abstract_el is not None else ""

        journal_el = art.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else ""

        year_el = art.find(".//PubDate/Year")
        year = int(year_el.text) if year_el is not None and year_el.text else None

        doi = None
        for aid in article.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text
                break

        papers.append({
            "title": title.strip(),
            "abstract": abstract.strip(),
            "pmid": pmid,
            "doi": doi,
            "journal": journal,
            "year": year,
            "source_uri": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        })

    return papers


# =============================================================================
# OPENALEX CONNECTOR
# =============================================================================

def search_openalex(query: str, max_results: int = 20, filter_str: str = None) -> list:
    """Search OpenAlex /works endpoint. Returns normalized paper dicts.

    If filter_str is provided (e.g. 'cites:W2565424224'), it is used instead of the
    search param, enabling citation lookups and other filter-based queries.
    Paginates automatically up to max_results.
    """
    select = "id,display_name,abstract_inverted_index,doi,ids,publication_year,primary_location,type"
    results = []
    cursor = "*"
    per_page = min(max_results, 200)

    while len(results) < max_results:
        params = {
            "per_page": min(per_page, max_results - len(results)),
            "select": select,
            "cursor": cursor,
        }
        if filter_str:
            params["filter"] = filter_str
        else:
            params["search"] = query
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY

        r = requests.get(f"{OPENALEX_BASE}/works", params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("results", [])
        results.extend(batch)
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor or not batch:
            break
        cursor = next_cursor

    return [_normalize_openalex(w) for w in results[:max_results]]


def _normalize_openalex(work: dict) -> dict:
    """Convert OpenAlex work dict to normalized paper dict."""
    abstract = ""
    aii = work.get("abstract_inverted_index")
    if aii:
        words = [""] * (max(max(v) for v in aii.values()) + 1)
        for word, positions in aii.items():
            for pos in positions:
                words[pos] = word
        abstract = " ".join(w for w in words if w)

    ids = work.get("ids", {})
    pmid = ids.get("pmid", "")
    if pmid and pmid.startswith("https://pubmed.ncbi.nlm.nih.gov/"):
        pmid = pmid.split("/")[-2] if pmid.endswith("/") else pmid.split("/")[-1]

    doi = work.get("doi", "") or ""
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]

    primary_loc = work.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    journal = source.get("display_name", "")

    return {
        "title": work.get("display_name", ""),
        "abstract": abstract,
        "doi": doi,
        "pmid": pmid,
        "year": work.get("publication_year"),
        "journal": journal,
        "source_uri": work.get("id", ""),
    }


def fetch_by_doi_openalex(doi: str):
    """Fetch a single work by DOI from OpenAlex."""
    params = {"select": "id,display_name,abstract_inverted_index,doi,ids,publication_year,primary_location"}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    try:
        r = requests.get(
            f"{OPENALEX_BASE}/works/https://doi.org/{doi}",
            params=params,
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        return _normalize_openalex(r.json())
    except Exception:
        return None


def fetch_by_doi_ncbi(doi: str):
    """Fetch a paper by DOI via NCBI esearch."""
    try:
        r = requests.get(
            f"{NCBI_BASE}/esearch.fcgi",
            params=_ncbi_params(db="pubmed", term=f"{doi}[doi]", retmax=1),
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return None
        time.sleep(0.34)
        papers = search_pubmed(f"{doi}[doi]", max_results=1)
        return papers[0] if papers else None
    except Exception:
        return None


def fetch_by_pmid_epmc(pmid: str):
    """Fetch a single paper by PMID via EPMC."""
    _, publications = run_epmc_query(f"EXT_ID:{pmid}", page_size=10, max_results=1)
    if not publications:
        return None
    return parse_epmc_record(publications[0])


# =============================================================================
# BIORXIV/MEDRXIV CONNECTOR
# =============================================================================

def search_biorxiv(query: str, max_results: int = 20, server: str = "biorxiv") -> list:
    """Search bioRxiv/medRxiv. Fetches recent preprints and filters by keyword."""
    base = BIORXIV_BASE if server == "biorxiv" else MEDRXIV_BASE
    papers = []
    cursor = 0
    query_lower = query.lower()

    while len(papers) < max_results:
        r = requests.get(f"{base}/{server}/30d/{cursor}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        collection = r.json().get("collection", [])
        if not collection:
            break

        for item in collection:
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            if query_lower in title.lower() or query_lower in abstract.lower():
                doi = item.get("doi", "")
                papers.append({
                    "title": title,
                    "abstract": abstract,
                    "doi": doi,
                    "year": int(item.get("date", "0000")[:4]) if item.get("date") else None,
                    "journal": f"{server.capitalize()} preprint",
                    "source_uri": f"https://doi.org/{doi}" if doi else "",
                })
            if len(papers) >= max_results:
                break

        cursor += 100
        if len(collection) < 100:
            break
        time.sleep(0.5)

    return papers[:max_results]


# =============================================================================
# COMMANDS
# =============================================================================

def cmd_search(args):
    """Search a literature source and store results."""
    source = args.source.lower()
    query = args.query

    if source == "epmc":
        # EPMC: cursor-based pagination, creates collection, uses rich metadata
        total_count, publications = run_epmc_query(
            query, page_size=args.page_size, max_results=args.max_results
        )

        if not publications:
            print(json.dumps({
                "success": True, "total_count": total_count, "stored_count": 0,
                "message": "No results found",
            }))
            return

        collection_id = args.collection_id or generate_id("collection")
        collection_name = args.collection or f"EPMC Search: {query[:50]}"
        timestamp = get_timestamp()

        with get_driver() as driver:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'insert $c isa alh-collection, has id "{collection_id}", '
                    f'has name "{escape_string(collection_name)}", '
                    f'has description "EPMC search results for: {escape_string(query)}", '
                    f'has alh-logical-query "{escape_string(query)}", '
                    f'has alh-is-extensional true, has created-at {timestamp};'
                ).resolve()
                tx.commit()

            stored_count = 0
            skipped_count = 0
            paper_ids = []

            for record in tqdm(publications, desc="Storing papers", file=sys.stderr):
                paper = parse_epmc_record(record)
                if paper:
                    try:
                        paper_id = insert_epmc_paper(driver, paper, collection_id)
                        paper_ids.append(paper_id)
                        stored_count += 1
                    except Exception as e:
                        print(f"Error storing paper {paper.get('doi')}: {e}", file=sys.stderr)
                        skipped_count += 1
                else:
                    skipped_count += 1

        print(json.dumps({
            "success": True,
            "collection_id": collection_id,
            "collection_name": collection_name,
            "query": query,
            "total_count": total_count,
            "fetched_count": len(publications),
            "stored_count": stored_count,
            "skipped_count": skipped_count,
        }, indent=2))

    else:
        # PubMed / OpenAlex / bioRxiv / medRxiv
        print(f"Searching {source} for: {query}", file=sys.stderr)

        if source == "pubmed":
            papers = search_pubmed(query, args.max_results or 20)
        elif source == "openalex":
            papers = search_openalex(query, args.max_results or 20, filter_str=getattr(args, "filter", None))
        elif source in ("biorxiv", "medrxiv"):
            papers = search_biorxiv(query, args.max_results or 20, server=source)
        else:
            print(json.dumps({"success": False, "error": f"Unknown source: {source}"}))
            sys.exit(1)

        if not papers:
            print(json.dumps({"success": True, "inserted": 0, "skipped": 0, "papers": []}))
            return

        inserted = 0
        skipped = 0
        result_papers = []
        collection_id = args.collection_id or args.collection

        with get_driver() as driver:
            for paper in papers:
                existing_id = paper_exists(driver, doi=paper.get("doi"), pmid=paper.get("pmid"))
                if existing_id:
                    skipped += 1
                    result_papers.append({"id": existing_id, "title": paper["title"], "status": "existing"})
                    if collection_id:
                        try:
                            add_to_collection(driver, existing_id, collection_id)
                        except Exception as e:
                            print(f"Warning: could not add {existing_id} to collection: {e}", file=sys.stderr)
                    continue

                pid = insert_paper(driver, paper)
                inserted += 1
                result_papers.append({"id": pid, "title": paper["title"], "status": "inserted"})

                if collection_id:
                    try:
                        add_to_collection(driver, pid, collection_id)
                    except Exception as e:
                        print(f"Warning: could not add {pid} to collection: {e}", file=sys.stderr)

        print(json.dumps({
            "success": True,
            "source": source,
            "query": query,
            "inserted": inserted,
            "skipped": skipped,
            "papers": result_papers,
        }, indent=2))


def cmd_count(args):
    """Count EPMC results for a query without storing."""
    params = {"format": "JSON", "pageSize": 1, "query": args.query}
    response = requests.get(EPMC_API_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    print(json.dumps({"success": True, "query": args.query, "count": data["hitCount"]}))


def cmd_ingest(args):
    """Fetch and store a single paper by DOI or PMID."""
    with get_driver() as driver:
        if args.doi:
            doi = args.doi.strip()
            if doi.startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/"):]

            print(f"Ingesting DOI: {doi}", file=sys.stderr)
            existing_id = paper_exists(driver, doi=doi)
            if existing_id:
                if args.collection:
                    try:
                        add_to_collection(driver, existing_id, args.collection)
                    except Exception as e:
                        print(f"Warning: could not add to collection: {e}", file=sys.stderr)
                print(json.dumps({"success": True, "paper_id": existing_id, "status": "existing"}))
                return

            # Try OpenAlex first (JSON, richer abstract), then PubMed
            paper = fetch_by_doi_openalex(doi)
            if not paper or not paper.get("title"):
                paper = fetch_by_doi_ncbi(doi)
            if not paper:
                print(json.dumps({"success": False, "error": f"Could not find DOI: {doi}"}))
                sys.exit(1)

        elif args.pmid:
            pmid = str(args.pmid).strip()
            print(f"Ingesting PMID: {pmid}", file=sys.stderr)
            existing_id = paper_exists(driver, pmid=pmid)
            if existing_id:
                if args.collection:
                    try:
                        add_to_collection(driver, existing_id, args.collection)
                    except Exception as e:
                        print(f"Warning: could not add to collection: {e}", file=sys.stderr)
                print(json.dumps({"success": True, "paper_id": existing_id, "status": "existing"}))
                return

            epmc_paper = fetch_by_pmid_epmc(pmid)
            if epmc_paper:
                pid = insert_epmc_paper(driver, epmc_paper, getattr(args, "collection", None))
                print(json.dumps({
                    "success": True, "paper_id": pid,
                    "title": epmc_paper.get("title"), "status": "inserted",
                }, indent=2))
                return
            # Fallback: search PubMed directly
            papers = search_pubmed(f"{pmid}[uid]", max_results=1)
            if not papers:
                print(json.dumps({"success": False, "error": f"Could not find PMID: {pmid}"}))
                sys.exit(1)
            paper = papers[0]
            doi = paper.get("doi")
        else:
            print(json.dumps({"success": False, "error": "Must provide --doi or --pmid"}))
            sys.exit(1)

        pid = insert_paper(driver, paper)
        if getattr(args, "collection", None) and args.collection:
            try:
                add_to_collection(driver, pid, args.collection)
            except Exception as e:
                print(f"Warning: {e}", file=sys.stderr)

    print(json.dumps({
        "success": True,
        "paper_id": pid,
        "title": paper.get("title"),
        "doi": paper.get("doi"),
        "status": "inserted",
    }, indent=2))


def arxiv_pdf_url(doi: str) -> str | None:
    """Return arXiv PDF URL from a DOI like '10.48550/arxiv.2511.02824', else None."""
    doi_lower = doi.lower()
    if "arxiv." in doi_lower:
        arxiv_id = doi_lower.split("arxiv.")[-1]
        return f"https://arxiv.org/pdf/{arxiv_id}"
    return None


def cmd_fetch_pdf(args):
    """Download a paper PDF, extract full text, save both to disk, store artifact in TypeDB."""
    if not PDFPLUMBER_AVAILABLE:
        print(json.dumps({"success": False,
                          "error": "pdfplumber not installed. Run: uv add pdfplumber"}))
        sys.exit(1)
    if not CACHE_AVAILABLE:
        print(json.dumps({"success": False,
                          "error": "skillful_alhazen.utils.cache not available"}))
        sys.exit(1)

    paper_id = args.id
    pdf_url = None
    paper_name = ""

    with get_driver() as driver:
        # Resolve paper from TypeDB
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $p isa scilit-paper, has id "{escape_string(paper_id)}"; '
                f'fetch {{ "name": $p.name, "doi": $p.scilit-doi, "scilit-arxiv-id": $p.scilit-arxiv-id }};'
            ).resolve())
        if not results:
            print(json.dumps({"success": False, "error": f"Paper not found: {paper_id}"}))
            sys.exit(1)

        p = results[0]
        paper_name = p.get("name") or ""
        doi = p.get("doi") or ""
        arxiv_id_attr = p.get("scilit-arxiv-id") or ""

        # Check for existing pdf artifact to avoid re-download
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing = list(tx.query(
                f'match $p isa scilit-paper, has id "{escape_string(paper_id)}"; '
                f'$a isa scilit-pdf-fulltext; '
                f'(artifact: $a, referent: $p) isa alh-representation; '
                f'fetch {{ "id": $a.id, "cache-path": $a.cache-path, "source-uri": $a.source-uri }};'
            ).resolve())
        if existing and not getattr(args, "force", False):
            art = existing[0]
            artifact_id = art.get("id")
            text_cache_path = art.get("cache-path") or ""
            pdf_cache_path = (text_cache_path.replace("text/", "pdf/").replace(".txt", ".pdf")
                              if text_cache_path else "")
            print(json.dumps({
                "success": True,
                "paper_id": paper_id,
                "artifact_id": artifact_id,
                "status": "existing",
                "text_cache_path": text_cache_path,
                "pdf_cache_path": pdf_cache_path,
                "source_uri": art.get("source-uri"),
            }, indent=2))
            return

    # Build PDF URL
    if arxiv_id_attr:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id_attr}"
    elif doi:
        pdf_url = arxiv_pdf_url(doi)
    if args.url:
        pdf_url = args.url  # explicit override
    if not pdf_url:
        print(json.dumps({"success": False,
                          "error": "Cannot determine PDF URL. Provide --url explicitly."}))
        sys.exit(1)

    print(f"Downloading PDF from {pdf_url} ...", file=sys.stderr)
    resp = requests.get(pdf_url, timeout=60, allow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; alhazen/1.0)"})
    resp.raise_for_status()
    pdf_bytes = resp.content

    if pdf_bytes[:4] != b"%PDF":
        print(json.dumps({"success": False,
                          "error": "Response is not a PDF (bad URL or access denied)"}))
        sys.exit(1)

    # Generate single artifact_id used as stem for BOTH cache files
    artifact_id = generate_id("artifact")

    # Save PDF binary  ->  pdf/{artifact_id}.pdf
    pdf_cache = save_to_cache(artifact_id, pdf_bytes, "application/pdf")

    # Extract full text - NO character cap
    print(f"Extracting text ({len(pdf_bytes):,} bytes, {pdf_cache['full_path']}) ...",
          file=sys.stderr)
    import io as _io
    all_pages = []
    with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                all_pages.append(page_text)

    full_text = "\n\n".join(all_pages)
    print(f"Extracted {len(full_text):,} chars from {page_count} pages.", file=sys.stderr)

    # Save extracted text  ->  text/{artifact_id}.txt
    text_cache = save_to_cache(artifact_id, full_text, "text/plain")

    timestamp = get_timestamp()

    # Insert scilit-pdf-fulltext artifact into TypeDB
    name_esc = escape_string(f"{paper_name} [PDF text]")
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'insert $a isa scilit-pdf-fulltext, '
                f'has id "{artifact_id}", '
                f'has name "{name_esc}", '
                f'has source-uri "{escape_string(pdf_url)}", '
                f'has cache-path "{escape_string(text_cache["cache_path"])}", '
                f'has mime-type "text/plain", '
                f'has file-size {text_cache["file_size"]}, '
                f'has content-hash "{text_cache["content_hash"]}", '
                f'has format "pdf-extracted-text", '
                f'has created-at {timestamp};'
            ).resolve()
            tx.commit()

        # Link artifact -> paper via representation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $p isa scilit-paper, has id "{escape_string(paper_id)}"; '
                f'$a isa scilit-pdf-fulltext, has id "{artifact_id}"; '
                f'insert (artifact: $a, referent: $p) isa alh-representation;'
            ).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "paper_id": paper_id,
        "paper_name": paper_name,
        "artifact_id": artifact_id,
        "status": "inserted",
        "source_uri": pdf_url,
        "pdf_cache_path": pdf_cache["cache_path"],
        "text_cache_path": text_cache["cache_path"],
        "pdf_full_path": pdf_cache["full_path"],
        "text_full_path": text_cache["full_path"],
        "page_count": page_count,
        "char_count": len(full_text),
        "file_size_bytes": text_cache["file_size"],
    }, indent=2))


def cmd_show(args):
    """Show a paper's details for sensemaking."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            result = list(tx.query(
                f'match $p isa scilit-paper, has id "{args.id}"; '
                f'fetch {{ "id": $p.id, "name": $p.name, "abstract-text": $p.abstract-text, '
                f'"doi": $p.scilit-doi, "pmid": $p.scilit-pmid, "year": $p.scilit-publication-year, '
                f'"journal": $p.scilit-journal-name, "source-uri": $p.source-uri }};'
            ).resolve())

            if not result:
                print(json.dumps({"success": False, "error": "Paper not found"}))
                sys.exit(1)

            notes = list(tx.query(
                f'match $p isa scilit-paper, has id "{args.id}"; '
                f'(note: $n, subject: $p) isa alh-aboutness; '
                f'fetch {{ "id": $n.id, "name": $n.name, "content": $n.content }};'
            ).resolve())

            art_results = list(tx.query(
                f'match $p isa scilit-paper, has id "{escape_string(args.id)}"; '
                f'$a isa scilit-pdf-fulltext; '
                f'(artifact: $a, referent: $p) isa alh-representation; '
                f'fetch {{ "id": $a.id, "source-uri": $a.source-uri, '
                f'"cache-path": $a.cache-path, "file-size": $a.file-size }};'
            ).resolve())

    paper = {k: v for k, v in result[0].items() if v is not None}
    print(json.dumps({
        "success": True,
        "paper": paper,
        "notes": [{k: v for k, v in n.items() if v is not None} for n in notes],
        "pdf_artifacts": [{k: v for k, v in a.items() if v is not None} for a in art_results],
    }, indent=2))


def cmd_list(args):
    """List papers, optionally filtered by collection."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if args.collection:
                query = (
                    f'match $c isa alh-collection, has id "{args.collection}"; '
                    f'(collection: $c, member: $p) isa alh-collection-membership; '
                    f'$p isa scilit-paper; '
                    f'fetch {{ "id": $p.id, "name": $p.name, "doi": $p.scilit-doi, "year": $p.scilit-publication-year }};'
                )
            else:
                query = (
                    'match $p isa scilit-paper; '
                    'fetch { "id": $p.id, "name": $p.name, "doi": $p.scilit-doi, "year": $p.scilit-publication-year };'
                )
            results = list(tx.query(query).resolve())

    papers = [{k: v for k, v in r.items() if v is not None} for r in results]
    print(json.dumps({
        "success": True,
        "papers": papers,
        "count": len(papers),
        "collection": args.collection if hasattr(args, "collection") else None,
    }, indent=2))


def cmd_list_collections(args):
    """List all collections created from searches."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                'match $c isa alh-collection, has alh-logical-query $q; '
                'fetch { "id": $c.id, "name": $c.name, "description": $c.description, '
                '"alh-logical-query": $c.alh-logical-query };'
            ).resolve())

    print(json.dumps({"success": True, "collections": results, "count": len(results)}, indent=2))


def cmd_list_by_keyword(args):
    """List papers tagged with a keyword, optionally scoped to a collection."""
    keyword = args.keyword
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if args.collection:
                query = (
                    f'match $c isa alh-collection, has id "{escape_string(args.collection)}"; '
                    f'(collection: $c, member: $p) isa alh-collection-membership; '
                    f'$p isa scilit-paper, has scilit-keyword "{escape_string(keyword)}", '
                    f'has scilit-publication-year $yr; '
                    f'fetch {{ "id": $p.id, "name": $p.name, "abstract": $p.abstract-text, '
                    f'"year": $yr, "doi": $p.scilit-doi, "journal": $p.scilit-journal-name }};'
                )
            else:
                query = (
                    f'match $p isa scilit-paper, has scilit-keyword "{escape_string(keyword)}", '
                    f'has scilit-publication-year $yr; '
                    f'fetch {{ "id": $p.id, "name": $p.name, "abstract": $p.abstract-text, '
                    f'"year": $yr, "doi": $p.scilit-doi, "journal": $p.scilit-journal-name }};'
                )
            results = list(tx.query(query).resolve())

    papers = [{k: v for k, v in r.items() if v is not None} for r in results]

    # Apply year-range filter in Python
    if args.year_from:
        papers = [p for p in papers if p.get("year") and int(p["year"]) >= args.year_from]
    if args.year_to:
        papers = [p for p in papers if p.get("year") and int(p["year"]) <= args.year_to]

    # Sort by year ascending
    papers.sort(key=lambda p: int(p.get("year", 0)))

    # Apply limit
    if args.limit:
        papers = papers[:args.limit]

    years = [int(p["year"]) for p in papers if p.get("year")]
    year_range = [min(years), max(years)] if years else []

    print(json.dumps({
        "success": True,
        "keyword": keyword,
        "collection": args.collection,
        "count": len(papers),
        "year_range": year_range,
        "papers": papers,
    }, indent=2))


# =============================================================================
# SEMANTIC SEARCH + CLUSTERING COMMANDS
# =============================================================================

def _get_collection_papers(driver, collection_id: str) -> list:
    """Fetch all scilit-papers in a collection from TypeDB."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        results = list(tx.query(
            f'match $c isa alh-collection, has id "{collection_id}"; '
            f'(collection: $c, member: $p) isa alh-collection-membership; '
            f'$p isa scilit-paper; '
            f'fetch {{ "id": $p.id, "name": $p.name, '
            f'"abstract-text": $p.abstract-text, '
            f'"doi": $p.scilit-doi, "year": $p.scilit-publication-year }};'
        ).resolve())
    return [{k: v for k, v in r.items() if v is not None} for r in results]


def cmd_embed(args):
    """Fetch papers from TypeDB, embed with Voyage AI, upsert into Qdrant."""
    try:
        from skillful_alhazen.utils.embeddings import VOYAGE_BATCH_SIZE, embed_texts
        from skillful_alhazen.utils.vector_store import (
            ensure_collection, get_existing_paper_ids, get_qdrant_client, upsert_papers,
        )
    except ImportError as e:
        print(json.dumps({"success": False, "error": f"Missing dependency: {e}"}))
        sys.exit(1)

    if not VOYAGE_API_KEY:
        print(json.dumps({"success": False, "error": "VOYAGE_API_KEY not set"}))
        sys.exit(1)

    collection_id = args.collection
    print(f"Fetching papers for collection {collection_id}...", file=sys.stderr)

    with get_driver() as driver:
        papers = _get_collection_papers(driver, collection_id)

    if not papers:
        print(json.dumps({"success": False, "error": "No papers found in collection"}))
        sys.exit(1)

    print(f"Found {len(papers)} papers", file=sys.stderr)

    qdrant = get_qdrant_client()
    ensure_collection(qdrant)

    all_ids = [p["id"] for p in papers]
    if args.reembed:
        already_in_qdrant = 0
        to_embed = papers
    else:
        existing_ids = get_existing_paper_ids(qdrant, all_ids)
        already_in_qdrant = len(existing_ids)
        to_embed = [p for p in papers if p["id"] not in existing_ids]

    if args.limit > 0:
        to_embed = to_embed[:args.limit]

    print(f"Embedding {len(to_embed)} papers ({already_in_qdrant} already in Qdrant)...", file=sys.stderr)

    if not to_embed:
        print(json.dumps({
            "success": True, "embedded": 0, "skipped": already_in_qdrant,
            "collection_id": collection_id,
        }, indent=2))
        return

    texts = [f"{p.get('name', '')}\n\n{p.get('abstract-text', '')}" for p in to_embed]

    all_vectors = []
    for i in range(0, len(texts), VOYAGE_BATCH_SIZE):
        batch_end = min(i + VOYAGE_BATCH_SIZE, len(texts))
        print(f"  Embedding {i + 1}-{batch_end} / {len(texts)}...", file=sys.stderr)
        batch_vectors = embed_texts(texts[i:batch_end], input_type="document")
        all_vectors.extend(batch_vectors)

    points = [
        {
            "paper_id": p["id"],
            "vector": v,
            "title": p.get("name", ""),
            "collection_ids": [collection_id],
            "doi": p.get("doi", ""),
            "year": p.get("year"),
        }
        for p, v in zip(to_embed, all_vectors)
    ]
    upsert_papers(qdrant, points)

    print(json.dumps({
        "success": True,
        "embedded": len(to_embed),
        "skipped": already_in_qdrant,
        "collection_id": collection_id,
    }, indent=2))


def cmd_search_semantic(args):
    """Embed a query and return similar papers from Qdrant."""
    try:
        from skillful_alhazen.utils.embeddings import embed_texts
        from skillful_alhazen.utils.vector_store import get_qdrant_client, search_similar
    except ImportError as e:
        print(json.dumps({"success": False, "error": f"Missing dependency: {e}"}))
        sys.exit(1)

    if not VOYAGE_API_KEY:
        print(json.dumps({"success": False, "error": "VOYAGE_API_KEY not set"}))
        sys.exit(1)

    print(f"Embedding query: {args.query}", file=sys.stderr)
    query_vector = embed_texts([args.query], input_type="query")[0]

    qdrant = get_qdrant_client()
    results = search_similar(qdrant, query_vector, collection_id=args.collection, limit=args.limit)

    print(json.dumps({
        "success": True,
        "query": args.query,
        "collection": args.collection,
        "results": results,
    }, indent=2))


def cmd_cluster(args):
    """Cluster collection embeddings with UMAP + HDBSCAN."""
    try:
        import hdbscan
        import numpy as np
        import umap
        from skillful_alhazen.utils.vector_store import get_collection_vectors, get_qdrant_client
    except ImportError as e:
        print(json.dumps({"success": False, "error": f"Missing dependency: {e}"}))
        sys.exit(1)

    collection_id = args.collection
    print(f"Loading vectors for collection {collection_id}...", file=sys.stderr)

    qdrant = get_qdrant_client()
    points = get_collection_vectors(qdrant, collection_id)

    if not points:
        print(json.dumps({"success": False, "error": "No vectors found for collection"}))
        sys.exit(1)

    n = len(points)
    print(f"Reducing {n} papers with UMAP...", file=sys.stderr)

    vectors = np.array([p["vector"] for p in points], dtype=np.float32)
    reducer = umap.UMAP(
        n_components=50, n_neighbors=min(15, n - 1),
        min_dist=0.0, metric="cosine", random_state=42,
    )
    reduced = reducer.fit_transform(vectors)

    print(f"Clustering with HDBSCAN (min_cluster_size={args.min_cluster_size})...", file=sys.stderr)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=args.min_cluster_size, metric="euclidean")
    labels = clusterer.fit_predict(reduced)

    clusters = []
    for label in sorted(set(labels)):
        if label == -1:
            continue
        mask = labels == label
        cluster_indices = np.where(mask)[0]
        centroid = reduced[cluster_indices].mean(axis=0)
        dists = np.linalg.norm(reduced[cluster_indices] - centroid, axis=1)
        closest_idx = np.argsort(dists)[:5]
        representative_papers = [
            {
                "paper_id": points[cluster_indices[i]]["paper_id"],
                "title": points[cluster_indices[i]]["title"],
                "doi": points[cluster_indices[i]].get("doi", ""),
            }
            for i in closest_idx
        ]
        clusters.append({
            "cluster_id": int(label),
            "size": int(mask.sum()),
            "representative_papers": representative_papers,
        })

    noise_count = int((labels == -1).sum())

    if not args.dry_run and args.labels:
        label_map = {}
        for entry in args.labels:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                try:
                    label_map[int(parts[0])] = parts[1]
                except ValueError:
                    pass

        if label_map:
            print("Writing theme tags to TypeDB...", file=sys.stderr)
            with get_driver() as driver:
                for cluster in clusters:
                    cid = cluster["cluster_id"]
                    theme = label_map.get(cid)
                    if not theme:
                        continue
                    cluster_paper_ids = [
                        points[i]["paper_id"] for i in np.where(labels == cid)[0]
                    ]
                    theme_escaped = escape_string(theme)
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        for pid in cluster_paper_ids:
                            try:
                                tx.query(
                                    f'match $p isa scilit-paper, has id "{pid}"; '
                                    f'insert $p has scilit-keyword "{theme_escaped}";'
                                ).resolve()
                            except Exception:
                                pass
                        tx.commit()
                    print(f"  Tagged {len(cluster_paper_ids)} papers with '{theme}'", file=sys.stderr)

    print(json.dumps({
        "success": True,
        "collection_id": collection_id,
        "total_papers": len(points),
        "clustered": len(points) - noise_count,
        "noise": noise_count,
        "num_clusters": len(clusters),
        "clusters": clusters,
    }, indent=2))


def cmd_plot_clusters(args):
    """Generate a 2D UMAP scatter plot coloured by HDBSCAN cluster."""
    try:
        import hdbscan
        import matplotlib.pyplot as plt
        import numpy as np
        import umap
        from skillful_alhazen.utils.vector_store import get_collection_vectors, get_qdrant_client
    except ImportError as e:
        print(json.dumps({"success": False, "error": f"Missing dependency: {e}"}))
        sys.exit(1)

    collection_id = args.collection
    output = args.output

    print(f"Loading vectors for collection {collection_id}...", file=sys.stderr)
    qdrant = get_qdrant_client()
    points = get_collection_vectors(qdrant, collection_id)

    if not points:
        print(json.dumps({"success": False, "error": "No vectors found for collection"}))
        sys.exit(1)

    n = len(points)
    vectors = np.array([p["vector"] for p in points], dtype=np.float32)

    print("UMAP 50-dim for clustering...", file=sys.stderr)
    reducer_50 = umap.UMAP(
        n_components=50, n_neighbors=min(15, n - 1),
        min_dist=0.0, metric="cosine", random_state=42,
    )
    reduced_50 = reducer_50.fit_transform(vectors)

    print(f"HDBSCAN (min_cluster_size={args.min_cluster_size})...", file=sys.stderr)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=args.min_cluster_size, metric="euclidean")
    labels = clusterer.fit_predict(reduced_50)

    print("UMAP 2-dim for plot...", file=sys.stderr)
    reducer_2d = umap.UMAP(
        n_components=2, n_neighbors=min(15, n - 1),
        min_dist=0.1, metric="euclidean", random_state=42,
    )
    xy = reducer_2d.fit_transform(reduced_50)

    unique_labels = sorted(set(labels))
    cluster_labels = [l for l in unique_labels if l != -1]
    cmap = plt.colormaps["tab20"].resampled(max(len(cluster_labels), 1))
    colour_map = {l: cmap(i % 20) for i, l in enumerate(cluster_labels)}
    colour_map[-1] = (0.8, 0.8, 0.8, 0.3)
    colours = [colour_map[l] for l in labels]

    label_map = {}
    if args.labels:
        for entry in args.labels:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                try:
                    label_map[int(parts[0])] = parts[1]
                except ValueError:
                    pass

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.scatter(xy[:, 0], xy[:, 1], c=colours, s=6, linewidths=0)

    for label in cluster_labels:
        mask = labels == label
        cx, cy = xy[mask, 0].mean(), xy[mask, 1].mean()
        size = mask.sum()
        theme = label_map.get(label)
        text = f"{theme}\n(C{label}, n={size})" if theme else f"C{label} (n={size})"
        ax.annotate(text, (cx, cy), fontsize=7, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.75, lw=0))

    noise_count = (labels == -1).sum()
    clustered = n - noise_count
    ax.set_title(
        f"Literature corpus -- {n} papers, {len(cluster_labels)} clusters, "
        f"{clustered} assigned ({noise_count} noise)\n"
        f"UMAP(cosine->50d) + HDBSCAN(min_size={args.min_cluster_size})",
        fontsize=11,
    )
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    plt.close()

    print(json.dumps({
        "success": True, "output": output,
        "num_clusters": len(cluster_labels),
        "clustered": int(clustered),
        "noise": int(noise_count),
        "total": n,
    }, indent=2))


# =============================================================================
# APT SECTION EMBEDDING COMMANDS
# =============================================================================

def cmd_embed_sections(args):
    """Fetch scilit-section fragments for a paper, embed them, upsert into apt-sections Qdrant collection."""
    try:
        from skillful_alhazen.utils.embeddings import VOYAGE_BATCH_SIZE, embed_texts
        from skillful_alhazen.utils.vector_store import get_qdrant_client
        from qdrant_client import models as qdrant_models
    except ImportError as e:
        print(json.dumps({"success": False, "error": f"Missing dependency: {e}"}))
        sys.exit(1)

    if not VOYAGE_API_KEY:
        print(json.dumps({"success": False, "error": "VOYAGE_API_KEY not set"}))
        sys.exit(1)

    paper_id = args.paper_id
    collection_name = args.collection
    mondo_id = args.tag_mondo_id or ""

    print(f"Fetching sections for paper {paper_id}...", file=sys.stderr)

    query = (
        f'match '
        f'$paper isa scilit-paper, has id "{paper_id}"; '
        f'(artifact: $artifact, subject: $paper) isa alh-representation; '
        f'$section isa scilit-section; '
        f'(whole: $artifact, part: $section) isa alh-fragmentation; '
        f'$section has id $sid; '
        f'$section has content $content; '
        f'fetch {{ "section_id": $sid, "content": $content }};'
    )

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(query).resolve())

    if not results:
        print(json.dumps({
            "success": False,
            "error": f"No scilit-section fragments found for paper {paper_id}",
            "paper_id": paper_id,
        }))
        sys.exit(1)

    section_count = len(results)
    print(f"Found {section_count} sections, embedding...", file=sys.stderr)

    texts = [r["content"] for r in results]
    section_ids = [r["section_id"] for r in results]

    all_vectors = []
    for i in range(0, len(texts), VOYAGE_BATCH_SIZE):
        batch_end = min(i + VOYAGE_BATCH_SIZE, len(texts))
        print(f"  Embedding {i + 1}-{batch_end} / {len(texts)}...", file=sys.stderr)
        batch_vectors = embed_texts(texts[i:batch_end], input_type="document")
        all_vectors.extend(batch_vectors)

    qdrant = get_qdrant_client()

    # Ensure collection exists
    existing_collections = [c.name for c in qdrant.get_collections().collections]
    if collection_name not in existing_collections:
        print(f"Creating Qdrant collection '{collection_name}'...", file=sys.stderr)
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=VECTOR_DIM_SECTIONS,
                distance=qdrant_models.Distance.COSINE,
            ),
        )

    # Upsert points
    points = []
    for section_id, vector, content in zip(section_ids, all_vectors, texts):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, section_id))
        points.append(qdrant_models.PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "section_id": section_id,
                "paper_id": paper_id,
                "mondo_id": mondo_id,
                "content_preview": content[:200] if content else "",
            },
        ))

    qdrant.upsert(collection_name=collection_name, points=points)
    print(f"Upserted {len(points)} section vectors into '{collection_name}'", file=sys.stderr)

    print(json.dumps({
        "success": True,
        "paper_id": paper_id,
        "collection": collection_name,
        "mondo_id": mondo_id,
        "section_count": section_count,
        "embedded_count": len(points),
    }, indent=2))


def cmd_search_sections(args):
    """Semantic search over scilit-section fragments in the apt-sections Qdrant collection."""
    try:
        from skillful_alhazen.utils.embeddings import embed_texts
        from skillful_alhazen.utils.vector_store import get_qdrant_client
        from qdrant_client import models as qdrant_models
    except ImportError as e:
        print(json.dumps({"success": False, "error": f"Missing dependency: {e}"}))
        sys.exit(1)

    if not VOYAGE_API_KEY:
        print(json.dumps({"success": False, "error": "VOYAGE_API_KEY not set"}))
        sys.exit(1)

    query_text = args.query
    collection_name = getattr(args, "collection", APT_SECTIONS_COLLECTION)
    mondo_id = args.mondo_id or ""
    top_k = args.top_k

    print(f"Embedding query: {query_text}", file=sys.stderr)
    query_vector = embed_texts([query_text], input_type="query")[0]

    qdrant = get_qdrant_client()

    # Build optional mondo_id filter
    search_filter = None
    if mondo_id:
        search_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="mondo_id",
                    match=qdrant_models.MatchValue(value=mondo_id),
                )
            ]
        )

    hits = qdrant.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k,
        query_filter=search_filter,
        with_payload=True,
    )

    results = []
    for hit in hits:
        payload = hit.payload or {}
        results.append({
            "section_id": payload.get("section_id", ""),
            "paper_id": payload.get("paper_id", ""),
            "mondo_id": payload.get("mondo_id", ""),
            "score": hit.score,
            "content_preview": payload.get("content_preview", ""),
        })

    print(json.dumps({
        "success": True,
        "query": query_text,
        "collection": collection_name,
        "mondo_id": mondo_id,
        "results": results,
    }, indent=2))


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scientific Literature CLI - multi-source paper search and ingestion"
    )
    subparsers = parser.add_subparsers(dest="command")

    # search
    p = subparsers.add_parser("search", help="Search a literature source and store results")
    p.add_argument("--source", required=True,
                   choices=["epmc", "pubmed", "openalex", "biorxiv", "medrxiv"],
                   help="Literature source to search")
    p.add_argument("--query", "-q", default="", help="Search query (required for epmc/pubmed/biorxiv; optional for openalex when --filter is used)")
    p.add_argument("--collection", "-c", help="Collection name (EPMC) or ID (others)")
    p.add_argument("--collection-id", help="Specific collection ID (EPMC: overrides auto-generated ID)")
    p.add_argument("--max-results", "-m", type=int, help="Maximum results to fetch")
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="EPMC: results per page")
    p.add_argument("--filter", help="OpenAlex filter string (e.g. 'cites:W2565424224'); overrides --query for OpenAlex")

    # count
    p = subparsers.add_parser("count", help="Count EPMC results for a query (no storage)")
    p.add_argument("--query", "-q", required=True, help="EPMC search query")

    # ingest
    p = subparsers.add_parser("ingest", help="Fetch and store a paper by DOI or PMID")
    p.add_argument("--doi", help="DOI (with or without https://doi.org/ prefix)")
    p.add_argument("--pmid", help="PubMed ID")
    p.add_argument("--collection", help="Collection ID to add to")

    # fetch-pdf
    p = subparsers.add_parser("fetch-pdf",
        help="Download paper PDF, extract full text, store both to disk and TypeDB")
    p.add_argument("--id", required=True,
        help="scilit-paper TypeDB ID (e.g. scilit-paper-fd0a1617ef99)")
    p.add_argument("--url",
        help="Override PDF URL (default: derived from arXiv DOI)")
    p.add_argument("--force", action="store_true",
        help="Re-download even if artifact already exists")

    # show
    p = subparsers.add_parser("show", help="Show a paper for sensemaking")
    p.add_argument("--id", required=True, help="Paper ID (scilit-paper-...)")

    # list
    p = subparsers.add_parser("list", help="List papers in the knowledge graph")
    p.add_argument("--collection", help="Filter by collection ID")

    # list-collections
    subparsers.add_parser("list-collections", help="List all scilit search collections")

    # list-by-keyword
    p = subparsers.add_parser("list-by-keyword", help="List papers tagged with a keyword")
    p.add_argument("--keyword", "-k", required=True, help="Keyword tag to filter by")
    p.add_argument("--collection", "-c", help="Scope to this collection ID")
    p.add_argument("--year-from", type=int, dest="year_from", help="Earliest year (inclusive)")
    p.add_argument("--year-to", type=int, dest="year_to", help="Latest year (inclusive)")
    p.add_argument("--limit", "-n", type=int, help="Max results to return")

    # embed
    p = subparsers.add_parser("embed", help="Embed collection papers with Voyage AI into Qdrant")
    p.add_argument("--collection", required=True, help="Collection ID to embed")
    p.add_argument("--reembed", action="store_true", help="Re-embed even if paper already in Qdrant")
    p.add_argument("--limit", type=int, default=0, help="Max papers to embed (0=all)")

    # search-semantic
    p = subparsers.add_parser("search-semantic", help="Semantic similarity search via Qdrant")
    p.add_argument("--query", required=True, help="Natural language query")
    p.add_argument("--collection", help="Filter results to this collection ID")
    p.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")

    # cluster
    p = subparsers.add_parser("cluster", help="HDBSCAN clustering of collection embeddings")
    p.add_argument("--collection", required=True, help="Collection ID to cluster")
    p.add_argument("--min-cluster-size", type=int, default=15,
                   help="HDBSCAN min_cluster_size (default: 15)")
    p.add_argument("--dry-run", action="store_true",
                   help="Output cluster info without writing tags to TypeDB")
    p.add_argument("--labels", nargs="*",
                   help="Theme labels: 0:theme-name 1:other-theme ...")

    # plot-clusters
    p = subparsers.add_parser("plot-clusters", help="2D UMAP scatter plot coloured by cluster")
    p.add_argument("--collection", required=True, help="Collection ID")
    p.add_argument("--min-cluster-size", type=int, default=10,
                   help="HDBSCAN min_cluster_size (default: 10)")
    p.add_argument("--output", default="clusters.png", help="Output PNG path")
    p.add_argument("--labels", nargs="*", help="Theme labels: 0:theme-a 1:theme-b ...")

    # embed-sections
    p_embed_sections = subparsers.add_parser(
        "embed-sections",
        help="Embed scilit-section fragments for a paper into the apt-sections Qdrant collection",
    )
    p_embed_sections.add_argument("--paper-id", required=True,
        help="scilit-paper TypeDB ID (e.g. scilit-paper-abc123)")
    p_embed_sections.add_argument("--collection", default=APT_SECTIONS_COLLECTION,
        help=f"Qdrant collection name (default: {APT_SECTIONS_COLLECTION})")
    p_embed_sections.add_argument("--tag-mondo-id", default="",
        help="MONDO ID to tag all sections with (e.g. MONDO:0100135)")
    p_embed_sections.set_defaults(func=cmd_embed_sections)

    # search-sections
    p_search_sections = subparsers.add_parser(
        "search-sections",
        help="Semantic search over scilit-section fragments in the apt-sections Qdrant collection",
    )
    p_search_sections.add_argument("--query", required=True,
        help="Natural language query")
    p_search_sections.add_argument("--collection", default=APT_SECTIONS_COLLECTION,
        help=f"Qdrant collection name (default: {APT_SECTIONS_COLLECTION})")
    p_search_sections.add_argument("--mondo-id", default="",
        help="Filter results to sections tagged with this MONDO ID")
    p_search_sections.add_argument("--top-k", type=int, default=10,
        help="Number of results to return (default: 10)")
    p_search_sections.set_defaults(func=cmd_search_sections)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    SEMANTIC_COMMANDS = {"embed", "search-semantic", "cluster", "plot-clusters",
                         "embed-sections", "search-sections"}
    NON_DB_COMMANDS = {"count"} | SEMANTIC_COMMANDS

    if args.command not in NON_DB_COMMANDS:
        if not TYPEDB_AVAILABLE:
            print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
            sys.exit(1)

    if args.command not in SEMANTIC_COMMANDS and not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests not installed. Run: uv add requests"}))
        sys.exit(1)

    commands = {
        "search": cmd_search,
        "count": cmd_count,
        "ingest": cmd_ingest,
        "fetch-pdf": cmd_fetch_pdf,
        "show": cmd_show,
        "list": cmd_list,
        "list-collections": cmd_list_collections,
        "list-by-keyword": cmd_list_by_keyword,
        "embed": cmd_embed,
        "search-semantic": cmd_search_semantic,
        "cluster": cmd_cluster,
        "plot-clusters": cmd_plot_clusters,
        "embed-sections": cmd_embed_sections,
        "search-sections": cmd_search_sections,
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
