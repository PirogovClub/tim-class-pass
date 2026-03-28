# ML Step 9 — Handoff

## Implemented

- **`ml/step9_decision_config.yaml`** — Thresholds, evidence paths, scoring parameters, tie-break order, PIT text, output filenames.
- **`ml/step9/evidence_loader.py`** — Load/validate config; resolve Step 8 paths; load JSON/JSONL; build `step9_evidence_summary.json`.
- **`ml/step9/failure_mode_analysis.py`** — Class, fold, calibration, policy, support, representation hints (including optional Step 7 QA / label manifests).
- **`ml/step9/model_family_decider.py`** — Weighted scores for the four outcomes; vision safety clamp; rationale fields per spec questions.
- **`ml/step9/step10_brief_builder.py`** — Brief with scope, I/O, evaluation, acceptance, risks, deferred work; sequence/vision/upstream contracts by outcome.
- **`ml/step9/report_builder.py`** — Writes all JSON + readiness scorecard + manifest.
- **`ml/step9/cli.py`** — `validate-config`, `evidence-summary`, `failure-modes`, `decide`, `step10-brief`, `full-audit-run`.
- **Tests** — Config, evidence loader, failure modes, decider scenarios, brief builder, report/manifest consistency.
- **Docs** — `docs/ml_step9_model_family_decision.md`, `RUN_ML_STEP9_AUDIT.md`, this file.
- **Audit packaging** — `scripts/generate_ml_step9_audit_bundle.py`.

## Inputs expected

- Step 8 output directory (default `ml_output/step8_audit_sample`) containing at least:
  `walkforward_report.json`, `fold_metrics.json`, `model_comparison_report.json`, `calibration_drift_report.json`, `policy_report.json`, `backtest_predictions.jsonl`, `step8_manifest.json`.
- Optionally: `dataset_manifest.json`, `feature_quality_report.json`, `label_dataset_manifest.json` via `evidence.optional_files` in the YAML.

## Outputs produced

Under `outputs.root` (default `ml_output/step9/`): evidence summary, failure report, decision, Step 10 brief, readiness scorecard, **`regime_breakdown_report.json`**, **`class_stability_report.json`**, manifest. Config includes explicit **`no_go`** (maps to `improve_upstream_first`).

## What Step 10 should do next

| Step 9 outcome | Step 10 focus |
|----------------|---------------|
| `improve_upstream_first` | Fix labels/features/data volume/calibration; re-run Step 8 then Step 9. |
| `tabular_only_for_now` | More folds, monitoring; defer sequence/vision until evidence shifts. |
| `sequence_model_next` | Implement narrow sequence baseline per `step10_architecture_brief.json` contract. |
| `vision_model_next` | Vision pilot with mandatory proof vs structured + sequence baselines. |

## Deferred (explicit)

- Training sequence/vision models **inside** Step 9 (out of scope).
- RAG-text training, live execution, broker logic.
- Combined symbolic + RAG + model decision layer (later roadmap).

## Auditor checklist

1. `validate-config` succeeds.
2. `full-audit-run` writes all JSON files and `step9_manifest.json`.
3. `model_family_decision.json` contains `outcome` ∈ four allowed strings and `rationale.decision_report_answers`.
4. `step10_architecture_brief.json` matches outcome family.
5. Pytest Step 9 suite passes.
6. Audit zip contains `source/`, `examples/`, `test_output.txt`, runbook + handoff.
