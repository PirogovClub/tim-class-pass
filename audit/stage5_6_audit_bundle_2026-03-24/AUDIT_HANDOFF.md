# Stage 5.6 — Reviewed corpus export — audit handoff

## 1. What was implemented

- **Export modules** under `pipeline/adjudication/`: `export_enums.py`, `export_policy.py`, `export_models.py`, `export_service.py`, `export_validation.py`, `export_cli.py`, `export_docs.md`.
- **Repository**: `list_all_materialized_tiers`, `list_canonical_families_by_status` for read-only bulk export.
- **Gold / Silver JSONL** bundles (`gold_*.jsonl`, `silver_*.jsonl`) plus **`export_manifest.json`** with counts, inclusion rules, exclusion categories, DB summaries.
- **Eval subsets**: `eval_retrieval_rules.jsonl`, `eval_duplicate_pairs.jsonl`, `eval_evidence_support.jsonl`, `eval_canonical_assignments.jsonl` (derived from gold rows).
- **CLI**: `python -m pipeline.adjudication.export_cli` with `export` and `validate` subcommands; console script `adjudication-export` in `pyproject.toml`.
- **Tests**: `tests/adjudication_api/test_export_stage56.py` (gold/silver separation, manifest counts, validation pass/fail, reproducibility, eval structure, canonical families).
- **Sample generator**: `scripts/generate_stage56_audit_examples.py` → `examples/` in this bundle.

## 2. Definition of done checklist

- [x] Gold export stable schema (`export.v1` + documented row fields)
- [x] Silver export separated (distinct files; validation checks tier + non-overlap)
- [x] Manifest metadata present (`export_manifest.json`)
- [x] Validation scripts passed (`export_validation.py` + CLI `validate`)
- [x] Reproducibility checked (`normalize_export_for_repro_compare` test)
- [x] Tests run (`pytest tests/adjudication_api/` — see `test_output.txt`)
- [x] Export run + validation run on sample (`examples/`, `validation_sample_output.txt`)
- [x] Audit zip created (`../archives/stage5_6_audit_bundle_2026-03-24.zip`)

## 3. Commands run

```text
python -m pytest tests/adjudication_api/test_export_stage56.py -v
python -m pytest tests/adjudication_api/ -q
python scripts/generate_stage56_audit_examples.py
python -m pipeline.adjudication.export_cli validate --export-dir audit/stage5_6_audit_bundle_2026-03-24/examples
```

## 4. Tests run

- Focused: `tests/adjudication_api/test_export_stage56.py` (13 tests: gold/silver, manifest, validation tiers, DB validation, strict provenance, duplicate row, broken canonical, eval consistency, reproducibility).
- Full adjudication API suite: `tests/adjudication_api/` — see `test_output.txt` (125 passed at bundle refresh).

## 5. Export files produced

See `examples/` in this bundle. Empty JSONL files (0 bytes) are intentional where no rows matched (e.g. no gold concept links in the sample DB).

## 6. Validation results

- `validation_sample_output.txt` — default validator + `--db`-equivalent call after generating `examples/` (see `scripts/generate_stage56_audit_examples.py`).
- CLI:
  - `python -m pipeline.adjudication.export_cli validate --export-dir audit/stage5_6_audit_bundle_2026-03-24/examples`
  - Optional: `--db <adjudication.sqlite>` for DB-backed reference resolution; `--strict-provenance` to require `lesson_id` on rule rows.

**Gap closure (post-audit):** `export_validation.py` now enforces uniqueness within tier files, cross-file canonical + family membership consistency, closed-world duplicate targets (without `--db`), eval subset pointer checks, and optional DB / strict-provenance modes.

**Intentional failures** (pytest only, not shipped as corrupt examples): wrong tier, duplicate row in `gold_rules.jsonl`, broken `canonical_family_id`, strict provenance without `lesson_id` — see `test_export_stage56.py`.

## 7. Reproducibility check

- `test_reproducibility_normalized`: two exports from the same DB; `normalize_export_for_repro_compare` (sorted JSONL lines + manifest without `export_timestamp`) is **byte-identical**.

## 8. Known limitations

- No explorer in default CLI path → `lesson_id` / `evidence_ref_ids` may be null (`provenance_note` set).
- Bronze / unresolved tiers are not exported.
- Canonical family rows are not read from `materialized_tier_state`; export lists **active** families with ≥1 **gold** member rule.

## 9. Deferred work

- Model training / serving / dashboards (explicitly out of scope for 5.6).
- Optional: wire explorer into CLI for full lesson/evidence provenance.

## 10. Zip location

- **Folder:** `audit/stage5_6_audit_bundle_2026-03-24/`
- **Zip:** `audit/archives/stage5_6_audit_bundle_2026-03-24.zip`
