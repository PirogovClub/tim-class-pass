# ML Step 6 — Deterministic label generation

## Purpose

Turn the Step 5 contract (`level_interaction_rule_satisfaction_v1`) into **executable**, **point-in-time-safe** multiclass labels from structured OHLCV windows. This step does **not** train models or build a feature store.

## Inputs (source of truth)

| Artifact | Role |
|----------|------|
| `ml/task_definition.yaml` | `task_id`, `label_set`, `class_decision_order`, confidence tier meanings, ambiguity policy |
| `ml/window_contract.yaml` | Max forward bars (48), min context bars, PIT rules |
| `ml/class_ontology.json` | Class semantics (documentation + allowed tiers) |
| `ml/rule_to_class_mapping.json` | Concept → class hints, excluded rule families |
| `ml/task_examples.json` | Loaded and validated during compile; digest embedded in `label_specs.json` |
| `ml/label_specs.json` | **Compiled** runtime spec (via `label_spec_compiler`) |

## Candidate market window (JSON)

Each fixture / adapter payload includes at minimum:

- `candidate_id`, `anchor_timestamp`, `timeframe`, `reference_level`, `approach_direction` (`from_below` \| `from_above` \| `unknown`)
- `anchor_bar_index` into `bars` (0-based, ascending time)
- `bars[]` with `t` (ISO UTC), `open`, `high`, `low`, `close`, `volume`
- Optional: `tick_size`, `linked_concept_ids`, `bars_after_anchor_within_allowed_horizon`, `bars_before_anchor` (must equal `anchor_bar_index` when present), `rule_family_hint`, `source_metadata` (e.g. `lesson_id` for reporting)

Validation rejects missing level, non-monotonic timestamps, forward length beyond `max_forward_bars`, and optional `forbidden_future_leak`.

## Compiled label spec

`python -m ml.label_spec_compiler` writes `ml/label_specs.json` containing:

- Versions / ids for task, window contract, ontology, mapping
- `class_decision_order` (permutation of `label_set`, **not** redefined in code)
- Numeric thresholds: persistence closes, max forward bars, `level_relative_epsilon`, `chop_close_band_relative`, etc.

## Decision order (enforced)

Matches `task_definition.yaml`:

1. `ambiguous` — only when explicit ambiguity codes fire (e.g. `MULTIPLE_PLAUSIBLE`, `APPROACH_CONFLICT`, or `force_ambiguity_reason` on a window for tests)
2. `false_breakout_up` / `false_breakout_down` — pierce then failed continuation, **without** a completed acceptance streak in the same direction
3. `acceptance_above` / `acceptance_below` — consecutive closes beyond level ± ε (approach direction gates which side applies)
4. `rejection` — level touched, no acceptance / false-breakout patterns, not “chop only”
5. `no_setup` — valid task window but no catalog pattern (tight close band around level)
6. Implicit fallback: `no_setup` if nothing else matched

`decision_order_path` on each output row records the evaluation trace.

## Class logic (executable summary)

- **ε (pattern band):** `max(tick_size × ticks, L × level_relative_epsilon)` from `label_specs.json`.
- **Acceptance:** `N` consecutive closes above `L+ε` (below `L−ε`) within the forward window.
- **False breakout:** pierce via wick (`high` / `low`) beyond `L±ε`, then `M` consecutive closes on the failed side; suppressed if acceptance in that direction already holds.
- **Chop / no_setup:** all forward closes satisfy `|close − L| ≤ L × chop_close_band_relative`.

Full trading nuance remains intentionally simplified; behavior is **deterministic**, **documented**, and **test-backed**.

## Confidence tiers (encoded)

| Tier | Rules (v1) |
|------|------------|
| `gold` | Assigned non-ambiguous; known approach; `tick_size` present; forward bars ≥ 10 after anchor |
| `silver` | Assigned non-ambiguous with `approach_direction == unknown` |
| `weak` | Excluded / skipped rows; ambiguous default (`weak_ambiguity` window flag forces weak); forward &lt; 10 bars; or `borderline_geometry` |

`ambiguous` is never `gold` (ontology + validator).

## Point-in-time safety

- Labeling uses only bars from `anchor_bar_index + 1` through `anchor + max_forward_bars` (capped by array length).
- Validator rejects more forward bars than the contract allows.
- `point_in_time_safe` is `false` when `simulate_pit_violation` is set on a window (audit demo) or when validation marks leakage flags.
- `invalidation_hits` may include `pit_001` when PIT is false on an otherwise assigned row.

## Outputs

Running:

```bash
python -m ml.label_generation --out-dir ml_output/step6_sample
```

produces:

- `generated_labels.jsonl` — one JSON object per window
- `label_generation_report.json` — counts by class, tier, status
- `label_dataset_manifest.json` — task id, spec versions, generator version, distributions, PIT declaration

Schema: `ml/generated_labels.schema.json`. Row validation: `ml/label_output_validator.py` (logic checks plus optional `jsonschema` Draft7 validation via `validate_row_against_json_schema`, dev dependency).

`label_generation_report.json` includes `counts_by_lesson_id` and `counts_by_rule_family_hint` when those fields appear under `metadata.source` on rows.

## Known limitations

- Higher timeframe context is not used in v1 predicates.
- Numeric thresholds are a first cut vs full microstructure rules from production.
- `rule_family_hint` exclusion uses `excluded_rule_families` from the mapping file only.

## Commands

```bash
python -m ml.label_spec_compiler
python -m ml.label_generation --out-dir ml_output/step6_sample
python -m pytest tests/test_label_specs.py tests/test_label_generation.py -q
```

See `RUN_ML_STEP6_AUDIT.md` for audit packaging.
