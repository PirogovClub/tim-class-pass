"""Narrow Step 10 architecture brief from model-family decision."""

from __future__ import annotations

from typing import Any


def build_step10_brief(
    cfg: dict[str, Any],
    decision: dict[str, Any],
    failure: dict[str, Any],
    evidence_summary: dict[str, Any],
) -> dict[str, Any]:
    outcome = decision.get("outcome", "improve_upstream_first")
    task_id = cfg.get("task_id", "")
    alts = [
        "tabular_only_for_now",
        "sequence_model_next",
        "vision_model_next",
        "improve_upstream_first",
    ]
    non_chosen = [x for x in alts if x != outcome]

    base = {
        "step10_architecture_brief_id": "step10_architecture_brief_v1",
        "task_id": task_id,
        "chosen_next_direction": outcome,
        "non_chosen_alternatives": non_chosen,
        "pit_assumptions": cfg.get("pit_declaration", ""),
        "scope_boundaries": _scope(outcome),
        "expected_inputs": _inputs(outcome, evidence_summary),
        "expected_outputs": _outputs(outcome),
        "evaluation_plan": _eval_plan(outcome),
        "acceptance_criteria": _acceptance(outcome, failure),
        "risks_and_limitations": _risks(outcome),
        "explicitly_deferred": _deferred(outcome),
    }

    if outcome == "sequence_model_next":
        base["sequence_model_contract"] = {
            "candidate_families": ["TCN", "LSTM", "transformer_encoder_ohlcv"],
            "input_sequence_schema": "Fixed-length OHLCV (and engineered bar features) ending at anchor bar, PIT-safe",
            "sequence_length_bars": 64,
            "timeframes": ["primary from task definition; align with Step 7 observation window"],
            "target_labels": "Same multiclass as Step 6/7 task_id",
            "calibration_plan": "Fit calibrator on validation fold only per walk-forward fold",
            "explanation_limitations": "Sequence models do not replace RAG/rule provenance; combine in later decision layer",
        }
    elif outcome == "vision_model_next":
        base["vision_model_contract"] = {
            "chart_rendering_contract": "Rasterize PIT-safe window to fixed resolution; axis scale policy TBD in Step 10 spec",
            "image_standardization": "Fixed W×H, color policy, padding rules",
            "label_alignment_policy": "Each image maps to same anchor_timestamp / dataset_row_id as tabular row",
            "proof_requirement": "Must beat structured-price + sequence baselines on same walk-forward splits",
            "evaluation_plan": "Walk-forward identical to Step 8; separate calibration on val",
        }
    elif outcome in ("tabular_only_for_now", "improve_upstream_first"):
        base["upstream_improvement_contract"] = {
            "focus": "labels" if failure.get("representation_hints", {}).get("label_manifest_concern") else "features_data",
            "actions": _upstream_actions(outcome, failure),
        }

    return base


def _scope(outcome: str) -> list[str]:
    if outcome == "improve_upstream_first":
        return [
            "Step 6–7 quality and coverage only",
            "No new sequence/vision training in Step 10 under this brief",
        ]
    if outcome == "tabular_only_for_now":
        return ["Extend tabular/symbolic evaluation", "More folds/data before advanced models"]
    if outcome == "sequence_model_next":
        return ["Single sequence baseline family pilot", "No vision", "No RAG-text training"]
    return ["Vision pilot only with mandatory structured baselines", "No production serving"]


def _inputs(outcome: str, ev: dict[str, Any]) -> list[str]:
    base = ["modeling_dataset.jsonl", "walkforward_config.yaml", "feature_spec.yaml"]
    if outcome in ("sequence_model_next", "vision_model_next"):
        base.append("step8 walk-forward split definitions (fold JSON)")
    if outcome == "vision_model_next":
        base.append("chart rendering pipeline output (Step 10)")
    return base


def _outputs(outcome: str) -> list[str]:
    if outcome == "improve_upstream_first":
        return ["revised manifests", "optional refreshed Step 7 QA JSON", "re-run Step 8 gate"]
    if outcome == "tabular_only_for_now":
        return ["expanded walk-forward report", "updated step8_manifest.json"]
    if outcome == "sequence_model_next":
        return ["sequence_model_fold_metrics.json", "calibration artifacts", "comparison to logreg"]
    return ["vision_fold_metrics.json", "ablation vs sequence/tabular"]


def _eval_plan(outcome: str) -> list[str]:
    return [
        "Reuse Step 8 walk-forward policy (time-ordered folds, same metrics)",
        "No test-set threshold tuning beyond Step 8 policy",
    ]


def _acceptance(outcome: str, failure: dict[str, Any]) -> list[str]:
    if outcome == "improve_upstream_first":
        return [
            "Critical manifest/integrity checks pass",
            "Minimum fold count and per-class support meet Step 9 config minima before re-deciding",
        ]
    if outcome == "tabular_only_for_now":
        return ["Mean tabular macro-F1 holds above config min across folds", "Weak class count within bound"]
    if outcome == "sequence_model_next":
        return ["Sequence model beats logistic_regression mean macro-F1 by configured margin on same folds"]
    return ["Vision beats best structured baseline by pre-registered margin on held-forward folds"]


def _risks(outcome: str) -> list[str]:
    return [
        "Small-sample folds can invert rankings",
        "Overfitting advanced models without upstream fixes",
    ]


def _deferred(outcome: str) -> list[str]:
    d = ["live trading", "multimodal RAG fusion", "hyperparameter search platform"]
    if outcome != "vision_model_next":
        d.append("chart vision models")
    if outcome != "sequence_model_next":
        d.append("deep sequence encoders")
    return d


def _upstream_actions(outcome: str, failure: dict[str, Any]) -> list[str]:
    acts = ["Increase labeled eval volume where possible", "Re-check label ambiguity rates"]
    if failure.get("calibration_level", {}).get("drift_flag"):
        acts.append("Investigate calibration stability before adding model capacity")
    if failure.get("class_level", {}).get("low_support_class_labels"):
        acts.append("Address rare-class support or collapse label taxonomy")
    if outcome == "tabular_only_for_now":
        acts.append("Collect more forward folds; re-run Step 9 decider")
    return acts
