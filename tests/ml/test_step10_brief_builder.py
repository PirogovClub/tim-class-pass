"""Step 10 brief builder."""

from __future__ import annotations

import copy
from pathlib import Path

from ml.step9.evidence_loader import load_step9_decision_config
from ml.step9.failure_mode_analysis import analyze_failure_modes
from ml.step9.model_family_decider import decide_model_family
from ml.step9.step10_brief_builder import build_step10_brief

REPO = Path(__file__).resolve().parents[2]


def test_brief_matches_tabular_decision() -> None:
    cfg = copy.deepcopy(load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml"))
    cfg["minimum_evidence"]["min_folds_evaluated"] = 2
    from tests.ml.test_model_family_decider import _bundle, _fold, _mc

    raw = _bundle(
        mc=_mc(0.35, 0.62, 0.04),
        folds=[_fold(0.6), _fold(0.62), _fold(0.61)],
        weak=[],
        drift=False,
        preds_n=120,
    )
    ev = {"counts": {"folds": 3, "prediction_lines": 120}}
    failure = analyze_failure_modes(cfg, raw, REPO)
    decision = decide_model_family(cfg, ev, failure, raw)
    brief = build_step10_brief(cfg, decision, failure, ev)
    assert brief["chosen_next_direction"] == decision["outcome"]
    assert brief["scope_boundaries"]
    assert brief["expected_inputs"]
    assert brief["expected_outputs"]
    assert brief["evaluation_plan"]
    assert brief["acceptance_criteria"]
    assert brief["risks_and_limitations"]
    assert brief["explicitly_deferred"]


def test_brief_sequence_includes_contract() -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    decision = {"outcome": "sequence_model_next", "task_id": cfg["task_id"], "scores": {}, "rationale": {}}
    failure: dict = {"representation_hints": {}}
    ev: dict = {"counts": {}}
    brief = build_step10_brief(cfg, decision, failure, ev)
    assert "sequence_model_contract" in brief
    assert "TCN" in str(brief["sequence_model_contract"]["candidate_families"])
