# Stage 5.6 audit bundle (2026-03-24)

Start with **AUDIT_HANDOFF.md** and **RUN_AUDIT_TESTS.md**.

| Path | Purpose |
|------|---------|
| `examples/` | Sample JSONL + `export_manifest.json` from `scripts/generate_stage56_audit_examples.py` |
| `examples/VALIDATION_NOTES.txt` | What default vs `--db` / `--strict-provenance` validation covers |
| `validation_sample_output.txt` | Validator outcome after generating examples |
| `test_output.txt` | `pytest tests/adjudication_api/` summary |
| `source/` | Copy of new/changed Python modules for inspection without full checkout |

**Zip:** `../archives/stage5_6_audit_bundle_2026-03-24.zip`
