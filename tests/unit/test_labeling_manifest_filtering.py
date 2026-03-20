"""Unit tests for labeling manifest filtering (12-phase2, brief Part 5)."""

from pipeline.component2.ml_prep import build_labeling_tasks


def test_labeling_manifest_empty_when_only_illustrations():
    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        }
    ]

    tasks = build_labeling_tasks(evidence_refs)

    assert tasks == []
