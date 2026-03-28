"""Walk-forward config loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ml.backtest.walkforward_config_loader import WalkforwardConfigError, load_walkforward_config


def test_load_default_config() -> None:
    root = Path(__file__).resolve().parents[2]
    cfg = load_walkforward_config(root / "src" / "ml" / "walkforward_config.yaml")
    assert cfg["task_id"]
    assert "path" in cfg["dataset"]
    assert int(cfg["fold_policy"]["min_train_rows"]) >= 1
    assert cfg["fold_policy"]["mode"] == "expanding_absorb_val_into_train"


def test_invalid_step_size_mismatch(tmp_path: Path) -> None:
    import yaml

    root = Path(__file__).resolve().parents[2]
    raw = yaml.safe_load((root / "src" / "ml" / "walkforward_config.yaml").read_text(encoding="utf-8"))
    raw["fold_policy"]["step_size_rows"] = 99
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(WalkforwardConfigError):
        load_walkforward_config(p)


def test_invalid_config_missing_fold_policy(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("task_id: x\ndataset:\n  path: d.jsonl\nml_root: ml\n", encoding="utf-8")
    with pytest.raises(WalkforwardConfigError):
        load_walkforward_config(p)
