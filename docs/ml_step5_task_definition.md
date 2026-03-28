# ML roadmap Step 5 — first narrow task definition

## Purpose

This document defines **one** production-oriented machine-learning task for the trading knowledge system: **multiclass classification of level-interaction rule satisfaction** on a **point-in-time-safe** market window. Step 5 is **definition only**: no full label generator, no feature store, no model training.

The knowledge base (RAG, rule cards, concepts) informs **what** classes mean and **which** rule families map into the task; **OHLCV and the window contract** are the eventual training signal — not raw lesson prose.

## Why this task (and not PnL first)

- **Aligns with rule cards**: many rules describe behavior at levels (acceptance, failure, rejection).
- **Safer than PnL**: predicting immediate pattern satisfaction is more auditable than return prediction.
- **Narrow scope**: seven classes + explicit ambiguity vs no-setup separation.
- **PnL / signal engine** are explicitly **deferred** to later roadmap steps.

## Task ID and type

| Field | Value |
|--------|--------|
| `task_id` | `level_interaction_rule_satisfaction_v1` |
| `task_type` | `multiclass_classification` |
| `target_unit` | `candidate_level_interaction_window` |
| `status` | `defined_not_generated` |

## What is being predicted?

Given:

- A **candidate level interaction** at time **T0** with reference level **L** and approach direction (from below / above / unknown).
- **OHLCV** on a **primary** timeframe (and optional higher-TF context) from **context_before** through **decision_horizon** (see `ml/window_contract.yaml`).

Output (for Step 6 to generate deterministically):

- Exactly **one** label from the class list below.
- A **confidence tier** (`gold` / `silver` / `weak`).
- For class `ambiguous`, a non-empty **`ambiguity_reason`** code; for `no_setup`, **no** ambiguity reason.

## Class list (ontology summary)

| Class | Market-data intent (summary) |
|--------|-------------------------------|
| `acceptance_above` | Persistent establishment above **L** within horizon after approach; not a one-bar wick. |
| `acceptance_below` | Persistent establishment below **L** (mirror). |
| `false_breakout_up` | Pierce / short break above **L** then failure back below without meeting acceptance. |
| `false_breakout_down` | Mirror downward. |
| `rejection` | Clear test of **L** and move away without acceptance or false-breakout structure. |
| `no_setup` | Preconditions hold but **no** v1 pattern matches — not the same as “unknown”. |
| `ambiguous` | **Withhold** deterministic label: multiple classes plausible, bad anchor, insufficient bars, or excess noise — **not** a catch-all for “hard”. |

Full definitions, positive/negative conditions, and allowed confidence tiers per class are in **`ml/class_ontology.json`**.

## Preconditions and exclusions

- Preconditions: valid anchor **L** and **T0**, required bars present, fixed instrument/session — see **`ml/task_definition.yaml`**.
- Exclusions: undefined level, missing OHLCV, narrative-only windows, and rule families listed in **`ml/rule_to_class_mapping.json`** (`excluded_rule_families`).

## Ambiguity vs `no_setup`

- **`no_setup`**: “We see the data; no defined pattern applies.”
- **`ambiguous`**: “We should not assign a single class” — document **why** (`MULTIPLE_PLAUSIBLE`, `ANCHOR_UNCLEAR`, `INSUFFICIENT_BARS`, `EXCESSIVE_NOISE`, etc. in Step 6).

`ambiguous` **must not** use confidence tier **`gold`** (see ontology).

## Label confidence tiers (for future generated labels)

| Tier | Meaning |
|------|--------|
| **gold** | Deterministic from bars + clear anchor + clear class boundary; no conflicting mapping evidence. |
| **silver** | Mostly deterministic; at most one documented heuristic from Step 6. |
| **weak** | Heuristic / partial; weak supervision or analysis, not primary high-trust training. |

## Class decision order (conflict resolution)

When multiple pattern definitions could apply, **first match in this list wins** (see `ml/task_definition.yaml`):

1. `ambiguous`  
2. `false_breakout_up`  
3. `false_breakout_down`  
4. `acceptance_above`  
5. `acceptance_below`  
6. `rejection`  
7. `no_setup`  

**Rationale**: withhold first; then failed breaks before successful acceptance; rejection before generic “no pattern” fallback.

## Point-in-time safety

Mandatory rules (detail in **`ml/window_contract.yaml`**):

- No bar **after** the end of the labeling horizon may influence the assigned class.
- No future session outcomes, no refit normalization using future data, no human labels created after the horizon.
- RAG text does **not** substitute for OHLCV at labeling time.

## Rule-to-class mapping

**`ml/rule_to_class_mapping.json`** links **canonical concept ids** (e.g. `concept:level`, `node:breakout`) to **eligible** task classes. Mappings may be `direct`, `partial`, or `heuristic`. Many corpus rules remain **out of scope** for this `task_id`; excluded families are listed explicitly.

## Example instances

**`ml/task_examples.json`** contains **14** synthetic examples (two per class) that conform to the example schema used by the validator.

## Machine-readable sources of truth

| File | Role |
|------|------|
| `ml/task_definition.yaml` | Task metadata, label set, tiers, decision order, PIT reference |
| `ml/window_contract.yaml` | Anchors, horizons, OHLCV, PIT rules |
| `ml/class_ontology.json` | Per-class semantics |
| `ml/rule_to_class_mapping.json` | KB concepts → classes |
| `ml/task_examples.json` | Contract examples |
| `ml/task_validator.py` | Deterministic validation |

## Step 6 (next) — deterministic label generation

Should implement:

- Bar-level predicates for each class aligned with ontology text.
- `ambiguity_reason` enumeration and tests.
- Output schema: `{ task_id, window_id, class_label, confidence_tier, ambiguity_reason?, provenance }`.

## Step 7 (later) — datasets and features

Should implement:

- Feature builders respecting the same window contract and PIT rules.
- Join keys to `linked_rule_card_ids` / `linked_concept_ids` where applicable.

## Known limitations

- Numeric thresholds (N closes, tolerances) are intentionally left to Step 6.
- Optional higher-TF context is not required in v1.
- Only one primary `task_id` is defined; additional tasks are out of scope.

## Validation

```bash
python -m ml.task_validator
python -m pytest tests/test_ml_task_definition.py -q
```

## Related repo components

- **`pipeline.component2.ml_prep`**: labeling manifests and ML-prep helpers (Task 13); this Step 5 contract **complements** that layer with a **narrow bar-based task** definition, not a duplicate manifest format.
