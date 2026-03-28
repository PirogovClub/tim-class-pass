# Run ML Step 8 audit (walk-forward backtests)

## Where to run from

**Full repository:** use `tim-class-pass/` as the current working directory for all commands below.

**Extracted audit zip:** the bundle includes `source/` (code + tests), `examples/` (sample configs and artifacts), and `requirements-ml-step7-audit.txt` at the bundle root (and a copy under `source/`). Use **`source/` as cwd** so `import ml` and `tests/` paths match what pytest and the CLIs expect:

```bash
unzip ml_step8_audit_bundle_<timestamp>.zip
cd <extracted_folder>/source
pip install -r requirements-ml-step7-audit.txt
```

The snapshot ships `ml/dataset_builder.py`, `ml/feature_builder.py`, and `ml/split_builder.py` under `source/ml/` so the Step 8 test suite and the dataset-builder command in §1 work without the rest of the repo.

## Dependencies

Same as Step 7 baselines: `scikit-learn`, `numpy`, `PyYAML`; optional `xgboost` / `lightgbm` if enabled in `walkforward_config.yaml`.

```bash
pip install -r requirements-ml-step7-audit.txt
```

From an extracted bundle you can use `../requirements-ml-step7-audit.txt` if you prefer to stay one level above `source/`, or the copy at `source/requirements-ml-step7-audit.txt` after `cd source`.

(or `uv sync --group dev` in the full repo).

## 1. Prerequisite: Step 7 modeling dataset

From **repo root** or from **`source/`** (audit snapshot):

```bash
python -m ml.dataset_builder --labels tests/fixtures/step6_for_step7/generated_labels.jsonl --out-dir ml_output/step7 --include-weak
```

Or use an existing `ml_output/step7/modeling_dataset.jsonl` and set `dataset.path` in `src/ml/walkforward_config.yaml`.

**Smoke path without rebuilding:** use the bundled sample under `examples/modeling_dataset_sample.jsonl` and `examples/walkforward_config_audit_sample.yaml` — copy or point your config’s `dataset.path` and `outputs.root` at those paths if you only need to verify the walk-forward runner.

## 2. Validate walk-forward config

```bash
python -m ml.backtest.walkforward_config_loader --config src/ml/walkforward_config.yaml
```

## 3. Build folds only

```bash
python -m ml.backtest.fold_builder --config src/ml/walkforward_config.yaml
```

Writes `ml_output/step8/walkforward_folds.json` (or path from `outputs.root` in config).

## 4. Full walk-forward run (folds + train/eval + reports)

```bash
python -m ml.backtest.walkforward_runner --config src/ml/walkforward_config.yaml
```

Or chained:

```bash
python -m ml.backtest.cli full-audit-run
```

## 4b. Policy evaluation only (from existing predictions)

Requires a prior `walkforward_runner` run (writes `backtest_predictions.jsonl`).

```bash
python -m ml.backtest.cli policy-eval
```

Or: `python -m ml.backtest.artifact_reports policy-eval --config src/ml/walkforward_config.yaml`

## 4c. Regenerate aggregate reports only (no retrain)

Requires `fold_metrics.json`, `walkforward_folds.json`, `calibration_drift_report.json`, and predictions under `outputs.root`.

```bash
python -m ml.backtest.cli build-reports
```

Or: `python -m ml.backtest.artifact_reports build-reports --config src/ml/walkforward_config.yaml`

## 5. Tests

From repo root or from **`source/`** inside an extracted bundle:

```bash
python -m pytest tests/ml/test_walkforward_config.py tests/ml/test_fold_builder.py tests/ml/test_walkforward_runner.py tests/pipeline/test_policy_evaluator.py tests/ml/test_backtest_reports.py tests/ml/test_calibration_drift.py tests/ml/test_dataset_integrity.py -q
```

## 6. Inspect outputs

- `ml_output/step8/backtest_predictions.jsonl` — per-example `actual_label` / `predicted_label`
- `ml_output/step8/fold_metrics.json`
- `ml_output/step8/walkforward_report.json`
- `ml_output/step8/step8_manifest.json`

## 7. Docs

- `docs/ml_step8_walkforward_backtests.md`
- `ML_STEP8_HANDOFF.md`

## 8. Audit zip (timestamped)

```bash
python scripts/generate_ml_step8_audit_bundle.py
```

Produces `audit/ml_step8_audit_bundle_<UTC-timestamp>.zip` and a copy under `audit/archives/`.
