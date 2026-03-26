# Rerun Stage 5.6 audit checks

**Assumptions:** Python 3.12+, repo root `tim-class-pass` on `PYTHONPATH` or run from repo root with `pip install -e .` so `pipeline.*` imports resolve.

## Unit / integration tests

```bash
cd /path/to/tim-class-pass
python -m pytest tests/adjudication_api/test_export_stage56.py -v --tb=short
python -m pytest tests/adjudication_api/ -q
```

## Regenerate example exports

```bash
cd /path/to/tim-class-pass
python scripts/generate_stage56_audit_examples.py
```

Output: `audit/stage5_6_audit_bundle_2026-03-24/examples/*.jsonl` and `export_manifest.json`.

## Validate an export directory

```bash
cd /path/to/tim-class-pass
python -m pipeline.adjudication.export_cli validate --export-dir audit/stage5_6_audit_bundle_2026-03-24/examples
```

With adjudication DB (stronger reference checks):

```bash
python -m pipeline.adjudication.export_cli validate --export-dir audit/stage5_6_audit_bundle_2026-03-24/examples --db path/to/adjudication.sqlite
```

Require non-empty `lesson_id` on exported rules:

```bash
python -m pipeline.adjudication.export_cli validate --export-dir DIR --strict-provenance
```

Or after `pip install -e .`:

```bash
adjudication-export validate --export-dir audit/stage5_6_audit_bundle_2026-03-24/examples
```

## Live export from your adjudication DB

Requires a **corpus JSON** (inventory allow-lists) unless you pass `--no-corpus-filter`.

Example corpus shape:

```json
{
  "rule_card_ids": ["rule:http:1"],
  "evidence_link_ids": ["ev:1"],
  "concept_link_ids": [],
  "related_rule_relation_ids": []
}
```

```bash
python -m pipeline.adjudication.export_cli export \
  --db /path/to/adjudication.sqlite \
  --output-dir /path/to/out \
  --tiers both \
  --corpus-json /path/to/corpus_index.json
```

Gold-only:

```bash
python -m pipeline.adjudication.export_cli export --db ... --output-dir ... --tiers gold --no-corpus-filter
```

**Note:** Export is read-only on the database.
