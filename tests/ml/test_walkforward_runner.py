"""Walk-forward runner integration (uses committed Step 7–style rows)."""

from __future__ import annotations

import json
from pathlib import Path

from ml.backtest.walkforward_config_loader import load_walkforward_config
from ml.backtest.walkforward_runner import run_walkforward
from tests.ml.step7_audit_fixtures import modeling_rows_from_committed_step6


def test_runner_writes_predictions_and_manifest(tmp_path: Path) -> None:
    rows, _ = modeling_rows_from_committed_step6(include_weak_in_training=True)
    ds = tmp_path / "modeling_dataset.jsonl"
    with ds.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    repo = Path(__file__).resolve().parents[2]
    cfg = load_walkforward_config(repo / "src" / "ml" / "walkforward_config.yaml")
    cfg["dataset"] = {"path": str(ds.resolve())}
    cfg["outputs"] = {**cfg["outputs"], "root": str(tmp_path / "step8_out")}

    summary = run_walkforward(repo, cfg)
    out = Path(summary["out_dir"])
    assert (out / "backtest_predictions.jsonl").is_file()
    assert summary["n_folds"] >= 1
    lines = [ln for ln in (out / "backtest_predictions.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    for ln in lines:
        o = json.loads(ln)
        assert "actual_label" in o
        assert "predicted_label" in o
        assert o["actual_label"] is not None
    assert (out / "step8_manifest.json").is_file()
    assert (out / "fold_metrics.json").is_file()
