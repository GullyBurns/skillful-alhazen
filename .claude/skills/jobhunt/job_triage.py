#!/usr/bin/env python3
"""LLM-based job candidate triage using local Ollama model.

Reads candidates from TypeDB, sends each to a local LLM for scoring (0.0-1.0),
and updates candidate status based on the score (>= 0.5 → reviewed, < 0.5 → dismissed).

Usage:
    # Triage all "new" candidates
    python job_triage.py triage

    # Triage with a specific model
    python job_triage.py triage --model qwen3:8b

    # Dry run (don't update TypeDB)
    python job_triage.py triage --dry-run

    # Test with a single candidate
    python job_triage.py test --title "Research Scientist, AI for Science" --location "San Francisco"
"""

import argparse
import json
import os
import re
import sys
import time

import requests

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# TypeDB imports
try:
    from typedb.driver import TypeDB, SessionType, TransactionType
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False

# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("TRIAGE_MODEL", "qwen3:8b")

# Candidate profile for triage prompt
CANDIDATE_PROFILE = """You are triaging job postings for a senior scientist/engineer with this background:
- 20+ years in scientific knowledge engineering, biomedical informatics, NLP
- Strong: Python, knowledge graphs, biomedical ontologies, scientific writing, AI/ML systems, agentic AI
- Some: machine learning, LLM evaluation, bioinformatics, experimental neuroscience
- Built AI systems for scientific literature analysis at scale (Chan Zuckerberg Initiative)
- Currently building TypeDB-powered scientific knowledge notebooks with Claude Code
- Looking for: research scientist, applied AI, knowledge engineering, AI for science roles
- Location: San Francisco Bay Area (in-person or hybrid preferred, remote OK)
- Level: Senior/Staff/Principal (not junior, not intern)
"""

TRIAGE_PROMPT = """{profile}

The candidate is NOT:
- A general software engineer or full-stack developer
- A data analyst or business intelligence professional
- A DevOps/SRE/infrastructure engineer
- A product manager or designer
- A junior/entry-level candidate

Score this job posting from 0.0 to 1.0 based on how well it matches the candidate.
A score of 0.5 is the hit/miss boundary: >= 0.5 means worth reviewing, < 0.5 means skip.

Scoring guide:
- 0.9-1.0: Perfect fit — scientific AI, knowledge engineering, biomedical informatics at the right level
- 0.7-0.9: Strong match — senior AI/ML at science-focused companies, NLP for science, AI agents for research
- 0.5-0.7: Moderate hit — related AI/ML role that partially overlaps with expertise
- 0.3-0.5: Weak miss — some AI relevance but wrong domain, level, or focus
- 0.0-0.3: Clear miss — generic engineering, unrelated domain, wrong level, no match

Job Title: {title}
Company/Source: {source}
Location: {location}
Department: {department}
Description snippet: {snippet}

Respond with ONLY a JSON object (no markdown, no explanation):
{{"score": 0.85, "reason": "one short sentence"}}"""


def get_driver():
    """Get TypeDB driver."""
    return TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")


def get_attr(entity_map: dict, attr_name: str, default=""):
    """Extract attribute value from TypeDB fetch result."""
    val = entity_map.get(attr_name)
    if val is None:
        return default
    if isinstance(val, dict):
        return val.get("value", default)
    if isinstance(val, list) and val:
        return val[0].get("value", default)
    return default


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def fetch_job_content(url: str) -> str:
    """Fetch job posting URL and extract text content.

    Returns extracted text (up to 3000 chars) or empty string on failure.
    """
    if not url or not BS4_AVAILABLE:
        return ""

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove non-content elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        return text[:3000]

    except Exception as e:
        print(f"  Fetch error for {url[:60]}: {e}", file=sys.stderr)
        return ""


def ollama_score(title: str, source: str, location: str,
                 department: str = "", snippet: str = "",
                 model: str = DEFAULT_MODEL) -> dict:
    """Call Ollama to score a job posting.

    Returns {"score": float, "reason": "..."}
    """
    prompt = TRIAGE_PROMPT.format(
        profile=CANDIDATE_PROFILE,
        title=title,
        source=source,
        location=location,
        department=department,
        snippet=snippet[:2000] if snippet else "(not available)",
    )

    try:
        # Use chat API with /no_think to disable Qwen3's thinking mode
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt + " /no_think"}],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                },
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        text = result.get("message", {}).get("content", "").strip()

        # Parse JSON from response (handle markdown wrapping)
        json_match = re.search(r'\{[^}]+\}', text)
        if json_match:
            parsed = json.loads(json_match.group())
            score = parsed.get("score")
            reason = parsed.get("reason", "")
            if score is not None:
                score = max(0.0, min(1.0, float(score)))
                return {"score": score, "reason": reason}

        # Fallback: try to find a bare number
        num_match = re.search(r'\b(0\.\d+|1\.0|0|1)\b', text)
        if num_match:
            score = max(0.0, min(1.0, float(num_match.group())))
            return {"score": score, "reason": text[:100]}

        return {"score": 0.0, "reason": f"parse error: {text[:100]}"}

    except Exception as e:
        print(f"  Ollama error: {e}", file=sys.stderr)
        return {"score": 0.0, "reason": str(e)}


def load_candidates(status: str = "new", limit: int = 0) -> list[dict]:
    """Load candidates from TypeDB."""
    candidates = []
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match $c isa jobhunt-candidate, has candidate-status "{status}";
                    fetch $c: id, name, job-url, location, external-job-id, description;'''
                results = list(tx.query.fetch(query))
                for r in results:
                    candidates.append({
                        "id": get_attr(r["c"], "id"),
                        "title": get_attr(r["c"], "name"),
                        "url": get_attr(r["c"], "job-url"),
                        "location": get_attr(r["c"], "location"),
                        "external_id": get_attr(r["c"], "external-job-id"),
                        "description": get_attr(r["c"], "description"),
                    })
    if limit:
        candidates = candidates[:limit]
    return candidates


def update_candidate_status(candidate_id: str, new_status: str,
                            relevance_score: float | None = None,
                            triage_reason: str | None = None):
    """Update candidate status and optionally relevance-score and triage-reason in TypeDB."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.delete(f'''match
                    $c isa jobhunt-candidate, has id "{candidate_id}", has candidate-status $s;
                    delete $c has $s;''')
                tx.query.insert(f'''match
                    $c isa jobhunt-candidate, has id "{candidate_id}";
                    insert $c has candidate-status "{new_status}";''')
                if relevance_score is not None:
                    # Delete old score if exists, then insert new one
                    tx.query.delete(f'''match
                        $c isa jobhunt-candidate, has id "{candidate_id}", has relevance-score $rs;
                        delete $c has $rs;''')
                    tx.query.insert(f'''match
                        $c isa jobhunt-candidate, has id "{candidate_id}";
                        insert $c has relevance-score {relevance_score};''')
                if triage_reason is not None:
                    # Delete old reason if exists, then insert new one
                    tx.query.delete(f'''match
                        $c isa jobhunt-candidate, has id "{candidate_id}", has triage-reason $tr;
                        delete $c has $tr;''')
                    tx.query.insert(f'''match
                        $c isa jobhunt-candidate, has id "{candidate_id}";
                        insert $c has triage-reason "{escape_string(triage_reason)}";''')
                tx.commit()


def extract_source_from_id(external_id: str) -> str:
    """Extract source platform from external ID."""
    if external_id.startswith("linkedin-"):
        return "LinkedIn"
    elif external_id.startswith("ashby-"):
        return "Ashby/OpenAI"
    elif external_id.startswith("remotive-"):
        return "Remotive"
    # Greenhouse IDs are numeric
    return "Greenhouse"


def cmd_triage(args):
    """Run LLM triage on candidates."""
    model = args.model or DEFAULT_MODEL
    dry_run = args.dry_run
    no_fetch = args.no_fetch
    batch_size = args.batch_size or 50

    print(f"Loading candidates (status={args.status})...", file=sys.stderr)
    candidates = load_candidates(status=args.status, limit=args.limit)
    print(f"  Found {len(candidates)} candidates to triage", file=sys.stderr)

    if not candidates:
        print(json.dumps({"success": True, "message": "No candidates to triage", "total": 0}))
        return

    # Check Ollama is running
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        if not any(model in m for m in models):
            print(f"  Warning: model '{model}' not found in Ollama. Available: {models}",
                  file=sys.stderr)
    except Exception as e:
        print(f"  Error connecting to Ollama: {e}", file=sys.stderr)
        return

    print(f"  Using model: {model}", file=sys.stderr)
    print(f"  Dry run: {dry_run}", file=sys.stderr)

    reviewed = []
    dismissed = []
    errors = []
    scores = []
    start_time = time.time()

    for i, candidate in enumerate(candidates):
        source = extract_source_from_id(candidate.get("external_id", ""))

        # Get job posting content: fetch URL first, fall back to stored description
        snippet = ""
        fetch_tag = ""
        if not no_fetch and candidate.get("url"):
            snippet = fetch_job_content(candidate["url"])
            if snippet:
                fetch_tag = "[fetched]"
        if not snippet and candidate.get("description"):
            snippet = candidate["description"]
            fetch_tag = fetch_tag or "[stored]"
        if not snippet:
            snippet = "(not available)"
            fetch_tag = fetch_tag or "[none]"

        result = ollama_score(
            title=candidate["title"],
            source=source,
            location=candidate["location"],
            snippet=snippet,
            model=model,
        )

        score = result["score"]
        reason = result["reason"]
        scores.append(score)

        if score >= 0.5:
            reviewed.append(candidate)
            status = "reviewed"
            marker = "✓"
        else:
            dismissed.append(candidate)
            status = "dismissed"
            marker = "✗"

        print(f"  [{i+1}/{len(candidates)}] {score:.2f} {marker} {fetch_tag} {candidate['title'][:50]} | {reason[:50]}",
              file=sys.stderr)

        if not dry_run:
            try:
                update_candidate_status(candidate["id"], status,
                                               relevance_score=score, triage_reason=reason)
            except Exception as e:
                print(f"    Error updating {candidate['id']}: {e}", file=sys.stderr)
                errors.append(candidate)

    elapsed = time.time() - start_time
    per_candidate = elapsed / len(candidates) if candidates else 0

    reviewed_scores = [s for s in scores if s >= 0.5]
    summary = {
        "success": True,
        "total": len(candidates),
        "reviewed": len(reviewed),
        "dismissed": len(dismissed),
        "errors": len(errors),
        "dry_run": dry_run,
        "model": model,
        "elapsed_seconds": round(elapsed, 1),
        "seconds_per_candidate": round(per_candidate, 2),
        "score_stats": {
            "mean": round(sum(scores) / len(scores), 3) if scores else 0,
            "min": round(min(scores), 3) if scores else 0,
            "max": round(max(scores), 3) if scores else 0,
            "reviewed_mean": round(sum(reviewed_scores) / len(reviewed_scores), 3) if reviewed_scores else 0,
        },
        "reviewed_titles": [c["title"] for c in reviewed[:30]],
    }
    print(json.dumps(summary, indent=2))


def cmd_test(args):
    """Test triage on a single job."""
    model = args.model or DEFAULT_MODEL
    result = ollama_score(
        title=args.title,
        source=args.source or "Unknown",
        location=args.location or "Unknown",
        department=args.department or "",
        snippet=args.snippet or "",
        model=model,
    )
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="LLM-based job candidate triage")
    subparsers = parser.add_subparsers(dest="command")

    # triage command
    p = subparsers.add_parser("triage", help="Triage candidates via LLM")
    p.add_argument("--model", default=None, help=f"Ollama model (default: {DEFAULT_MODEL})")
    p.add_argument("--status", default="new", help="Candidate status to triage (default: new)")
    p.add_argument("--limit", type=int, default=0, help="Max candidates to process (0=all)")
    p.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")
    p.add_argument("--dry-run", action="store_true", help="Don't update TypeDB")
    p.add_argument("--no-fetch", action="store_true", help="Skip URL fetching, use stored snippet only")

    # test command
    p = subparsers.add_parser("test", help="Test triage on a single job")
    p.add_argument("--title", required=True, help="Job title")
    p.add_argument("--source", default="", help="Source/company")
    p.add_argument("--location", default="", help="Location")
    p.add_argument("--department", default="", help="Department")
    p.add_argument("--snippet", default="", help="Description snippet")
    p.add_argument("--model", default=None, help=f"Ollama model (default: {DEFAULT_MODEL})")

    args = parser.parse_args()

    if args.command == "triage":
        cmd_triage(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
