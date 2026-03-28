# ML Step 5 — Handoff summary

## Task defined

- **task_id:** `level_interaction_rule_satisfaction_v1`
- **Type:** Multiclass classification on a **candidate level interaction window** (OHLCV + anchor level L at T0).
- **Classes (7):** `acceptance_above`, `acceptance_below`, `false_breakout_up`, `false_breakout_down`, `rejection`, `no_setup`, `ambiguous`.

## Deliverables (repo)

| Artifact | Path |
|----------|------|
| Human doc | `docs/ml_step5_task_definition.md` |
| Task spec | `ml/task_definition.yaml` |
| Window / PIT | `ml/window_contract.yaml` |
| Ontology | `ml/class_ontology.json` |
| Rule mapping | `ml/rule_to_class_mapping.json` |
| Examples | `ml/task_examples.json` (14 instances) |
| Validator | `ml/task_validator.py` |
| Tests | `tests/test_ml_task_definition.py` |
| Bad fixtures | `tests/fixtures/ml_step5_bad/*` |
| Audit runner | `scripts/generate_ml_step5_audit_bundle.py` |
| This handoff | `ML_STEP5_HANDOFF.md` |
| Audit runbook | `RUN_ML_STEP5_AUDIT.md` |

## Intentionally excluded (not Step 5)

- Full deterministic label generator (`label_generation.py` logic).
- Feature store / feature builder implementation.
- Dataset build over full corpus.
- Model training, backtest, walk-forward, live inference.
- Training on raw RAG markdown as the supervised signal.

## Step 6 should implement next

- Numeric predicates (N-bar persistence, tolerances, touch definitions) per class.
- Deterministic labeling pipeline emitting `{ class_label, confidence_tier, ambiguity_reason? }` per window.
- Enumerated `ambiguity_reason` codes aligned with ontology notes.
- Unit tests on synthetic OHLCV series for each class boundary.

## Step 7 should implement later

- Feature columns aligned to `window_contract.yaml` with provenance to rule/concept ids.
- Dataset materialization and train/val splits with PIT checks.

## Open questions

- Exact primary timeframe default per instrument class (5m vs 15m) — product decision.
- Whether higher-TF context becomes **required** in v2.

## Auditor checklist

1. Single primary `task_id` in `task_definition.yaml`.
2. Seven classes; `ambiguous` vs `no_setup` cleanly separated in ontology + examples.
3. `window_contract.yaml` contains explicit `point_in_time_safety.rules`.
4. `class_decision_order` is a permutation of `label_set` with no duplicates.
5. `python -m ml.task_validator` exits 0.
6. `pytest tests/test_ml_task_definition.py` passes.
7. Audit zip contains spec snapshots + `test_output.txt` + runbook + handoff.
