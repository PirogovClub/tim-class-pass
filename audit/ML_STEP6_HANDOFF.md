# ML Step 6 — Handoff summary

## What was implemented

- **Spec compiler** (`ml/label_spec_compiler.py`) — loads Step 5 files plus **`task_examples.json`** (validated) into `ml/label_specs.json` (includes `task_examples_digest`).
- **Market window validation** (`ml/market_window.py`) — structure, monotonic time, context length, forward horizon, optional PIT leak flag.
- **Pattern engine** (`ml/label_rules.py`) — deterministic predicates + `class_decision_order` application.
- **Label generator** (`ml.label_generation`) — provenance, confidence tiers, exclusions (`rule_family_hint` vs `excluded_rule_families`), CLI.
- **Manifest/report** (`ml/label_manifest_builder.py`), **output validation** (`ml/label_output_validator.py`).
- **Fixtures** — `ml/fixtures/market_windows/*.json` covering all classes + invalid / PIT / tier cases.
- **Tests** — `tests/test_label_specs.py`, `tests/test_label_generation.py`.

## Task and classes

- **task_id:** `level_interaction_rule_satisfaction_v1`
- **Labels:** `acceptance_above`, `acceptance_below`, `false_breakout_up`, `false_breakout_down`, `rejection`, `no_setup`, `ambiguous`

## Inputs expected

JSON windows as documented in `docs/ml_step6_label_generation.md` and fixture files.

## Outputs

- `generated_labels.jsonl`, `label_generation_report.json`, `label_dataset_manifest.json` (per run directory).

## What Step 7 should do next

- Feature columns aligned to `window_contract.yaml` with provenance to rule/concept ids.
- Dataset materialization and train/val splits with PIT checks.
- Optional integration with real bar stores / session calendars.

## Deferred / out of scope

- Feature store, model training, backtests, live scorer, broad ingestion.

## Auditor checklist

1. `python -m ml.task_validator` exits 0.
2. `python -m ml.label_spec_compiler` produces `label_specs.json` consistent with Step 5 sources.
3. `class_decision_order` in `label_specs.json` matches `task_definition.yaml`.
4. `python -m pytest tests/test_label_specs.py tests/test_label_generation.py` passes.
5. `python -m ml.label_generation` runs on `ml/fixtures/market_windows` and writes three artifacts.
6. `no_setup` ≠ `ambiguous` in fixtures and logic.
7. Excluded / skipped rows have `exclusion_reason` and no pattern label.
8. `point_in_time_safe` and `invalidation_hits` behave as documented for PIT demo windows.
9. Audit zip from `scripts/generate_ml_step6_audit_bundle.py` contains `test_output.txt`, `examples/`, `source/`, runbook, and this handoff.
