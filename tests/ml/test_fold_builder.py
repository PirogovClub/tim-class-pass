"""Fold builder determinism and time ordering."""

from __future__ import annotations

from ml.backtest.fold_builder import build_folds, filter_eval_pool, sort_by_time


def _row(ts: str, cid: str, tier: str = "gold", label: str = "no_setup", status: str = "assigned") -> dict:
    return {
        "anchor_timestamp": ts,
        "candidate_id": cid,
        "confidence_tier": tier,
        "label": label,
        "label_status": status,
        "eligible_for_training": True,
        "features": {},
        "dataset_row_id": f"dr_{cid}",
        "timeframe": "1h",
        "point_in_time_safe": True,
    }


def test_folds_time_ordered_train_before_test() -> None:
    rows = [_row(f"2024-01-{i+1:02d}T00:00:00Z", f"c{i}") for i in range(12)]
    inclusion = {
        "require_eligible_for_training": True,
        "confidence_tiers_primary": ["gold"],
        "include_weak_sensitivity_track": False,
        "exclude_label_status": ["ambiguous", "excluded", "skipped_invalid_input"],
    }
    pool, _ = filter_eval_pool(rows, inclusion)
    sp = sort_by_time(pool)
    folds, _ = build_folds(
        sp,
        {
            "min_train_rows": 4,
            "min_val_rows": 2,
            "test_window_rows": 2,
            "step_size_rows": 2,
            "max_folds": 8,
            "skip_fold_if_insufficient_classes": True,
            "min_classes_in_train": 1,
        },
    )
    assert folds
    for f in folds:
        if f["train_anchor_end"] and f["test_anchor_start"]:
            assert f["train_anchor_end"] <= f["test_anchor_start"]
        tr = f["train_row_indices"]
        te = f["test_row_indices"]
        assert tr and te
        assert max(tr) < min(te)


def test_folds_deterministic() -> None:
    rows = [_row(f"2024-01-{i+1:02d}T00:00:00Z", f"c{i}") for i in range(12)]
    inclusion = {
        "require_eligible_for_training": True,
        "confidence_tiers_primary": ["gold"],
        "include_weak_sensitivity_track": False,
        "exclude_label_status": ["ambiguous", "excluded", "skipped_invalid_input"],
    }
    pool, _ = filter_eval_pool(rows, inclusion)
    sp = sort_by_time(pool)
    fp = {
        "min_train_rows": 4,
        "min_val_rows": 2,
        "test_window_rows": 2,
        "step_size_rows": 2,
        "max_folds": 8,
        "skip_fold_if_insufficient_classes": True,
        "min_classes_in_train": 1,
    }
    a, _ = build_folds(sp, fp)
    b, _ = build_folds(sp, fp)
    assert [x["fold_id"] for x in a] == [x["fold_id"] for x in b]
    assert a[0]["test_row_indices"] == b[0]["test_row_indices"]


def test_exclude_lesson_id_drops_rows() -> None:
    rows = [
        {
            **_row("2024-01-01T00:00:00Z", "a"),
            "source_refs": {"lesson_id": "L_keep"},
        },
        {
            **_row("2024-01-02T00:00:00Z", "b"),
            "source_refs": {"lesson_id": "L_drop"},
        },
    ]
    inclusion = {
        "require_eligible_for_training": True,
        "confidence_tiers_primary": ["gold"],
        "include_weak_sensitivity_track": False,
        "exclude_lesson_ids": ["L_drop"],
        "exclude_label_status": ["ambiguous", "excluded", "skipped_invalid_input"],
    }
    pool, log = filter_eval_pool(rows, inclusion)
    assert len(pool) == 1
    assert log["excluded_lesson_id"] == 1


def test_ambiguous_excluded_from_pool() -> None:
    rows = [
        _row("2024-01-01T00:00:00Z", "a"),
        {**_row("2024-01-02T00:00:00Z", "b"), "label_status": "ambiguous", "label": "ambiguous"},
    ]
    inclusion = {
        "require_eligible_for_training": True,
        "confidence_tiers_primary": ["gold"],
        "include_weak_sensitivity_track": False,
        "exclude_label_status": ["ambiguous", "excluded", "skipped_invalid_input"],
    }
    pool, log = filter_eval_pool(rows, inclusion)
    assert len(pool) == 1
    assert log["excluded_label_status"] >= 1
