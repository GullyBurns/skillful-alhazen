#!/usr/bin/env python3
"""
Algorithm for Precision Medicine (APM) CLI - Rare disease investigation notebook.

This script handles INGESTION and QUERIES. Claude handles SENSEMAKING via the SKILL.md.

Usage:
    python .claude/skills/apm/apm.py <command> [options]

Commands:
    # Entity Creation
    add-case            Create an investigation case
    add-gene            Add a gene
    add-variant         Add a genomic variant
    add-disease         Add a disease/condition
    add-phenotype       Add an HPO phenotype
    add-protein         Add a protein
    add-drug            Add a therapeutic compound
    add-pathway         Add a biological pathway
    add-model           Add a disease model

    # Ingestion
    ingest-report       Ingest a sequencing report (PDF/file)
    ingest-record       Ingest a database record (ClinVar, OMIM, etc.)

    # Relations (Diagnostic Chain)
    link-case-phenotype     Link phenotype to case
    link-case-variant       Link variant to case
    link-case-diagnosis     Link diagnosis to case
    link-variant-gene       Link variant to gene
    link-variant-disease    Variant pathogenicity claim

    # Relations (Therapeutic Chain)
    link-mechanism          Mechanism of harm (variant -> gene)
    link-gene-protein       Gene encodes protein
    link-drug-target        Drug targets gene/protein
    link-drug-indication    Drug-disease relationship
    link-pathway-gene       Gene in pathway
    link-model-disease      Model for disease

    # Notes
    add-note            Create a note about any entity

    # Queries
    show-case               Full case details
    show-diagnostic-chain   Diagnostic reasoning chain
    show-therapeutic-chain  Therapeutic reasoning chain
    list-cases              List all cases
    list-genes              List all genes
    list-variants           List all variants
    list-diseases           List all diseases
    list-phenotypes         List all phenotypes
    list-drugs              List all drugs
    list-artifacts          List artifacts by status
    show-artifact           Get artifact content

    # Tagging
    tag                 Tag an entity
    search-tag          Search by tag

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

try:
    import requests
    from bs4 import BeautifulSoup

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from typedb.driver import SessionType, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=2.25.0,<3.0.0'",
        file=sys.stderr,
    )

try:
    from skillful_alhazen.utils.cache import (
        save_to_cache,
        load_from_cache_text,
        should_cache,
        get_cache_stats,
        format_size,
    )

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

    def should_cache(content):
        return False

    def get_cache_stats():
        return {"error": "Cache module not available"}

    def format_size(size):
        return f"{size} bytes"


# =============================================================================
# CONFIGURATION
# =============================================================================

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")


# =============================================================================
# UTILITIES
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


def fetch_url_content(url: str) -> tuple[str, str]:
    """Fetch URL and return (title, text_content)."""
    if not REQUESTS_AVAILABLE:
        return "", ""

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        title = soup.title.string if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        if len(text) > 50000:
            text = text[:50000] + "\n... [truncated]"

        return title, text

    except Exception as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return "", ""


# =============================================================================
# ENTITY CREATION COMMANDS
# =============================================================================


def cmd_add_case(args):
    """Create an investigation case."""
    case_id = args.id or generate_id("case")
    timestamp = get_timestamp()

    query = f'''insert $c isa apm-case,
        has id "{case_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.diagnostic_status:
        query += f', has apm-diagnostic-status "{args.diagnostic_status}"'
    if args.therapeutic_status:
        query += f', has apm-therapeutic-status "{args.therapeutic_status}"'
    if args.phase:
        query += f', has apm-investigation-phase "{args.phase}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "case_id": case_id, "name": args.name}))


def cmd_add_gene(args):
    """Add a gene."""
    gene_id = args.id or generate_id("gene")
    timestamp = get_timestamp()

    name = args.name or args.symbol
    query = f'''insert $g isa apm-gene,
        has id "{gene_id}",
        has name "{escape_string(name)}",
        has apm-gene-symbol "{escape_string(args.symbol)}",
        has created-at {timestamp}'''

    if args.entrez_id:
        query += f', has apm-entrez-id "{escape_string(args.entrez_id)}"'
    if args.ensembl_id:
        query += f', has apm-ensembl-id "{escape_string(args.ensembl_id)}"'
    if args.inheritance:
        query += f', has apm-inheritance-pattern "{args.inheritance}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "gene_id": gene_id, "symbol": args.symbol}))


def cmd_add_variant(args):
    """Add a genomic variant."""
    variant_id = args.id or generate_id("variant")
    timestamp = get_timestamp()

    # Build a descriptive name from HGVS notation
    name_parts = []
    if args.gene:
        name_parts.append(args.gene)
    if args.hgvs_c:
        name_parts.append(args.hgvs_c)
    name = args.name or " ".join(name_parts) or f"Variant {variant_id}"

    query = f'''insert $v isa apm-variant,
        has id "{variant_id}",
        has name "{escape_string(name)}",
        has created-at {timestamp}'''

    if args.chromosome:
        query += f', has apm-chromosome "{escape_string(args.chromosome)}"'
    if args.hgvs_c:
        query += f', has apm-hgvs-c "{escape_string(args.hgvs_c)}"'
    if args.hgvs_p:
        query += f', has apm-hgvs-p "{escape_string(args.hgvs_p)}"'
    if args.hgvs_g:
        query += f', has apm-hgvs-g "{escape_string(args.hgvs_g)}"'
    if args.acmg_class:
        query += f', has apm-acmg-class "{args.acmg_class}"'
    if args.acmg_criteria:
        query += f', has apm-acmg-criteria "{escape_string(args.acmg_criteria)}"'
    # Note: zygosity is a property of the case-has-variant relation, not the variant itself.
    # Use link-case-variant --zygosity to set it.
    if args.allele_frequency is not None:
        query += f", has apm-allele-frequency {args.allele_frequency}"
    if args.gnomad_af is not None:
        query += f", has apm-gnomad-af {args.gnomad_af}"
    if args.clinvar_id:
        query += f', has apm-clinvar-id "{escape_string(args.clinvar_id)}"'
    if args.genome_build:
        query += f', has apm-genome-build "{escape_string(args.genome_build)}"'
    if args.transcript_id:
        query += f', has apm-transcript-id "{escape_string(args.transcript_id)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

            # Link to gene if gene ID provided
            if args.gene_id:
                with session.transaction(TransactionType.WRITE) as tx:
                    rel_query = f'''match
                        $v isa apm-variant, has id "{variant_id}";
                        $g isa apm-gene, has id "{args.gene_id}";
                    insert (variant: $v, gene: $g) isa apm-variant-in-gene;'''
                    tx.query.insert(rel_query)
                    tx.commit()

    print(json.dumps({"success": True, "variant_id": variant_id, "name": name}))


def cmd_add_disease(args):
    """Add a disease/condition."""
    disease_id = args.id or generate_id("disease")
    timestamp = get_timestamp()

    query = f'''insert $d isa apm-disease,
        has id "{disease_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.omim_id:
        query += f', has apm-omim-id "{escape_string(args.omim_id)}"'
    if args.orpha_id:
        query += f', has apm-orpha-id "{escape_string(args.orpha_id)}"'
    if args.mondo_id:
        query += f', has apm-mondo-id "{escape_string(args.mondo_id)}"'
    if args.inheritance:
        query += f', has apm-inheritance-pattern "{args.inheritance}"'
    if args.penetrance:
        query += f', has apm-penetrance "{args.penetrance}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "disease_id": disease_id, "name": args.name}))


def cmd_add_phenotype(args):
    """Add an HPO phenotype."""
    phenotype_id = args.id or generate_id("phenotype")
    timestamp = get_timestamp()

    name = args.label or args.hpo_id
    query = f'''insert $p isa apm-phenotype,
        has id "{phenotype_id}",
        has name "{escape_string(name)}",
        has apm-hpo-id "{escape_string(args.hpo_id)}",
        has apm-hpo-label "{escape_string(args.label)}",
        has created-at {timestamp}'''

    if args.onset:
        query += f', has apm-onset-category "{args.onset}"'
    if args.severity:
        query += f', has apm-severity "{args.severity}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "phenotype_id": phenotype_id, "hpo_id": args.hpo_id, "label": args.label}))


def cmd_add_protein(args):
    """Add a protein."""
    protein_id = args.id or generate_id("protein")
    timestamp = get_timestamp()

    query = f'''insert $p isa apm-protein,
        has id "{protein_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.uniprot_id:
        query += f', has apm-uniprot-id "{escape_string(args.uniprot_id)}"'
    if args.domain:
        query += f', has apm-protein-domain "{escape_string(args.domain)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "protein_id": protein_id, "name": args.name}))


def cmd_add_drug(args):
    """Add a therapeutic compound."""
    drug_id = args.id or generate_id("drug")
    timestamp = get_timestamp()

    query = f'''insert $d isa apm-drug,
        has id "{drug_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.drugbank_id:
        query += f', has apm-drugbank-id "{escape_string(args.drugbank_id)}"'
    if args.chembl_id:
        query += f', has apm-chembl-id "{escape_string(args.chembl_id)}"'
    if args.approach:
        query += f', has apm-therapeutic-approach "{args.approach}"'
    if args.stage:
        query += f', has apm-development-stage "{args.stage}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "drug_id": drug_id, "name": args.name}))


def cmd_add_pathway(args):
    """Add a biological pathway."""
    pathway_id = args.id or generate_id("pathway")
    timestamp = get_timestamp()

    query = f'''insert $p isa apm-pathway,
        has id "{pathway_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "pathway_id": pathway_id, "name": args.name}))


def cmd_add_model(args):
    """Add a disease model."""
    model_id = args.id or generate_id("model")
    timestamp = get_timestamp()

    query = f'''insert $m isa apm-disease-model,
        has id "{model_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.model_type:
        query += f', has apm-model-type "{args.model_type}"'
    if args.species:
        query += f', has apm-model-species "{escape_string(args.species)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "model_id": model_id, "name": args.name}))


# =============================================================================
# INGESTION COMMANDS
# =============================================================================


def cmd_ingest_report(args):
    """Ingest a sequencing report file."""
    artifact_id = generate_id("artifact")
    timestamp = get_timestamp()

    file_path = args.file
    if not os.path.exists(file_path):
        print(json.dumps({"success": False, "error": f"File not found: {file_path}"}))
        return

    file_size = os.path.getsize(file_path)
    name = args.name or os.path.basename(file_path)

    # Determine mime type from extension
    ext = os.path.splitext(file_path)[1].lower()
    mime_types = {".pdf": "application/pdf", ".vcf": "text/plain", ".txt": "text/plain", ".csv": "text/csv"}
    mime_type = mime_types.get(ext, "application/octet-stream")

    # For text files, read content; for binary, store path reference
    content = None
    cache_path = None
    if mime_type.startswith("text/"):
        with open(file_path, "r", errors="replace") as f:
            content = f.read()
        if CACHE_AVAILABLE and should_cache(content):
            cache_result = save_to_cache(artifact_id=artifact_id, content=content, mime_type=mime_type)
            cache_path = cache_result["cache_path"]
            content = None  # Don't store inline

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''insert $a isa apm-sequencing-report,
                    has id "{artifact_id}",
                    has name "{escape_string(name)}",
                    has mime-type "{mime_type}",
                    has file-size {file_size},
                    has source-uri "file://{escape_string(os.path.abspath(file_path))}",
                    has created-at {timestamp}'''

                if content:
                    query += f', has content "{escape_string(content)}"'
                if cache_path:
                    query += f', has cache-path "{cache_path}"'

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({
        "success": True,
        "artifact_id": artifact_id,
        "name": name,
        "file_size": file_size,
        "mime_type": mime_type,
        "message": "Report ingested. Ask Claude to 'analyze this report' for sensemaking.",
    }, indent=2))


def cmd_ingest_record(args):
    """Ingest a database record from URL."""
    if not REQUESTS_AVAILABLE:
        print(json.dumps({"success": False, "error": "requests/beautifulsoup4 not installed"}))
        return

    artifact_id = generate_id("artifact")
    timestamp = get_timestamp()

    title, content = fetch_url_content(args.url)
    if not content:
        print(json.dumps({"success": False, "error": "Could not fetch URL content"}))
        return

    # Map record type to TypeDB artifact type
    type_map = {
        "clinvar": "apm-clinvar-record",
        "omim": "apm-omim-record",
        "gnomad": "apm-gnomad-record",
        "drugbank": "apm-drug-record",
        "prediction": "apm-prediction-record",
        "pathway": "apm-pathway-record",
        "screening": "apm-screening-result",
        "general": "artifact",
    }
    artifact_type = type_map.get(args.type, "artifact")

    name = args.name or title or f"{args.type} record: {args.source_id or args.url[:50]}"

    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                if CACHE_AVAILABLE and should_cache(content):
                    cache_result = save_to_cache(artifact_id=artifact_id, content=content, mime_type="text/html")
                    query = f'''insert $a isa {artifact_type},
                        has id "{artifact_id}",
                        has name "{escape_string(name)}",
                        has cache-path "{cache_result['cache_path']}",
                        has mime-type "text/html",
                        has file-size {cache_result['file_size']},
                        has content-hash "{cache_result['content_hash']}",
                        has source-uri "{escape_string(args.url)}",
                        has created-at {timestamp}'''
                else:
                    query = f'''insert $a isa {artifact_type},
                        has id "{artifact_id}",
                        has name "{escape_string(name)}",
                        has content "{escape_string(content)}",
                        has source-uri "{escape_string(args.url)}",
                        has created-at {timestamp}'''

                # Add type-specific attributes
                if args.type == "clinvar" and args.source_id:
                    query += f', has apm-clinvar-id "{escape_string(args.source_id)}"'
                elif args.type == "omim" and args.source_id:
                    query += f', has apm-omim-id "{escape_string(args.source_id)}"'

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({
        "success": True,
        "artifact_id": artifact_id,
        "type": args.type,
        "name": name,
        "content_length": len(content),
        "message": "Record ingested. Ask Claude to 'analyze this record' for sensemaking.",
    }, indent=2))


# =============================================================================
# RELATION COMMANDS - Diagnostic Chain
# =============================================================================


def cmd_link_case_phenotype(args):
    """Link a phenotype to a case."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $c isa apm-case, has id "{args.case}";
                    $p isa apm-phenotype, has id "{args.phenotype}";
                insert $r (case: $c, phenotype: $p) isa apm-case-has-phenotype'''

                if args.onset:
                    query += f', has apm-onset-category "{args.onset}"'
                if args.severity:
                    query += f', has apm-severity "{args.severity}"'

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "case": args.case, "phenotype": args.phenotype}))


def cmd_link_case_variant(args):
    """Link a variant to a case."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $c isa apm-case, has id "{args.case}";
                    $v isa apm-variant, has id "{args.variant}";
                insert $r (case: $c, variant: $v) isa apm-case-has-variant'''

                if args.zygosity:
                    query += f', has apm-zygosity "{args.zygosity}"'

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "case": args.case, "variant": args.variant}))


def cmd_link_case_diagnosis(args):
    """Link a diagnosis to a case."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $c isa apm-case, has id "{args.case}";
                    $d isa apm-disease, has id "{args.disease}";
                insert $r (case: $c, disease: $d) isa apm-case-has-diagnosis'''

                if args.status:
                    query += f', has apm-diagnostic-status "{args.status}"'
                if args.confidence is not None:
                    query += f", has confidence {args.confidence}"

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "case": args.case, "disease": args.disease}))


def cmd_link_variant_gene(args):
    """Link a variant to a gene."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $v isa apm-variant, has id "{args.variant}";
                    $g isa apm-gene, has id "{args.gene}";
                insert (variant: $v, gene: $g) isa apm-variant-in-gene;'''
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "variant": args.variant, "gene": args.gene}))


def cmd_link_variant_disease(args):
    """Create a variant pathogenicity claim."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $v isa apm-variant, has id "{args.variant}";
                    $d isa apm-disease, has id "{args.disease}";
                insert $r (variant: $v, disease: $d) isa apm-variant-pathogenicity'''

                if args.acmg_class:
                    query += f', has apm-acmg-class "{args.acmg_class}"'
                if args.confidence is not None:
                    query += f", has confidence {args.confidence}"

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "variant": args.variant, "disease": args.disease}))


# =============================================================================
# RELATION COMMANDS - Therapeutic Chain
# =============================================================================


def cmd_link_mechanism(args):
    """Create a mechanism of harm relation."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $v isa apm-variant, has id "{args.variant}";
                    $g isa apm-gene, has id "{args.gene}";
                insert $r (variant: $v, gene: $g) isa apm-mechanism-of-harm'''

                if args.mechanism_type:
                    query += f', has apm-mechanism-type "{args.mechanism_type}"'
                if args.functional_impact:
                    query += f', has apm-functional-impact "{args.functional_impact}"'
                if args.confidence is not None:
                    query += f", has confidence {args.confidence}"

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "variant": args.variant, "gene": args.gene}))


def cmd_link_gene_protein(args):
    """Link gene to protein it encodes."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $g isa apm-gene, has id "{args.gene}";
                    $p isa apm-protein, has id "{args.protein}";
                insert (gene: $g, protein: $p) isa apm-gene-encodes;'''
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "gene": args.gene, "protein": args.protein}))


def cmd_link_drug_target(args):
    """Link drug to its target gene/protein."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                # Build match clause for available targets
                match_parts = [f'$d isa apm-drug, has id "{args.drug}";']
                insert_roles = ["drug: $d"]

                if args.gene:
                    match_parts.append(f'$g isa apm-gene, has id "{args.gene}";')
                    insert_roles.append("target-gene: $g")
                if args.protein:
                    match_parts.append(f'$p isa apm-protein, has id "{args.protein}";')
                    insert_roles.append("target-protein: $p")

                match_clause = "\n                    ".join(match_parts)
                roles = ", ".join(insert_roles)

                query = f'''match
                    {match_clause}
                insert $r ({roles}) isa apm-drug-target'''

                if args.approach:
                    query += f', has apm-therapeutic-approach "{args.approach}"'
                if args.confidence is not None:
                    query += f", has confidence {args.confidence}"

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "drug": args.drug, "gene": args.gene, "protein": args.protein}))


def cmd_link_drug_indication(args):
    """Link drug to disease indication."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $d isa apm-drug, has id "{args.drug}";
                    $dis isa apm-disease, has id "{args.disease}";
                insert $r (drug: $d, indication: $dis) isa apm-drug-indication'''

                if args.stage:
                    query += f', has apm-development-stage "{args.stage}"'

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "drug": args.drug, "disease": args.disease}))


def cmd_link_pathway_gene(args):
    """Link gene to pathway."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $g isa apm-gene, has id "{args.gene}";
                    $p isa apm-pathway, has id "{args.pathway}";
                insert (member-gene: $g, pathway: $p) isa apm-pathway-membership;'''
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "gene": args.gene, "pathway": args.pathway}))


def cmd_link_model_disease(args):
    """Link model to disease."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                query = f'''match
                    $m isa apm-disease-model, has id "{args.model}";
                    $d isa apm-disease, has id "{args.disease}";
                insert $r (model: $m, disease: $d) isa apm-model-for-disease'''

                if args.recapitulated is not None:
                    query += f", has apm-phenotype-recapitulated {str(args.recapitulated).lower()}"
                if args.confidence is not None:
                    query += f", has confidence {args.confidence}"

                query += ";"
                tx.query.insert(query)
                tx.commit()

    print(json.dumps({"success": True, "model": args.model, "disease": args.disease}))


# =============================================================================
# NOTE COMMANDS
# =============================================================================


def cmd_add_note(args):
    """Create a note about any entity."""
    note_id = args.note_id or generate_id("note")
    timestamp = get_timestamp()

    type_map = {
        "diagnosis-hypothesis": "apm-diagnosis-hypothesis-note",
        "variant-interpretation": "apm-variant-interpretation-note",
        "mechanism-analysis": "apm-mechanism-analysis-note",
        "therapeutic-strategy": "apm-therapeutic-strategy-note",
        "phenotype-genotype": "apm-phenotype-genotype-note",
        "reanalysis": "apm-reanalysis-note",
        "cross-case": "apm-cross-case-synthesis-note",
        "screening-analysis": "apm-screening-analysis-note",
        "general": "note",
    }

    note_type = type_map.get(args.type, "note")

    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(args.content)}",
        has created-at {timestamp}'''

    if args.name:
        query += f', has name "{escape_string(args.name)}"'
    if args.confidence is not None:
        query += f", has confidence {args.confidence}"

    # Type-specific attributes
    if args.type == "diagnosis-hypothesis":
        if args.diagnostic_status:
            query += f', has apm-diagnostic-status "{args.diagnostic_status}"'
        if args.acmg_class:
            query += f', has apm-acmg-class "{args.acmg_class}"'

    if args.type == "variant-interpretation":
        if args.acmg_class:
            query += f', has apm-acmg-class "{args.acmg_class}"'
        if args.acmg_criteria:
            query += f', has apm-acmg-criteria "{escape_string(args.acmg_criteria)}"'

    if args.type == "mechanism-analysis":
        if args.mechanism_type:
            query += f', has apm-mechanism-type "{args.mechanism_type}"'
        if args.functional_impact:
            query += f', has apm-functional-impact "{args.functional_impact}"'

    if args.type == "therapeutic-strategy":
        if args.therapeutic_approach:
            query += f', has apm-therapeutic-approach "{args.therapeutic_approach}"'
        if args.functional_impact:
            query += f', has apm-functional-impact "{args.functional_impact}"'

    if args.type == "reanalysis":
        if args.diagnostic_status:
            query += f', has apm-diagnostic-status "{args.diagnostic_status}"'

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


# =============================================================================
# QUERY COMMANDS
# =============================================================================


def cmd_show_case(args):
    """Get full case details."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Case details
                case_query = f'''match
                    $c isa apm-case, has id "{args.id}";
                fetch $c: id, name, description, apm-diagnostic-status,
                    apm-therapeutic-status, apm-investigation-phase;'''
                case_result = list(tx.query.fetch(case_query))

                if not case_result:
                    print(json.dumps({"success": False, "error": "Case not found"}))
                    return

                # Phenotypes
                phenotype_query = f'''match
                    $c isa apm-case, has id "{args.id}";
                    (case: $c, phenotype: $p) isa apm-case-has-phenotype;
                fetch $p: id, apm-hpo-id, apm-hpo-label, apm-onset-category, apm-severity;'''
                phenotypes = list(tx.query.fetch(phenotype_query))

                # Variants
                variant_query = f'''match
                    $c isa apm-case, has id "{args.id}";
                    (case: $c, variant: $v) isa apm-case-has-variant;
                fetch $v: id, name, apm-hgvs-c, apm-hgvs-p, apm-acmg-class;'''
                variants = list(tx.query.fetch(variant_query))

                # Diagnosis
                diagnosis_query = f'''match
                    $c isa apm-case, has id "{args.id}";
                    (case: $c, disease: $d) isa apm-case-has-diagnosis;
                fetch $d: id, name, apm-omim-id;'''
                diagnoses = list(tx.query.fetch(diagnosis_query))

                # Notes
                notes_query = f'''match
                    $c isa apm-case, has id "{args.id}";
                    (note: $n, subject: $c) isa aboutness;
                fetch $n: id, name, content;'''
                notes = list(tx.query.fetch(notes_query))

    output = {
        "success": True,
        "case": case_result[0]["c"],
        "phenotypes": [p["p"] for p in phenotypes],
        "variants": [v["v"] for v in variants],
        "diagnoses": [d["d"] for d in diagnoses],
        "notes": [n["n"] for n in notes],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_diagnostic_chain(args):
    """Show the diagnostic reasoning chain for a case."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Full diagnostic chain
                chain_query = f'''match
                    $case isa apm-case, has id "{args.case}";
                    (case: $case, phenotype: $p) isa apm-case-has-phenotype;
                fetch $case: name; $p: apm-hpo-id, apm-hpo-label;'''
                phenotypes = list(tx.query.fetch(chain_query))

                variant_query = f'''match
                    $case isa apm-case, has id "{args.case}";
                    (case: $case, variant: $v) isa apm-case-has-variant;
                    (variant: $v, gene: $g) isa apm-variant-in-gene;
                fetch $v: id, apm-hgvs-c, apm-hgvs-p, apm-acmg-class;
                    $g: apm-gene-symbol;'''
                variants = list(tx.query.fetch(variant_query))

                diagnosis_query = f'''match
                    $case isa apm-case, has id "{args.case}";
                    (case: $case, disease: $d) isa apm-case-has-diagnosis;
                fetch $d: name, apm-omim-id;'''
                diagnoses = list(tx.query.fetch(diagnosis_query))

                # Pathogenicity evidence
                pathogenicity_query = f'''match
                    $case isa apm-case, has id "{args.case}";
                    (case: $case, variant: $v) isa apm-case-has-variant;
                    (variant: $v, disease: $d) isa apm-variant-pathogenicity,
                        has apm-acmg-class $acmg;
                fetch $v: apm-hgvs-c; $d: name; $acmg;'''
                pathogenicity = list(tx.query.fetch(pathogenicity_query))

    output = {
        "success": True,
        "case_id": args.case,
        "phenotypes": [p["p"] for p in phenotypes],
        "variants_with_genes": [{"variant": v["v"], "gene": v["g"]} for v in variants],
        "diagnoses": [d["d"] for d in diagnoses],
        "pathogenicity": pathogenicity,
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_therapeutic_chain(args):
    """Show the therapeutic reasoning chain for a case."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Mechanism of harm
                mechanism_query = f'''match
                    $case isa apm-case, has id "{args.case}";
                    (case: $case, variant: $v) isa apm-case-has-variant;
                    (variant: $v, gene: $g) isa apm-mechanism-of-harm,
                        has apm-mechanism-type $mech, has apm-functional-impact $impact;
                fetch $v: apm-hgvs-c; $g: apm-gene-symbol; $mech; $impact;'''
                mechanisms = list(tx.query.fetch(mechanism_query))

                # Gene-protein links
                protein_query = f'''match
                    $case isa apm-case, has id "{args.case}";
                    (case: $case, variant: $v) isa apm-case-has-variant;
                    (variant: $v, gene: $g) isa apm-variant-in-gene;
                    (gene: $g, protein: $p) isa apm-gene-encodes;
                fetch $g: apm-gene-symbol; $p: name, apm-uniprot-id;'''
                proteins = list(tx.query.fetch(protein_query))

                # Drug targets
                drug_query = f'''match
                    $case isa apm-case, has id "{args.case}";
                    (case: $case, variant: $v) isa apm-case-has-variant;
                    (variant: $v, gene: $g) isa apm-variant-in-gene;
                    (drug: $d, target-gene: $g) isa apm-drug-target;
                fetch $d: name, apm-therapeutic-approach, apm-development-stage;
                    $g: apm-gene-symbol;'''
                drugs = list(tx.query.fetch(drug_query))

    output = {
        "success": True,
        "case_id": args.case,
        "mechanisms": mechanisms,
        "proteins": [{"gene": p["g"], "protein": p["p"]} for p in proteins],
        "drug_targets": [{"drug": d["d"], "gene": d["g"]} for d in drugs],
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_list_cases(args):
    """List all investigation cases."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = "match $c isa apm-case;"

                if args.status:
                    query = f'''match $c isa apm-case,
                        has apm-diagnostic-status "{args.status}";'''

                query += "\nfetch $c: id, name, apm-diagnostic-status, apm-therapeutic-status, apm-investigation-phase;"
                results = list(tx.query.fetch(query))

    cases = []
    for r in results:
        cases.append({
            "id": get_attr(r["c"], "id"),
            "name": get_attr(r["c"], "name"),
            "diagnostic_status": get_attr(r["c"], "apm-diagnostic-status"),
            "therapeutic_status": get_attr(r["c"], "apm-therapeutic-status"),
            "phase": get_attr(r["c"], "apm-investigation-phase"),
        })

    print(json.dumps({"success": True, "cases": cases, "count": len(cases)}, indent=2))


def _list_entities(entity_type, fetch_attrs, label):
    """Generic list command for APM entities."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f"match $e isa {entity_type};\nfetch $e: {fetch_attrs};"
                results = list(tx.query.fetch(query))

    entities = [r["e"] for r in results]
    print(json.dumps({"success": True, label: entities, "count": len(entities)}, indent=2, default=str))


def cmd_list_genes(args):
    _list_entities("apm-gene", "id, name, apm-gene-symbol, apm-entrez-id", "genes")


def cmd_list_variants(args):
    _list_entities("apm-variant", "id, name, apm-hgvs-c, apm-hgvs-p, apm-acmg-class", "variants")


def cmd_list_diseases(args):
    _list_entities("apm-disease", "id, name, apm-omim-id", "diseases")


def cmd_list_phenotypes(args):
    _list_entities("apm-phenotype", "id, apm-hpo-id, apm-hpo-label", "phenotypes")


def cmd_list_drugs(args):
    _list_entities("apm-drug", "id, name, apm-drugbank-id, apm-therapeutic-approach, apm-development-stage", "drugs")


# =============================================================================
# ARTIFACT COMMANDS
# =============================================================================


def cmd_list_artifacts(args):
    """List artifacts by analysis status."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                # Get all APM artifacts (sequencing reports, records, etc.)
                query = """match
                    $a isa artifact;
                    $a has id $aid;
                    { $a isa apm-sequencing-report; } or
                    { $a isa apm-clinvar-record; } or
                    { $a isa apm-omim-record; } or
                    { $a isa apm-gnomad-record; } or
                    { $a isa apm-prediction-record; } or
                    { $a isa apm-drug-record; } or
                    { $a isa apm-pathway-record; } or
                    { $a isa apm-screening-result; };
                fetch $a: id, name, source-uri, created-at;"""
                artifacts = list(tx.query.fetch(query))

                results = []
                for art in artifacts:
                    artifact_id = get_attr(art["a"], "id")

                    # Check for notes (heuristic for "analyzed")
                    notes_query = f'''match
                        $a isa artifact, has id "{artifact_id}";
                        (artifact: $a, referent: $e) isa representation;
                        (note: $n, subject: $e) isa aboutness;
                    fetch $n: id;'''

                    try:
                        notes = list(tx.query.fetch(notes_query))
                        has_notes = len(notes) > 0
                    except Exception:
                        has_notes = False

                    status = "analyzed" if has_notes else "raw"

                    if args.status and args.status != "all":
                        if args.status != status:
                            continue

                    results.append({
                        "id": artifact_id,
                        "name": get_attr(art["a"], "name"),
                        "source_url": get_attr(art["a"], "source-uri"),
                        "created_at": get_attr(art["a"], "created-at"),
                        "status": status,
                    })

    print(json.dumps({
        "success": True,
        "artifacts": results,
        "count": len(results),
        "filter": args.status or "all",
    }, indent=2))


def cmd_show_artifact(args):
    """Get artifact content for sensemaking."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                query = f'''match
                    $a isa artifact, has id "{args.id}";
                fetch $a: id, name, content, cache-path, mime-type, file-size, source-uri, created-at;'''
                result = list(tx.query.fetch(query))

                if not result:
                    print(json.dumps({"success": False, "error": "Artifact not found"}))
                    return

    art = result[0]["a"]

    cache_path = get_attr(art, "cache-path")
    if cache_path and CACHE_AVAILABLE:
        try:
            content = load_from_cache_text(cache_path)
            storage = "cache"
        except FileNotFoundError:
            content = f"[ERROR: Cache file not found: {cache_path}]"
            storage = "cache_missing"
    else:
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
    }

    print(json.dumps(output, indent=2))


# =============================================================================
# TAGGING COMMANDS
# =============================================================================


def cmd_tag(args):
    """Tag an entity."""
    with get_driver() as driver:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            tag_id = generate_id("tag")
            with session.transaction(TransactionType.READ) as tx:
                tag_check = f'match $t isa tag, has name "{args.tag}"; fetch $t: id;'
                existing_tag = list(tx.query.fetch(tag_check))

            if not existing_tag:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(f'insert $t isa tag, has id "{tag_id}", has name "{args.tag}";')
                    tx.commit()

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

    print(json.dumps({
        "success": True,
        "tag": args.tag,
        "entities": [r["e"] for r in results],
        "count": len(results),
    }, indent=2, default=str))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Algorithm for Precision Medicine (APM) CLI - Rare disease investigation notebook"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- Entity Creation ---

    # add-case
    p = subparsers.add_parser("add-case", help="Create an investigation case")
    p.add_argument("--name", required=True, help="Case name")
    p.add_argument("--diagnostic-status", choices=["unsolved", "candidate", "confirmed", "reclassified"],
                    help="Diagnostic status")
    p.add_argument("--therapeutic-status", choices=["exploring", "candidate-therapy", "in-trial", "treating"],
                    help="Therapeutic status")
    p.add_argument("--phase", choices=["diagnostic", "therapeutic", "both"], help="Investigation phase")
    p.add_argument("--description", help="Case description")
    p.add_argument("--id", help="Specific ID")

    # add-gene
    p = subparsers.add_parser("add-gene", help="Add a gene")
    p.add_argument("--symbol", required=True, help="Gene symbol (e.g., NGLY1)")
    p.add_argument("--name", help="Full gene name")
    p.add_argument("--entrez-id", help="NCBI Entrez Gene ID")
    p.add_argument("--ensembl-id", help="Ensembl gene ID")
    p.add_argument("--inheritance", choices=["autosomal-dominant", "autosomal-recessive", "X-linked", "de-novo"],
                    help="Inheritance pattern")
    p.add_argument("--description", help="Gene description")
    p.add_argument("--id", help="Specific ID")

    # add-variant
    p = subparsers.add_parser("add-variant", help="Add a genomic variant")
    p.add_argument("--name", help="Variant name")
    p.add_argument("--gene", help="Gene symbol (for name generation)")
    p.add_argument("--gene-id", help="Gene entity ID to link to")
    p.add_argument("--chromosome", help="Chromosome (e.g., chr1)")
    p.add_argument("--hgvs-c", help="HGVS coding DNA notation")
    p.add_argument("--hgvs-p", help="HGVS protein notation")
    p.add_argument("--hgvs-g", help="HGVS genomic notation")
    p.add_argument("--acmg-class", choices=["pathogenic", "likely-pathogenic", "VUS", "likely-benign", "benign"],
                    help="ACMG classification")
    p.add_argument("--acmg-criteria", help="ACMG criteria (e.g., PS1,PM2,PP3)")
    p.add_argument("--allele-frequency", type=float, help="Allele frequency")
    p.add_argument("--gnomad-af", type=float, help="gnomAD allele frequency")
    p.add_argument("--clinvar-id", help="ClinVar variation ID")
    p.add_argument("--genome-build", help="Genome build (GRCh37, GRCh38)")
    p.add_argument("--transcript-id", help="Transcript ID")
    p.add_argument("--id", help="Specific ID")

    # add-disease
    p = subparsers.add_parser("add-disease", help="Add a disease/condition")
    p.add_argument("--name", required=True, help="Disease name")
    p.add_argument("--omim-id", help="OMIM number")
    p.add_argument("--orpha-id", help="Orphanet ID")
    p.add_argument("--mondo-id", help="MONDO ID")
    p.add_argument("--inheritance", choices=["autosomal-dominant", "autosomal-recessive", "X-linked", "de-novo"],
                    help="Inheritance pattern")
    p.add_argument("--penetrance", choices=["complete", "incomplete", "variable"], help="Penetrance")
    p.add_argument("--description", help="Disease description")
    p.add_argument("--id", help="Specific ID")

    # add-phenotype
    p = subparsers.add_parser("add-phenotype", help="Add an HPO phenotype")
    p.add_argument("--hpo-id", required=True, help="HPO ID (e.g., HP:0001250)")
    p.add_argument("--label", required=True, help="Phenotype label (e.g., Seizures)")
    p.add_argument("--onset", choices=["infantile", "childhood", "juvenile", "adult"], help="Onset category")
    p.add_argument("--severity", choices=["mild", "moderate", "severe", "profound"], help="Severity")
    p.add_argument("--id", help="Specific ID")

    # add-protein
    p = subparsers.add_parser("add-protein", help="Add a protein")
    p.add_argument("--name", required=True, help="Protein name")
    p.add_argument("--uniprot-id", help="UniProt ID")
    p.add_argument("--domain", help="Protein domain")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # add-drug
    p = subparsers.add_parser("add-drug", help="Add a therapeutic compound")
    p.add_argument("--name", required=True, help="Drug name")
    p.add_argument("--drugbank-id", help="DrugBank ID")
    p.add_argument("--chembl-id", help="ChEMBL ID")
    p.add_argument("--approach", help="Therapeutic approach (inhibitor, activator, gene-therapy, ERT, etc.)")
    p.add_argument("--stage", help="Development stage (preclinical, phase-1, ..., approved, off-label)")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # add-pathway
    p = subparsers.add_parser("add-pathway", help="Add a biological pathway")
    p.add_argument("--name", required=True, help="Pathway name")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # add-model
    p = subparsers.add_parser("add-model", help="Add a disease model")
    p.add_argument("--name", required=True, help="Model name")
    p.add_argument("--model-type", choices=["patient-fibroblast", "iPSC", "mouse", "zebrafish", "fly", "yeast"],
                    help="Model type")
    p.add_argument("--species", help="Model species")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # --- Ingestion ---

    # ingest-report
    p = subparsers.add_parser("ingest-report", help="Ingest a sequencing report")
    p.add_argument("--file", required=True, help="Path to report file")
    p.add_argument("--name", help="Report name")

    # ingest-record
    p = subparsers.add_parser("ingest-record", help="Ingest a database record from URL")
    p.add_argument("--type", required=True,
                    choices=["clinvar", "omim", "gnomad", "drugbank", "prediction", "pathway", "screening", "general"],
                    help="Record type")
    p.add_argument("--url", required=True, help="Source URL")
    p.add_argument("--source-id", help="Source-specific ID (ClinVar VCV, OMIM MIM, etc.)")
    p.add_argument("--name", help="Record name")

    # --- Relations (Diagnostic) ---

    # link-case-phenotype
    p = subparsers.add_parser("link-case-phenotype", help="Link phenotype to case")
    p.add_argument("--case", required=True, help="Case ID")
    p.add_argument("--phenotype", required=True, help="Phenotype ID")
    p.add_argument("--onset", help="Onset category for this presentation")
    p.add_argument("--severity", help="Severity for this presentation")

    # link-case-variant
    p = subparsers.add_parser("link-case-variant", help="Link variant to case")
    p.add_argument("--case", required=True, help="Case ID")
    p.add_argument("--variant", required=True, help="Variant ID")
    p.add_argument("--zygosity", choices=["heterozygous", "homozygous", "hemizygous", "compound-het"],
                    help="Zygosity in this patient")

    # link-case-diagnosis
    p = subparsers.add_parser("link-case-diagnosis", help="Link diagnosis to case")
    p.add_argument("--case", required=True, help="Case ID")
    p.add_argument("--disease", required=True, help="Disease ID")
    p.add_argument("--status", choices=["unsolved", "candidate", "confirmed", "reclassified"],
                    help="Diagnostic status")
    p.add_argument("--confidence", type=float, help="Confidence score")

    # link-variant-gene
    p = subparsers.add_parser("link-variant-gene", help="Link variant to gene")
    p.add_argument("--variant", required=True, help="Variant ID")
    p.add_argument("--gene", required=True, help="Gene ID")

    # link-variant-disease
    p = subparsers.add_parser("link-variant-disease", help="Create variant pathogenicity claim")
    p.add_argument("--variant", required=True, help="Variant ID")
    p.add_argument("--disease", required=True, help="Disease ID")
    p.add_argument("--acmg-class", choices=["pathogenic", "likely-pathogenic", "VUS", "likely-benign", "benign"],
                    help="ACMG classification")
    p.add_argument("--confidence", type=float, help="Confidence score")

    # --- Relations (Therapeutic) ---

    # link-mechanism
    p = subparsers.add_parser("link-mechanism", help="Create mechanism of harm relation")
    p.add_argument("--variant", required=True, help="Variant ID")
    p.add_argument("--gene", required=True, help="Gene ID")
    p.add_argument("--mechanism-type", choices=["gain-of-function", "partial-loss", "total-loss",
                    "dominant-negative", "toxification"], help="Mechanism type")
    p.add_argument("--functional-impact", choices=["overactivity", "underactivity", "absence", "toxicity"],
                    help="Functional impact")
    p.add_argument("--confidence", type=float, help="Confidence score")

    # link-gene-protein
    p = subparsers.add_parser("link-gene-protein", help="Gene encodes protein")
    p.add_argument("--gene", required=True, help="Gene ID")
    p.add_argument("--protein", required=True, help="Protein ID")

    # link-drug-target
    p = subparsers.add_parser("link-drug-target", help="Drug targets gene/protein")
    p.add_argument("--drug", required=True, help="Drug ID")
    p.add_argument("--gene", help="Target gene ID")
    p.add_argument("--protein", help="Target protein ID")
    p.add_argument("--approach", help="Therapeutic approach")
    p.add_argument("--confidence", type=float, help="Confidence score")

    # link-drug-indication
    p = subparsers.add_parser("link-drug-indication", help="Drug-disease relationship")
    p.add_argument("--drug", required=True, help="Drug ID")
    p.add_argument("--disease", required=True, help="Disease ID")
    p.add_argument("--stage", help="Development stage")

    # link-pathway-gene
    p = subparsers.add_parser("link-pathway-gene", help="Gene in pathway")
    p.add_argument("--gene", required=True, help="Gene ID")
    p.add_argument("--pathway", required=True, help="Pathway ID")

    # link-model-disease
    p = subparsers.add_parser("link-model-disease", help="Model for disease")
    p.add_argument("--model", required=True, help="Model ID")
    p.add_argument("--disease", required=True, help="Disease ID")
    p.add_argument("--recapitulated", type=bool, help="Phenotype recapitulated")
    p.add_argument("--confidence", type=float, help="Confidence score")

    # --- Notes ---

    # add-note
    p = subparsers.add_parser("add-note", help="Create a note about any entity")
    p.add_argument("--about", required=True, help="Entity ID this note is about")
    p.add_argument("--type", required=True,
                    choices=["diagnosis-hypothesis", "variant-interpretation", "mechanism-analysis",
                             "therapeutic-strategy", "phenotype-genotype", "reanalysis",
                             "cross-case", "screening-analysis", "general"],
                    help="Note type")
    p.add_argument("--content", required=True, help="Note content")
    p.add_argument("--name", help="Note title")
    p.add_argument("--confidence", type=float, help="Confidence score")
    p.add_argument("--tags", nargs="+", help="Tags to apply")
    # Type-specific args
    p.add_argument("--acmg-class", help="ACMG class (for diagnosis/variant notes)")
    p.add_argument("--acmg-criteria", help="ACMG criteria (for variant-interpretation)")
    p.add_argument("--diagnostic-status", help="Diagnostic status (for diagnosis/reanalysis)")
    p.add_argument("--mechanism-type", help="Mechanism type (for mechanism-analysis)")
    p.add_argument("--functional-impact", help="Functional impact (for mechanism/therapeutic)")
    p.add_argument("--therapeutic-approach", help="Therapeutic approach (for therapeutic-strategy)")
    p.add_argument("--id", dest="note_id", help="Specific ID")

    # --- Queries ---

    # show-case
    p = subparsers.add_parser("show-case", help="Full case details")
    p.add_argument("--id", required=True, help="Case ID")

    # show-diagnostic-chain
    p = subparsers.add_parser("show-diagnostic-chain", help="Diagnostic reasoning chain")
    p.add_argument("--case", required=True, help="Case ID")

    # show-therapeutic-chain
    p = subparsers.add_parser("show-therapeutic-chain", help="Therapeutic reasoning chain")
    p.add_argument("--case", required=True, help="Case ID")

    # list-cases
    p = subparsers.add_parser("list-cases", help="List investigation cases")
    p.add_argument("--status", choices=["unsolved", "candidate", "confirmed", "reclassified"],
                    help="Filter by diagnostic status")

    # list-* entity commands
    subparsers.add_parser("list-genes", help="List all genes")
    subparsers.add_parser("list-variants", help="List all variants")
    subparsers.add_parser("list-diseases", help="List all diseases")
    subparsers.add_parser("list-phenotypes", help="List all phenotypes")
    subparsers.add_parser("list-drugs", help="List all drugs")

    # list-artifacts
    p = subparsers.add_parser("list-artifacts", help="List artifacts by status")
    p.add_argument("--status", choices=["raw", "analyzed", "all"], help="Filter by analysis status")

    # show-artifact
    p = subparsers.add_parser("show-artifact", help="Get artifact content")
    p.add_argument("--id", required=True, help="Artifact ID")

    # --- Tagging ---

    # tag
    p = subparsers.add_parser("tag", help="Tag an entity")
    p.add_argument("--entity", required=True, help="Entity ID")
    p.add_argument("--tag", required=True, help="Tag name")

    # search-tag
    p = subparsers.add_parser("search-tag", help="Search by tag")
    p.add_argument("--tag", required=True, help="Tag to search for")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        # Entity Creation
        "add-case": cmd_add_case,
        "add-gene": cmd_add_gene,
        "add-variant": cmd_add_variant,
        "add-disease": cmd_add_disease,
        "add-phenotype": cmd_add_phenotype,
        "add-protein": cmd_add_protein,
        "add-drug": cmd_add_drug,
        "add-pathway": cmd_add_pathway,
        "add-model": cmd_add_model,
        # Ingestion
        "ingest-report": cmd_ingest_report,
        "ingest-record": cmd_ingest_record,
        # Relations (Diagnostic)
        "link-case-phenotype": cmd_link_case_phenotype,
        "link-case-variant": cmd_link_case_variant,
        "link-case-diagnosis": cmd_link_case_diagnosis,
        "link-variant-gene": cmd_link_variant_gene,
        "link-variant-disease": cmd_link_variant_disease,
        # Relations (Therapeutic)
        "link-mechanism": cmd_link_mechanism,
        "link-gene-protein": cmd_link_gene_protein,
        "link-drug-target": cmd_link_drug_target,
        "link-drug-indication": cmd_link_drug_indication,
        "link-pathway-gene": cmd_link_pathway_gene,
        "link-model-disease": cmd_link_model_disease,
        # Notes
        "add-note": cmd_add_note,
        # Queries
        "show-case": cmd_show_case,
        "show-diagnostic-chain": cmd_show_diagnostic_chain,
        "show-therapeutic-chain": cmd_show_therapeutic_chain,
        "list-cases": cmd_list_cases,
        "list-genes": cmd_list_genes,
        "list-variants": cmd_list_variants,
        "list-diseases": cmd_list_diseases,
        "list-phenotypes": cmd_list_phenotypes,
        "list-drugs": cmd_list_drugs,
        "list-artifacts": cmd_list_artifacts,
        "show-artifact": cmd_show_artifact,
        # Tagging
        "tag": cmd_tag,
        "search-tag": cmd_search_tag,
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
