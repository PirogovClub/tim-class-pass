# ML Step 8 — Handoff

## Implemented

- **`src/ml/walkforward_config.yaml`** — Task id, dataset paths, inclusion policy, fold policy, models, calibration, policy thresholds, metrics, outputs, PIT declaration.
- **`src/ml/backtest/walkforward_config_loader.py`** — Validate config; CLI `python -m ml.backtest.walkforward_config_loader`.
- **`src/ml/backtest/fold_builder.py`** — Deterministic time-sorted folds; exclusion log; CLI `python -m ml.backtest.fold_builder`.
- **`src/ml/backtest/prediction_replay.py`** — Per-example replay records (`replay_id`, fold, model, probs, labels).
- **`src/ml/backtest/walkforward_runner.py`** — End-to-end walk-forward: symbolic + logistic regression (+ optional trees), calibration on val only, JSON/JSONL artifacts; CLI `python -m ml.backtest.walkforward_runner`.
- **`src/ml/backtest/policy_evaluator.py`** — Threshold and symbolic+model policies (no execution engine).
- **`src/ml/backtest/calibration_drift.py`** — Cross-fold Brier / bucket summaries.
- **`src/ml/backtest/report_builder.py`** — Aggregate reports and `step8_manifest.json`.
- **`src/ml/backtest/cli.py`** — `validate-config`, `build-folds`, `run`, `full-audit-run`.
- **Tests** — `tests/ml/test_walkforward_config.py`, `tests/ml/test_fold_builder.py`, `tests/ml/test_walkforward_runner.py`, `tests/pipeline/test_policy_evaluator.py`, `tests/ml/test_backtest_reports.py`, `tests/ml/test_calibration_drift.py`.
- **Docs** — `docs/ml_step8_walkforward_backtests.md`, `RUN_ML_STEP8_AUDIT.md`, this file.
- **Audit packaging** — `scripts/generate_ml_step8_audit_bundle.py` (bundle `source/ml/` includes `dataset_builder`, `feature_builder`, `split_builder` so shipped tests and §1 of the runbook work standalone; generator re-runs pytest from `source/` before zipping).

## Inputs expected

- Step 7 `modeling_dataset.jsonl` (and implicitly Step 6 labels + `src/ml/fixtures/market_windows` used to build it).
- `src/ml/feature_spec.yaml` for feature columns.
- `src/ml/walkforward_config.yaml`.

## Outputs produced

Under `outputs.root` (default `ml_output/step8/`): `walkforward_folds.json`, `backtest_predictions.jsonl`, `fold_metrics.json`, `walkforward_report.json`, `model_comparison_report.json`, `calibration_drift_report.json`, `policy_report.json`, `step8_manifest.json`, plus optional breakdown JSON files.

## What Step 9 should decide

- Whether richer models (sequences, retrieval fusion) are justified given forward baseline behavior.
- How to combine symbolic filters, calibrated probabilities, and RAG explanations in a **combined decision layer** (out of scope for Step 8).

## Deferred

- Live execution, brokers, order simulation beyond policy stats.
- Production monitoring, HP tuning platforms, new label ontologies.
- Broad refactors outside evaluation.

## Auditor checklist

1. Config validates; fold JSON is time-ordered; train indices precede test indices.
2. `backtest_predictions.jsonl` lines include `actual_label` and `predicted_label`.
3. Preprocessing fit only on train; calibration only on val (see fold code + PIT text).
4. Symbolic and logistic regression appear in `fold_metrics.json`.
5. `calibration_drift_report.json` and `policy_report.json` exist after a run.
6. Pytest Step 8 tests pass.
7. Audit zip contains `source/` (including Step 7 dataset-builder modules required by tests), `examples/`, `test_output.txt`, runbook + handoff; `test_output.txt` includes a passing pytest run from `source/` as auditors extract it.
