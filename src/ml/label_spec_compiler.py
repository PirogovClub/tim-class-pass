"""Compile Step 5 machine-readable specs into a runtime label spec (label_specs.json)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ml.task_validator import validate_task_examples

GENERATOR_VERSION = "1.0.0"


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected mapping")
    return raw


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected object")
    return raw


def compile_label_specs(ml_root: Path) -> dict[str, Any]:
    """Load task_definition, window_contract, ontology, mapping; emit structured runtime spec."""
    task = _load_yaml(ml_root / "task_definition.yaml")
    window = _load_yaml(ml_root / "window_contract.yaml")
    ontology = _load_json(ml_root / "class_ontology.json")
    mapping = _load_json(ml_root / "rule_to_class_mapping.json")
    examples_path = ml_root / "task_examples.json"
    examples = _load_json(examples_path)

    task_id = task["task_id"]
    if task_id != window.get("task_id"):
        raise ValueError("task_id mismatch between task_definition and window_contract")
    if ontology.get("task_id") != task_id:
        raise ValueError("task_id mismatch in class_ontology.json")
    if mapping.get("task_id") != task_id:
        raise ValueError("task_id mismatch in rule_to_class_mapping.json")
    if examples.get("task_id") != task_id:
        raise ValueError("task_id mismatch in task_examples.json")
    ex_errs = validate_task_examples(
        examples,
        source=str(examples_path),
        known_classes=set(task["label_set"]),
    )
    if ex_errs:
        raise ValueError("task_examples.json: " + "; ".join(ex_errs))

    label_set = list(task["label_set"])
    order = list(task["class_decision_order"])
    if set(order) != set(label_set):
        raise ValueError("class_decision_order must match label_set")

    ontology_names = {c["class_name"] for c in ontology["classes"]}
    if set(label_set) != ontology_names:
        raise ValueError(f"ontology classes {ontology_names} != label_set {set(label_set)}")

    max_forward = int(
        window["lookforward_for_labeling"]["max_forward_bars"]
    )
    ctx = window["context_before"]["primary_timeframe"]
    min_ctx = int(ctx["min_bars"])

    numeric = {
        "persistence_closes_acceptance": 2,
        "persistence_closes_failure": 2,
        "max_forward_bars": max_forward,
        "touch_tolerance_ticks_default": 1,
        "chop_band_relative": 0.0005,
        "level_relative_epsilon": 0.0002,
        "chop_close_band_relative": 0.00018,
        "min_context_bars_inclusive_anchor": min_ctx,
    }

    pit_rules = window["point_in_time_safety"]["rules"]

    compiled: dict[str, Any] = {
        "compiled_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator_version": GENERATOR_VERSION,
        "task_id": task_id,
        "task_definition_version": str(task["version"]),
        "window_contract_id": window["contract_id"],
        "window_contract_version": str(window["version"]),
        "ontology_id": ontology["ontology_id"],
        "ontology_version": str(ontology["version"]),
        "mapping_id": mapping["mapping_id"],
        "mapping_version": str(mapping["version"]),
        "label_set": label_set,
        "class_decision_order": order,
        "numeric_thresholds": numeric,
        "confidence_tier_meanings": task["confidence_tiers"],
        "ambiguity_policy_text": str(task["ambiguity_policy"]).strip(),
        "task_exclusions": task.get("exclusions", []),
        "pit_rule_ids": [r["id"] for r in pit_rules if isinstance(r, dict) and "id" in r],
        "pit_rules_full": pit_rules,
        "ambiguity_codes": [
            "MULTIPLE_PLAUSIBLE",
            "ANCHOR_UNCLEAR",
            "INSUFFICIENT_BARS",
            "EXCESSIVE_NOISE",
            "APPROACH_CONFLICT",
            "PIT_VIOLATION",
        ],
        "exclusion_codes": [
            "MISSING_REQUIRED_FIELD",
            "MISSING_REFERENCE_LEVEL",
            "MALFORMED_BARS",
            "NON_MONOTONIC_TIME",
            "ANCHOR_OUT_OF_RANGE",
            "HORIZON_EXCEEDED",
            "INSUFFICIENT_CONTEXT",
            "UNSUPPORTED_TIMEFRAME",
            "EXCLUDED_RULE_FAMILY",
            "FUTURE_DATA_LEAK",
        ],
        "mapping_entries": mapping["mappings"],
        "excluded_rule_families": mapping.get("excluded_rule_families", []),
        "task_examples_version": str(examples["version"]),
        "task_examples_count": len(examples.get("examples", [])),
        "task_examples_digest": [
            {
                "example_id": e.get("example_id"),
                "expected_label": e.get("expected_label"),
                "confidence_tier": e.get("confidence_tier"),
            }
            for e in examples.get("examples", [])
            if isinstance(e, dict)
        ],
    }
    return compiled


def write_label_specs(ml_root: Path, out_path: Path) -> None:
    spec = compile_label_specs(ml_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Compile Step 5 specs to ml/label_specs.json")
    p.add_argument("--ml-root", type=Path, default=Path("ml"))
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path (default: <ml-root>/label_specs.json)",
    )
    args = p.parse_args()
    ml_root = args.ml_root.resolve()
    out = (args.out or (ml_root / "label_specs.json")).resolve()
    try:
        write_label_specs(ml_root, out)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
