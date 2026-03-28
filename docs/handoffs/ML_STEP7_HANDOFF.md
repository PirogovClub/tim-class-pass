# ML Step 7 — Handoff

## Implemented

- **`ml/feature_spec.yaml`** — 21 features, `modeling_feature_columns`, PIT observation window.
- **`ml/feature_spec_loader.py`** — CLI validation.
- **`ml/feature_builder.py`** — PIT-safe features from windows; CLI → `feature_rows.jsonl`.
- **`ml/dataset_builder.py`** — Joins Step 6 labels + windows + features; inclusion policy; `dataset_manifest.json`; `split_manifest.json` via split builder.
- **`ml/dataset_schema.json`** — JSON Schema draft-07 for rows.
- **`ml/feature_qa.py`** — `feature_quality_report.json`.
- **`ml/split_builder.py`** — Deterministic time-ordered splits.
- **`ml/baselines/symbolic_baseline.py`** — Heuristic baseline + report.
- **`ml/baselines/train_tabular_baseline.py`** — LogReg, optional XGBoost, calibration, reports.
- **`ml/baselines/calibration.py`**, **`evaluate_tabular_baseline.py`** — Metrics helpers.
- **`ml/step7_pipeline.py`** — Subcommand dispatcher.
- **Tests** — `tests/test_feature_spec.py`, `test_feature_builder.py`, `test_dataset_builder.py`, `test_baselines.py`.

## Inputs

- Step 6 `generated_labels.jsonl`
- `ml/fixtures/market_windows/*.json` (same `candidate_id` as labels)

## Outputs

See `docs/ml_step7_feature_store_and_baselines.md` and `ml_output/step7/` after running the pipeline.

## Step 8 (next)

- Walk-forward / backtest harness.
- Live or batch scoring API.
- Richer feature store backend (parquet warehouse, partitions).

## Deferred

- Production MLOps, HP tuning platform, deep sequence / vision models.
- Training on RAG text.

## Audit bundle (reproducibility)

The timestamped zip from `scripts/generate_ml_step7_audit_bundle.py` includes:

- **Step 6** — `ml/label_generation.py` and its dependency modules under `source/ml/`, plus `class_ontology.json`, `rule_to_class_mapping.json`, `task_examples.json` for spec recompilation.
- **Step 6 label inputs** — `examples/generated_labels.jsonl` with `label_generation_report.json` and `label_dataset_manifest.json` (same files under `source/tests/fixtures/step6_for_step7/` for pytest).
- **Step 7** — feature/dataset/QA/baseline modules, `market_windows` fixtures, docs, `requirements-ml-step7-audit.txt`, and `RUN_ML_STEP7_AUDIT.md` (paths for full repo vs extracted bundle).

## Auditor checklist

1. `feature_spec.yaml` loads (`python -m ml.feature_spec_loader`).
2. Features use **only** pre-anchor bars (see spec `observation_window`).
3. `modeling_dataset.jsonl` rows include `eligible_for_training` and correct policy.
4. `split_manifest.json` matches eligible split counts.
5. `feature_quality_report.json` exists and row counts match.
6. Symbolic + logreg + calibration JSON reports exist under `ml_output/step7/` (or `examples/step7_rerun/` when following the bundle runbook).
7. Pytest Step 7 tests pass (from `source/` in the bundle; core tests use committed fixtures, not `ml_output/`).
8. Audit zip produced with `test_output.txt` and `examples/`.
