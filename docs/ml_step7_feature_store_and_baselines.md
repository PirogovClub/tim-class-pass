# ML Step 7 — Feature store and baseline models

## Purpose

Build a **point-in-time-safe** tabular feature layer on top of **Step 6 `generated_labels.jsonl`**, materialize a **modeling dataset**, run **feature QA**, **deterministic splits**, and **baseline models** (symbolic + logistic regression + optional XGBoost) with **probability calibration**.

## Inputs

| Artifact | Use |
|----------|-----|
| `ml/feature_spec.yaml` | Source of truth for feature names, dtypes, PIT notes, modeling columns |
| `ml/label_specs.json` | Task versions (dataset manifest) |
| Step 6 `generated_labels.jsonl` | Labels, tiers, status, provenance |
| `ml/fixtures/market_windows/*.json` | OHLCV windows keyed by `candidate_id` |

## Feature families (implemented)

1. **Level relative** — `close_distance_pct`, `high_distance_pct`, `low_distance_pct`
2. **Volatility** — `atr_pct_14`, `range_pct_lookback`, `vol_regime_high`
3. **Candle structure** — body/wick ratios, `close_location_anchor`
4. **Interaction / persistence** — pre-anchor counts above/below level, persistence ratio, re-entry crossings
5. **Pre-break context** — `consolidation_width_pct`, `pre_anchor_trend_slope`
6. **Volume** — `volume_ratio_anchor`, `volume_zscore_anchor`
7. **Time** — `session_hour_bucket`, `day_of_week` from `anchor_timestamp`
8. **HTF** — `htf_alignment_placeholder` (0.0 when no HTF data)

## PIT safety

- **Observation window:** only `bars[0]` … `bars[anchor_bar_index]` inclusive.
- **Label horizon** (post-anchor bars) is used **only** by Step 6 labeling, **not** copied into feature vectors.
- Dataset manifest repeats this declaration.

## Dataset inclusion policy

Default **trainable** rows:

- `label_status == assigned`
- `confidence_tier` in **`gold` or `silver`**
- `point_in_time_safe == true`
- non-null `label`

**Weak** tier: excluded from primary training unless `dataset_builder` is run with **`--include-weak`** (used for small fixture smoke tests; document in manifest).

**Ambiguous**, **excluded**, **skipped_invalid_input**: **not** trainable; remain in joined rows for QA with `eligible_for_training: false`.

## Split policy

- Sort eligible rows by `(anchor_timestamp, candidate_id)`.
- Assign contiguous blocks: **60% train**, **20% validation**, **20% test** (adjusted for tiny N).
- Deterministic given fixed input order.
- See `split_manifest.json`.

## Symbolic baseline

`ml/baselines/symbolic_baseline.py` applies depth-1 thresholds on PIT features (not a second label generator). Used as an explainable floor vs learned models.

## Tabular baselines

- **Logistic regression** (scaled numeric + one-hot categoricals).
- **XGBoost** if import succeeds and enough rows.
- **Calibration:** `CalibratedClassifierCV` Platt (`sigmoid`) **prefit** on validation split when validation has ≥2 samples and ≥2 classes.

## Outputs (under `ml_output/step7/` by default)

- `feature_rows.jsonl` — `candidate_id` + `features`
- `modeling_dataset.jsonl` — full schema rows + `eligible_for_training` + `split`
- `dataset_manifest.json`, `split_manifest.json`
- `feature_quality_report.json`
- `baseline_symbolic_report.json`
- `baseline_logreg_report.json`, `coefficient_report.json`
- `baseline_xgb_or_lgbm_report.json`, `feature_importance_report.json`
- `calibration_report.json`

## Commands

```bash
python -m ml.feature_spec_loader
python -m ml.feature_builder --out ml_output/step7/feature_rows.jsonl
python -m ml.dataset_builder --labels ml_output/step6_sample/generated_labels.jsonl --include-weak
python -m ml.feature_qa
python -m ml.baselines.symbolic_baseline
python -m ml.baselines.train_tabular_baseline
```

Orchestration: `python -m ml.step7_pipeline <subcommand>`.

## Known limitations

- Small fixture sets: multiclass metrics noisy; some classes may be missing from train.
- No parquet in default path (JSONL for portability).
- No walk-forward or backtest (Step 8).
