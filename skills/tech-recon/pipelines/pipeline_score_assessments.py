"""
Agentic Memory Systems — Schema-First Assessment Score Pipeline

Hamilton DAG that reads assessment notes from TypeDB and produces:
  - table_data: JSON array of MemorySystemAssessment records (stored in TypeDB analysis.content)
  - plot_code:  Observable Plot heatmap JS expression (stored in TypeDB analysis.plot-code)

Node graph:
  fetch_assessment_notes(investigation_id)  <- TypeDB query
            |
      parse_scores()                        <- Pydantic-validated records
          /        \\
  table_data()   plot_code()               <- terminal outputs

Run via:
  tech_recon.py run-pipeline --id <analysis-id>

The investigation_id is provided via the pipeline config's "inputs" field.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Pydantic models (from parent skill directory)
sys.path.insert(0, str(Path(__file__).parent.parent))
from memory_eval_models import (
    DatasetCharacteristics,
    DimensionScoreSet,
    EvaluationTask,
    MemorySystemAssessment,
    MemoryType,
    Score,
    SystemType,
)

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────

TYPEDB_HOST = os.environ.get("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.environ.get("TYPEDB_PORT", 1729))
TYPEDB_DATABASE = os.environ.get("TYPEDB_DATABASE", "alhazen_notebook")
TYPEDB_PASSWORD = os.environ.get("TYPEDB_PASSWORD", "password")

# Systems that are deployed memory products (vs. evaluation benchmarks)
MEMORY_SYSTEMS: set[str] = {
    "MemPalace",
    "Mem0",
    "Zep",
    "Letta / MemGPT",
    "Supermemory ASMR",
    "Mastra",
    "Karpathy LLM Wiki",
    "lhl/agentic-memory",
}

# Keyword → dimension field mapping for score table parsing
DIMENSION_KEYWORDS: list[tuple[list[str], str]] = [
    (["episodic", "conversational"], "episodic"),
    (["relational", "structured"], "relational"),
    (["schema", "conformance"], "schema_conformance"),
    (["provenance", "attribution"], "provenance"),
    (["contradiction"], "contradiction"),
    (["longitudinal", "stability"], "longitudinal"),
]

# Regex: matches a markdown table row like "| criterion text | 2 | ..."
_SCORE_ROW_RE = re.compile(
    r"^\s*\|\s*([^|]+?)\s*\|\s*(\d)\s*[/|]",
    re.MULTILINE,
)


# ─────────────────────────────────────────
# HAMILTON NODES
# ─────────────────────────────────────────

def fetch_assessment_notes(investigation_id: str) -> list[dict]:
    """
    Fetch all systems + their assessment notes from TypeDB for this investigation.

    Returns a list of dicts with keys:
      system_id, system_name, note_content (str or None)
    """
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    driver = TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials("admin", TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )

    records = []
    try:
        # Step 1: get all systems in the investigation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            systems = list(tx.query(f'''
                match
                  $inv isa tech-recon-investigation, has id "{investigation_id}";
                  $sys isa tech-recon-system, has id $sys_id, has name $sys_name;
                  (investigation: $inv, system: $sys) isa investigated-in;
                fetch {{
                  "system_id": $sys_id,
                  "system_name": $sys_name
                }};
            ''').resolve())

        sys_list = [{"id": r["system_id"], "name": r["system_name"]} for r in systems]

        # Step 2: for each system, fetch its assessment note (if any)
        for sys_info in sys_list:
            sid = sys_info["id"]
            content = None
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                notes = list(tx.query(f'''
                    match
                      $sys isa tech-recon-system, has id "{sid}";
                      $note isa note, has topic "assessment", has content $content;
                      (subject: $sys, note: $note) isa aboutness;
                    fetch {{
                      "content": $content
                    }};
                ''').resolve())
                if notes:
                    content = notes[0].get("content")

            records.append({
                "system_id": sid,
                "system_name": sys_info["name"],
                "note_content": content,
            })

    finally:
        driver.close()

    return records


def parse_scores(
    fetch_assessment_notes: list[dict],
) -> list[MemorySystemAssessment]:
    """
    Parse assessment notes into Pydantic-validated MemorySystemAssessment records.

    For notes with a markdown score table:
      - Extract scores by matching criterion labels to dimension keywords
    For notes without a score table:
      - Default all scores to 0 and log a parse_warning
    """
    results: list[MemorySystemAssessment] = []

    for record in fetch_assessment_notes:
        sys_id = record["system_id"]
        sys_name = record["system_name"]
        content: Optional[str] = record.get("note_content")

        system_type = SystemType.system if sys_name in MEMORY_SYSTEMS else SystemType.benchmark
        warnings: list[str] = []

        # Initialise all dimension scores to 0
        dim_scores: dict[str, int] = {
            "episodic": 0,
            "relational": 0,
            "schema_conformance": 0,
            "provenance": 0,
            "contradiction": 0,
            "longitudinal": 0,
        }

        if content is None:
            warnings.append("no assessment note found; all scores default to 0")
        else:
            # Try to parse a score table from the note content
            rows = _SCORE_ROW_RE.findall(content)
            if not rows:
                warnings.append(
                    "assessment note has no parseable score table; all scores default to 0"
                )
            else:
                found_dims: set[str] = set()
                for criterion_text, score_str in rows:
                    criterion_lower = criterion_text.lower()
                    score_val = int(score_str)
                    matched = False
                    for keywords, field in DIMENSION_KEYWORDS:
                        if any(kw in criterion_lower for kw in keywords):
                            dim_scores[field] = score_val
                            found_dims.add(field)
                            matched = True
                            break
                    if not matched:
                        warnings.append(
                            f"unrecognised criterion in score table: '{criterion_text.strip()}'"
                        )

                missing = set(dim_scores.keys()) - found_dims
                if missing:
                    warnings.append(
                        f"dimensions not found in table (defaulted to 0): {sorted(missing)}"
                    )

        # Build Pydantic model (validates score range 0-3)
        try:
            score_set = DimensionScoreSet(**dim_scores)
        except Exception as exc:
            warnings.append(f"score validation error: {exc}; clamping values")
            clamped = {k: max(0, min(3, v)) for k, v in dim_scores.items()}
            score_set = DimensionScoreSet(**clamped)

        # Extract a brief summary from note content (first non-header paragraph)
        summary: Optional[str] = None
        if content:
            summary_match = re.search(
                r"\*\*Overall fit score[^*]*\*\*([^\n]+)?|Overall Assessment\s*\n([^\n]+)",
                content,
            )
            if not summary_match:
                # Fall back to first non-heading, non-empty line
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("|"):
                        summary = line[:200]
                        break

        assessment = MemorySystemAssessment(
            id=sys_id,
            name=sys_name,
            system_type=system_type,
            scores=score_set,
            assessment_summary=summary,
            parse_warnings=warnings,
        )
        results.append(assessment)

    # Sort: memory systems first (by total desc), then benchmarks (by total desc)
    results.sort(
        key=lambda a: (
            0 if a.system_type == SystemType.system else 1,
            -a.scores.total,
            a.name,
        )
    )
    return results


def table_data(parse_scores: list[MemorySystemAssessment]) -> list[dict]:
    """
    Return validated assessments as a list of dicts.
    run-pipeline serialises this via json.dumps() into TypeDB analysis.content.
    The dashboard then JSON.parse()s it back into the `data` variable for the plot.
    """
    return [a.model_dump(mode="json") for a in parse_scores]


def plot_code(parse_scores: list[MemorySystemAssessment]) -> str:
    """
    Return an Observable Plot heatmap JS expression.
    Stored in TypeDB analysis.plot-code.

    The dashboard evaluates this with `data` bound to the parsed table_data JSON array
    and `Plot` bound to the Observable Plot library.

    Layout:
      - Y axis: system/benchmark names (memory systems first, then benchmarks, both by total desc)
      - X axis: the 6 assessment dimensions
      - Cell color: 0=dark red, 1=amber, 2=green, 3=forest green
      - Cell text: numeric score, light on dark cells, dark on light cells
    """
    return r"""
Plot.plot({
  width: 820, height: 1150,
  marginLeft: 220, marginBottom: 90, marginRight: 20,
  style: {background: "transparent", color: "#e2e8f0", fontSize: "11px"},
  color: {
    domain: [0, 1, 2, 3],
    range: ["#7f1d1d", "#92400e", "#3b6e3b", "#166534"],
    legend: true, label: "Score (0-3)"
  },
  x: {
    label: null, tickRotate: -35,
    domain: ["Episodic", "Relational", "Schema", "Provenance", "Contradiction", "Longitudinal"]
  },
  y: {
    label: null,
    domain: [...data]
      .sort((a, b) =>
        a.system_type !== b.system_type
          ? (a.system_type === "system" ? -1 : 1)
          : b.scores.total - a.scores.total
      )
      .map(d => d.name)
  },
  marks: [
    Plot.cell(
      data.flatMap(d => [
        {s: d.name, c: "Episodic",      v: d.scores.episodic,           t: d.system_type},
        {s: d.name, c: "Relational",    v: d.scores.relational,         t: d.system_type},
        {s: d.name, c: "Schema",        v: d.scores.schema_conformance, t: d.system_type},
        {s: d.name, c: "Provenance",    v: d.scores.provenance,         t: d.system_type},
        {s: d.name, c: "Contradiction", v: d.scores.contradiction,      t: d.system_type},
        {s: d.name, c: "Longitudinal",  v: d.scores.longitudinal,       t: d.system_type}
      ]),
      {x: "c", y: "s", fill: "v", stroke: "#0f172a", strokeWidth: 0.5, inset: 1}
    ),
    Plot.text(
      data.flatMap(d => [
        {s: d.name, c: "Episodic",      v: d.scores.episodic},
        {s: d.name, c: "Relational",    v: d.scores.relational},
        {s: d.name, c: "Schema",        v: d.scores.schema_conformance},
        {s: d.name, c: "Provenance",    v: d.scores.provenance},
        {s: d.name, c: "Contradiction", v: d.scores.contradiction},
        {s: d.name, c: "Longitudinal",  v: d.scores.longitudinal}
      ]),
      {x: "c", y: "s", text: d => String(d.v), fontSize: 10,
       fill: d => d.v >= 2 ? "#f8fafc" : "#94a3b8"}
    )
  ]
})
""".strip()


# ─────────────────────────────────────────
# RUNNER (called by run-pipeline)
# ─────────────────────────────────────────

if __name__ == "__main__":
    import hamilton.driver as hd

    # Hamilton requires inputs to be passed at execute time
    # investigation_id comes from pipeline_config["inputs"]
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
