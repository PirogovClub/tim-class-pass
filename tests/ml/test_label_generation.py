"""Tests for ML Step 6 deterministic label generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ml.label_generation import generate_label_for_window, run_batch
from ml.label_manifest_builder import build_dataset_manifest, build_generation_report
from ml.label_output_validator import (
    load_schema,
    validate_generated_label_row,
    validate_row_against_json_schema,
)
from ml.market_window import validate_market_window

REPO = Path(__file__).resolve().parents[2]
ML = REPO / "src" / "ml"
FIX = ML / "fixtures" / "market_windows"


@pytest.fixture(scope="module")
def compiled() -> dict:
    return json.loads((ML / "label_specs.json").read_text(encoding="utf-8"))


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_valid_window_accepted(compiled: dict) -> None:
    w = _load("acceptance_above.json")
    n = compiled["numeric_thresholds"]
    vr = validate_market_window(
        w,
        max_forward_bars=n["max_forward_bars"],
        min_context_bars_inclusive_anchor=n["min_context_bars_inclusive_anchor"],
    )
    assert vr.ok


def test_missing_level_rejected(compiled: dict) -> None:
    w = _load("invalid_missing_level.json")
    n = compiled["numeric_thresholds"]
    vr = validate_market_window(
        w,
        max_forward_bars=n["max_forward_bars"],
        min_context_bars_inclusive_anchor=n["min_context_bars_inclusive_anchor"],
    )
    assert not vr.ok


def test_horizon_exceeded_rejected(compiled: dict) -> None:
    w = _load("invalid_horizon.json")
    n = compiled["numeric_thresholds"]
    vr = validate_market_window(
        w,
        max_forward_bars=n["max_forward_bars"],
        min_context_bars_inclusive_anchor=n["min_context_bars_inclusive_anchor"],
    )
    assert not vr.ok
    assert any("exceed" in e for e in vr.errors)


def test_fixture_labels(
    compiled: dict,
) -> None:
    expect = {
        "acceptance_above.json": ("acceptance_above", "assigned"),
        "acceptance_below.json": ("acceptance_below", "assigned"),
        "false_breakout_up.json": ("false_breakout_up", "assigned"),
        "false_breakout_down.json": ("false_breakout_down", "assigned"),
        "rejection.json": ("rejection", "assigned"),
        "no_setup.json": ("no_setup", "assigned"),
        "ambiguous.json": ("ambiguous", "ambiguous"),
        "invalid_missing_level.json": (None, "skipped_invalid_input"),
        "invalid_horizon.json": (None, "skipped_invalid_input"),
        "invalid_pit_leak.json": (None, "skipped_invalid_input"),
        "excluded_rule_family.json": (None, "excluded"),
    }
    for fname, (lab, st) in expect.items():
        w = _load(fname)
        r = generate_label_for_window(w, compiled)
        assert r["status"] == st, (fname, r)
        assert r["label"] == lab, (fname, r)
        errs = validate_generated_label_row(r)
        assert not errs, (fname, errs)


def test_confidence_tiers(compiled: dict) -> None:
    g = generate_label_for_window(_load("confidence_gold.json"), compiled)
    assert g["confidence_tier"] == "gold"
    s = generate_label_for_window(_load("confidence_silver.json"), compiled)
    assert s["confidence_tier"] == "silver"
    wk = generate_label_for_window(_load("confidence_weak.json"), compiled)
    assert wk["confidence_tier"] == "weak"


def test_pit_simulated_violation(compiled: dict) -> None:
    r = generate_label_for_window(_load("pit_simulated_violation.json"), compiled)
    assert r["point_in_time_safe"] is False
    assert "pit_001" in r["invalidation_hits"]


def test_no_setup_not_ambiguous(compiled: dict) -> None:
    r = generate_label_for_window(_load("no_setup.json"), compiled)
    assert r["label"] == "no_setup"
    assert r["status"] == "assigned"
    assert r["ambiguity_reason"] is None


def test_ambiguous_has_reason(compiled: dict) -> None:
    r = generate_label_for_window(_load("ambiguous.json"), compiled)
    assert r["ambiguity_reason"]


def test_excluded_no_pattern_label(compiled: dict) -> None:
    r = generate_label_for_window(_load("excluded_rule_family.json"), compiled)
    assert r["label"] is None
    assert r["exclusion_reason"]


def test_bars_before_anchor_must_match_index(compiled: dict) -> None:
    w = _load("acceptance_above.json")
    w = json.loads(json.dumps(w))
    w["bars_before_anchor"] = 5
    n = compiled["numeric_thresholds"]
    vr = validate_market_window(
        w,
        max_forward_bars=n["max_forward_bars"],
        min_context_bars_inclusive_anchor=n["min_context_bars_inclusive_anchor"],
    )
    assert not vr.ok
    assert any("bars_before_anchor" in e for e in vr.errors)


def test_generated_row_validates_against_json_schema(compiled: dict) -> None:
    w = _load("acceptance_above.json")
    row = generate_label_for_window(w, compiled)
    schema = load_schema(ML)
    js_errs = validate_row_against_json_schema(row, schema)
    assert not js_errs, js_errs


def test_report_includes_source_rollups(compiled: dict) -> None:
    from ml.label_manifest_builder import build_generation_report

    windows = sorted(FIX.glob("*.json"))
    labels = [generate_label_for_window(json.loads(p.read_text(encoding="utf-8")), compiled) for p in windows]
    rep = build_generation_report(labels)
    assert rep["counts_by_rule_family_hint"].get("macro_calendar") >= 1
    assert rep["counts_by_lesson_id"].get("audit_fixture_cal") >= 1


def test_non_monotonic_timestamps_rejected(compiled: dict) -> None:
    w = _load("acceptance_above.json")
    w = json.loads(json.dumps(w))
    w["bars"] = list(w["bars"])
    w["bars"][21] = dict(w["bars"][21])
    w["bars"][21]["t"] = w["bars"][20]["t"]
    n = compiled["numeric_thresholds"]
    vr = validate_market_window(
        w,
        max_forward_bars=n["max_forward_bars"],
        min_context_bars_inclusive_anchor=n["min_context_bars_inclusive_anchor"],
    )
    assert not vr.ok


def test_manifest_report_aligns(compiled: dict) -> None:
    windows = sorted(FIX.glob("*.json"))
    labels = [generate_label_for_window(json.loads(p.read_text(encoding="utf-8")), compiled) for p in windows]
    rep = build_generation_report(labels)
    assert rep["row_count"] == len(labels)
    assert sum(rep["counts_by_status"].values()) == len(labels)
    man = build_dataset_manifest(
        labels,
        task_id=compiled["task_id"],
        spec_versions={"task": "1"},
        generator_version="t",
        input_sources=["fixtures"],
        pit_declaration="test",
        known_limitations=[],
    )
    assert man["row_count"] == len(labels)
    assert man["integrity"]["status_counts_sum"] == len(labels)
