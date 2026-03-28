"""Score and select model-family outcome from evidence + failure modes."""

from __future__ import annotations

from typing import Any

OUTCOMES = (
    "improve_upstream_first",
    "tabular_only_for_now",
    "sequence_model_next",
    "vision_model_next",
)


def _mc_mean(mc: dict[str, Any], key: str) -> float | None:
    block = mc.get(key) or {}
    v = block.get("macro_f1_mean")
    return float(v) if v is not None else None


def _mc_pstdev(mc: dict[str, Any], key: str) -> float | None:
    block = mc.get(key) or {}
    v = block.get("macro_f1_pstdev")
    return float(v) if v is not None else None


def decide_model_family(
    cfg: dict[str, Any],
    evidence_summary: dict[str, Any],
    failure: dict[str, Any],
    raw: dict[str, Any],
) -> dict[str, Any]:
    """
    Returns model_family_decision.json-shaped dict (without file paths).
    """
    scores: dict[str, float] = {o: 0.0 for o in OUTCOMES}
    sc = cfg.get("scoring") or {}
    iu_w = cfg.get("improve_upstream_first") or {}
    min_ev = cfg.get("minimum_evidence") or {}
    base = cfg.get("baseline_comparison") or {}
    seq_cfg = cfg.get("sequence_justification") or {}
    vis_cfg = cfg.get("vision_justification") or {}
    tab_cfg = cfg.get("tabular_only") or {}
    fold_inst = cfg.get("fold_instability") or {}

    mc = raw["model_comparison_report"]
    sym_key = base.get("symbolic_model_key", "symbolic")
    tab_key = base.get("tabular_model_key", "logistic_regression")
    sym_m = _mc_mean(mc, sym_key)
    tab_m = _mc_mean(mc, tab_key)
    tab_sd = _mc_pstdev(mc, tab_key) or 0.0

    n_folds = int((evidence_summary.get("counts") or {}).get("folds") or 0)
    n_pred = int((evidence_summary.get("counts") or {}).get("prediction_lines") or 0)
    min_folds = int(min_ev.get("min_folds_evaluated", 2))
    min_pred = int(min_ev.get("min_prediction_lines", 10))

    weak_classes = failure.get("class_level", {}).get("weak_classes_from_walkforward") or []
    n_weak = len(weak_classes)
    weak_upstream_thr = int((cfg.get("class_weakness") or {}).get("weak_class_count_upstream_trigger", 5))

    delta = (tab_m - sym_m) if (tab_m is not None and sym_m is not None) else None
    beat_delta = float(base.get("material_beat_min_delta_macro_f1", 0.05))
    stable_max = float(base.get("stable_macro_f1_pstdev_max", 0.15))

    tab_beats = delta is not None and delta >= beat_delta
    stable = tab_sd <= stable_max or n_folds <= 1

    if n_folds < min_folds:
        scores["improve_upstream_first"] += float(iu_w.get("insufficient_folds_weight", 6))
    if n_pred < min_pred:
        scores["improve_upstream_first"] += float(iu_w.get("tiny_dataset_weight", 4))

    if failure.get("calibration_level", {}).get("drift_flag"):
        scores["improve_upstream_first"] += float(iu_w.get("calibration_drift_weight", 4))

    if n_weak >= weak_upstream_thr:
        scores["improve_upstream_first"] += float(iu_w.get("many_weak_classes_weight", 3))

    low_sup = failure.get("class_level", {}).get("low_support_class_labels") or []
    if low_sup:
        scores["improve_upstream_first"] += float(iu_w.get("low_class_support_weight", 3))

    f1_range = float(failure.get("fold_level", {}).get("macro_f1_range") or 0)
    if f1_range >= float(fold_inst.get("macro_f1_range_upstream_trigger", 0.5)) and n_folds > 1:
        scores["improve_upstream_first"] += float(iu_w.get("fold_instability_weight", 3))

    if failure.get("policy_level", {}).get("policies_likely_low_utility"):
        scores["improve_upstream_first"] += float(iu_w.get("policy_useless_weight", 2))

    if failure.get("representation_hints", {}).get("feature_quality_concern"):
        scores["improve_upstream_first"] += float(iu_w.get("feature_quality_concern_weight", 3))
    if failure.get("representation_hints", {}).get("label_manifest_concern"):
        scores["improve_upstream_first"] += float(iu_w.get("label_manifest_concern_weight", 2))

    rh = failure.get("representation_hints") or {}
    tf_spread = float((rh.get("aggregate_dimension_accuracy_spreads") or {}).get("timeframe") or 0)
    sess_spread = float((rh.get("aggregate_dimension_accuracy_spreads") or {}).get("session") or 0)

    seq_min_folds = int(seq_cfg.get("min_folds", 3))
    seq_tf = float(seq_cfg.get("timeframe_accuracy_spread_min", 0.18))
    seq_sess = float(seq_cfg.get("session_accuracy_spread_min", 0.15))
    seq_need_weak = int(seq_cfg.get("min_weak_classes_for_temporal_hypothesis", 2))
    seq_tab_beats = bool(seq_cfg.get("tabular_must_beat_symbolic", True))

    sequence_signal = (
        n_folds >= seq_min_folds
        and (tf_spread >= seq_tf or sess_spread >= seq_sess or n_weak >= seq_need_weak)
        and (tab_beats or not seq_tab_beats)
        and stable
    )
    if sequence_signal:
        bonus = float(sc.get("sequence_temporal_spread_bonus", 4))
        if tf_spread >= seq_tf or sess_spread >= seq_sess:
            scores["sequence_model_next"] += bonus
        if n_weak >= seq_need_weak:
            scores["sequence_model_next"] += float(sc.get("sequence_weak_class_bonus", 2))

    vis_min_folds = int(vis_cfg.get("min_folds", 5))
    vis_tf = float(vis_cfg.get("timeframe_accuracy_spread_min", 0.35))
    vis_sess = float(vis_cfg.get("session_accuracy_spread_min", 0.30))
    chart_ok = bool(rh.get("chart_geometry_hypothesis"))
    vision_gates = (
        n_folds >= vis_min_folds
        and tf_spread >= vis_tf
        and sess_spread >= vis_sess
        and chart_ok
        and bool(vis_cfg.get("require_chart_geometry_hypothesis", True))
    )
    if vision_gates:
        scores["vision_model_next"] += float(sc.get("vision_gate_bonus", 8))

    max_weak_tab = int(tab_cfg.get("max_weak_classes", 2))
    min_tab_f1 = float(tab_cfg.get("min_mean_tabular_macro_f1", 0.55))
    if tab_m is not None and tab_m >= min_tab_f1 and n_weak <= max_weak_tab and stable and tab_beats:
        scores["tabular_only_for_now"] += float(sc.get("tabular_stable_beat_bonus", 5))
        scores["tabular_only_for_now"] += float(sc.get("tabular_low_weak_bonus", 2))

    tie = cfg.get("tie_break_order") or list(OUTCOMES)
    best = max(scores.values())
    candidates = [o for o, s in scores.items() if s == best]
    chosen = candidates[0]
    if len(candidates) > 1:
        for o in tie:
            if o in candidates:
                chosen = o
                break

    # Vision is last resort: never win if gates failed or sequence scores at least as high.
    if chosen == "vision_model_next":
        if not vision_gates:
            chosen = "improve_upstream_first"
        elif scores["sequence_model_next"] >= scores["vision_model_next"] and sequence_signal:
            chosen = "sequence_model_next"

    bottleneck = _dominant_bottleneck(failure, chosen)
    rejected = _rejected_directions(chosen, scores, sequence_signal, vision_gates)

    report_answers = {
        "tabular_beat_symbolic_materially": tab_beats and delta is not None,
        "delta_macro_f1_tab_minus_sym": delta,
        "gain_stable_across_folds": stable,
        "weak_classes": weak_classes,
        "calibration_usable_forward": not failure.get("calibration_level", {}).get("drift_flag"),
        "failures_concentrated_note": _concentration_note(failure),
        "dominant_next_bottleneck": bottleneck,
        "recommended_step10_direction": chosen,
        "non_recommended_directions": rejected,
        "next_experiment_summary": _next_experiment_line(chosen, bottleneck),
    }

    return {
        "model_family_decision_id": "model_family_decision_v1",
        "task_id": cfg.get("task_id"),
        "outcome": chosen,
        "scores": scores,
        "rationale": {
            "decision_report_answers": report_answers,
            "pit_declaration": cfg.get("pit_declaration", ""),
            "no_go_policy": cfg.get("no_go"),
        },
    }


def _concentration_note(failure: dict[str, Any]) -> str:
    sp = failure.get("representation_hints", {}).get("aggregate_dimension_accuracy_spreads") or {}
    if float(sp.get("timeframe", 0)) > 0 or float(sp.get("session", 0)) > 0:
        return "Some concentration risk across timeframe/session buckets (see failure_mode_report)."
    return "No strong concentration signal in aggregate dimensions; see fold-level metrics."


def _dominant_bottleneck(failure: dict[str, Any], outcome: str) -> str:
    if outcome == "improve_upstream_first":
        if failure.get("calibration_level", {}).get("drift_flag"):
            return "calibration_stability"
        if failure.get("class_level", {}).get("low_support_class_labels"):
            return "data_volume_or_class_support"
        if failure.get("representation_hints", {}).get("label_manifest_concern"):
            return "labels"
        if failure.get("representation_hints", {}).get("feature_quality_concern"):
            return "features"
        return "data_volume_or_evaluation_conditions"
    if outcome == "sequence_model_next":
        return "temporal_modeling"
    if outcome == "vision_model_next":
        return "visual_representation"
    return "none_dominant_tabular_adequate"


def _rejected_directions(
    chosen: str,
    scores: dict[str, float],
    had_sequence_signal: bool,
    had_vision_gates: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for o, s in scores.items():
        if o == chosen:
            continue
        reason = f"score={s} below winning outcome"
        if o == "vision_model_next" and not had_vision_gates:
            reason = "vision gates not satisfied (high bar: chart geometry + spreads + folds)"
        if o == "sequence_model_next" and not had_sequence_signal:
            reason = "sequence justification thresholds not met"
        out.append({"outcome": o, "reason": reason})
    return out


def _next_experiment_line(chosen: str, bottleneck: str) -> str:
    if chosen == "improve_upstream_first":
        return f"Stabilize upstream layers first (bottleneck: {bottleneck})."
    if chosen == "tabular_only_for_now":
        return "Continue tabular + symbolic stack; monitor with more folds before advanced models."
    if chosen == "sequence_model_next":
        return "Implement narrow sequence baseline (see step10_architecture_brief.json)."
    return "Implement vision pilot only per brief; prove gain vs structured-price baselines."
