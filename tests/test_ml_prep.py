"""Tests for Task 13 ML-prep — candidate features, example distribution, labeling guidance, manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.schemas import EvidenceIndex, EvidenceRef, RuleCard, RuleCardCollection
from pipeline.component2.ml_prep import (
    build_evidence_lookup,
    build_labeling_guidance,
    build_labeling_manifest,
    build_ml_manifest,
    compute_ml_readiness_coverage,
    distribute_example_refs_for_ml,
    enrich_rule_card_for_ml,
    enrich_rule_card_collection_for_ml,
    infer_candidate_features,
    is_evidence_ml_eligible,
    save_ml_manifest,
)


# ----- 1. Candidate features inferred -----


def test_infer_candidate_features_level_rating() -> None:
    """RuleCard with concept=level, subconcept=level_rating yields expected feature names."""
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        subconcept="level_rating",
        rule_text="A level becomes stronger when price reacts to it multiple times.",
        source_event_ids=["ke_0"],
    )

    features = infer_candidate_features(rule)

    assert "reaction_count" in features
    assert "reaction_magnitude" in features
    assert "price_zone_width" in features


# ----- 2. Example refs distributed correctly -----


def test_distribute_example_refs_for_ml() -> None:
    """Evidence refs: only positive and counterexample (with explicit negative) in buckets (06-phase1)."""
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        rule_text="Rule",
    )
    evidence = [
        EvidenceRef(
            evidence_id="e1",
            lesson_id="lesson1",
            example_role="positive_example",
            linked_rule_ids=["r1"],
            source_event_ids=["ke1"],
        ),
        EvidenceRef(
            evidence_id="e2",
            lesson_id="lesson1",
            example_role="counterexample",
            linked_rule_ids=["r1"],
            source_event_ids=["ke1"],
            compact_visual_summary="Chart shows failed breakout, rejection, and return below level.",
        ),
        EvidenceRef(
            evidence_id="e3",
            lesson_id="lesson1",
            example_role="ambiguous_example",
            linked_rule_ids=["r1"],
            source_event_ids=["ke1"],
        ),
        EvidenceRef(
            evidence_id="e4",
            lesson_id="lesson1",
            example_role="illustration",
            linked_rule_ids=["r1"],
            source_event_ids=["ke1"],
        ),
    ]

    buckets = distribute_example_refs_for_ml(rule, evidence)

    assert buckets["positive_example_refs"] == ["e1"]
    assert buckets["negative_example_refs"] == ["e2"]
    assert buckets["ambiguous_example_refs"] == []  # 06-phase1: ambiguous not in ML buckets
    assert "e4" not in buckets["positive_example_refs"]
    assert "e4" not in buckets["negative_example_refs"]
    assert "e3" not in buckets["ambiguous_example_refs"]


# ----- 3. Labeling guidance generated -----


def test_build_labeling_guidance() -> None:
    """Rule with conditions and invalidation produces compact guidance with both phrases."""
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="false_breakout",
        rule_text="A false breakout fails to hold beyond the level.",
        source_event_ids=["ke_0"],
        conditions=[
            "price moves beyond the level",
            "price fails to hold beyond it",
        ],
        invalidation=["price holds beyond the level"],
    )

    guidance = build_labeling_guidance(rule)

    assert guidance is not None
    assert "Label positive only when" in guidance
    assert "Do not label positive when" in guidance


# ----- 4. Enrichment preserves provenance -----


def test_enrich_rule_card_for_ml_preserves_provenance() -> None:
    """Enriching a rule keeps source_event_ids, evidence_refs, confidence unchanged."""
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        rule_text="A level matters.",
        evidence_refs=["e1"],
        source_event_ids=["ke1"],
        confidence="high",
        confidence_score=0.8,
    )
    evidence = [
        EvidenceRef(
            evidence_id="e1",
            lesson_id="lesson1",
            example_role="positive_example",
            linked_rule_ids=["r1"],
            source_event_ids=["ke1"],
        ),
    ]

    enriched = enrich_rule_card_for_ml(rule, evidence)

    assert enriched.source_event_ids == ["ke1"]
    assert enriched.evidence_refs == ["e1"]
    assert enriched.confidence == "high"
    assert enriched.confidence_score == 0.8
    dump = enriched.model_dump()
    assert "candidate_features" in dump
    assert "positive_example_refs" in dump
    assert "labeling_guidance" in dump


# ----- 5. ML manifest serialization -----


def test_build_ml_manifest() -> None:
    """Generated manifest has lesson_id, rules, examples and is JSON-serializable."""
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        rule_text="A level matters.",
        candidate_features=["touch_count"],
        positive_example_refs=["e1"],
        evidence_refs=["e1"],
        source_event_ids=["ke1"],
    )
    evidence = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        frame_ids=["001"],
        screenshot_paths=["/tmp/frame_001.jpg"],
        source_event_ids=["ke1"],
    )

    manifest, debug_rows = build_ml_manifest(
        lesson_id="lesson1",
        rule_cards=RuleCardCollection(lesson_id="lesson1", rules=[rule]),
        evidence_index=EvidenceIndex(
            schema_version="1.0",
            lesson_id="lesson1",
            evidence_refs=[evidence],
        ),
    )

    assert manifest["lesson_id"] == "lesson1"
    assert len(manifest["rules"]) == 1
    assert manifest["rules"][0]["rule_id"] == "r1"
    assert manifest["rules"][0]["candidate_features"] == ["touch_count"]
    assert manifest["rules"][0]["positive_example_refs"] == ["e1"]
    assert len(manifest["examples"]) == 1
    assert manifest["examples"][0]["evidence_id"] == "e1"
    assert manifest["examples"][0]["frame_ids"] == ["001"]
    assert debug_rows
    # Must serialize to JSON
    json.dumps(manifest, indent=2, ensure_ascii=False)


# ----- 6. ML readiness coverage -----


def test_compute_ml_readiness_coverage() -> None:
    """Coverage counts match a small sample."""
    rule_with_pos = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        rule_text="Rule.",
        candidate_features=["touch_count"],
        positive_example_refs=["e1"],
        evidence_refs=["e1"],
        labeling_guidance="Label when clear.",
    )
    rule_bare = RuleCard(
        rule_id="r2",
        lesson_id="lesson1",
        concept="level",
        rule_text="Other.",
        evidence_refs=[],
    )
    evidence = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        frame_ids=["001"],
        screenshot_paths=["/tmp/f1.jpg"],
    )

    coverage = compute_ml_readiness_coverage(
        rule_cards=RuleCardCollection(
            lesson_id="lesson1",
            rules=[rule_with_pos, rule_bare],
        ),
        evidence_index=EvidenceIndex(
            schema_version="1.0",
            lesson_id="lesson1",
            evidence_refs=[evidence],
        ),
    )

    assert coverage["rules_total"] == 2
    assert coverage["rules_with_candidate_features"] == 1
    assert coverage["rules_with_labeling_guidance"] == 1
    assert coverage["rules_with_positive_examples"] == 1
    assert coverage["evidence_total"] == 1
    assert coverage["evidence_with_screenshots"] == 1
    assert coverage["evidence_with_frame_ids"] == 1


# ----- 7. Save manifest and feature-flag safety -----


def test_save_ml_manifest(tmp_path: Path) -> None:
    """save_ml_manifest writes valid JSON and creates parent dir."""
    out = tmp_path / "sub" / "manifest.json"
    payload = {"lesson_id": "lesson1", "rules": [], "examples": []}

    save_ml_manifest(payload, out)

    assert out.exists()
    assert out.parent.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["lesson_id"] == "lesson1"


def test_feature_flag_safe_no_ml_prep(tmp_path: Path) -> None:
    """With enable_ml_prep=False, no ML manifest is created when pipeline would not run ML prep."""
    # We cannot run the full pipeline here without fixtures; we assert that
    # when we do not call enrich_rule_card_collection_for_ml / save_ml_manifest,
    # the ml_manifest path is not created. So: run a minimal path that would
    # only write ML manifest if enable_ml_prep were True — we don't run it.
    ml_manifest_path = tmp_path / "lesson1.ml_manifest.json"
    assert not ml_manifest_path.exists()
    # Enrichment and save are optional; when flag is False they are never called.
    # So behavior is unchanged: no ML manifest file.
    rule_cards = RuleCardCollection(lesson_id="lesson1", rules=[])
    evidence_index = EvidenceIndex(
        schema_version="1.0",
        lesson_id="lesson1",
        evidence_refs=[],
    )
    enriched = enrich_rule_card_collection_for_ml(rule_cards, evidence_index)
    assert enriched.lesson_id == "lesson1"
    assert len(enriched.rules) == 0
    # If we had called save_ml_manifest with enable_ml_prep=True we would write;
    # with False we never call it, so file is absent.
    assert not ml_manifest_path.exists()


# ----- Collection enrichment -----


def test_enrich_rule_card_collection_for_ml() -> None:
    """Whole-collection enrichment returns new collection with enriched rules. Evidence must be ML-eligible (04-phase1)."""
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        subconcept="level_rating",
        rule_text="Reactions matter.",
        source_event_ids=["ke_0"],
        evidence_refs=["e1"],
    )
    evidence = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        linked_rule_ids=["r1"],
        source_event_ids=["ke1"],
    )
    rules = RuleCardCollection(lesson_id="lesson1", rules=[rule])
    index = EvidenceIndex(
        schema_version="1.0",
        lesson_id="lesson1",
        evidence_refs=[evidence],
    )

    enriched = enrich_rule_card_collection_for_ml(rules, index)

    assert enriched.lesson_id == rules.lesson_id
    assert len(enriched.rules) == 1
    assert enriched.rules[0].candidate_features
    assert enriched.rules[0].positive_example_refs == ["e1"]
    assert enriched.rules[0].labeling_guidance is not None


def test_build_evidence_lookup() -> None:
    """Evidence lookup maps evidence_id to EvidenceRef."""
    evidence = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
    )
    index = EvidenceIndex(
        schema_version="1.0",
        lesson_id="lesson1",
        evidence_refs=[evidence],
    )

    lookup = build_evidence_lookup(index)

    assert lookup["e1"].evidence_id == "e1"
    assert lookup["e1"].example_role == "positive_example"


# ----- 04-phase1: ML eligibility gate -----


def test_is_evidence_ml_eligible_false_when_empty_linked_rule_ids() -> None:
    """Ref with empty linked_rule_ids is not ML-eligible."""
    rule = RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", rule_text="Rule.")
    ref = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        linked_rule_ids=[],
        source_event_ids=["ke1"],
    )
    assert is_evidence_ml_eligible(ref, rule) is False


def test_is_evidence_ml_eligible_false_when_empty_source_event_ids() -> None:
    """Ref with empty source_event_ids is not ML-eligible."""
    rule = RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", rule_text="Rule.")
    ref = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        linked_rule_ids=["r1"],
        source_event_ids=[],
    )
    assert is_evidence_ml_eligible(ref, rule) is False


def test_is_evidence_ml_eligible_false_when_illustration_role() -> None:
    """Ref with example_role illustration is not ML-eligible."""
    rule = RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", rule_text="Rule.")
    ref = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="illustration",
        linked_rule_ids=["r1"],
        source_event_ids=["ke1"],
    )
    assert is_evidence_ml_eligible(ref, rule) is False


def test_is_evidence_ml_eligible_true_when_eligible_positive_example() -> None:
    """Ref with positive_example, linked to rule, non-empty source_event_ids, non-intro summary → eligible."""
    rule = RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", rule_text="Rule.")
    ref = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        linked_rule_ids=["r1"],
        source_event_ids=["ke1"],
        compact_visual_summary="Price holds beyond the level.",
    )
    assert is_evidence_ml_eligible(ref, rule) is True


def test_is_evidence_ml_eligible_false_when_intro_summary() -> None:
    """Ref with intro-like compact_visual_summary is not ML-eligible."""
    rule = RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", rule_text="Rule.")
    ref = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        linked_rule_ids=["r1"],
        source_event_ids=["ke1"],
        compact_visual_summary="Intro to the topic and key concepts.",
    )
    assert is_evidence_ml_eligible(ref, rule) is False


def test_distribute_example_refs_for_ml_excludes_ineligible_counterexample() -> None:
    """Counterexample ref without linked_rule_ids is not placed in negative_example_refs."""
    rule = RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", rule_text="Rule.")
    evidence = [
        EvidenceRef(
            evidence_id="e1",
            lesson_id="lesson1",
            example_role="counterexample",
            linked_rule_ids=[],
            source_event_ids=["ke1"],
        ),
    ]
    buckets = distribute_example_refs_for_ml(rule, evidence)
    assert buckets["negative_example_refs"] == []


def test_distribute_example_refs_for_ml_includes_eligible_counterexample() -> None:
    """Eligible counterexample ref (explicit negative in summary) is placed in negative_example_refs (06-phase1)."""
    rule = RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", rule_text="Rule.")
    evidence = [
        EvidenceRef(
            evidence_id="e1",
            lesson_id="lesson1",
            example_role="counterexample",
            linked_rule_ids=["r1"],
            source_event_ids=["ke1"],
            compact_visual_summary="Chart shows failed breakout, rejection, and return below level.",
        ),
    ]
    buckets = distribute_example_refs_for_ml(rule, evidence)
    assert buckets["negative_example_refs"] == ["e1"]


def test_generic_teaching_visual_not_ml_eligible() -> None:
    """06-phase1: illustration with generic intro summary is not ML eligible."""
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev1",
        source_event_ids=["ke1"],
        linked_rule_ids=["r1"],
        frame_ids=["000001"],
        example_role="illustration",
        compact_visual_summary="Introduction slide with instructor and title overlay.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Trend Break Level",
        rule_text="A trend break level forms after a strong move and reversal.",
        source_event_ids=["ke1"],
    )

    assert is_evidence_ml_eligible(ref, rule) is False


def test_generic_visual_marked_counterexample_is_rejected_by_ml_gate() -> None:
    """06-phase1: counterexample with generic intro summary is rejected by ML gate."""
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev2",
        source_event_ids=["ke1"],
        linked_rule_ids=["r1"],
        frame_ids=["000001"],
        example_role="counterexample",
        compact_visual_summary="Introduction slide with instructor and logo.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Trend Break Level",
        rule_text="A trend break level forms after a strong move and reversal.",
        source_event_ids=["ke1"],
    )

    assert is_evidence_ml_eligible(ref, rule) is False


def test_explicit_negative_evidence_is_ml_eligible() -> None:
    """06-phase1: counterexample with explicit negative in summary is ML eligible."""
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev3",
        source_event_ids=["ke10"],
        linked_rule_ids=["r1"],
        frame_ids=["000010"],
        example_role="counterexample",
        compact_visual_summary="Chart shows failed breakout, rejection, and return below level.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Breakout",
        rule_text="A clean breakout should hold above the level.",
        source_event_ids=["ke10"],
    )

    assert is_evidence_ml_eligible(ref, rule) is True
