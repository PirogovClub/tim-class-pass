"""RAG configuration — paths, model names, retrieval defaults."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


UnitType = Literal[
    "rule_card",
    "knowledge_event",
    "evidence_ref",
    "concept_node",
    "concept_relation",
]

ALL_UNIT_TYPES: list[UnitType] = [
    "rule_card",
    "knowledge_event",
    "evidence_ref",
    "concept_node",
    "concept_relation",
]


class RAGConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    corpus_root: Path = Path("output_corpus")
    rag_root: Path = Path("output_rag")
    asset_root: Path = Path("data")

    embedding_backend: str = "sentence-transformers"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    embedding_batch_size: int = 256

    lexical_backend: str = "bm25"
    lexical_top_k: int = 40
    vector_top_k: int = 40
    merged_top_k: int = 80
    final_top_k: int = 10

    default_unit_weights: dict[str, float] = Field(default_factory=lambda: {
        "rule_card": 1.00,
        "knowledge_event": 0.95,
        "evidence_ref": 0.95,
        "concept_node": 0.85,
        "concept_relation": 0.80,
    })
    exact_alias_boost: float = 0.15
    timestamp_boost: float = 0.05
    evidence_boost: float = 0.05
    confidence_boost: float = 0.05
    lesson_diversity_adjustment: float = 0.05

    reranker_weights: dict[str, float] = Field(default_factory=lambda: {
        "lexical_score": 0.26,
        "vector_score": 0.26,
        "graph_boost": 0.14,
        "concept_exact_match": 0.12,
        "alias_match": 0.05,
        "unit_type_relevance": 0.06,
        "support_basis_relevance": 0.04,
        "teaching_mode_relevance": 0.03,
        "evidence_requirement_relevance": 0.04,
        "evidence_strength_relevance": 0.03,
        "confidence_score": 0.04,
        "evidence_available": 0.06,
        "timestamp_available": 0.05,
        "provenance_richness": 0.04,
        "lesson_diversity_bonus": 0.02,
        "groundedness": 0.04,
        "intent_cross_lesson_boost": 0.12,
        "intent_timeframe_boost": 0.14,
        "intent_evidence_priority_boost": 0.34,
        "example_role_relevance": 0.06,
        "intent_evidence_mismatch_penalty": 0.18,
        "intent_transcript_policy_signal": 0.28,
        "intent_concept_priority_signal": 0.38,
    })

    # Scales for applying config.timestamp_boost / evidence_boost inside reranker (Step 3.1)
    step31_timestamp_scale: float = 1.0
    step31_evidence_scale: float = 1.0

    enable_graph_expand: bool = True
    max_graph_expansion: int = 3
    max_expansion_hops: int = 1
    max_expanded_per_concept: int = 3

    @classmethod
    def from_sources(
        cls,
        config_path: str | Path | None = None,
        **overrides: object,
    ) -> "RAGConfig":
        data: dict[str, object] = {}
        yaml_path = Path(config_path) if config_path else Path("rag_config.yaml")
        if yaml_path.exists():
            loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"RAG config YAML must contain an object: {yaml_path}")
            data.update(loaded)
        data.update(_env_overrides())
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**data)

    @property
    def index_dir(self) -> Path:
        return self.rag_root / "index"

    @property
    def eval_dir(self) -> Path:
        return self.rag_root / "eval"


def _json_env(name: str) -> object | None:
    value = os.getenv(name)
    if not value:
        return None
    return json.loads(value)


def _bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str) -> int | None:
    value = os.getenv(name)
    return int(value) if value else None


def _float_env(name: str) -> float | None:
    value = os.getenv(name)
    return float(value) if value else None


def _path_env(name: str) -> Path | None:
    value = os.getenv(name)
    return Path(value) if value else None


def _env_overrides() -> dict[str, object]:
    mapping: dict[str, object | None] = {
        "corpus_root": _path_env("RAG_CORPUS_ROOT"),
        "rag_root": _path_env("RAG_ROOT"),
        "asset_root": _path_env("RAG_ASSET_ROOT"),
        "embedding_backend": os.getenv("RAG_EMBEDDING_BACKEND"),
        "embedding_model": os.getenv("RAG_EMBEDDING_MODEL"),
        "embedding_dim": _int_env("RAG_EMBEDDING_DIM"),
        "embedding_batch_size": _int_env("RAG_EMBEDDING_BATCH_SIZE"),
        "lexical_backend": os.getenv("RAG_LEXICAL_BACKEND"),
        "lexical_top_k": _int_env("RAG_LEXICAL_TOP_K"),
        "vector_top_k": _int_env("RAG_VECTOR_TOP_K"),
        "merged_top_k": _int_env("RAG_MERGED_TOP_K"),
        "final_top_k": _int_env("RAG_FINAL_TOP_K"),
        "default_unit_weights": _json_env("RAG_DEFAULT_UNIT_WEIGHTS"),
        "reranker_weights": _json_env("RAG_RERANKER_WEIGHTS"),
        "enable_graph_expand": _bool_env("RAG_ENABLE_GRAPH_EXPAND"),
        "max_graph_expansion": _int_env("RAG_MAX_GRAPH_EXPANSION"),
        "max_expansion_hops": _int_env("RAG_MAX_EXPANSION_HOPS"),
        "max_expanded_per_concept": _int_env("RAG_MAX_EXPANDED_PER_CONCEPT"),
        "exact_alias_boost": _float_env("RAG_EXACT_ALIAS_BOOST"),
        "timestamp_boost": _float_env("RAG_TIMESTAMP_BOOST"),
        "evidence_boost": _float_env("RAG_EVIDENCE_BOOST"),
        "confidence_boost": _float_env("RAG_CONFIDENCE_BOOST"),
        "lesson_diversity_adjustment": _float_env("RAG_LESSON_DIVERSITY_ADJUSTMENT"),
    }
    return {key: value for key, value in mapping.items() if value is not None}
