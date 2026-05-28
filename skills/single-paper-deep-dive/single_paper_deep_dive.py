#!/usr/bin/env python3
"""
Single Paper Deep Dive — TypeDB persistence layer for structured paper analysis.

Stores and retrieves analyses consisting of claims (primary/secondary/peripheral),
evidence (with experimental design + data), and citation impact records.

READ commands (use 2>/dev/null to suppress TypeDB noise):
  list-analyses                                    List all stored analyses
  get-analysis --doi DOI                           Full analysis with claims + evidence
  export-analysis --doi DOI [--format json|md]     Formatted analysis output

WRITE commands:
  new-analysis --doi DOI --title TITLE [--year N] [--paper-type TYPE]
  add-claim --analysis-doi DOI --type TYPE --statement TEXT
  add-evidence --analysis-doi DOI --claim-statement TEXT
               --evidence-type TYPE [--source-doi DOI] [--source-title TITLE]
               [--source-url URL] [--experimental-design TEXT] [--data-summary TEXT]
  add-citation-impact --analysis-doi DOI --citing-doi DOI --citing-title TITLE
                      --impact-type TYPE --impact-summary TEXT
  complete-analysis --doi DOI [--source-count N] [--scope-note TEXT]

Claim types:    primary | secondary | peripheral
Evidence types: experimental | observational | computational | review | theoretical | anecdotal
Impact types:   supports | refutes | extends | nuances | uses | unrelated
Paper types:    research | review | meta-analysis | preprint | book-chapter

Environment variables:
  TYPEDB_HOST      (default: localhost)
  TYPEDB_PORT      (default: 1729)
  TYPEDB_DATABASE  (default: alhazen_notebook)
  TYPEDB_USERNAME  (default: admin)
  TYPEDB_PASSWORD  (default: password)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = os.getenv("TYPEDB_PORT", "1729")
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def escape_string(s: str) -> str:
    if s is None:
        return ""
    return (s.replace("\\", "\\\\")
             .replace('"', '\\"')
             .replace("\n", "\\n")
             .replace("\r", ""))


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def new_id(prefix: str = "dive-") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def get_val(obj, key):
    """Extract a scalar value from a TypeDB fetch result entry."""
    v = obj.get(key)
    if v is None:
        return None
    if hasattr(v, "as_string"):
        return v.as_string()
    if hasattr(v, "as_long"):
        return v.as_long()
    if hasattr(v, "as_double"):
        return v.as_double()
    if hasattr(v, "as_boolean"):
        return v.as_boolean()
    return v


def require_typedb():
    if not TYPEDB_AVAILABLE:
        print(json.dumps({"error": "typedb-driver not installed — run: uv sync --all-extras"}))
        sys.exit(1)


# =============================================================================
# Commands
# =============================================================================

def cmd_new_analysis(args):
    require_typedb()
    doi = args.doi
    title = args.title
    year = args.year
    paper_type = args.paper_type or "research"

    doi_esc = escape_string(doi)
    title_esc = escape_string(title)
    paper_type_esc = escape_string(paper_type)
    now = now_ts()

    # Check if already exists
    check_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
    fetch {{ "id": $a.id, "status": $a.dive-analysis-status }};
    '''
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing = list(tx.query(check_q).resolve())

    if existing:
        existing_id = get_val(existing[0], "id")
        existing_status = get_val(existing[0], "status")
        print(json.dumps({
            "success": True,
            "analysis_id": existing_id,
            "doi": doi,
            "status": existing_status,
            "note": "analysis already exists",
        }))
        return

    analysis_id = new_id("dive-")
    name_esc = escape_string(title[:80])
    year_clause = f', has dive-paper-year {year}' if year else ''

    insert_q = f'''
    insert $a isa dive-analysis,
        has id "{analysis_id}",
        has name "{name_esc}",
        has dive-paper-doi "{doi_esc}",
        has dive-paper-title "{title_esc}",
        has dive-paper-type "{paper_type_esc}",
        has dive-analysis-status "in-progress",
        has created-at {now}{year_clause};
    '''

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(insert_q).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "analysis_id": analysis_id,
        "doi": doi,
        "title": title,
        "status": "in-progress",
    }))


def cmd_add_claim(args):
    require_typedb()
    doi = args.analysis_doi
    claim_type = args.type
    statement = args.statement

    doi_esc = escape_string(doi)
    statement_esc = escape_string(statement)
    claim_type_esc = escape_string(claim_type)
    now = now_ts()
    claim_id = new_id("claim-")
    name_esc = escape_string(statement[:60])

    # Check analysis exists
    check_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
    fetch {{ "id": $a.id }};
    '''
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            analyses = list(tx.query(check_q).resolve())

    if not analyses:
        print(json.dumps({"error": f"Analysis not found for DOI: {doi}. Run new-analysis first."}))
        sys.exit(1)

    insert_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
    insert
        $c isa dive-claim,
            has id "{claim_id}",
            has name "{name_esc}",
            has dive-claim-type "{claim_type_esc}",
            has dive-claim-statement "{statement_esc}",
            has created-at {now};
        (analysis: $a, claim: $c) isa dive-analysis-has-claim;
    '''

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(insert_q).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "claim_id": claim_id,
        "type": claim_type,
        "statement": statement,
    }))


def cmd_add_evidence(args):
    require_typedb()
    doi = args.analysis_doi
    claim_statement = args.claim_statement
    evidence_type = args.evidence_type
    source_doi = args.source_doi or ""
    source_title = args.source_title or ""
    source_url = args.source_url or ""
    experimental_design = args.experimental_design or ""
    data_summary = args.data_summary or ""

    doi_esc = escape_string(doi)
    claim_esc = escape_string(claim_statement)
    ev_type_esc = escape_string(evidence_type)
    source_doi_esc = escape_string(source_doi)
    source_title_esc = escape_string(source_title)
    source_url_esc = escape_string(source_url)
    design_esc = escape_string(experimental_design)
    data_esc = escape_string(data_summary)
    now = now_ts()
    ev_id = new_id("ev-")
    name_esc = escape_string(f"{evidence_type}: {source_title or source_doi}"[:60])

    # Verify claim exists
    check_q = f'''
    match
        $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
        $c isa dive-claim, has dive-claim-statement "{claim_esc}";
        (analysis: $a, claim: $c) isa dive-analysis-has-claim;
    fetch {{ "claim_id": $c.id }};
    '''
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            claims = list(tx.query(check_q).resolve())

    if not claims:
        print(json.dumps({
            "error": f"Claim not found. Make sure the statement matches exactly what was stored with add-claim.",
            "doi": doi,
            "claim_statement": claim_statement,
        }))
        sys.exit(1)

    # Build optional attribute clauses
    optional_attrs = ""
    if source_doi_esc:
        optional_attrs += f',\n            has dive-paper-doi "{source_doi_esc}"'
    if source_title_esc:
        optional_attrs += f',\n            has dive-paper-title "{source_title_esc}"'
    if source_url_esc:
        optional_attrs += f',\n            has dive-source-url "{source_url_esc}"'
    if design_esc:
        optional_attrs += f',\n            has dive-experimental-design "{design_esc}"'
    if data_esc:
        optional_attrs += f',\n            has dive-data-summary "{data_esc}"'

    insert_q = f'''
    match
        $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
        $c isa dive-claim, has dive-claim-statement "{claim_esc}";
        (analysis: $a, claim: $c) isa dive-analysis-has-claim;
    insert
        $e isa dive-evidence,
            has id "{ev_id}",
            has name "{name_esc}",
            has dive-evidence-type "{ev_type_esc}",
            has created-at {now}{optional_attrs};
        (claim: $c, evidence: $e) isa dive-claim-has-evidence;
    '''

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(insert_q).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "evidence_id": ev_id,
        "evidence_type": evidence_type,
        "source_doi": source_doi,
        "source_title": source_title,
    }))


def cmd_add_citation_impact(args):
    require_typedb()
    doi = args.analysis_doi
    citing_doi = args.citing_doi
    citing_title = args.citing_title
    impact_type = args.impact_type
    impact_summary = args.impact_summary

    doi_esc = escape_string(doi)
    citing_doi_esc = escape_string(citing_doi)
    citing_title_esc = escape_string(citing_title)
    impact_type_esc = escape_string(impact_type)
    impact_summary_esc = escape_string(impact_summary)
    now = now_ts()
    impact_id = new_id("impact-")
    name_esc = escape_string(f"{impact_type}: {citing_title[:50]}")

    check_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
    fetch {{ "id": $a.id }};
    '''
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            analyses = list(tx.query(check_q).resolve())

    if not analyses:
        print(json.dumps({"error": f"Analysis not found for DOI: {doi}"}))
        sys.exit(1)

    insert_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
    insert
        $i isa dive-citation-impact,
            has id "{impact_id}",
            has name "{name_esc}",
            has dive-paper-doi "{citing_doi_esc}",
            has dive-paper-title "{citing_title_esc}",
            has dive-impact-type "{impact_type_esc}",
            has dive-impact-summary "{impact_summary_esc}",
            has created-at {now};
        (focal-analysis: $a, citation-impact: $i) isa dive-analysis-cited-by;
    '''

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(insert_q).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "impact_id": impact_id,
        "citing_doi": citing_doi,
        "impact_type": impact_type,
    }))


def cmd_complete_analysis(args):
    require_typedb()
    doi = args.doi
    source_count = args.source_count
    scope_note = args.scope_note or ""
    status = args.status or "complete"

    doi_esc = escape_string(doi)
    scope_note_esc = escape_string(scope_note)
    now = now_ts()

    # Fetch current status to delete it
    check_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}",
          has dive-analysis-status $s;
    fetch {{ "id": $a.id, "status": $s }};
    '''
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(check_q).resolve())

    if not results:
        print(json.dumps({"error": f"Analysis not found for DOI: {doi}"}))
        sys.exit(1)

    # Delete old status + source-count (if set), insert new values
    delete_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}",
          has dive-analysis-status $s;
    delete has $s of $a;
    '''

    new_attrs = f'has dive-analysis-status "{escape_string(status)}", has updated-at {now}'
    if source_count is not None:
        new_attrs += f', has dive-source-count {source_count}'
    if scope_note_esc:
        new_attrs += f', has dive-scope-note "{scope_note_esc}"'

    insert_q = f'''
    match $a isa dive-analysis, has dive-paper-doi "{doi_esc}";
    insert $a {new_attrs};
    '''

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(delete_q).resolve()
            tx.query(insert_q).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "doi": doi,
        "status": status,
        "source_count": source_count,
    }))


def cmd_get_analysis(args):
    require_typedb()
    analysis_id = getattr(args, 'id', None)
    doi = getattr(args, 'doi', None)

    if not analysis_id and not doi:
        print(json.dumps({"error": "Provide --doi or --id"}))
        sys.exit(1)

    if analysis_id:
        id_esc = escape_string(analysis_id)
        match_clause = f'$a isa dive-analysis, has id "{id_esc}"'
        not_found_msg = f"Analysis not found for id: {analysis_id}"
    else:
        doi_esc = escape_string(doi)
        match_clause = f'$a isa dive-analysis, has dive-paper-doi "{doi_esc}"'
        not_found_msg = f"Analysis not found for DOI: {doi}"

    with get_driver() as driver:
        # 1. Fetch analysis metadata
        meta_q = f'''
        match {match_clause};
        fetch {{
            "id": $a.id,
            "title": $a.dive-paper-title,
            "doi": $a.dive-paper-doi,
            "year": $a.dive-paper-year,
            "paper_type": $a.dive-paper-type,
            "status": $a.dive-analysis-status,
            "source_count": $a.dive-source-count,
            "scope_note": $a.dive-scope-note
        }};
        '''
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            meta_results = list(tx.query(meta_q).resolve())

        if not meta_results:
            print(json.dumps({"error": not_found_msg}))
            sys.exit(1)

        meta = meta_results[0]
        entity_id = get_val(meta, "id")
        entity_id_esc = escape_string(entity_id)
        analysis = {
            "id": entity_id,
            "doi": get_val(meta, "doi"),
            "title": get_val(meta, "title"),
            "year": get_val(meta, "year"),
            "paper_type": get_val(meta, "paper_type"),
            "status": get_val(meta, "status"),
            "source_count": get_val(meta, "source_count"),
            "scope_note": get_val(meta, "scope_note"),
        }

        # 2. Fetch claims — use entity id for all subsequent queries
        claims_q = f'''
        match
            $a isa dive-analysis, has id "{entity_id_esc}";
            (analysis: $a, claim: $c) isa dive-analysis-has-claim;
        fetch {{
            "id": $c.id,
            "type": $c.dive-claim-type,
            "statement": $c.dive-claim-statement
        }};
        '''
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            claim_results = list(tx.query(claims_q).resolve())

        claims_by_id = {}
        for cr in claim_results:
            cid = get_val(cr, "id")
            claims_by_id[cid] = {
                "id": cid,
                "type": get_val(cr, "type"),
                "statement": get_val(cr, "statement"),
                "evidence": [],
            }

        # 3. Fetch evidence for each claim
        for cid, claim in claims_by_id.items():
            cid_esc = escape_string(cid)
            ev_q = f'''
            match
                $c isa dive-claim, has id "{cid_esc}";
                (claim: $c, evidence: $e) isa dive-claim-has-evidence;
            fetch {{
                "id": $e.id,
                "evidence_type": $e.dive-evidence-type,
                "experimental_design": $e.dive-experimental-design,
                "data_summary": $e.dive-data-summary,
                "source_doi": $e.dive-paper-doi,
                "source_title": $e.dive-paper-title,
                "source_url": $e.dive-source-url
            }};
            '''
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                ev_results = list(tx.query(ev_q).resolve())
            for er in ev_results:
                claim["evidence"].append({
                    "id": get_val(er, "id"),
                    "evidence_type": get_val(er, "evidence_type"),
                    "experimental_design": get_val(er, "experimental_design"),
                    "data_summary": get_val(er, "data_summary"),
                    "source_doi": get_val(er, "source_doi"),
                    "source_title": get_val(er, "source_title"),
                    "source_url": get_val(er, "source_url"),
                })

        # 4. Fetch citation impacts
        impact_q = f'''
        match
            $a isa dive-analysis, has id "{entity_id_esc}";
            (focal-analysis: $a, citation-impact: $i) isa dive-analysis-cited-by;
        fetch {{
            "id": $i.id,
            "impact_type": $i.dive-impact-type,
            "impact_summary": $i.dive-impact-summary,
            "citing_doi": $i.dive-paper-doi,
            "citing_title": $i.dive-paper-title
        }};
        '''
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            impact_results = list(tx.query(impact_q).resolve())

        citation_impacts = []
        for ir in impact_results:
            citation_impacts.append({
                "id": get_val(ir, "id"),
                "impact_type": get_val(ir, "impact_type"),
                "impact_summary": get_val(ir, "impact_summary"),
                "citing_doi": get_val(ir, "citing_doi"),
                "citing_title": get_val(ir, "citing_title"),
            })

    # Sort claims by type order
    type_order = {"primary": 0, "secondary": 1, "peripheral": 2}
    claims_list = sorted(
        claims_by_id.values(),
        key=lambda c: type_order.get(c.get("type", ""), 99),
    )

    analysis["claims"] = claims_list
    analysis["citation_impacts"] = citation_impacts

    print(json.dumps({"success": True, "analysis": analysis}, indent=2))


def cmd_list_analyses(args):
    require_typedb()

    q = '''
    match $a isa dive-analysis;
    fetch {
        "id": $a.id,
        "doi": $a.dive-paper-doi,
        "title": $a.dive-paper-title,
        "year": $a.dive-paper-year,
        "status": $a.dive-analysis-status,
        "source_count": $a.dive-source-count
    };
    '''
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(q).resolve())

    analyses = []
    for r in results:
        analyses.append({
            "id": get_val(r, "id"),
            "doi": get_val(r, "doi"),
            "title": get_val(r, "title"),
            "year": get_val(r, "year"),
            "status": get_val(r, "status"),
            "source_count": get_val(r, "source_count"),
        })

    print(json.dumps({"success": True, "count": len(analyses), "analyses": analyses}, indent=2))


def cmd_export_analysis(args):
    require_typedb()
    doi = args.doi
    fmt = args.format or "md"

    # Reuse get_analysis logic by delegating
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        get_args = argparse.Namespace(doi=doi)
        cmd_get_analysis(get_args)
    raw = buf.getvalue()
    data = json.loads(raw)

    if not data.get("success"):
        print(raw)
        return

    a = data["analysis"]

    if fmt == "json":
        print(json.dumps(data, indent=2))
        return

    # Markdown format
    lines = []
    lines.append(f"## Deep Dive: {a.get('title', 'Unknown Title')}")
    lines.append("")
    lines.append(f"**DOI:** {a.get('doi', '—')}  |  **Year:** {a.get('year', '—')}  |  **Type:** {a.get('paper_type', '—')}")
    lines.append(f"**Status:** {a.get('status', '—')}  |  **Sources examined:** {a.get('source_count', '?')}/100")
    if a.get("scope_note"):
        lines.append(f"**Scope note:** {a['scope_note']}")
    lines.append("")

    # Group claims by type
    by_type = {"primary": [], "secondary": [], "peripheral": []}
    for c in a.get("claims", []):
        by_type.setdefault(c.get("type", "peripheral"), []).append(c)

    impact_counts = {}
    for imp in a.get("citation_impacts", []):
        t = imp.get("impact_type", "unrelated")
        impact_counts[t] = impact_counts.get(t, 0) + 1

    for tier, label in [("primary", "Primary Claims"), ("secondary", "Secondary Claims"), ("peripheral", "Peripheral Claims")]:
        claims = by_type.get(tier, [])
        if not claims:
            continue
        lines.append(f"### {label}")
        lines.append("")
        for i, c in enumerate(claims, 1):
            lines.append(f"{i}. **{c['statement']}**")
            evidence = c.get("evidence", [])
            if evidence:
                lines.append("   Evidence:")
                for e in evidence:
                    src = e.get("source_title") or e.get("source_doi") or e.get("source_url") or "unknown source"
                    design = e.get("experimental_design") or ""
                    data_s = e.get("data_summary") or ""
                    ev_type = e.get("evidence_type", "")
                    if design or data_s:
                        lines.append(f"   - [{ev_type}] **{src}**")
                        if design:
                            lines.append(f"     - Design: {design}")
                        if data_s:
                            lines.append(f"     - Data: {data_s}")
                    else:
                        lines.append(f"   - [{ev_type}] {src}")
            else:
                lines.append("   *No evidence recorded yet*")
            lines.append("")

    # Citation impact summary
    impacts = a.get("citation_impacts", [])
    if impacts:
        lines.append("### Citation Impact")
        lines.append("")
        if impact_counts:
            summary_parts = [f"{v} {k}" for k, v in sorted(impact_counts.items())]
            lines.append(f"**{len(impacts)} citing papers examined:** {', '.join(summary_parts)}")
            lines.append("")
        for imp in impacts:
            t = imp.get("impact_type", "")
            title = imp.get("citing_title") or imp.get("citing_doi") or "unknown"
            summary = imp.get("impact_summary") or ""
            lines.append(f"- [{t}] **{title}**: {summary}")
        lines.append("")

    print("\n".join(lines))


# =============================================================================
# Argument parser
# =============================================================================

def build_parser():
    parser = argparse.ArgumentParser(
        description="Single Paper Deep Dive — TypeDB persistence layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # new-analysis
    p = sub.add_parser("new-analysis", help="Start a new paper analysis")
    p.add_argument("--doi", required=True, help="DOI of the paper (canonical identifier)")
    p.add_argument("--title", required=True, help="Full title of the paper")
    p.add_argument("--year", type=int, help="Publication year")
    p.add_argument("--paper-type", choices=["research", "review", "meta-analysis", "preprint", "book-chapter"],
                   default="research", help="Type of paper (default: research)")

    # add-claim
    p = sub.add_parser("add-claim", help="Add a claim to an analysis")
    p.add_argument("--analysis-doi", required=True, help="DOI of the analysis")
    p.add_argument("--type", required=True, choices=["primary", "secondary", "peripheral"],
                   help="Claim tier")
    p.add_argument("--statement", required=True, help="The claim as a precise, falsifiable statement")

    # add-evidence
    p = sub.add_parser("add-evidence", help="Add evidence for a claim")
    p.add_argument("--analysis-doi", required=True, help="DOI of the analysis")
    p.add_argument("--claim-statement", required=True, help="Exact statement of the claim (must match stored text)")
    p.add_argument("--evidence-type", required=True,
                   choices=["experimental", "observational", "computational", "review", "theoretical", "anecdotal"],
                   help="Type of evidence")
    p.add_argument("--source-doi", help="DOI of the source paper")
    p.add_argument("--source-title", help="Title of the source paper or resource")
    p.add_argument("--source-url", help="URL of the source (if no DOI)")
    p.add_argument("--experimental-design",
                   help="Description of the experimental design (what was studied, measured, compared)")
    p.add_argument("--data-summary",
                   help="The actual data / observations / results cited (numbers, p-values, etc.)")

    # add-citation-impact
    p = sub.add_parser("add-citation-impact", help="Record how a citing paper relates to the focal paper")
    p.add_argument("--analysis-doi", required=True, help="DOI of the focal paper analysis")
    p.add_argument("--citing-doi", required=True, help="DOI of the citing paper")
    p.add_argument("--citing-title", required=True, help="Title of the citing paper")
    p.add_argument("--impact-type", required=True,
                   choices=["supports", "refutes", "extends", "nuances", "uses", "unrelated"],
                   help="How the citing paper relates to the focal paper's claims")
    p.add_argument("--impact-summary", required=True,
                   help="1-2 sentence description of how the citing paper relates")

    # complete-analysis
    p = sub.add_parser("complete-analysis", help="Mark an analysis as complete")
    p.add_argument("--doi", required=True, help="DOI of the analysis")
    p.add_argument("--source-count", type=int, help="Total number of sources examined")
    p.add_argument("--scope-note", help="Note on what was included/excluded from scope")
    p.add_argument("--status", choices=["complete", "scope-exhausted"],
                   default="complete", help="Completion status")

    # get-analysis
    p = sub.add_parser("get-analysis", help="Retrieve full analysis with all claims and evidence")
    p.add_argument("--doi", help="DOI of the paper")
    p.add_argument("--id", help="Analysis entity id (alternative to --doi)")

    # list-analyses
    sub.add_parser("list-analyses", help="List all stored analyses")

    # export-analysis
    p = sub.add_parser("export-analysis", help="Export analysis as formatted text or JSON")
    p.add_argument("--doi", required=True, help="DOI of the paper")
    p.add_argument("--format", choices=["md", "json"], default="md",
                   help="Output format (default: md)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "new-analysis": cmd_new_analysis,
        "add-claim": cmd_add_claim,
        "add-evidence": cmd_add_evidence,
        "add-citation-impact": cmd_add_citation_impact,
        "complete-analysis": cmd_complete_analysis,
        "get-analysis": cmd_get_analysis,
        "list-analyses": cmd_list_analyses,
        "export-analysis": cmd_export_analysis,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
