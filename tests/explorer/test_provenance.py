"""Tests for Task 11 provenance helpers (builders, merge, validation, coverage)."""

from __future__ import annotations

import pytest

from pipeline.component2.provenance import (
    build_evidence_ref_provenance,
    build_knowledge_event_provenance,
    build_rule_card_provenance,
    compact_nonempty_ints,
    compact_nonempty_strs,
    compute_provenance_coverage,
    dedupe_preserve_order,
    format_compact_provenance,
    merge_evidence_refs,
    merge_source_event_ids,
    merge_source_chunk_indexes,
    merge_source_sections,
    merge_source_subsections,
    prune_none_values,
    validate_evidence_ref_provenance,
    validate_knowledge_event_provenance,
    validate_rule_card_provenance,
)


# ---- Core helpers ----


def test_dedupe_preserve_order():
    assert dedupe_preserve_order([1, 2, 1, 3, 2]) == [1, 2, 3]
    assert dedupe_preserve_order(["a", "b", "a"]) == ["a", "b"]
    assert dedupe_preserve_order([None, "", "x", ""]) == ["x"]
    assert dedupe_preserve_order([]) == []


def test_compact_nonempty_strs():
    assert compact_nonempty_strs(["a", "  ", "", "b", "a"]) == ["a", "b"]
    assert compact_nonempty_strs([None, "x"]) == ["x"]


def test_compact_nonempty_ints():
    assert compact_nonempty_ints([1, None, 2, "", 1]) == [1, 2]
    assert compact_nonempty_ints([3, "4", 5]) == [3, 4, 5]


def test_prune_none_values():
    assert prune_none_values({"a": 1, "b": None, "c": []}) == {"a": 1}
    assert prune_none_values({"x": [1, 2]}) == {"x": [1, 2]}


# ---- 1. KnowledgeEvent provenance builder ----


def test_build_knowledge_event_provenance():
    payload = build_knowledge_event_provenance(
        lesson_id="lesson1",
        chunk_index=4,
        chunk_start_time_seconds=10.0,
        chunk_end_time_seconds=20.0,
        transcript_line_count=3,
        candidate_visual_frame_keys=["001", "001", "002"],
        candidate_visual_types=["annotated_chart", "annotated_chart"],
        candidate_example_types=["false_breakout", ""],
    )

    assert payload["chunk_index"] == 4
    assert payload["candidate_visual_frame_keys"] == ["001", "002"]
    assert payload["candidate_visual_types"] == ["annotated_chart"]
    assert payload["candidate_example_types"] == ["false_breakout"]


# ---- 2. EvidenceRef provenance builder ----


def test_build_evidence_ref_provenance():
    payload = build_evidence_ref_provenance(
        lesson_id="lesson1",
        timestamp_start=12.0,
        timestamp_end=18.0,
        frame_ids=["001", "002", "001"],
        screenshot_paths=["a.png", "a.png", "b.png"],
        raw_visual_event_ids=["ve_raw_001", "ve_raw_002"],
        source_event_ids=["ke_1", "ke_2", "ke_1"],
    )

    assert payload["frame_ids"] == ["001", "002"]
    assert payload["screenshot_paths"] == ["a.png", "b.png"]
    assert payload["source_event_ids"] == ["ke_1", "ke_2"]


# ---- 3. RuleCard provenance builder ----


def test_build_rule_card_provenance():
    class E:
        def __init__(self, event_id, section, subsection, chunk_index):
            self.event_id = event_id
            self.section = section
            self.subsection = subsection
            self.metadata = {"chunk_index": chunk_index}

    class V:
        def __init__(self, evidence_id):
            self.evidence_id = evidence_id

    events = [
        E("ke_1", "Level", "rating", 4),
        E("ke_2", "Level", "rating", 5),
    ]
    evidence = [V("evid_1"), V("evid_1"), V("evid_2")]

    payload = build_rule_card_provenance(
        lesson_id="lesson1",
        source_events=events,
        linked_evidence=evidence,
    )

    assert payload["source_event_ids"] == ["ke_1", "ke_2"]
    assert payload["evidence_refs"] == ["evid_1", "evid_2"]
    assert payload["source_sections"] == ["Level"]
    assert payload["source_subsections"] == ["rating"]
    assert payload["source_chunk_indexes"] == [4, 5]


# ---- 4. Validation warnings ----


def test_validate_rule_card_provenance_warns_on_missing_source_ids():
    class Rule:
        lesson_id = "lesson1"
        source_event_ids = []
        evidence_refs = []
        visual_summary = None
        concept = "level"

    warnings = validate_rule_card_provenance(Rule())
    assert "missing source_event_ids" in warnings


def test_validate_knowledge_event_provenance_warnings():
    class Event:
        lesson_id = ""
        timestamp_start = None
        timestamp_end = None
        metadata = {"chunk_index": None}

    warnings = validate_knowledge_event_provenance(Event())
    assert "missing metadata.chunk_index" in warnings or "missing lesson_id" in warnings


def test_validate_evidence_ref_provenance_warnings():
    class Evidence:
        lesson_id = "lesson1"
        timestamp_start = None
        timestamp_end = None
        frame_ids = []
        raw_visual_event_ids = []
        source_event_ids = []

    warnings = validate_evidence_ref_provenance(Evidence())
    assert "missing both frame_ids and raw_visual_event_ids" in warnings
    assert "missing source_event_ids" in warnings


# ---- 5. Coverage checker ----


def test_compute_provenance_coverage():
    class Event:
        def __init__(self, chunk_index=None, frame_keys=None):
            self.metadata = {
                "chunk_index": chunk_index,
                "candidate_visual_frame_keys": frame_keys or [],
            }

    class Evidence:
        def __init__(self, frame_ids=None, source_event_ids=None):
            self.frame_ids = frame_ids or []
            self.source_event_ids = source_event_ids or []

    class Rule:
        def __init__(self, source_event_ids=None, evidence_refs=None):
            self.source_event_ids = source_event_ids or []
            self.evidence_refs = evidence_refs or []

    stats = compute_provenance_coverage(
        knowledge_events=[Event(1, ["001"]), Event(None, [])],
        evidence_refs=[Evidence(["001"], ["ke_1"]), Evidence([], [])],
        rule_cards=[Rule(["ke_1"], ["evid_1"]), Rule([], [])],
    )

    assert stats["knowledge_events_total"] == 2
    assert stats["knowledge_events_with_chunk_index"] == 1
    assert stats["evidence_refs_with_source_event_ids"] == 1
    assert stats["rule_cards_with_source_event_ids"] == 1


# ---- 6. Merge stability ----


def test_merge_source_event_ids_deduped_and_ordered():
    a = ["ke_1", "ke_2", "ke_1"]
    b = ["ke_2", "ke_3"]
    out = merge_source_event_ids(a, b)
    assert out == ["ke_1", "ke_2", "ke_3"]


def test_merge_evidence_refs_deduped_and_ordered():
    a = ["evid_1", "evid_2"]
    b = ["evid_2", "evid_3", "evid_1"]
    out = merge_evidence_refs(a, b)
    assert out == ["evid_1", "evid_2", "evid_3"]


# ---- 7. Review markdown provenance ----


def test_format_compact_provenance():
    class Rule:
        source_event_ids = ["ke_1", "ke_2"]
        evidence_refs = ["evid_1"]

    block = format_compact_provenance(Rule())
    assert "Evidence refs" in block
    assert "Source events" in block
    assert "evid_1" in block
    assert "ke_1" in block


def test_format_compact_provenance_returns_none_when_empty():
    class Rule:
        source_event_ids = []
        evidence_refs = []

    assert format_compact_provenance(Rule()) is None
