"""Step 7 manifest alignment for Step 8."""

from __future__ import annotations

import json
from pathlib import Path

from ml.backtest.dataset_integrity import build_step7_alignment_report, count_jsonl_rows


def test_count_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "a.jsonl"
    p.write_text("{}\n{}\n", encoding="utf-8")
    assert count_jsonl_rows(p) == 2


def test_alignment_passes_when_manifest_matches(tmp_path: Path) -> None:
    ds = tmp_path / "m.jsonl"
    ds.write_text('{"x":1}\n{"x":2}\n', encoding="utf-8")
    man = tmp_path / "man.json"
    man.write_text(
        json.dumps({"row_counts": {"total_with_features": 2}, "summary": {"task_id": "t1"}}),
        encoding="utf-8",
    )
    r = build_step7_alignment_report(ds, dataset_manifest_path=man, split_manifest_path=None)
    assert r["checks_passed"] is True
    assert not r["critical_issues"]


def test_alignment_fails_on_row_count_mismatch(tmp_path: Path) -> None:
    ds = tmp_path / "m.jsonl"
    ds.write_text("{}\n", encoding="utf-8")
    man = tmp_path / "man.json"
    man.write_text(json.dumps({"row_counts": {"total_with_features": 99}}), encoding="utf-8")
    r = build_step7_alignment_report(ds, dataset_manifest_path=man)
    assert r["checks_passed"] is False
    assert r["critical_issues"]
