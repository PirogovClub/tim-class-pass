"""Write Step 9 JSON artifacts and manifest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml.step9.failure_mode_analysis import build_class_stability_report, build_regime_breakdown_report


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_readiness_scorecard(
    scores: dict[str, float],
    failure: dict[str, Any],
    evidence_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "advanced_model_readiness_scorecard_id": "readiness_scorecard_v1",
        "outcome_scores": scores,
        "readiness_flags": {
            "sufficient_folds": int((evidence_summary.get("counts") or {}).get("folds") or 0) >= 2,
            "calibration_stable": not failure.get("calibration_level", {}).get("drift_flag"),
            "policy_not_all_poor": not failure.get("policy_level", {}).get("policies_likely_low_utility"),
        },
    }


def build_step9_manifest(
    cfg: dict[str, Any],
    out_dir: Path,
    written: dict[str, str],
) -> dict[str, Any]:
    return {
        "step9_manifest_id": "step9_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": cfg.get("task_id"),
        "output_dir": str(out_dir),
        "artifacts": written,
        "pit_declaration": cfg.get("pit_declaration", ""),
    }


def write_step9_bundle(
    cfg: dict[str, Any],
    repo_root: Path,
    evidence_summary: dict[str, Any],
    failure: dict[str, Any],
    decision: dict[str, Any],
    brief: dict[str, Any],
    raw: dict[str, Any],
) -> dict[str, Any]:
    root_s = str(cfg.get("outputs", {}).get("root", "ml_output/step9"))
    out_path = Path(root_s)
    out = out_path.resolve() if out_path.is_absolute() else (repo_root / root_s).resolve()
    outs = cfg.get("outputs") or {}
    paths_map = {
        "evidence_summary": out / str(outs.get("evidence_summary", "step9_evidence_summary.json")),
        "failure_mode_report": out / str(outs.get("failure_mode_report", "failure_mode_report.json")),
        "model_family_decision": out / str(outs.get("model_family_decision", "model_family_decision.json")),
        "step10_architecture_brief": out / str(outs.get("step10_architecture_brief", "step10_architecture_brief.json")),
        "readiness_scorecard": out / str(outs.get("readiness_scorecard", "advanced_model_readiness_scorecard.json")),
        "regime_breakdown_report": out / str(outs.get("regime_breakdown_report", "regime_breakdown_report.json")),
        "class_stability_report": out / str(outs.get("class_stability_report", "class_stability_report.json")),
    }
    scorecard = build_readiness_scorecard(
        decision.get("scores") or {},
        failure,
        evidence_summary,
    )
    regime = build_regime_breakdown_report(cfg, raw, failure)
    class_stab = build_class_stability_report(cfg, raw)
    write_json(paths_map["evidence_summary"], evidence_summary)
    write_json(paths_map["failure_mode_report"], failure)
    write_json(paths_map["model_family_decision"], decision)
    write_json(paths_map["step10_architecture_brief"], brief)
    write_json(paths_map["readiness_scorecard"], scorecard)
    write_json(paths_map["regime_breakdown_report"], regime)
    write_json(paths_map["class_stability_report"], class_stab)

    written = {k: str(v.resolve()) for k, v in paths_map.items()}
    manifest = build_step9_manifest(cfg, out, written)
    man_path = out / str(outs.get("step9_manifest", "step9_manifest.json"))
    write_json(man_path, manifest)
    written["step9_manifest"] = str(man_path.resolve())

    return {"output_dir": str(out), "manifest": manifest, "paths": written}
