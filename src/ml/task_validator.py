"""Deterministic validation for ML Step 5 task spec files (YAML/JSON)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TASK_KEYS = frozenset(
    {
        "task_id",
        "task_name",
        "task_type",
        "version",
        "status",
        "description",
        "target_unit",
        "label_set",
        "preconditions",
        "exclusions",
        "ambiguity_policy",
        "confidence_tiers",
        "input_window",
        "required_inputs",
        "optional_inputs",
        "rule_sources",
        "canonical_concepts",
        "class_decision_order",
        "notes",
        "downstream_dependencies",
        "point_in_time_safety",
    }
)

REQUIRED_WINDOW_KEYS = frozenset(
    {
        "anchor_event",
        "context_before",
        "decision_horizon",
        "point_in_time_safety",
        "required_ohlcv_fields",
        "lookforward_for_labeling",
        "contract_id",
        "task_id",
    }
)

REQUIRED_CONFIDENCE_TIERS = frozenset({"gold", "silver", "weak"})

REQUIRED_ONTOLOGY_CLASS_FIELDS = frozenset(
    {
        "class_name",
        "description",
        "semantic_intent",
        "positive_conditions",
        "negative_conditions",
        "common_confusions",
        "invalidated_by",
        "allowed_confidence_tiers",
        "notes",
    }
)


class TaskValidationError(Exception):
    """Bundle validation failed."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TaskValidationError([f"{path}: root must be a mapping"])
    return raw


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TaskValidationError([f"{path}: root must be an object"])
    return raw


def validate_task_definition(data: dict[str, Any], *, source: str) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_TASK_KEYS - set(data.keys()))
    if missing:
        errors.append(f"{source}: missing keys: {missing}")
    ls = data.get("label_set")
    if ls is not None:
        if not isinstance(ls, list) or not ls:
            errors.append(f"{source}: label_set must be a non-empty list")
        elif len(ls) != len(set(ls)):
            errors.append(f"{source}: label_set contains duplicates")
    cdo = data.get("class_decision_order")
    if cdo is not None and isinstance(ls, list):
        if not isinstance(cdo, list) or not cdo:
            errors.append(f"{source}: class_decision_order must be a non-empty list")
        else:
            if len(cdo) != len(set(cdo)):
                errors.append(f"{source}: class_decision_order contains duplicates")
            if set(cdo) != set(ls):
                errors.append(
                    f"{source}: class_decision_order must be a permutation of label_set "
                    f"(got symmetric_diff={set(cdo) ^ set(ls)})"
                )
    ct = data.get("confidence_tiers")
    if ct is not None:
        if not isinstance(ct, dict):
            errors.append(f"{source}: confidence_tiers must be a mapping")
        else:
            missing_t = REQUIRED_CONFIDENCE_TIERS - set(ct.keys())
            if missing_t:
                errors.append(f"{source}: confidence_tiers missing: {sorted(missing_t)}")
            for tier, body in ct.items():
                if isinstance(body, dict) and "meaning" not in body:
                    errors.append(f"{source}: confidence_tiers.{tier} missing 'meaning'")
    ap = data.get("ambiguity_policy")
    if ap is not None:
        if not isinstance(ap, str) or not ap.strip():
            errors.append(f"{source}: ambiguity_policy must be a non-empty string")
    pit = data.get("point_in_time_safety")
    if pit is None:
        errors.append(f"{source}: point_in_time_safety section missing")
    elif isinstance(pit, dict) and not str(pit.get("summary", "")).strip() and "rules" not in pit:
        errors.append(f"{source}: point_in_time_safety must include summary text or nested rules")
    return errors


def validate_window_contract(data: dict[str, Any], *, source: str) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_WINDOW_KEYS - set(data.keys()))
    if missing:
        errors.append(f"{source}: missing keys: {missing}")
    pit = data.get("point_in_time_safety")
    if not isinstance(pit, dict):
        errors.append(f"{source}: point_in_time_safety must be a mapping")
    else:
        rules = pit.get("rules")
        if not isinstance(rules, list) or not rules:
            errors.append(f"{source}: point_in_time_safety.rules must be a non-empty list")
        else:
            for i, r in enumerate(rules):
                if not isinstance(r, dict) or "text" not in r:
                    errors.append(f"{source}: point_in_time_safety.rules[{i}] needs 'text'")
    return errors


def validate_class_ontology(data: dict[str, Any], *, source: str) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    classes = data.get("classes")
    if not isinstance(classes, list) or not classes:
        return [f"{source}: classes must be a non-empty list"], set()
    names: list[str] = []
    for i, c in enumerate(classes):
        if not isinstance(c, dict):
            errors.append(f"{source}: classes[{i}] must be an object")
            continue
        miss = sorted(REQUIRED_ONTOLOGY_CLASS_FIELDS - set(c.keys()))
        if miss:
            errors.append(f"{source}: classes[{i}] missing fields: {miss}")
        cn = c.get("class_name")
        if isinstance(cn, str):
            names.append(cn)
        tiers = c.get("allowed_confidence_tiers")
        if isinstance(tiers, list):
            unknown = set(tiers) - REQUIRED_CONFIDENCE_TIERS
            if unknown:
                errors.append(f"{source}: classes[{i}] unknown confidence tiers: {unknown}")
        if cn == "ambiguous" and isinstance(tiers, list) and "gold" in tiers:
            errors.append(f"{source}: ambiguous class must not allow gold confidence tier")
    return errors, set(names)


def validate_rule_mapping(
    data: dict[str, Any],
    *,
    source: str,
    known_classes: set[str],
) -> list[str]:
    errors: list[str] = []
    mappings = data.get("mappings")
    if not isinstance(mappings, list):
        return [f"{source}: mappings must be a list"]
    for i, m in enumerate(mappings):
        if not isinstance(m, dict):
            errors.append(f"{source}: mappings[{i}] must be an object")
            continue
        tc = m.get("task_classes")
        if not isinstance(tc, list) or not tc:
            errors.append(f"{source}: mappings[{i}].task_classes must be a non-empty list")
            continue
        for cls in tc:
            if cls not in known_classes:
                errors.append(f"{source}: mappings[{i}] references unknown class {cls!r}")
    return errors


def validate_task_examples(
    data: dict[str, Any],
    *,
    source: str,
    known_classes: set[str],
) -> list[str]:
    errors: list[str] = []
    ex = data.get("examples")
    if not isinstance(ex, list):
        return [f"{source}: examples must be a list"]
    required_example_keys = frozenset(
        {
            "example_id",
            "class_label",
            "anchor_description",
            "market_window_summary",
            "rule_concepts",
            "expected_label",
            "confidence_tier",
            "notes",
        }
    )
    for i, row in enumerate(ex):
        if not isinstance(row, dict):
            errors.append(f"{source}: examples[{i}] must be an object")
            continue
        miss = sorted(required_example_keys - set(row.keys()))
        if miss:
            errors.append(f"{source}: examples[{i}] missing keys: {miss}")
        lab = row.get("class_label")
        if lab not in known_classes:
            errors.append(f"{source}: examples[{i}] unknown class_label {lab!r}")
        if row.get("expected_label") != lab:
            errors.append(f"{source}: examples[{i}] expected_label must match class_label")
        tier = row.get("confidence_tier")
        if tier not in REQUIRED_CONFIDENCE_TIERS:
            errors.append(f"{source}: examples[{i}] invalid confidence_tier {tier!r}")
        if lab == "ambiguous":
            ar = row.get("ambiguity_reason")
            if not isinstance(ar, str) or not ar.strip():
                errors.append(f"{source}: examples[{i}] ambiguous class requires non-empty ambiguity_reason")
            if tier == "gold":
                errors.append(f"{source}: examples[{i}] ambiguous must not use gold tier")
        if lab == "no_setup":
            ar = row.get("ambiguity_reason")
            if ar is not None and ar != "":
                errors.append(
                    f"{source}: examples[{i}] no_setup must not carry ambiguity_reason "
                    "(use ambiguous class if withholding)"
                )
    return errors


def validate_task_bundle(ml_root: Path | None = None) -> list[str]:
    """Validate all Step 5 spec files under ``ml_root``. Returns a list of error strings (empty if OK)."""
    root = ml_root or Path(__file__).resolve().parent
    errors: list[str] = []

    td_path = root / "task_definition.yaml"
    wc_path = root / "window_contract.yaml"
    onto_path = root / "class_ontology.json"
    map_path = root / "rule_to_class_mapping.json"
    ex_path = root / "task_examples.json"

    for p in (td_path, wc_path, onto_path, map_path, ex_path):
        if not p.is_file():
            errors.append(f"Missing required file: {p}")

    if errors:
        return errors

    try:
        task_def = _load_yaml(td_path)
        errors.extend(validate_task_definition(task_def, source=str(td_path)))
    except TaskValidationError as e:
        errors.extend(e.errors)

    try:
        window_c = _load_yaml(wc_path)
        errors.extend(validate_window_contract(window_c, source=str(wc_path)))
        tid_td = task_def.get("task_id")
        tid_wc = window_c.get("task_id")
        if tid_td and tid_wc and tid_td != tid_wc:
            errors.append(f"task_id mismatch: task_definition={tid_td!r} window_contract={tid_wc!r}")
    except TaskValidationError as e:
        errors.extend(e.errors)

    known_classes: set[str] = set()
    try:
        onto = _load_json(onto_path)
        o_errs, known_classes = validate_class_ontology(onto, source=str(onto_path))
        errors.extend(o_errs)
    except TaskValidationError as e:
        errors.extend(e.errors)

    label_set = set(task_def.get("label_set") or [])
    expected = {
        "acceptance_above",
        "acceptance_below",
        "false_breakout_up",
        "false_breakout_down",
        "rejection",
        "no_setup",
        "ambiguous",
    }
    if label_set != expected:
        errors.append(f"label_set must equal required 7 classes; got {sorted(label_set)}")
    if known_classes and known_classes != label_set:
        errors.append(
            f"ontology class_name set must match label_set; diff label_set-onto={sorted(label_set - known_classes)} "
            f"onto-label_set={sorted(known_classes - label_set)}"
        )

    try:
        mapping = _load_json(map_path)
        tid_m = mapping.get("task_id")
        if tid_td and tid_m and tid_m != tid_td:
            errors.append(f"task_id mismatch: task_definition={tid_td!r} mapping={tid_m!r}")
        errors.extend(validate_rule_mapping(mapping, source=str(map_path), known_classes=label_set))
    except TaskValidationError as e:
        errors.extend(e.errors)

    try:
        examples = _load_json(ex_path)
        tid_e = examples.get("task_id")
        if tid_td and tid_e and tid_e != tid_td:
            errors.append(f"task_id mismatch: task_definition={tid_td!r} task_examples={tid_e!r}")
        errors.extend(validate_task_examples(examples, source=str(ex_path), known_classes=label_set))
    except TaskValidationError as e:
        errors.extend(e.errors)

    return errors


def validate_task_bundle_or_raise(ml_root: Path | None = None) -> None:
    errs = validate_task_bundle(ml_root)
    if errs:
        raise TaskValidationError(errs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ML Step 5 task definition bundle.")
    parser.add_argument(
        "--ml-root",
        type=Path,
        default=None,
        help="Directory containing task_definition.yaml (default: this package directory)",
    )
    args = parser.parse_args(argv)
    root = args.ml_root or Path(__file__).resolve().parent
    errs = validate_task_bundle(root)
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1
    print(f"OK: ML Step 5 task bundle valid under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
