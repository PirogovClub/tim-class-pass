"""Forward calibration checks across walk-forward folds."""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any


def summarize_fold_calibration(
    fold_id: str,
    y_true_idx: list[int] | None,
    proba_raw: list[list[float]] | None,
    proba_cal: list[list[float]] | None,
    class_order: list[str],
    bucket_report_raw: dict[str, Any] | None,
    bucket_report_cal: dict[str, Any] | None,
    brier_raw: float | None,
    brier_cal: float | None,
) -> dict[str, Any]:
    return {
        "fold_id": fold_id,
        "n_test": len(y_true_idx or []),
        "class_order": class_order,
        "brier_raw": brier_raw,
        "brier_cal": brier_cal,
        "bucket_report_raw": bucket_report_raw,
        "bucket_report_cal": bucket_report_cal,
    }


def build_calibration_drift_report(fold_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare calibration stability across folds (brier + bucket spread)."""
    br = [f["brier_raw"] for f in fold_summaries if f.get("brier_raw") is not None]
    bc = [f["brier_cal"] for f in fold_summaries if f.get("brier_cal") is not None]
    out: dict[str, Any] = {
        "calibration_drift_report_id": "calibration_drift_v1",
        "n_folds_with_metrics": len(fold_summaries),
        "brier_raw": {
            "per_fold": br,
            "mean": mean(br) if br else None,
            "pstdev": pstdev(br) if len(br) > 1 else 0.0,
        },
        "brier_calibrated": {
            "per_fold": bc,
            "mean": mean(bc) if bc else None,
            "pstdev": pstdev(bc) if len(bc) > 1 else 0.0,
        },
        "drift_heuristic": None,
        "notes": "Large increase in brier variance across forward folds suggests calibration drift.",
    }
    if len(br) > 1 and mean(br) > 0:
        cv = pstdev(br) / mean(br) if mean(br) else 0.0
        out["drift_heuristic"] = {
            "brier_raw_coefficient_of_variation": cv,
            "flag_potential_drift": cv > 0.35,
        }
    return out
