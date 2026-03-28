"""Tests for Step 6 label spec compiler (consumes Step 5 sources)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ml.label_spec_compiler import compile_label_specs, write_label_specs

REPO = Path(__file__).resolve().parents[2]
ML = REPO / "src" / "ml"


def test_compile_loads_step5_sources() -> None:
    spec = compile_label_specs(ML)
    assert spec["task_id"] == "level_interaction_rule_satisfaction_v1"
    assert spec["generator_version"]


def test_decision_order_is_permutation_of_label_set() -> None:
    spec = compile_label_specs(ML)
    assert set(spec["class_decision_order"]) == set(spec["label_set"])
    assert len(spec["class_decision_order"]) == len(set(spec["class_decision_order"]))


def test_ontology_classes_match_label_set() -> None:
    spec = compile_label_specs(ML)
    onto = json.loads((ML / "class_ontology.json").read_text(encoding="utf-8"))
    names = {c["class_name"] for c in onto["classes"]}
    assert names == set(spec["label_set"])


def test_label_specs_json_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "label_specs.json"
    write_label_specs(ML, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["numeric_thresholds"]["max_forward_bars"] == 48
    assert data.get("task_examples_version")
    assert isinstance(data.get("task_examples_digest"), list)
    assert len(data["task_examples_digest"]) == data["task_examples_count"]


def test_task_yaml_unchanged_decision_order_stable() -> None:
    task = yaml.safe_load((ML / "task_definition.yaml").read_text(encoding="utf-8"))
    assert task["class_decision_order"][0] == "ambiguous"
    assert task["class_decision_order"][-1] == "no_setup"
