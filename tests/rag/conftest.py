from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pipeline.rag.config import RAGConfig
from pipeline.rag.corpus_loader import build_and_persist, load_corpus_and_build_docs
from pipeline.rag.embedding_index import EmbeddingIndex
from pipeline.rag.graph_expand import ConceptExpander
from pipeline.rag.lexical_index import LexicalIndex
from pipeline.rag.retriever import HybridRetriever


class FakeEmbeddingBackend:
    def __init__(self, model_name: str = "fake-multilingual", batch_size: int = 256) -> None:
        self._model_name = model_name
        self._batch_size = batch_size

    def _embed(self, text: str) -> list[float]:
        lowered = text.lower()
        tokens = lowered.split()
        return [
            float(len(lowered)),
            float(len(tokens)),
            float(lowered.count("stop") + lowered.count("стоп")),
            float(lowered.count("example") + lowered.count("пример") + lowered.count("накоплен")),
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def model_id(self) -> str:
        return self._model_name

    def dimension(self) -> int:
        return 4


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _sample_corpus_payloads() -> dict[str, Any]:
    lessons = [
        {
            "lesson_id": "lesson_alpha",
            "lesson_slug": "lesson_alpha",
            "lesson_title": "Lesson Alpha",
            "available_artifacts": ["knowledge_events", "rule_cards", "evidence_index", "concept_graph"],
            "artifact_paths": {},
            "artifact_counts": {"knowledge_events": 2, "rule_cards": 2, "evidence_index": 1},
            "content_hashes": {},
            "status": "ok",
            "warnings": [],
        },
        {
            "lesson_id": "lesson_beta",
            "lesson_slug": "lesson_beta",
            "lesson_title": "Lesson Beta",
            "available_artifacts": ["knowledge_events", "rule_cards", "evidence_index", "concept_graph"],
            "artifact_paths": {},
            "artifact_counts": {"knowledge_events": 1, "rule_cards": 1, "evidence_index": 1},
            "content_hashes": {},
            "status": "ok",
            "warnings": [],
        },
    ]

    knowledge_events = [
        {
            "timestamp_start": "00:10",
            "timestamp_end": "00:16",
            "lesson_id": "lesson_alpha",
            "lesson_title": "Lesson Alpha",
            "section": "Stops",
            "subsection": "Technical stop",
            "source_event_ids": [],
            "event_id": "ke_stop_loss_1",
            "event_type": "rule_statement",
            "raw_text": "Технический стоп прячется за откат.",
            "normalized_text": "Технический стоп прячется за откат.",
            "concept": "Stop Loss",
            "subconcept": "Technical Stop Loss",
            "evidence_refs": ["evidence:lesson_alpha:ev_stop_loss"],
            "confidence": "high",
            "confidence_score": 0.95,
            "ambiguity_notes": [],
            "source_chunk_index": 1,
            "source_line_start": 4,
            "source_line_end": 5,
            "source_quote": "технический стоп прячется за откат",
            "transcript_anchors": [
                {"line_index": 4, "text": "технический стоп", "timestamp_start": "00:10", "timestamp_end": "00:12", "match_source": "llm_source_quote"},
            ],
            "timestamp_confidence": "span",
            "anchor_match_source": "llm_source_quote",
            "anchor_line_count": 1,
            "anchor_span_width": 1,
            "anchor_density": 1.0,
            "metadata": {"candidate_example_types": ["teaching"]},
            "source_language": "ru",
            "concept_id": "node:stop_loss",
            "subconcept_id": "node:technical_stop_loss",
            "condition_ids": [],
            "invalidation_ids": [],
            "exception_ids": [],
            "rule_type": "rule",
            "pattern_tags": ["stop"],
            "normalized_text_ru": "Технический стоп прячется за откат.",
            "concept_label_ru": "Стоп-лосс",
            "subconcept_label_ru": "Технический стоп-лосс",
            "support_basis": "transcript_primary",
            "evidence_requirement": "optional",
            "teaching_mode": "theory",
            "visual_support_level": "illustration",
            "transcript_support_level": "strong",
            "transcript_support_score": 0.9,
            "visual_support_score": 0.2,
            "global_id": "event:lesson_alpha:ke_stop_loss_1",
            "lesson_slug": "lesson_alpha",
        },
        {
            "timestamp_start": "00:30",
            "timestamp_end": "00:36",
            "lesson_id": "lesson_alpha",
            "lesson_title": "Lesson Alpha",
            "section": "Levels",
            "subsection": "Accumulation",
            "source_event_ids": [],
            "event_id": "ke_accumulation_1",
            "event_type": "example",
            "raw_text": "Накопление перед уровнем часто предшествует пробою.",
            "normalized_text": "Накопление перед уровнем часто предшествует пробою.",
            "concept": "Price Action",
            "subconcept": "Accumulation",
            "evidence_refs": ["evidence:lesson_alpha:ev_accumulation"],
            "confidence": "high",
            "confidence_score": 0.92,
            "ambiguity_notes": [],
            "source_chunk_index": 2,
            "source_line_start": 10,
            "source_line_end": 12,
            "source_quote": "накопление перед уровнем",
            "transcript_anchors": [],
            "timestamp_confidence": "span",
            "anchor_match_source": "llm_source_quote",
            "anchor_line_count": 2,
            "anchor_span_width": 2,
            "anchor_density": 1.0,
            "metadata": {"candidate_example_types": ["positive_example"]},
            "source_language": "ru",
            "concept_id": "node:price_action",
            "subconcept_id": "node:accumulation",
            "condition_ids": [],
            "invalidation_ids": [],
            "exception_ids": [],
            "rule_type": "rule",
            "pattern_tags": ["accumulation"],
            "normalized_text_ru": "Накопление перед уровнем часто предшествует пробою.",
            "concept_label_ru": "Прайс экшен",
            "subconcept_label_ru": "Накопление",
            "support_basis": "transcript_plus_visual",
            "evidence_requirement": "required",
            "teaching_mode": "example",
            "visual_support_level": "strong_example",
            "transcript_support_level": "strong",
            "transcript_support_score": 0.8,
            "visual_support_score": 0.7,
            "global_id": "event:lesson_alpha:ke_accumulation_1",
            "lesson_slug": "lesson_alpha",
        },
        {
            "timestamp_start": "00:45",
            "timestamp_end": "00:52",
            "lesson_id": "lesson_beta",
            "lesson_title": "Lesson Beta",
            "section": "Breakouts",
            "subsection": "Failure",
            "source_event_ids": [],
            "event_id": "ke_false_breakout_1",
            "event_type": "warning",
            "raw_text": "Ложный пробой часто отменяет продолжение сценария.",
            "normalized_text": "Ложный пробой часто отменяет продолжение сценария.",
            "concept": "False Breakout",
            "subconcept": "Breakout Failure",
            "evidence_refs": ["evidence:lesson_beta:ev_false_breakout"],
            "confidence": "high",
            "confidence_score": 0.88,
            "ambiguity_notes": [],
            "source_chunk_index": 1,
            "source_line_start": 2,
            "source_line_end": 3,
            "source_quote": "ложный пробой отменяет сценарий",
            "transcript_anchors": [],
            "timestamp_confidence": "span",
            "anchor_match_source": "chunk_fallback",
            "anchor_line_count": 1,
            "anchor_span_width": 1,
            "anchor_density": 1.0,
            "metadata": {},
            "source_language": "ru",
            "concept_id": "node:false_breakout",
            "subconcept_id": "node:breakout_failure",
            "condition_ids": [],
            "invalidation_ids": [],
            "exception_ids": [],
            "rule_type": "rule",
            "pattern_tags": ["breakout"],
            "normalized_text_ru": "Ложный пробой часто отменяет продолжение сценария.",
            "concept_label_ru": "Ложный пробой",
            "subconcept_label_ru": "Срыв пробоя",
            "support_basis": "transcript_plus_visual",
            "evidence_requirement": "optional",
            "teaching_mode": "mixed",
            "visual_support_level": "supporting_example",
            "transcript_support_level": "moderate",
            "transcript_support_score": 0.7,
            "visual_support_score": 0.4,
            "global_id": "event:lesson_beta:ke_false_breakout_1",
            "lesson_slug": "lesson_beta",
        },
    ]

    rule_cards = [
        {
            "lesson_id": "lesson_alpha",
            "lesson_title": "Lesson Alpha",
            "section": "Stops",
            "subsection": "Technical stop",
            "source_event_ids": ["event:lesson_alpha:ke_stop_loss_1"],
            "rule_id": "rule_stop_loss_1",
            "concept": "Stop Loss",
            "subconcept": "Technical Stop Loss",
            "title": "Technical stop loss",
            "rule_text": "Technical stop loss should be hidden behind the pullback.",
            "conditions": ["Use the pullback structure as protection."],
            "context": [],
            "invalidation": ["Do not place it inside noisy consolidation."],
            "exceptions": [],
            "comparisons": ["Calculation stop is shallower."],
            "algorithm_notes": ["Anchor it behind the reaction."],
            "visual_summary": "Chart marks a pullback and technical stop position.",
            "evidence_refs": ["evidence:lesson_alpha:ev_stop_loss"],
            "confidence": "high",
            "confidence_score": 0.94,
            "candidate_features": [],
            "positive_example_refs": [],
            "negative_example_refs": [],
            "ambiguous_example_refs": [],
            "labeling_guidance": None,
            "metadata": {"source_chunk_indexes": [1]},
            "source_language": "ru",
            "concept_id": "node:stop_loss",
            "subconcept_id": "node:technical_stop_loss",
            "condition_ids": [],
            "invalidation_ids": [],
            "exception_ids": [],
            "rule_type": "rule",
            "pattern_tags": ["stop"],
            "rule_text_ru": "Технический стоп прячется за откат.",
            "concept_label_ru": "Стоп-лосс",
            "subconcept_label_ru": "Технический стоп-лосс",
            "support_basis": "transcript_primary",
            "evidence_requirement": "optional",
            "teaching_mode": "theory",
            "visual_support_level": "illustration",
            "transcript_support_level": "strong",
            "transcript_support_score": 0.9,
            "visual_support_score": 0.2,
            "has_visual_evidence": True,
            "transcript_anchor_count": 1,
            "transcript_repetition_count": 0,
            "global_id": "rule:lesson_alpha:rule_stop_loss_1",
            "lesson_slug": "lesson_alpha",
        },
        {
            "lesson_id": "lesson_alpha",
            "lesson_title": "Lesson Alpha",
            "section": "Levels",
            "subsection": "Accumulation",
            "source_event_ids": ["event:lesson_alpha:ke_accumulation_1"],
            "rule_id": "rule_accumulation_1",
            "concept": "Price Action",
            "subconcept": "Accumulation",
            "title": "Accumulation near levels",
            "rule_text": "Accumulation near the level often precedes breakout continuation.",
            "conditions": ["Look for repeated pullbacks into the level."],
            "context": [],
            "invalidation": ["Avoid weak accumulation without reaction."],
            "exceptions": [],
            "comparisons": [],
            "algorithm_notes": ["Use the example chart for confirmation."],
            "visual_summary": "Annotated chart highlights accumulation before breakout.",
            "evidence_refs": ["evidence:lesson_alpha:ev_accumulation"],
            "confidence": "high",
            "confidence_score": 0.91,
            "candidate_features": [],
            "positive_example_refs": [],
            "negative_example_refs": [],
            "ambiguous_example_refs": [],
            "labeling_guidance": None,
            "metadata": {"source_chunk_indexes": [2]},
            "source_language": "ru",
            "concept_id": "node:price_action",
            "subconcept_id": "node:accumulation",
            "condition_ids": [],
            "invalidation_ids": [],
            "exception_ids": [],
            "rule_type": "rule",
            "pattern_tags": ["accumulation"],
            "rule_text_ru": "Накопление перед уровнем часто предшествует пробою.",
            "concept_label_ru": "Прайс экшен",
            "subconcept_label_ru": "Накопление",
            "support_basis": "transcript_plus_visual",
            "evidence_requirement": "required",
            "teaching_mode": "example",
            "visual_support_level": "strong_example",
            "transcript_support_level": "strong",
            "transcript_support_score": 0.8,
            "visual_support_score": 0.7,
            "has_visual_evidence": True,
            "transcript_anchor_count": 2,
            "transcript_repetition_count": 1,
            "global_id": "rule:lesson_alpha:rule_accumulation_1",
            "lesson_slug": "lesson_alpha",
        },
        {
            "lesson_id": "lesson_beta",
            "lesson_title": "Lesson Beta",
            "section": "Breakouts",
            "subsection": "Failure",
            "source_event_ids": ["event:lesson_beta:ke_false_breakout_1"],
            "rule_id": "rule_false_breakout_1",
            "concept": "False Breakout",
            "subconcept": "Breakout Failure",
            "title": "False breakout invalidation",
            "rule_text": "A false breakout invalidates breakout continuation.",
            "conditions": ["Watch for fast return below the level."],
            "context": [],
            "invalidation": ["Continuation is invalidated once price loses acceptance."],
            "exceptions": [],
            "comparisons": ["Acceptance keeps the breakout valid."],
            "algorithm_notes": ["Use HTF context if available."],
            "visual_summary": "Example shows a failed breakout and return below level.",
            "evidence_refs": ["evidence:lesson_beta:ev_false_breakout"],
            "confidence": "high",
            "confidence_score": 0.9,
            "candidate_features": [],
            "positive_example_refs": [],
            "negative_example_refs": [],
            "ambiguous_example_refs": [],
            "labeling_guidance": None,
            "metadata": {"source_chunk_indexes": [1]},
            "source_language": "ru",
            "concept_id": "node:false_breakout",
            "subconcept_id": "node:breakout_failure",
            "condition_ids": [],
            "invalidation_ids": [],
            "exception_ids": [],
            "rule_type": "rule",
            "pattern_tags": ["breakout"],
            "rule_text_ru": "Ложный пробой часто отменяет продолжение сценария.",
            "concept_label_ru": "Ложный пробой",
            "subconcept_label_ru": "Срыв пробоя",
            "support_basis": "transcript_plus_visual",
            "evidence_requirement": "optional",
            "teaching_mode": "mixed",
            "visual_support_level": "supporting_example",
            "transcript_support_level": "moderate",
            "transcript_support_score": 0.7,
            "visual_support_score": 0.4,
            "has_visual_evidence": True,
            "transcript_anchor_count": 1,
            "transcript_repetition_count": 0,
            "global_id": "rule:lesson_beta:rule_false_breakout_1",
            "lesson_slug": "lesson_beta",
        },
    ]

    evidence = [
        {
            "timestamp_start": "00:11",
            "timestamp_end": "00:15",
            "lesson_id": "lesson_alpha",
            "lesson_title": "Lesson Alpha",
            "section": "Stops",
            "subsection": "Technical stop",
            "source_event_ids": ["event:lesson_alpha:ke_stop_loss_1"],
            "evidence_id": "ev_stop_loss",
            "frame_ids": ["000011"],
            "screenshot_paths": ["lesson_alpha/frames_dense/000011.jpg"],
            "visual_type": "annotated_chart",
            "example_role": "illustration",
            "compact_visual_summary": "Annotated chart shows technical stop placement behind pullback.",
            "linked_rule_ids": ["rule:lesson_alpha:rule_stop_loss_1"],
            "raw_visual_event_ids": ["raw_11"],
            "metadata": {},
            "source_language": "ru",
            "related_concept_ids": ["node:stop_loss"],
            "summary_primary": "Annotated chart shows technical stop placement behind pullback.",
            "summary_language": "en",
            "summary_ru": "График показывает расположение технического стопа.",
            "summary_en": "Annotated chart shows technical stop placement behind pullback.",
            "evidence_strength": "moderate",
            "evidence_role_detail": "illustrates_rule",
            "global_id": "evidence:lesson_alpha:ev_stop_loss",
            "lesson_slug": "lesson_alpha",
        },
        {
            "timestamp_start": "00:31",
            "timestamp_end": "00:35",
            "lesson_id": "lesson_alpha",
            "lesson_title": "Lesson Alpha",
            "section": "Levels",
            "subsection": "Accumulation",
            "source_event_ids": ["event:lesson_alpha:ke_accumulation_1"],
            "evidence_id": "ev_accumulation",
            "frame_ids": ["000031"],
            "screenshot_paths": ["lesson_alpha/frames_dense/000031.jpg"],
            "visual_type": "annotated_chart",
            "example_role": "positive_example",
            "compact_visual_summary": "Annotated chart highlights accumulation before breakout.",
            "linked_rule_ids": ["rule:lesson_alpha:rule_accumulation_1"],
            "raw_visual_event_ids": ["raw_31"],
            "metadata": {},
            "source_language": "ru",
            "related_concept_ids": ["node:accumulation", "node:breakout"],
            "summary_primary": "Annotated chart highlights accumulation before breakout.",
            "summary_language": "en",
            "summary_ru": "График показывает накопление перед пробоем.",
            "summary_en": "Annotated chart highlights accumulation before breakout.",
            "evidence_strength": "strong",
            "evidence_role_detail": "positive_example",
            "global_id": "evidence:lesson_alpha:ev_accumulation",
            "lesson_slug": "lesson_alpha",
        },
        {
            "timestamp_start": "00:47",
            "timestamp_end": "00:50",
            "lesson_id": "lesson_beta",
            "lesson_title": "Lesson Beta",
            "section": "Breakouts",
            "subsection": "Failure",
            "source_event_ids": ["event:lesson_beta:ke_false_breakout_1"],
            "evidence_id": "ev_false_breakout",
            "frame_ids": ["000047"],
            "screenshot_paths": ["lesson_beta/frames_dense/000047.jpg"],
            "visual_type": "annotated_chart",
            "example_role": "counterexample",
            "compact_visual_summary": "Chart shows false breakout and failure to hold above level.",
            "linked_rule_ids": ["rule:lesson_beta:rule_false_breakout_1"],
            "raw_visual_event_ids": ["raw_47"],
            "metadata": {},
            "source_language": "ru",
            "related_concept_ids": ["node:false_breakout", "node:breakout"],
            "summary_primary": "Chart shows false breakout and failure to hold above level.",
            "summary_language": "en",
            "summary_ru": "График показывает ложный пробой.",
            "summary_en": "Chart shows false breakout and failure to hold above level.",
            "evidence_strength": "strong",
            "evidence_role_detail": "counterexample",
            "global_id": "evidence:lesson_beta:ev_false_breakout",
            "lesson_slug": "lesson_beta",
        },
    ]

    graph = {
        "lesson_id": "corpus",
        "graph_version": "1.0",
        "nodes": [
            {"concept_id": "stop_loss", "name": "Stop Loss", "type": "concept", "parent_id": None, "aliases": ["стоп лосс", "sl"], "source_rule_ids": ["rule:lesson_alpha:rule_stop_loss_1"], "canonical_label": "stop_loss", "metadata": {}, "global_id": "node:stop_loss", "source_lessons": ["lesson_alpha", "lesson_beta"]},
            {"concept_id": "technical_stop_loss", "name": "Technical Stop Loss", "type": "subconcept", "parent_id": "node:stop_loss", "aliases": ["технический стоп"], "source_rule_ids": ["rule:lesson_alpha:rule_stop_loss_1"], "canonical_label": "technical_stop_loss", "metadata": {}, "global_id": "node:technical_stop_loss", "source_lessons": ["lesson_alpha"]},
            {"concept_id": "price_action", "name": "Price Action", "type": "concept", "parent_id": None, "aliases": ["прайс экшен"], "source_rule_ids": ["rule:lesson_alpha:rule_accumulation_1"], "canonical_label": "price_action", "metadata": {}, "global_id": "node:price_action", "source_lessons": ["lesson_alpha"]},
            {"concept_id": "accumulation", "name": "Accumulation", "type": "subconcept", "parent_id": "node:price_action", "aliases": ["накопление"], "source_rule_ids": ["rule:lesson_alpha:rule_accumulation_1"], "canonical_label": "accumulation", "metadata": {}, "global_id": "node:accumulation", "source_lessons": ["lesson_alpha"]},
            {"concept_id": "breakout", "name": "Breakout", "type": "concept", "parent_id": None, "aliases": ["пробой"], "source_rule_ids": ["rule:lesson_alpha:rule_accumulation_1", "rule:lesson_beta:rule_false_breakout_1"], "canonical_label": "breakout", "metadata": {}, "global_id": "node:breakout", "source_lessons": ["lesson_alpha", "lesson_beta"]},
            {"concept_id": "false_breakout", "name": "False Breakout", "type": "concept", "parent_id": None, "aliases": ["ложный пробой"], "source_rule_ids": ["rule:lesson_beta:rule_false_breakout_1"], "canonical_label": "false_breakout", "metadata": {}, "global_id": "node:false_breakout", "source_lessons": ["lesson_beta"]},
            {"concept_id": "breakout_failure", "name": "Breakout Failure", "type": "subconcept", "parent_id": "node:false_breakout", "aliases": ["срыв пробоя"], "source_rule_ids": ["rule:lesson_beta:rule_false_breakout_1"], "canonical_label": "breakout_failure", "metadata": {}, "global_id": "node:breakout_failure", "source_lessons": ["lesson_beta"]},
        ],
        "relations": [
            {"relation_id": "rel:node:accumulation:precedes:node:breakout", "source_id": "node:accumulation", "target_id": "node:breakout", "relation_type": "precedes", "weight": 1, "source_rule_ids": ["rule:lesson_alpha:rule_accumulation_1"], "source_lessons": ["lesson_alpha"]},
            {"relation_id": "rel:node:false_breakout:invalidates:node:breakout", "source_id": "node:false_breakout", "target_id": "node:breakout", "relation_type": "invalidates", "weight": 1, "source_rule_ids": ["rule:lesson_beta:rule_false_breakout_1"], "source_lessons": ["lesson_beta"]},
            {"relation_id": "rel:node:stop_loss:depends_on:node:breakout", "source_id": "node:stop_loss", "target_id": "node:breakout", "relation_type": "depends_on", "weight": 1, "source_rule_ids": ["rule:lesson_alpha:rule_stop_loss_1"], "source_lessons": ["lesson_alpha"]},
        ],
    }

    alias_registry = {
        "node:stop_loss": {"name": "Stop Loss", "aliases": ["стоп лосс", "sl"], "source_lessons": ["lesson_alpha", "lesson_beta"], "type": "concept"},
        "node:technical_stop_loss": {"name": "Technical Stop Loss", "aliases": ["технический стоп"], "source_lessons": ["lesson_alpha"], "type": "subconcept"},
        "node:price_action": {"name": "Price Action", "aliases": ["прайс экшен"], "source_lessons": ["lesson_alpha"], "type": "concept"},
        "node:accumulation": {"name": "Accumulation", "aliases": ["накопление"], "source_lessons": ["lesson_alpha"], "type": "subconcept"},
        "node:breakout": {"name": "Breakout", "aliases": ["пробой"], "source_lessons": ["lesson_alpha", "lesson_beta"], "type": "concept"},
        "node:false_breakout": {"name": "False Breakout", "aliases": ["ложный пробой"], "source_lessons": ["lesson_beta"], "type": "concept"},
        "node:breakout_failure": {"name": "Breakout Failure", "aliases": ["срыв пробоя"], "source_lessons": ["lesson_beta"], "type": "subconcept"},
    }

    return {
        "schema_versions.json": {"corpus_contract_version": "0.3.0"},
        "lesson_registry.json": lessons,
        "corpus_metadata.json": {"corpus_contract_version": "0.3.0", "lesson_count": 2},
        "corpus_lessons.jsonl": lessons,
        "corpus_knowledge_events.jsonl": knowledge_events,
        "corpus_rule_cards.jsonl": rule_cards,
        "corpus_evidence_index.jsonl": evidence,
        "corpus_concept_graph.json": graph,
        "concept_alias_registry.json": alias_registry,
        "concept_frequencies.json": {
            "node:stop_loss": {"rule_count": 1, "event_count": 1, "lesson_count": 2},
            "node:accumulation": {"rule_count": 1, "event_count": 1, "lesson_count": 1},
            "node:false_breakout": {"rule_count": 1, "event_count": 1, "lesson_count": 1},
        },
        "concept_rule_map.json": {
            "node:stop_loss": ["rule:lesson_alpha:rule_stop_loss_1"],
            "node:accumulation": ["rule:lesson_alpha:rule_accumulation_1"],
            "node:false_breakout": ["rule:lesson_beta:rule_false_breakout_1"],
            "node:breakout": ["rule:lesson_alpha:rule_accumulation_1", "rule:lesson_beta:rule_false_breakout_1"],
        },
        "rule_family_index.json": {
            "stop_loss_technical": ["rule:lesson_alpha:rule_stop_loss_1"],
            "accumulation_breakout": ["rule:lesson_alpha:rule_accumulation_1"],
            "false_breakout": ["rule:lesson_beta:rule_false_breakout_1"],
        },
        "concept_overlap_report.json": [
            {"concept_id": "node:stop_loss", "name": "Stop Loss", "lessons": ["lesson_alpha", "lesson_beta"], "lesson_count": 2},
            {"concept_id": "node:breakout", "name": "Breakout", "lessons": ["lesson_alpha", "lesson_beta"], "lesson_count": 2},
        ],
    }


@pytest.fixture
def rag_corpus_root(tmp_path: Path) -> Path:
    corpus_root = tmp_path / "output_corpus"
    payloads = _sample_corpus_payloads()
    for name, payload in payloads.items():
        path = corpus_root / name
        if name.endswith(".jsonl"):
            _write_jsonl(path, payload)
        else:
            _write_json(path, payload)
    return corpus_root


@pytest.fixture
def rag_output_root(tmp_path: Path) -> Path:
    return tmp_path / "output_rag"


@pytest.fixture
def rag_config(rag_corpus_root: Path, rag_output_root: Path) -> RAGConfig:
    return RAGConfig(corpus_root=rag_corpus_root, rag_root=rag_output_root, embedding_model="fake-multilingual")


@pytest.fixture
def fake_backend() -> FakeEmbeddingBackend:
    return FakeEmbeddingBackend()


@pytest.fixture
def doc_store(rag_config: RAGConfig):
    return load_corpus_and_build_docs(rag_config)


@pytest.fixture
def all_docs(doc_store):
    return doc_store.get_all()


@pytest.fixture
def lexical_index(all_docs):
    return LexicalIndex.build(all_docs)


@pytest.fixture
def embedding_index(all_docs, fake_backend: FakeEmbeddingBackend):
    return EmbeddingIndex.build(all_docs, backend=fake_backend)


@pytest.fixture
def concept_expander(rag_corpus_root: Path):
    return ConceptExpander.from_corpus(rag_corpus_root)


@pytest.fixture
def hybrid_retriever(doc_store, lexical_index, embedding_index, concept_expander, rag_config: RAGConfig):
    return HybridRetriever(doc_store, lexical_index, embedding_index, concept_expander, rag_config)


@pytest.fixture
def built_rag_root(rag_config: RAGConfig, fake_backend: FakeEmbeddingBackend) -> Path:
    build_and_persist(rag_config)
    store = load_corpus_and_build_docs(rag_config)
    lexical = LexicalIndex.build(store.get_all())
    lexical.save(rag_config.index_dir)
    embedding = EmbeddingIndex.build(store.get_all(), backend=fake_backend)
    embedding.save(rag_config.index_dir)
    return rag_config.rag_root


@pytest.fixture
def patch_fake_sentence_transformer(monkeypatch):
    from pipeline.rag import embedding_index as embedding_module

    monkeypatch.setattr(embedding_module, "SentenceTransformerBackend", FakeEmbeddingBackend)
    return FakeEmbeddingBackend
