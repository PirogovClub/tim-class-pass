"""Probability calibration helpers (Platt / isotonic via sklearn)."""

from __future__ import annotations

from typing import Any

import numpy as np


def calibration_bucket_report(
    y_true_idx: np.ndarray,
    probs: np.ndarray,
    clf_classes: np.ndarray,
    *,
    n_bins: int = 5,
) -> dict[str, Any]:
    """Bucket max predicted prob vs accuracy (pred class vs true class index)."""
    p_max = probs.max(axis=1)
    pred_col = probs.argmax(axis=1)
    pred_global = clf_classes[pred_col]
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (p_max >= lo) & (p_max < hi if i < n_bins - 1 else p_max <= hi)
        if not np.any(mask):
            rows.append({"bin": [float(lo), float(hi)], "n": 0, "mean_confidence": None, "accuracy": None})
            continue
        acc = float(np.mean((pred_global[mask] == y_true_idx[mask]).astype(float)))
        rows.append(
            {
                "bin": [float(lo), float(hi)],
                "n": int(np.sum(mask)),
                "mean_max_prob": float(np.mean(p_max[mask])),
                "accuracy": acc,
            }
        )
    return {"buckets": rows, "n_bins": n_bins}


def brier_multiclass(y_true: np.ndarray, probs: np.ndarray, n_classes: int) -> float:
    y_oh = np.zeros((len(y_true), n_classes))
    y_oh[np.arange(len(y_true)), y_true] = 1.0
    return float(np.mean(np.sum((probs - y_oh) ** 2, axis=1)))


def brier_multiclass_aligned(y_idx: np.ndarray, probs: np.ndarray, clf_classes: np.ndarray) -> float:
    """y_idx are integer class indices; clf_classes maps column j -> global class index."""
    k = probs.shape[1]
    y_oh = np.zeros((len(y_idx), k))
    pos = {int(c): j for j, c in enumerate(clf_classes)}
    for i, yi in enumerate(y_idx):
        j = pos.get(int(yi))
        if j is not None:
            y_oh[i, j] = 1.0
    return float(np.mean(np.sum((probs - y_oh) ** 2, axis=1)))
