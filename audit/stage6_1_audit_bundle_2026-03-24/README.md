# Stage 6.1 audit bundle (2026-03-24)

Frozen lesson export contract v1: schema versions, registry builder, corpus validator, tests, and example outputs.

- **Examples:** `examples/` — `schema_versions.json`, `lesson_registry.json`, `validator_report.json`, `lesson_contract_v1.md`
- **Contract doc (canonical):** `../pipeline/contracts/lesson_contract_v1.md` in the repo, copied under `examples/` here
- **Source mirror:** `source/` — snapshot of relevant Python, tests, and `pyproject.toml`
- **Handoff:** `AUDIT_HANDOFF.md`, `RUN_AUDIT_TESTS.md`, `test_output.txt`, `changed_files.txt`

Example corpus used for `lesson_registry.json` / validator report: `tests/fixtures/lesson_minimal` laid out as `corpus/lesson_minimal/output_intermediate/*.json` (see `tests/contracts/conftest.py`).

Final zip: `audit/archives/stage6_1_audit_bundle_2026-03-24.zip`
