"""Step 9 evidence loader."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ml.step9.evidence_loader import (
    Step9EvidenceError,
    build_evidence_summary,
    load_step9_decision_config,
)

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "tests" / "fixtures" / "step9_audit_step8"
if not SAMPLE.is_dir():
    SAMPLE = REPO / "ml_output" / "step8_audit_sample"


def test_evidence_summary_from_committed_step8(tmp_path: Path) -> None:
    if not SAMPLE.is_dir():
        pytest.skip("step9_audit_step8 fixture or ml_output/step8_audit_sample not present")
    dst = tmp_path / "s8"
    shutil.copytree(SAMPLE, dst)
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    cfg = dict(cfg)
    cfg["evidence"] = dict(cfg["evidence"])
    cfg["evidence"]["step8_root"] = str(dst.relative_to(tmp_path))
    summary = build_evidence_summary(cfg, tmp_path, strict=True)
    assert summary["status"] == "complete"
    assert summary["counts"]["folds"] >= 1


def test_missing_artifact_strict(tmp_path: Path) -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    cfg = dict(cfg)
    cfg["evidence"] = dict(cfg["evidence"])
    cfg["evidence"]["step8_root"] = "nonexistent_step8_dir"
    with pytest.raises(Step9EvidenceError):
        build_evidence_summary(cfg, tmp_path, strict=True)
