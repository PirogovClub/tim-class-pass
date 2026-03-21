"""RAG configuration — paths, model names, retrieval defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


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
    corpus_root: Path = Path("output_corpus")
    rag_root: Path = Path("output_rag")

    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    embedding_batch_size: int = 256

    lexical_top_k: int = 30
    vector_top_k: int = 30
    merged_top_k: int = 50
    final_top_k: int = 10

    reranker_weights: dict[str, float] = Field(default_factory=lambda: {
        "lexical_score": 0.30,
        "vector_score": 0.30,
        "concept_exact_match": 0.15,
        "alias_match": 0.05,
        "confidence_score": 0.05,
        "evidence_available": 0.05,
        "timestamp_available": 0.05,
        "provenance_richness": 0.05,
    })

    max_expansion_hops: int = 1
    max_expanded_per_concept: int = 3

    @property
    def index_dir(self) -> Path:
        return self.rag_root / "index"

    @property
    def eval_dir(self) -> Path:
        return self.rag_root / "eval"
