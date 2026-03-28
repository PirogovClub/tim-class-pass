"""Tests for PIT-safe feature builder."""

from __future__ import annotations

import json
from pathlib import Path

from ml.feature_builder import compute_features

FIX = Path(__file__).resolve().parents[2] / "src" / "ml" / "fixtures" / "market_windows"


def test_level_relative_features() -> None:
    w = json.loads((FIX / "acceptance_above.json").read_text(encoding="utf-8"))
    f = compute_features(w, max_lookback_bars=20)
    assert "close_distance_pct" in f
    assert abs(f["close_distance_pct"]) < 0.1
    assert -0.01 <= f["close_location_anchor"] <= 1.01


def test_wick_ratios_sum_reasonable() -> None:
    w = json.loads((FIX / "rejection.json").read_text(encoding="utf-8"))
    f = compute_features(w, max_lookback_bars=20)
    assert 0 <= f["upper_wick_ratio_anchor"] <= 1.5
    assert 0 <= f["lower_wick_ratio_anchor"] <= 1.5


def test_persistence_counts_non_negative() -> None:
    w = json.loads((FIX / "no_setup.json").read_text(encoding="utf-8"))
    f = compute_features(w, max_lookback_bars=20)
    assert f["n_closes_above_level_pre"] >= 0
    assert f["n_closes_below_level_pre"] >= 0


def test_volume_ratio_positive() -> None:
    w = json.loads((FIX / "acceptance_above.json").read_text(encoding="utf-8"))
    f = compute_features(w, max_lookback_bars=20)
    assert f["volume_ratio_anchor"] > 0


def test_htf_placeholder_zero() -> None:
    w = json.loads((FIX / "acceptance_above.json").read_text(encoding="utf-8"))
    f = compute_features(w, max_lookback_bars=20)
    assert f["htf_alignment_placeholder"] == 0.0
