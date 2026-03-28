# ML Step 9 — Model-family decision gate

## Purpose

Step 9 sits **after** Step 8 walk-forward evaluation. It consumes **only** approved pipeline artifacts (Step 6–8 JSON/JSONL) and answers:

- Is **tabular + symbolic** enough for now (`tabular_only_for_now`)?
- Is a **sequence** model the next justified experiment (`sequence_model_next`)?
- Is **vision** justified (`vision_model_next`) — **high bar**?
- Should the project **fix labels/features/data/evaluation first** (`improve_upstream_first`)?

This is a **decision gate**, not a research playground. Outcomes are **machine-readable** (`model_family_decision.json`) with a **Step 10 brief** (`step10_architecture_brief.json`).

## Why this step exists after Step 8

Step 8 proves how the current stack behaves under time-ordered folds. Step 9 **aggregates that evidence** with explicit thresholds from `ml/step9_decision_config.yaml` so the next direction is traceable, not anecdotal.

## Allowed decision outcomes (exact strings)

| Outcome | Meaning |
|--------|---------|
| `tabular_only_for_now` | Strong, stable tabular vs symbolic; few weak classes; advanced models not yet needed. |
| `sequence_model_next` | Temporal / shape signals in failure analysis + stable tabular lead + configured gates passed. |
| `vision_model_next` | **Rare**: strict gates (fold count, cross-bucket spreads, `chart_geometry_hypothesis`). Sequence must not clearly dominate. |
| `improve_upstream_first` | Insufficient folds/data, calibration drift, many weak classes, low support, policy useless, etc. |

## Decision criteria (source of truth)

All numeric gates live in **`ml/step9_decision_config.yaml`**. Python modules **read** those values; they do not hard-code parallel thresholds.

**Sequence vs vision:** By default, **sequence is easier to justify** than vision: vision requires `chart_geometry_hypothesis` (strict combination of feature-quality concern + high cross-timeframe/session spreads) and more folds. **Vision never wins** if its gates fail or if sequence scores at least as high with a sequence signal.

## Outputs (under `outputs.root`, default `ml_output/step9/`)

| File | Role |
|------|------|
| `step9_evidence_summary.json` | Normalized view of loaded Step 8 (and optional upstream) artifacts. |
| `failure_mode_report.json` | Class, fold, calibration, policy, support, representation hints. |
| `model_family_decision.json` | Scores, chosen outcome, rationale aligned to spec questions. |
| `step10_architecture_brief.json` | Narrow next implementation contract. |
| `advanced_model_readiness_scorecard.json` | Readiness flags + outcome scores. |
| `regime_breakdown_report.json` | Timeframe / session / tier buckets from aggregate dimensions + dispersion flags. |
| `class_stability_report.json` | Per-class F1 across folds (stable weak vs fold-specific). |
| `step9_manifest.json` | Paths to all artifacts + PIT declaration. |

`ml/step9_decision_config.yaml` includes an explicit **`no_go`** block: same real-world outcome as **`improve_upstream_first`**, with documented triggers pointing at the weighted rules.

## Point-in-time (PIT)

Step 9 must not import hidden future labels or external benchmarks. Evidence is limited to artifacts listed in config; `pit_declaration` in the YAML is copied into reports.

## Known limitations

- Sparse folds and tiny samples often yield **`improve_upstream_first`** — that is valid.
- Optional manifests (`dataset_manifest`, `feature_quality_report`, `label_dataset_manifest`) refine failure modes when present; absence does not block the run.
- Aggregate-dimension spreads are read from `aggregate_dimensions_report.json` when the Step 8 manifest path points to an existing file.

## CLI

See **`RUN_ML_STEP9_AUDIT.md`** for commands (`validate-config`, `evidence-summary`, `failure-modes`, `decide`, `step10-brief`, `full-audit-run`).
