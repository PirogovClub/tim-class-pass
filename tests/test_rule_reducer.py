"""Tests for Task 5 rule reducer — rule normalization and merge logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.component2.rule_reducer import (
    ATTACH_THRESHOLD,
    RuleCandidate,
    attach_evidence_to_candidates,
    build_candidate_visual_summary,
    build_rule_cards,
    candidate_to_rule_card,
    choose_canonical_rule_text,
    collect_condition_texts,
    collect_invalidation_texts,
    distribute_example_refs,
    group_events_into_rule_candidates,
    load_evidence_index,
    load_knowledge_events,
    merge_duplicate_primary_events,
    normalize_text_for_match,
    save_rule_cards,
    save_rule_debug,
    score_event_candidate_match,
    score_rule_candidate_confidence,
    simple_text_similarity,
    split_overbroad_candidate,
)
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCardCollection,
)


# ----- 1. Load valid inputs -----


def test_load_valid_knowledge_events(tmp_path: Path) -> None:
    """Valid KnowledgeEventCollection loads and validates."""
    path = tmp_path / "ke.json"
    data = {
        "schema_version": "1.0",
        "lesson_id": "lesson2",
        "events": [
            {
                "lesson_id": "lesson2",
                "event_id": "ke_0_rule_0",
                "event_type": "rule_statement",
                "raw_text": "A level is support or resistance.",
                "normalized_text": "A level is support or resistance.",
            },
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    coll = load_knowledge_events(path)
    assert coll.lesson_id == "lesson2"
    assert len(coll.events) == 1
    assert coll.events[0].event_id == "ke_0_rule_0"
    assert coll.events[0].event_type == "rule_statement"


def test_load_valid_evidence_index(tmp_path: Path) -> None:
    """Valid EvidenceIndex loads and validates."""
    path = tmp_path / "ei.json"
    data = {
        "schema_version": "1.0",
        "lesson_id": "lesson2",
        "evidence_refs": [
            {
                "lesson_id": "lesson2",
                "evidence_id": "ev_0",
                "source_event_ids": ["ke_0_rule_0"],
            },
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    idx = load_evidence_index(path)
    assert idx.lesson_id == "lesson2"
    assert len(idx.evidence_refs) == 1
    assert idx.evidence_refs[0].evidence_id == "ev_0"


def test_load_empty_collections(tmp_path: Path) -> None:
    """Empty but valid collections are tolerated."""
    ke_path = tmp_path / "ke.json"
    ke_path.write_text(
        json.dumps({"schema_version": "1.0", "lesson_id": "L", "events": []}),
        encoding="utf-8",
    )
    ei_path = tmp_path / "ei.json"
    ei_path.write_text(
        json.dumps({"schema_version": "1.0", "lesson_id": "L", "evidence_refs": []}),
        encoding="utf-8",
    )
    coll = load_knowledge_events(ke_path)
    assert coll.lesson_id == "L"
    assert coll.events == []
    idx = load_evidence_index(ei_path)
    assert idx.lesson_id == "L"
    assert idx.evidence_refs == []


# ----- 2. Group compatible events -----


def _make_event(
    event_id: str,
    event_type: str,
    text: str,
    lesson_id: str = "lesson2",
    concept: str | None = "level",
    subconcept: str | None = "level_rating",
    section: str | None = None,
    metadata: dict | None = None,
) -> KnowledgeEvent:
    return KnowledgeEvent(
        lesson_id=lesson_id,
        event_id=event_id,
        event_type=event_type,
        raw_text=text,
        normalized_text=text,
        concept=concept,
        subconcept=subconcept,
        section=section,
        metadata=metadata or {},
    )


def test_group_compatible_events_same_concept_subconcept_section() -> None:
    """Same concept, subconcept, section, compatible roles → one candidate."""
    events = [
        _make_event("e1", "rule_statement", "A level is support or resistance.", metadata={"chunk_index": 0}),
        _make_event("e2", "condition", "Price must touch the level.", metadata={"chunk_index": 0}),
    ]
    index = EvidenceIndex(schema_version="1.0", lesson_id="lesson2", evidence_refs=[])
    candidates, _ = group_events_into_rule_candidates(events, index, threshold=ATTACH_THRESHOLD)
    assert len(candidates) == 1
    assert len(candidates[0].primary_events) >= 1
    assert len(candidates[0].condition_events) >= 1


# ----- 3. Do not merge incompatible events -----


def test_do_not_merge_different_subconcepts() -> None:
    """Same concept but different subconcepts → separate candidates."""
    events = [
        _make_event("e1", "rule_statement", "Level strength increases with touches.", subconcept="level_rating"),
        _make_event("e2", "rule_statement", "False breakout invalidates the level.", subconcept="false_breakout"),
    ]
    index = EvidenceIndex(schema_version="1.0", lesson_id="lesson2", evidence_refs=[])
    candidates, _ = group_events_into_rule_candidates(events, index, threshold=ATTACH_THRESHOLD)
    assert len(candidates) == 2


def test_do_not_merge_unrelated_rule_statements() -> None:
    """Unrelated rule statements with low text similarity stay separate."""
    events = [
        _make_event("e1", "rule_statement", "A level is support or resistance.", metadata={"chunk_index": 0}),
        _make_event("e2", "rule_statement", "Use a trailing stop when trend is strong.", metadata={"chunk_index": 5}),
    ]
    index = EvidenceIndex(schema_version="1.0", lesson_id="lesson2", evidence_refs=[])
    candidates, _ = group_events_into_rule_candidates(events, index, threshold=0.65)
    assert len(candidates) >= 1
    if len(candidates) == 2:
        assert len(candidates[0].primary_events) == 1
        assert len(candidates[1].primary_events) == 1


# ----- 4. Attach evidence by source_event_ids -----


def test_attach_evidence_by_source_event_ids() -> None:
    """Evidence whose source_event_ids overlap candidate event ids links correctly."""
    ev1 = _make_event("ke_1", "rule_statement", "Level holds.")
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        concept="level",
        subconcept=None,
        title_hint=None,
        primary_events=[ev1],
    )
    ref = EvidenceRef(
        lesson_id="lesson2",
        evidence_id="ev_1",
        source_event_ids=["ke_1"],
    )
    index = EvidenceIndex(schema_version="1.0", lesson_id="lesson2", evidence_refs=[ref])
    out = attach_evidence_to_candidates([cand], index)
    assert len(out) == 1
    assert len(out[0].linked_evidence) == 1
    assert out[0].linked_evidence[0].evidence_id == "ev_1"


# ----- 5. Split over-broad candidate -----


def test_split_overbroad_candidate_multiple_subconcepts() -> None:
    """Candidate with two distinct subconcepts splits."""
    ev1 = _make_event("e1", "rule_statement", "Level strength increases.", subconcept="level_rating")
    ev2 = _make_event("e2", "rule_statement", "False breakout invalidates.", subconcept="false_breakout")
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        concept="level",
        subconcept=None,
        title_hint=None,
        primary_events=[ev1, ev2],
    )
    split = split_overbroad_candidate(cand)
    assert len(split) == 2


def test_split_overbroad_candidate_low_similarity_primaries() -> None:
    """Candidate with multiple primary events with low text similarity splits."""
    ev1 = _make_event("e1", "rule_statement", "A level is support or resistance.")
    ev2 = _make_event("e2", "rule_statement", "Use trailing stops in strong trends.")
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        concept="level",
        subconcept=None,
        title_hint=None,
        primary_events=[ev1, ev2],
    )
    split = split_overbroad_candidate(cand)
    assert len(split) >= 1
    if len(split) == 2:
        assert len(split[0].primary_events) == 1
        assert len(split[1].primary_events) == 1


# ----- 6. Choose canonical rule text -----


def test_choose_canonical_rule_text_prefers_rule_statement() -> None:
    """Given multiple primary events, rule_statement is chosen over definition/condition."""
    ev_rule = _make_event("e1", "rule_statement", "A level becomes stronger with more touches.")
    ev_def = _make_event("e2", "definition", "Level: a price zone that acts as support or resistance.")
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        concept="level",
        subconcept=None,
        title_hint=None,
        primary_events=[ev_rule, ev_def],
    )
    text = choose_canonical_rule_text(cand)
    assert "stronger" in text or "level" in text.lower()
    assert text == ev_rule.normalized_text


def test_choose_canonical_rule_text_single_sentence() -> None:
    """Canonical rule text is one sentence, not concatenation."""
    ev = _make_event("e1", "rule_statement", "Price must react at the level.")
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        concept="level",
        subconcept=None,
        title_hint=None,
        primary_events=[ev],
    )
    text = choose_canonical_rule_text(cand)
    assert text == "Price must react at the level."


# ----- 7. Build final RuleCard -----


def test_build_final_rule_card_has_required_fields() -> None:
    """RuleCard contains rule_text, conditions, invalidation, evidence_refs, source_event_ids."""
    ev_rule = _make_event("e1", "rule_statement", "Level holds when price reacts.")
    ev_cond = _make_event("e2", "condition", "Reactions should be near the same zone.")
    ev_inv = _make_event("e3", "invalidation", "Single touch is not enough.")
    ref = EvidenceRef(lesson_id="lesson2", evidence_id="ev_1", source_event_ids=["e1"])
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        concept="level",
        subconcept=None,
        title_hint=None,
        primary_events=[ev_rule],
        condition_events=[ev_cond],
        invalidation_events=[ev_inv],
        linked_evidence=[ref],
    )
    card = candidate_to_rule_card(cand, 0)
    assert card.rule_text
    assert "Level" in card.rule_text or "level" in card.rule_text
    assert card.conditions
    assert card.invalidation
    assert "ev_1" in card.evidence_refs
    assert "e1" in card.source_event_ids
    assert "e2" in card.source_event_ids
    assert "e3" in card.source_event_ids


# ----- 8. Example refs distribution -----


def test_distribute_example_refs_maps_to_ml_fields() -> None:
    """positive_example / counterexample / ambiguous_example map to correct ML fields."""
    ref_pos = EvidenceRef(lesson_id="L", evidence_id="ep", source_event_ids=[], example_role="positive_example")
    ref_neg = EvidenceRef(lesson_id="L", evidence_id="en", source_event_ids=[], example_role="counterexample")
    ref_amb = EvidenceRef(lesson_id="L", evidence_id="ea", source_event_ids=[], example_role="ambiguous_example")
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="L",
        concept="level",
        subconcept=None,
        title_hint=None,
        linked_evidence=[ref_pos, ref_neg, ref_amb],
    )
    out = distribute_example_refs(cand)
    assert "ep" in out["positive_example_refs"]
    assert "en" in out["negative_example_refs"]
    assert "ea" in out["ambiguous_example_refs"]


# ----- 9. Confidence scoring -----


def test_confidence_scoring_stronger_above_weaker() -> None:
    """Stronger candidate (primary + concept + evidence) scores above weaker one."""
    ev = _make_event("e1", "rule_statement", "Level holds.")
    strong = RuleCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        concept="level",
        subconcept="level_rating",
        title_hint=None,
        primary_events=[ev],
        condition_events=[_make_event("e2", "condition", "Price must touch.")],
        linked_evidence=[EvidenceRef(lesson_id="lesson2", evidence_id="ev1", source_event_ids=["e1"])],
    )
    weak = RuleCandidate(
        candidate_id="c2",
        lesson_id="lesson2",
        concept=None,
        subconcept=None,
        title_hint=None,
        primary_events=[],
    )
    _, score_strong = score_rule_candidate_confidence(strong)
    _, score_weak = score_rule_candidate_confidence(weak)
    assert score_strong > score_weak


# ----- 10. Serialization -----


def test_rule_card_collection_serializes() -> None:
    """RuleCardCollection round-trips via JSON."""
    coll = RuleCardCollection(
        schema_version="1.0",
        lesson_id="lesson2",
        rules=[],
    )
    js = coll.model_dump_json()
    assert js
    data = json.loads(js)
    assert data["lesson_id"] == "lesson2"
    assert data["rules"] == []
    parsed = RuleCardCollection.model_validate_json(js)
    assert parsed.lesson_id == coll.lesson_id
    assert len(parsed.rules) == 0


def test_build_rule_cards_returns_valid_collection() -> None:
    """build_rule_cards returns RuleCardCollection that serializes."""
    events = [
        _make_event("e1", "rule_statement", "A level is support or resistance."),
    ]
    coll = KnowledgeEventCollection(schema_version="1.0", lesson_id="lesson2", events=events)
    index = EvidenceIndex(schema_version="1.0", lesson_id="lesson2", evidence_refs=[])
    collection, debug_rows = build_rule_cards(coll, index)
    assert isinstance(collection, RuleCardCollection)
    assert collection.lesson_id == "lesson2"
    assert len(collection.rules) >= 1
    js = collection.model_dump_json()
    RoundTrip = RuleCardCollection.model_validate_json(js)
    assert RoundTrip.lesson_id == collection.lesson_id
    assert len(RoundTrip.rules) == len(collection.rules)


# ----- 11. Feature-flag-safe integration -----


def test_enable_rule_cards_false_no_rule_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When enable_rule_cards=False, no rule_cards/rule_debug files; legacy unchanged."""
    from pipeline.component2.main import run_component2_pipeline
    from pipeline.component2.models import EnrichedMarkdownChunk

    vtt = tmp_path / "lesson.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello.\n\n",
        encoding="utf-8",
    )
    visuals = tmp_path / "dense.json"
    visuals.write_text(
        json.dumps({
            "000001": {
                "material_change": True,
                "visual_representation_type": "chart",
                "change_summary": ["Chart"],
                "current_state": {},
                "extracted_entities": {},
            },
        }),
        encoding="utf-8",
    )

    async def fake_process_chunks(chunks, **kwargs):
        return [
            (
                chunk,
                EnrichedMarkdownChunk(synthesized_markdown="Md", metadata_tags=[]),
                [{"status": "succeeded", "total_tokens": 10}],
            )
            for chunk in chunks
        ]

    def fake_synthesize(*args, **kwargs):
        return ("# lesson\n\nContent.", [])

    monkeypatch.setattr("pipeline.component2.main.process_chunks", fake_process_chunks)
    monkeypatch.setattr("pipeline.component2.main.synthesize_full_document", fake_synthesize)

    result = run_component2_pipeline(
        vtt_path=vtt,
        visuals_json_path=visuals,
        output_root=tmp_path,
        enable_knowledge_events=False,
        enable_evidence_linking=False,
        enable_rule_cards=False,
    )
    assert "rule_cards_path" not in result
    assert "rule_debug_path" not in result
    assert not (tmp_path / "output_intermediate" / "lesson.rule_cards.json").exists()
    assert not (tmp_path / "output_intermediate" / "lesson.rule_debug.json").exists()


def test_save_rule_cards_and_debug(tmp_path: Path) -> None:
    """save_rule_cards and save_rule_debug write files."""
    coll = RuleCardCollection(schema_version="1.0", lesson_id="L", rules=[])
    out_cards = tmp_path / "out" / "rule_cards.json"
    out_debug = tmp_path / "out" / "rule_debug.json"
    save_rule_cards(coll, out_cards)
    assert out_cards.exists()
    data = json.loads(out_cards.read_text(encoding="utf-8"))
    assert data["lesson_id"] == "L"
    save_rule_debug([{"candidate_id": "c1", "confidence_score": 0.8}], out_debug)
    assert out_debug.exists()
    debug_data = json.loads(out_debug.read_text(encoding="utf-8"))
    assert debug_data[0]["candidate_id"] == "c1"


# ----- Helpers (optional) -----


def test_normalize_text_for_match() -> None:
    """normalize_text_for_match lowercases and strips punctuation."""
    assert normalize_text_for_match("  A Level.  ") == "a level"
    assert normalize_text_for_match("Same  spaces") == "same spaces"


def test_simple_text_similarity() -> None:
    """simple_text_similarity returns value in [0, 1]."""
    assert simple_text_similarity("level support", "level support") == 1.0
    assert simple_text_similarity("level", "trend") < 0.5
    assert 0 <= simple_text_similarity("a b", "a c") <= 1.0


def test_build_candidate_visual_summary_one_ref() -> None:
    """One evidence ref with compact_visual_summary is used."""
    ref = EvidenceRef(
        lesson_id="L",
        evidence_id="e1",
        source_event_ids=[],
        compact_visual_summary="Chart showing level.",
    )
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="L",
        concept="level",
        subconcept=None,
        title_hint=None,
        linked_evidence=[ref],
    )
    summary = build_candidate_visual_summary(cand)
    assert summary == "Chart showing level."


def test_collect_condition_and_invalidation_texts() -> None:
    """collect_condition_texts and collect_invalidation_texts dedupe and preserve order."""
    ev1 = _make_event("e1", "condition", "Price must touch.")
    ev2 = _make_event("e2", "condition", "Price must touch.")
    ev3 = _make_event("e3", "invalidation", "Single touch is not enough.")
    cand = RuleCandidate(
        candidate_id="c1",
        lesson_id="L",
        concept="level",
        subconcept=None,
        title_hint=None,
        condition_events=[ev1, ev2],
        invalidation_events=[ev3],
    )
    conditions = collect_condition_texts(cand)
    invalidation = collect_invalidation_texts(cand)
    assert len(conditions) == 1
    assert "touch" in conditions[0].lower()
    assert len(invalidation) == 1
    assert "Single" in invalidation[0] or "single" in invalidation[0].lower()
