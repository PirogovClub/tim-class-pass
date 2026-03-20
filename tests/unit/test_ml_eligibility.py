"""Unit tests for ML evidence eligibility (12-phase2, brief Part 2)."""

from pipeline.component2.ml_prep import is_evidence_ml_eligible


def test_illustration_is_not_ml_eligible():
    evidence = {
        "example_role": "illustration",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is False


def test_positive_example_is_ml_eligible():
    evidence = {
        "example_role": "positive_example",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is True


def test_counterexample_is_ml_eligible():
    evidence = {
        "example_role": "counterexample",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is True


def test_ml_eligibility_requires_linked_rule_ids():
    evidence = {
        "example_role": "positive_example",
        "linked_rule_ids": [],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is False


def test_ml_eligibility_requires_source_event_ids():
    evidence = {
        "example_role": "positive_example",
        "linked_rule_ids": ["r1"],
        "source_event_ids": [],
    }
    assert is_evidence_ml_eligible(evidence) is False
