# Run ML roadmap Step 7 audit

Two contexts:

1. **Full repository** — you have the whole `tim-class-pass` tree (default paths under `ml_output/`).
2. **Audit bundle zip** — you extracted `audit/ml_step7_audit_bundle_<timestamp>.zip`. The layout is:

   ```text
   ml_step7_audit_bundle_<timestamp>/
     requirements-ml-step7-audit.txt   # pip install -r this first
     RUN_ML_STEP7_AUDIT.md             # this file
     examples/                         # Step 6 label trio + Step 7 sample outputs
       generated_labels.jsonl
       label_generation_report.json
       label_dataset_manifest.json
       … (feature_rows, modeling_dataset, reports)
     source/
       ml/                             # Step 6 + Step 7 modules (including label_generation.py)
       tests/                          # pytest + fixtures/step6_for_step7 (same labels as examples/)
       scripts/
       docs/
   ```

The bundle is intended to be **re-runnable without the rest of the repo**: `source/ml` includes Step 6 generators, `examples/` includes the Step 6 artifacts Step 7 consumes, and tests use `tests/fixtures/step6_for_step7/` (same files).

---

## Dependencies

```bash
pip install -r requirements-ml-step7-audit.txt
```

From **inside the extracted bundle directory** (where `requirements-ml-step7-audit.txt` lives).  
In the **full repo**, you can use `uv sync --group dev` or install `scikit-learn`, `PyYAML`, `xgboost`, and `lightgbm` as needed.

---

## Working directory

- **Full repo:** run everything from repository root `tim-class-pass/`.
- **Bundle:** run commands from `source/` so that `import ml` resolves (`cd source`).

---

## 1. Validate feature spec

```bash
python -m ml.feature_spec_loader
```

---

## 2. Step 6 labels

**Option A — regenerate (bundle includes Step 6 code):**

```bash
python -m ml.label_generation --out-dir ../examples/step6_regen_out
```

Then point Step 7 at `../examples/step6_regen_out/generated_labels.jsonl`, or copy outputs over `examples/generated_labels.jsonl` if you want to compare.

**Option B — use bundled Step 6 artifacts (no regeneration):**

Use paths:

- `examples/generated_labels.jsonl`
- (sidecars `label_generation_report.json`, `label_dataset_manifest.json` are beside it for integrity checks)

From **`source/`**:

```text
../examples/generated_labels.jsonl
```

---

## 3. Build features and modeling dataset

From **`source/`**:

```bash
python -m ml.feature_builder --out ../examples/feature_rows_rerun.jsonl
python -m ml.dataset_builder --labels ../examples/generated_labels.jsonl --out-dir ../examples/step7_rerun --include-weak
```

In the **full repo**, defaults are fine, e.g.:

```bash
python -m ml.feature_builder --out ml_output/step7/feature_rows.jsonl
python -m ml.dataset_builder --labels ml_output/step6_sample/generated_labels.jsonl --include-weak
```

Omit `--include-weak` for strict gold+silver-only training (may yield few trainable rows on fixtures).

---

## 4. Feature QA

```bash
python -m ml.feature_qa --dataset ../examples/step7_rerun/modeling_dataset.jsonl --out ../examples/step7_rerun/feature_quality_report.json
```

(full repo: omit paths to use `ml_output/step7/` defaults where applicable.)

---

## 5. Baselines

```bash
python -m ml.baselines.symbolic_baseline --dataset ../examples/step7_rerun/modeling_dataset.jsonl --out ../examples/step7_rerun/baseline_symbolic_report.json
python -m ml.baselines.train_tabular_baseline --dataset ../examples/step7_rerun/modeling_dataset.jsonl --out-dir ../examples/step7_rerun
```

---

## 6. Tests

From **`source/`**:

```bash
python -m pytest tests/test_feature_spec.py tests/test_feature_builder.py tests/test_dataset_builder.py tests/test_baselines.py -q
```

These tests use **committed** `tests/fixtures/step6_for_step7/*` (shipped in the bundle); they do not depend on `ml_output/step6_sample` for the core path.

---

## 7. Docs

- `docs/ml_step7_feature_store_and_baselines.md` (under `source/docs/` in the bundle)
- `ML_STEP7_HANDOFF.md` (bundle root)

---

## 8. Regenerate audit zip (full repo only)

```bash
python scripts/generate_ml_step7_audit_bundle.py
```

Produces `audit/ml_step7_audit_bundle_<UTC-timestamp>.zip` and a copy under `audit/archives/`. Exits non-zero if any pipeline step fails.

---

## If something is missing

If `python -m ml.label_generation` fails, confirm you are using **`source/`** from the extracted bundle and that `source/ml/label_generation.py` exists. If tests fail on missing fixtures, confirm `source/tests/fixtures/step6_for_step7/generated_labels.jsonl` is present (it is part of the intended bundle contents).
