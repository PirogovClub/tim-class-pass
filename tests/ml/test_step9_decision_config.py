"""Step 9 decision config load/validate."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ml.step9.evidence_loader import Step9ConfigError, load_step9_decision_config

REPO = Path(__file__).resolve().parents[2]
CFG_PATH = REPO / "src" / "ml" / "step9_decision_config.yaml"


def test_decision_config_loads() -> None:
    cfg = load_step9_decision_config(CFG_PATH)
    assert cfg["task_id"]
    assert "evidence" in cfg
    assert cfg["tie_break_order"]


def test_invalid_config_missing_key(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump({"task_id": "x"}), encoding="utf-8")
    with pytest.raises(Step9ConfigError, match="Missing required"):
        load_step9_decision_config(p)


def test_invalid_no_go_section(tmp_path: Path) -> None:
    base = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8"))
    base["no_go"] = {"outcome": "sequence_model_next"}
    p = tmp_path / "bad_ngo.yaml"
    p.write_text(yaml.safe_dump(base), encoding="utf-8")
    with pytest.raises(Step9ConfigError, match="no_go"):
        load_step9_decision_config(p)


def test_invalid_tie_break_order(tmp_path: Path) -> None:
    base = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8"))
    base["tie_break_order"] = ["tabular_only_for_now", "sequence_model_next"]
    p = tmp_path / "bad2.yaml"
    p.write_text(yaml.safe_dump(base), encoding="utf-8")
    with pytest.raises(Step9ConfigError, match="tie_break_order"):
        load_step9_decision_config(p)
