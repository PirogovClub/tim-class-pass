"""Unit tests for ML manifest filtering and rule example refs (12-phase2, brief Parts 3–4)."""

from pipeline.component2.ml_prep import attach_rule_example_refs, build_ml_examples


def test_build_ml_examples_excludes_illustrations():
    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        },
        {
            "evidence_id": "ev2",
            "example_role": "positive_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e2"],
        },
    ]

    result = build_ml_examples(evidence_refs)

    assert [x["evidence_id"] for x in result] == ["ev2"]


def test_build_ml_examples_returns_empty_for_illustration_only_input():
    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        }
    ]

    result = build_ml_examples(evidence_refs)

    assert result == []


def test_attach_rule_example_refs_ignores_illustrations():
    rule = {"rule_id": "r1"}

    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        }
    ]

    result = attach_rule_example_refs(rule, evidence_refs)

    assert result["positive_example_refs"] == []
    assert result["negative_example_refs"] == []
    assert result["ambiguous_example_refs"] == []


def test_attach_rule_example_refs_maps_roles_correctly():
    rule = {"rule_id": "r1"}

    evidence_refs = [
        {
            "evidence_id": "ev_pos",
            "example_role": "positive_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        },
        {
            "evidence_id": "ev_neg",
            "example_role": "negative_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e2"],
        },
        {
            "evidence_id": "ev_cnt",
            "example_role": "counterexample",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e3"],
        },
        {
            "evidence_id": "ev_amb",
            "example_role": "ambiguous_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e4"],
        },
    ]

    result = attach_rule_example_refs(rule, evidence_refs)

    assert result["positive_example_refs"] == ["ev_pos"]
    assert sorted(result["negative_example_refs"]) == ["ev_cnt", "ev_neg"]
    assert result["ambiguous_example_refs"] == ["ev_amb"]
