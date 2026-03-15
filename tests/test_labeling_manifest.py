"""Tests for labeling manifest generation (06-phase1: no counterexample task for generic intro)."""

from __future__ import annotations

import pytest

from pipeline.schemas import EvidenceIndex, EvidenceRef, RuleCard, RuleCardCollection
from pipeline.component2.ml_prep import build_labeling_manifest


def test_labeling_manifest_skips_generic_intro_counterexample() -> None:
    """06-phase1: generic intro visual marked counterexample does not get a labeling task."""
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev1",
        source_event_ids=["ke1"],
        linked_rule_ids=["r1"],
        frame_ids=["000001"],
        example_role="counterexample",
        compact_visual_summary="Introduction slide with title and instructor.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Trend Break Level",
        rule_text="A trend break level forms after a strong move and reversal.",
        source_event_ids=["ke1"],
        labeling_guidance="Label positive only when the setup clearly matches the rule.",
    )

    rule_with_ref = rule.model_copy(
        update={"negative_example_refs": ["ev1"]}
    )

    manifest = build_labeling_manifest(
        lesson_id="lesson1",
        rule_cards=RuleCardCollection(lesson_id="lesson1", rules=[rule_with_ref]),
        evidence_index=EvidenceIndex(
            lesson_id="lesson1",
            evidence_refs=[ref],
        ),
    )

    assert manifest["tasks"] == []
