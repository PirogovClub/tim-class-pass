"""Typed contracts for the hybrid RAG pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from pipeline.rag.config import UnitType

RequiredCorpusFile = Literal[
    "schema_versions.json",
    "lesson_registry.json",
    "corpus_metadata.json",
    "corpus_lessons.jsonl",
    "corpus_knowledge_events.jsonl",
    "corpus_rule_cards.jsonl",
    "corpus_evidence_index.jsonl",
    "corpus_concept_graph.json",
    "concept_alias_registry.json",
    "concept_frequencies.json",
    "concept_rule_map.json",
    "rule_family_index.json",
    "concept_overlap_report.json",
]

REQUIRED_CORPUS_FILES: tuple[RequiredCorpusFile, ...] = (
    "schema_versions.json",
    "lesson_registry.json",
    "corpus_metadata.json",
    "corpus_lessons.jsonl",
    "corpus_knowledge_events.jsonl",
    "corpus_rule_cards.jsonl",
    "corpus_evidence_index.jsonl",
    "corpus_concept_graph.json",
    "concept_alias_registry.json",
    "concept_frequencies.json",
    "concept_rule_map.json",
    "rule_family_index.json",
    "concept_overlap_report.json",
)


class CorpusInputManifest(BaseModel):
    corpus_root: Path
    files: dict[str, Path]

    @classmethod
    def from_root(cls, corpus_root: Path) -> "CorpusInputManifest":
        missing: list[str] = []
        files: dict[str, Path] = {}
        for filename in REQUIRED_CORPUS_FILES:
            path = corpus_root / filename
            if not path.exists():
                missing.append(filename)
            files[filename] = path
        if missing:
            missing_list = ", ".join(missing)
            raise FileNotFoundError(f"Missing required corpus files under {corpus_root}: {missing_list}")
        return cls(corpus_root=corpus_root, files=files)

    def path(self, filename: RequiredCorpusFile) -> Path:
        return self.files[filename]


class GraphExpansionTraceStep(BaseModel):
    step_type: str
    source: str
    target: str | None = None
    relation: str | None = None
    reason: str


class GraphExpansionResult(BaseModel):
    detected_terms: list[str] = Field(default_factory=list)
    exact_alias_matches: dict[str, str] = Field(default_factory=dict)
    normalized_alias_matches: dict[str, str] = Field(default_factory=dict)
    canonical_concept_ids: list[str] = Field(default_factory=list)
    expanded_concept_ids: list[str] = Field(default_factory=list)
    boosted_rule_ids: list[str] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)
    expansion_trace: list[GraphExpansionTraceStep] = Field(default_factory=list)
    # Extra terms for lexical alias boost / query enrichment
    lexical_expansion_terms: list[str] = Field(default_factory=list)


class SearchFilters(BaseModel):
    lesson_ids: list[str] = Field(default_factory=list)
    concept_ids: list[str] = Field(default_factory=list)
    min_confidence_score: float | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    unit_types: list[UnitType] = Field(default_factory=list)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    return_summary: bool = True
    require_evidence: bool = Field(
        default=False,
        description="When true, only hits with at least one evidence_id are returned (Stage 6.3).",
    )


class SearchHit(BaseModel):
    model_config = {"extra": "allow"}

    doc_id: str
    global_id: str = ""
    unit_type: UnitType
    lesson_id: str | None = None
    concept: str = ""
    subconcept: str = ""
    title: str = ""
    text_snippet: str = ""
    timestamps: list[dict[str, Any]] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    source_rule_ids: list[str] = Field(default_factory=list)
    raw_lexical_score: float = 0.0
    raw_vector_score: float = 0.0
    graph_boost: float = 0.0
    score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    why_retrieved: list[str] = Field(default_factory=list)


class QueryIntentSignalsModel(BaseModel):
    """Deterministic intent sidecar (mirrors query_intents.QueryIntentSignals)."""

    prefers_transcript_only: bool = False
    prefers_visual_evidence: bool = False
    mentions_timeframe: bool = False
    mentions_cross_lesson: bool = False
    mentions_stoploss: bool = False
    prefers_actionable_rules: bool = False
    prefers_explicit_rules: bool = False
    prefers_examples: bool = False
    prefers_theory: bool = False


class SearchQueryAnalysis(BaseModel):
    normalized_query: str
    detected_concepts: list[str] = Field(default_factory=list)
    detected_unit_bias: str = "mixed"
    detected_intents: list[str] = Field(default_factory=list)
    intent_signals: QueryIntentSignalsModel = Field(default_factory=QueryIntentSignalsModel)
    expansion_trace: GraphExpansionResult = Field(default_factory=GraphExpansionResult)


class SearchSummary(BaseModel):
    answer_text: str | None = None
    limitations: list[str] = Field(default_factory=list)
    citation_doc_ids: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    query_analysis: SearchQueryAnalysis
    top_hits: list[SearchHit] = Field(default_factory=list)
    grouped_results: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    summary: SearchSummary = Field(default_factory=SearchSummary)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    hit_count: int = 0


class RAGBuildResult(BaseModel):
    corpus_contract_version: str
    source_corpus_root: Path
    retrieval_doc_counts: dict[str, int]
    total_retrieval_docs: int
    build_timestamp: datetime
    lexical_manifest_path: Path | None = None
    embedding_manifest_path: Path | None = None
