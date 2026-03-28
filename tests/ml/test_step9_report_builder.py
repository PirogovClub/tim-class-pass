"""Step 9 report/manifest consistency."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from ml.step9.evidence_loader import load_step9_decision_config
from ml.step9.failure_mode_analysis import analyze_failure_modes
from ml.step9.model_family_decider import decide_model_family
from ml.step9.report_builder import write_step9_bundle
from ml.step9.step10_brief_builder import build_step10_brief

REPO = Path(__file__).resolve().parents[2]


def test_manifest_aligns_with_written_artifacts(tmp_path: Path) -> None:
    cfg = copy.deepcopy(load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml"))  # noqa: PLW2901
    cfg["outputs"]["root"] = "step9_out"
    cfg["minimum_evidence"]["min_folds_evaluated"] = 2
    from tests.ml.test_model_family_decider import _bundle, _fold, _mc

    raw = _bundle(
        mc=_mc(0.35, 0.62, 0.04),
        folds=[_fold(0.6), _fold(0.62), _fold(0.61)],
        weak=[],
        drift=False,
        preds_n=120,
    )
    ev = {
        "counts": {"folds": 3, "prediction_lines": 120},
        "task_id": cfg["task_id"],
        "step9_evidence_summary_id": "step9_evidence_summary_v1",
        "status": "complete",
        "pit_declaration": "",
        "sources": {},
        "optional_sources": {},
        "model_comparison_headline": {},
        "walkforward_answers_excerpt": {},
        "calibration_drift_excerpt": {},
        "policy_excerpt": {},
        "optional_upstream": {},
    }
    failure = analyze_failure_modes(cfg, raw, REPO)
    decision = decide_model_family(cfg, ev, failure, raw)
    brief = build_step10_brief(cfg, decision, failure, ev)
    result = write_step9_bundle(cfg, tmp_path, ev, failure, decision, brief, raw)
    man_path = Path(result["manifest"]["artifacts"]["step9_manifest"])
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for k, p in man["artifacts"].items():
        assert Path(p).is_file(), k
    ra = decision["rationale"]["decision_report_answers"]
    for key in (
        "tabular_beat_symbolic_materially",
        "weak_classes",
        "recommended_step10_direction",
        "non_recommended_directions",
    ):
        assert key in ra
