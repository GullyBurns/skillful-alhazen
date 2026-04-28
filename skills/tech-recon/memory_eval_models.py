"""
Pydantic v2 models for the memory system assessment schema.

These are the typed intermediate data structures exchanged between Hamilton nodes
in pipeline_score_assessments.py. They implement the LinkML schema defined in
schema/memory_eval.yaml and provide:
  - Runtime validation (Pydantic)
  - JSON Schema generation (model_json_schema())
  - Automatic total score computation (model_validator)

Schema evolution: add Optional fields here to extend without breaking existing records.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────
# CONSTRAINED TYPES
# ─────────────────────────────────────────

Score = Annotated[int, Field(ge=0, le=3)]


# ─────────────────────────────────────────
# ENUMERATIONS
# ─────────────────────────────────────────

class SystemType(str, Enum):
    system = "system"
    benchmark = "benchmark"


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"
    temporal = "temporal"
    multi_session = "multi_session"
    preference = "preference"
    relational = "relational"
    working = "working"


class EvaluationTask(str, Enum):
    qa = "qa"
    generation = "generation"
    retrieval = "retrieval"
    multi_hop = "multi_hop"
    abstention = "abstention"
    temporal_reasoning = "temporal_reasoning"
    update_detection = "update_detection"
    contradiction_detection = "contradiction_detection"
    schema_validation = "schema_validation"


# ─────────────────────────────────────────
# CLASSES
# ─────────────────────────────────────────

class DimensionScoreSet(BaseModel):
    """Scores on the six schema-first curation assessment dimensions."""

    episodic: Score
    relational: Score
    schema_conformance: Score
    provenance: Score
    contradiction: Score
    longitudinal: Score
    total: int = 0

    @model_validator(mode="after")
    def compute_total(self) -> "DimensionScoreSet":
        self.total = (
            self.episodic
            + self.relational
            + self.schema_conformance
            + self.provenance
            + self.contradiction
            + self.longitudinal
        )
        return self


class DatasetCharacteristics(BaseModel):
    """Properties of the evaluation dataset used by this benchmark or system."""

    domain: Optional[str] = None
    synthetic: Optional[bool] = None
    session_count: Optional[int] = None
    question_count: Optional[int] = None
    languages: list[str] = []
    has_ground_truth: Optional[bool] = None


class MemorySystemAssessment(BaseModel):
    """
    Complete assessment record for one memory system or benchmark.

    One record per system in the tech-recon investigation. Acts as the top-level
    unit of analysis — a row in the heatmap visualization.
    """

    id: str
    name: str
    system_type: SystemType
    arxiv_id: Optional[str] = None
    source_url: Optional[str] = None
    github_url: Optional[str] = None
    scores: DimensionScoreSet
    memory_types_tested: list[MemoryType] = []
    evaluation_tasks: list[EvaluationTask] = []
    dataset: Optional[DatasetCharacteristics] = None
    assessment_summary: Optional[str] = None
    parse_warnings: list[str] = []


# ─────────────────────────────────────────
# JSON SCHEMA GENERATION
# ─────────────────────────────────────────

if __name__ == "__main__":
    import json
    print(json.dumps(MemorySystemAssessment.model_json_schema(), indent=2))
