"""Validate generated label records against generated_labels.schema.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_NON_AMBIGUOUS = frozenset(
    {
        "acceptance_above",
        "acceptance_below",
        "false_breakout_up",
        "false_breakout_down",
        "rejection",
        "no_setup",
    }
)


def validate_generated_label_row(row: dict[str, Any], *, idx: int | None = None) -> list[str]:
    errs: list[str] = []
    prefix = f"row[{idx}]" if idx is not None else "row"

    req = (
        "generated_label_id",
        "task_id",
        "candidate_id",
        "label",
        "confidence_tier",
        "status",
        "decision_order_path",
        "matched_rule_refs",
        "matched_concept_ids",
        "matched_conditions",
        "invalidation_hits",
        "ambiguity_reason",
        "exclusion_reason",
        "market_window_ref",
        "anchor_timestamp",
        "timeframe",
        "label_horizon",
        "point_in_time_safe",
    )
    for k in req:
        if k not in row:
            errs.append(f"{prefix}: missing '{k}'")

    st = row.get("status")
    lab = row.get("label")
    if st == "assigned":
        if lab not in _NON_AMBIGUOUS:
            errs.append(f"{prefix}: status assigned requires non-ambiguous label, got {lab!r}")
        if row.get("ambiguity_reason") not in (None, ""):
            errs.append(f"{prefix}: assigned must not set ambiguity_reason")
    elif st == "ambiguous":
        if not row.get("ambiguity_reason"):
            errs.append(f"{prefix}: ambiguous status requires ambiguity_reason")
        if lab != "ambiguous":
            errs.append(f"{prefix}: ambiguous status expects label 'ambiguous'")
    elif st in ("excluded", "skipped_invalid_input"):
        if not row.get("exclusion_reason"):
            errs.append(f"{prefix}: {st} requires exclusion_reason")
        if lab is not None and lab not in ("", "none"):
            errs.append(f"{prefix}: excluded/skipped should not assign pattern label")

    ct = row.get("confidence_tier")
    if ct not in ("gold", "silver", "weak"):
        errs.append(f"{prefix}: invalid confidence_tier {ct!r}")

    if st == "ambiguous" and ct == "gold":
        errs.append(f"{prefix}: ambiguous withhold cannot be gold tier")

    return errs


def load_schema(ml_root: Path) -> dict[str, Any]:
    p = ml_root / "generated_labels.schema.json"
    return json.loads(p.read_text(encoding="utf-8"))


def validate_row_against_json_schema(row: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate one row with Draft7 JSON Schema (optional ``jsonschema`` dev dependency)."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed — pip install jsonschema (dev dependency)"]
    errs: list[str] = []
    try:
        jsonschema.Draft7Validator(schema).validate(row)
    except jsonschema.ValidationError as e:
        errs.append(e.message)
    return errs


def validate_labels_file(path: Path) -> list[str]:
    errs: list[str] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            errs.append(f"line {i+1}: JSON error: {e}")
            continue
        if not isinstance(row, dict):
            errs.append(f"line {i+1}: expected object")
            continue
        errs.extend(validate_generated_label_row(row, idx=i))
    return errs
