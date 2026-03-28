"""Classification metrics and reports for tabular baselines."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix


def evaluate_multiclass(
    y_true: list[str] | np.ndarray,
    y_pred: list[str] | np.ndarray,
    labels: list[str],
) -> dict[str, Any]:
    yt = np.array(y_true)
    yp = np.array(y_pred)
    present = sorted(set(labels) | set(yt) | set(yp))
    cm = confusion_matrix(yt, yp, labels=present).tolist()
    rep = classification_report(yt, yp, labels=present, zero_division=0, output_dict=True)
    return {
        "labels_order": present,
        "confusion_matrix": cm,
        "classification_report": rep,
    }
