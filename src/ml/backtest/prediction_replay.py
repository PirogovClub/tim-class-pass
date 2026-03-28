"""Per-example prediction records for walk-forward replay."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def make_replay_id(fold_id: str, model_name: str, dataset_row_id: str) -> str:
    h = hashlib.sha256(f"{fold_id}|{model_name}|{dataset_row_id}".encode()).hexdigest()[:24]
    return f"rp_{h}"


def prediction_record(
    *,
    fold_id: str,
    model_name: str,
    row: dict[str, Any],
    predicted_label: str,
    predicted_probabilities: dict[str, float] | None,
    calibrated_probabilities: dict[str, float] | None,
    threshold_policy_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Single JSON-serializable replay row."""
    dsid = str(row.get("dataset_row_id", ""))
    rec = {
        "replay_id": make_replay_id(fold_id, model_name, dsid),
        "fold_id": fold_id,
        "model_name": model_name,
        "candidate_id": str(row.get("candidate_id", "")),
        "dataset_row_id": dsid,
        "anchor_timestamp": str(row.get("anchor_timestamp", "")),
        "timeframe": str(row.get("timeframe", "")),
        "actual_label": str(row.get("label", "")) if row.get("label") is not None else None,
        "predicted_label": predicted_label,
        "predicted_probabilities": predicted_probabilities,
        "calibrated_probabilities": calibrated_probabilities,
        "confidence_tier": str(row.get("confidence_tier", "")),
        "point_in_time_safe": bool(row.get("point_in_time_safe", True)),
        "threshold_policy_refs": threshold_policy_refs or [],
        "source_refs": row.get("source_refs"),
        "metadata": {"split_role": "test_forward_eval"},
    }
    return rec


def append_jsonl(path: Any, records: list[dict[str, Any]]) -> None:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
