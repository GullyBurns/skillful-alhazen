"""
<YourSkill> Assessment Pipeline -- Hamilton DAG

This is the canonical Analysis phase pipeline template for TypeDB-backed curation skills.
Copy and adapt for your skill's analysis challenge.

Nodes:
  fetch_records(investigation_id)  -> raw list of dicts from TypeDB
  parse_records(fetch_records)     -> List[EntityAssessment]  (Pydantic-validated)
  table_data(parse_records)        -> JSON string  (stored in TypeDB analysis.content)
  plot_code(parse_records)         -> Observable Plot JS expression  (stored in TypeDB analysis.plot-code)

Node graph:
  fetch_records(investigation_id)
          |
    parse_records()
        /         \\
  table_data()   plot_code()

Register via:
  <skill>.py add-pipeline \\
    --investigation <ID> \\
    --title "My Analysis" \\
    --analysis-type pipeline-plot \\
    --pipeline-script "@skills/<skill>/pipelines/pipeline_template.py" \\
    --pipeline-config '{"outputs":["plot_code","table_data"],"inputs":{"investigation_id":"<ID>"},"env_inputs":{}}'

Run via:
  <skill>.py run-pipeline --id <analysis-id>

Schema evolution: add Optional fields to Pydantic models and re-run -- no data migration needed.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Uncomment and update once you have defined your Pydantic models:
# sys.path.insert(0, str(Path(__file__).parent.parent))
# from eval_models import EntityAssessment, DimensionScores, EntityCategory

# ── CONFIGURATION ─────────────────────────────────────────────────
TYPEDB_HOST = os.environ.get("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.environ.get("TYPEDB_PORT", 1729))
TYPEDB_DATABASE = os.environ.get("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_PASSWORD = os.environ.get("TYPEDB_PASSWORD", "password")

# Keyword -> dimension field mapping for score table parsing.
# The sensemaking agent writes criterion labels that may vary slightly across runs.
# List keywords that should map to each dimension field.
DIMENSION_KEYWORDS: list[tuple[list[str], str]] = [
    (["dimension_a", "alias_a"], "dimension_a"),
    (["dimension_b", "alias_b"], "dimension_b"),
]

# Regex: matches a markdown table row like "| criterion | 2 | explanation |"
_SCORE_ROW_RE = re.compile(
    r"^\s*\|\s*([^|]+?)\s*\|\s*(\d)\s*[/|]",
    re.MULTILINE,
)


# ── HAMILTON NODES ─────────────────────────────────────────────────

def fetch_records(investigation_id: str) -> list[dict]:
    """
    Fetch all entities + their assessment notes from TypeDB.

    Returns a list of dicts with keys: entity_id, entity_name, note_content (str or None).
    Adapt the TypeQL query to match your skill's schema.
    """
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    driver = TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials("admin", TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )

    records = []
    try:
        # Step 1: get all entities in scope
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            entities = list(tx.query(f'''
                match
                  $ctx isa <your-collection-type>, has id "{investigation_id}";
                  $ent isa <your-entity-type>, has id $ent_id, has name $ent_name;
                  (investigation: $ctx, system: $ent) isa investigated-in;
                fetch {{
                  "entity_id": $ent_id,
                  "entity_name": $ent_name
                }};
            ''').resolve())

        for ent in entities:
            eid = ent["entity_id"]
            content = None
            # Step 2: fetch the assessment note for each entity
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                notes = list(tx.query(f'''
                    match
                      $ent isa <your-entity-type>, has id "{eid}";
                      $note isa note, has topic "assessment", has content $content;
                      (subject: $ent, note: $note) isa aboutness;
                    fetch {{ "content": $content }};
                ''').resolve())
                if notes:
                    content = notes[0].get("content")

            records.append({
                "entity_id": eid,
                "entity_name": ent["entity_name"],
                "note_content": content,
            })

    finally:
        driver.close()

    return records


def parse_records(fetch_records: list[dict]) -> list[dict]:
    """
    Parse raw records into validated assessment dicts.

    Once you define your Pydantic models, replace `list[dict]` with
    `list[EntityAssessment]` and uncomment the Pydantic validation block.
    """
    results = []

    for record in fetch_records:
        eid = record["entity_id"]
        ename = record["entity_name"]
        content: Optional[str] = record.get("note_content")
        warnings: list[str] = []

        # Initialise dimension scores to 0
        dim_scores: dict[str, int] = {field: 0 for _, field in DIMENSION_KEYWORDS}

        if content is None:
            warnings.append("no assessment note found; all scores default to 0")
        else:
            rows = _SCORE_ROW_RE.findall(content)
            if not rows:
                warnings.append(
                    "assessment note has no parseable score table; all scores default to 0"
                )
            else:
                found_dims: set[str] = set()
                for criterion_text, score_str in rows:
                    criterion_lower = criterion_text.lower()
                    for keywords, field in DIMENSION_KEYWORDS:
                        if any(kw in criterion_lower for kw in keywords):
                            dim_scores[field] = int(score_str)
                            found_dims.add(field)
                            break

                missing = set(dim_scores.keys()) - found_dims
                if missing:
                    warnings.append(
                        f"dimensions not found in table (defaulted to 0): {sorted(missing)}"
                    )

        total = sum(dim_scores.values())

        # Replace with Pydantic validation once models are defined:
        # assessment = EntityAssessment(
        #     id=eid, name=ename,
        #     scores=DimensionScores(**dim_scores),
        #     parse_warnings=warnings,
        # )
        # results.append(assessment.model_dump(mode="json"))

        results.append({
            "id": eid,
            "name": ename,
            "scores": {**dim_scores, "total": total},
            "parse_warnings": warnings,
        })

    # Sort by total score descending
    results.sort(key=lambda r: -r["scores"]["total"])
    return results


def table_data(parse_records: list[dict]) -> list[dict]:
    """
    Return validated assessments as a list of dicts.
    run-pipeline serialises this via json.dumps() into TypeDB analysis.content.
    The dashboard then JSON.parse()s it back into the `data` variable for the plot.
    """
    return parse_records


def plot_code(parse_records: list[dict]) -> str:
    """
    Return an Observable Plot JS expression.
    Stored in TypeDB analysis.plot-code.

    The dashboard evaluates this with `data` bound to the parsed table_data JSON array
    and `Plot` bound to the Observable Plot library.

    Replace this placeholder with your actual visualization.
    """
    return r"""
Plot.plot({
  width: 700, height: 400,
  marks: [
    Plot.barY(data, {
      x: "name",
      y: d => d.scores?.total ?? 0,
      fill: "steelblue",
      tip: true
    }),
    Plot.ruleY([0])
  ],
  x: {tickRotate: -45, label: null},
  y: {label: "Total score"}
})
""".strip()


# ── RUNNER (called by run-pipeline) ───────────────────────────────

if __name__ == "__main__":
    import hamilton.driver as hd

    investigation_id = os.environ.get("INVESTIGATION_ID", "")
    if not investigation_id:
        print(json.dumps({"success": False, "error": "INVESTIGATION_ID env var not set"}))
        sys.exit(1)

    dr = hd.Builder().with_modules(sys.modules[__name__]).build()
    outputs = dr.execute(
        ["table_data", "plot_code"],
        inputs={"investigation_id": investigation_id},
    )
    preview = {
        k: (v[:200] + "...") if isinstance(v, str) and len(v) > 200 else v
        for k, v in outputs.items()
    }
    print(json.dumps({"success": True, "outputs": preview}))
