"""ML roadmap Step 5 — task definition, ontology, window contract, validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ml.task_validator import (
    validate_class_ontology,
    validate_rule_mapping,
    validate_task_bundle,
    validate_task_definition,
    validate_task_examples,
    validate_window_contract,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = PROJECT_ROOT / "src" / "ml"
BAD_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "ml_step5_bad"


def test_task_definition_file_loads_and_validates() -> None:
    raw = yaml.safe_load((ML_ROOT / "task_definition.yaml").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    errs = validate_task_definition(raw, source="task_definition.yaml")
    assert errs == []
    assert raw["task_id"] == "level_interaction_rule_satisfaction_v1"
    assert raw["task_type"] == "multiclass_classification"


def test_ontology_contains_all_required_classes() -> None:
    onto = json.loads((ML_ROOT / "class_ontology.json").read_text(encoding="utf-8"))
    errs, names = validate_class_ontology(onto, source="class_ontology.json")
    assert errs == []
    expected = {
        "acceptance_above",
        "acceptance_below",
        "false_breakout_up",
        "false_breakout_down",
        "rejection",
        "no_setup",
        "ambiguous",
    }
    assert names == expected


def test_mapping_only_references_known_classes() -> None:
    mapping = json.loads((ML_ROOT / "rule_to_class_mapping.json").read_text(encoding="utf-8"))
    known = {
        "acceptance_above",
        "acceptance_below",
        "false_breakout_up",
        "false_breakout_down",
        "rejection",
        "no_setup",
        "ambiguous",
    }
    errs = validate_rule_mapping(mapping, source="rule_to_class_mapping.json", known_classes=known)
    assert errs == []


def test_examples_only_reference_known_classes() -> None:
    examples = json.loads((ML_ROOT / "task_examples.json").read_text(encoding="utf-8"))
    known = {
        "acceptance_above",
        "acceptance_below",
        "false_breakout_up",
        "false_breakout_down",
        "rejection",
        "no_setup",
        "ambiguous",
    }
    errs = validate_task_examples(examples, source="task_examples.json", known_classes=known)
    assert errs == []


def test_ambiguous_examples_include_ambiguity_reason() -> None:
    examples = json.loads((ML_ROOT / "task_examples.json").read_text(encoding="utf-8"))
    amb = [e for e in examples["examples"] if e["class_label"] == "ambiguous"]
    assert len(amb) >= 2
    for row in amb:
        assert isinstance(row.get("ambiguity_reason"), str) and row["ambiguity_reason"].strip()


def test_no_setup_not_treated_as_ambiguous() -> None:
    examples = json.loads((ML_ROOT / "task_examples.json").read_text(encoding="utf-8"))
    for row in examples["examples"]:
        if row["class_label"] == "no_setup":
            ar = row.get("ambiguity_reason")
            assert ar is None or ar == ""


def test_decision_order_has_no_duplicates() -> None:
    raw = yaml.safe_load((ML_ROOT / "task_definition.yaml").read_text(encoding="utf-8"))
    cdo = raw["class_decision_order"]
    assert len(cdo) == len(set(cdo))


def test_point_in_time_safety_section_exists() -> None:
    raw = yaml.safe_load((ML_ROOT / "task_definition.yaml").read_text(encoding="utf-8"))
    assert "point_in_time_safety" in raw
    wc = yaml.safe_load((ML_ROOT / "window_contract.yaml").read_text(encoding="utf-8"))
    errs = validate_window_contract(wc, source="window_contract.yaml")
    assert errs == []
    assert "rules" in wc["point_in_time_safety"]


def test_validator_fails_on_malformed_task_definition_fixture() -> None:
    bad_path = BAD_FIXTURES / "bad_task_definition.yaml"
    bad = yaml.safe_load(bad_path.read_text(encoding="utf-8"))
    errs = validate_task_definition(bad, source="bad_task_definition.yaml")
    assert any("duplicate" in e.lower() for e in errs)


def test_validator_fails_on_malformed_examples_fixture() -> None:
    bad = json.loads((BAD_FIXTURES / "bad_task_examples.json").read_text(encoding="utf-8"))
    known = {
        "acceptance_above",
        "acceptance_below",
        "false_breakout_up",
        "false_breakout_down",
        "rejection",
        "no_setup",
        "ambiguous",
    }
    errs = validate_task_examples(bad, source="bad_task_examples.json", known_classes=known)
    assert errs


def test_validator_passes_on_real_spec() -> None:
    assert validate_task_bundle(ML_ROOT) == []
