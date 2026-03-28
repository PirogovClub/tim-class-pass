"""Committed Step 6 labels + helpers for Step 7 tests (no ml_output/ dependency)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = _REPO_ROOT / "src" / "ml"
STEP6_DIR = _REPO_ROOT / "tests" / "fixtures" / "step6_for_step7"


def load_step6_fixture_labels() -> list[dict[str, Any]]:
    p = STEP6_DIR / "generated_labels.jsonl"
    assert p.is_file(), (
        f"Missing committed fixture {p}. Copy from ml_output/step6_sample after "
        "`python -m ml.label_generation --out-dir ml_output/step6_sample`."
    )
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def market_windows_by_candidate() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in (ML_ROOT / "fixtures" / "market_windows").glob("*.json"):
        w = json.loads(path.read_text(encoding="utf-8"))
        out[str(w.get("candidate_id", path.stem))] = w
    return out


def modeling_rows_from_committed_step6(
    *,
    include_weak_in_training: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from ml.dataset_builder import build_modeling_rows
    from ml.feature_spec_loader import load_feature_spec

    labels = load_step6_fixture_labels()
    spec = load_feature_spec(ML_ROOT / "feature_spec.yaml")
    task_id = labels[0].get("task_id", "level_interaction_rule_satisfaction_v1") if labels else ""
    max_lb = int(spec["observation_window"]["max_lookback_bars"])
    return build_modeling_rows(
        labels,
        market_windows_by_candidate(),
        task_id=task_id,
        max_lookback_bars=max_lb,
        apply_splits=True,
        include_weak_in_training=include_weak_in_training,
    )
