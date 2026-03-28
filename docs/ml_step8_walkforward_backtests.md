# ML Step 8 — Walk-forward backtests

## Purpose

Step 8 evaluates Step 7 **modeling datasets** and **baselines** under **forward-looking, time-ordered** conditions. The goal is to see whether symbolic and statistical baselines generalize forward in time, stay reasonably calibrated, and how simple threshold policies behave—without building a live trading stack.

## Why walk-forward (not a single random split)

A single static train/validation/test split can look good by accident. Walk-forward repeatedly:

1. Trains on the earliest slice of the timeline.
2. Optionally calibrates on a middle slice.
3. Evaluates on the next unseen forward slice.
4. Advances the window and repeats.

This matches how models would be used in production: fit on the past, score the future.

## Inclusion policy

Configured in `src/ml/walkforward_config.yaml` under `inclusion`:

- **Primary evaluation pool:** rows with `eligible_for_training: true`, tiers in `confidence_tiers_primary` (default gold + silver), and `label_status` not in `exclude_label_status` (ambiguous, excluded, skipped invalid).
- **Weak tier:** optional sensitivity track via `include_weak_sensitivity_track` (default false for primary scores).
- Exclusions are counted in `walkforward_folds.json` → `exclusion_log`.

## Fold policy

Mode `expanding_absorb_val_into_train` (see config):

- Rows are sorted by `(anchor_timestamp, candidate_id)`.
- Each fold uses **train** `[0 : val_start)`, **validation** `[val_start : test_start)`, **test** `[test_start : test_end)`.
- The next fold moves the validation/test window forward; training **absorbs** the previous validation interval (expanding train), so evaluation remains forward-looking.

Parameters: `min_train_rows`, `min_val_rows`, `test_window_rows`, `max_folds`, optional skip when too few classes in train.

## Models evaluated

- **Symbolic:** `ml.baselines.symbolic_baseline.symbolic_predict` on test rows (no training).
- **Logistic regression:** features from `feature_spec.yaml`; scaler + one-hot fit **only on train**; optional Platt calibration on **validation** only; metrics on **test**.
- **XGBoost / LightGBM:** optional (default off in config to keep CI fast); enable in YAML when native libs are available.

## Calibration policy

- If validation has enough rows and at least two classes, `CalibratedClassifierCV(..., cv="prefit")` is fit on validation and applied to test probabilities.
- Otherwise calibration is skipped and documented in fold outputs.
- `calibration_drift_report.json` summarizes Brier scores and bucket summaries **across folds** for drift heuristics.

## Policy evaluation

`policy_evaluator.evaluate_policies` runs **fixed** thresholds from config (no tuning on test):

- Top predicted class.
- Abstain if max probability &lt; τ for several τ.
- Combined: symbolic top class must agree with model top class **and** max prob ≥ threshold.

Results are aggregated in `policy_report.json`.

## Outputs (under `ml_output/step8/` by default)

| Artifact | Role |
|----------|------|
| `walkforward_folds.json` | Fold definitions, counts, exclusion log |
| `backtest_predictions.jsonl` | Per-example replay (all models × test rows × folds) |
| `fold_metrics.json` | Per-fold metrics per model |
| `walkforward_report.json` | Narrative answers (best model, stability, limitations) |
| `model_comparison_report.json` | Aggregated comparison |
| `calibration_drift_report.json` | Forward calibration drift |
| `policy_report.json` | Policy / threshold summary |
| `step8_manifest.json` | Paths and counts |
| `threshold_sweep_report.json`, `per_class_fold_metrics.json`, `confusion_matrices.json` | Extra breakdowns |

## Point-in-time safety

Documented in config `pit_declaration` and repeated in manifests: preprocessing and calibration never use test labels or features for fitting; folds are strictly time-ordered; policy thresholds are not optimized on test.

## Known limitations

- Fixture-scale corpora yield few folds and unstable macro-F1 variance.
- Tree models are optional and may be disabled in default config.
- Policy layer is analytical only—not execution or brokerage.

## Commands

See `RUN_ML_STEP8_AUDIT.md` for exact commands (validate config, build folds, run runner, tests, audit zip).
