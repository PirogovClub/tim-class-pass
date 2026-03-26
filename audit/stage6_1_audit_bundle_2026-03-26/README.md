# Stage 6.1 audit bundle (2026-03-26) — gaps closed

This bundle includes the **Stage 6.1** contract-freeze work plus **audit-gap closure**:

- **§10.2 timestamps:** cited `KnowledgeEvent` rows and visual/rule-tied `EvidenceRef` rows must have non-empty `timestamp_start` / `timestamp_end`.
- **§10.4 registry replay:** `validate_registry_v1` re-runs live lesson validation and reports `validation_status_mismatch` if the registry is stale vs disk.
- **§16 example corpus:** full `output_intermediate` layout under `examples/corpus_example/lesson_minimal/`.
- **§15 static check:** `lint_output.txt` from `python -m compileall` on `pipeline/contracts` and `tests/contracts` (no Ruff config in repo).

## Layout

| Path | Purpose |
|------|---------|
| `AUDIT_HANDOFF.md` | 11-section handoff + gap closure notes |
| `RUN_AUDIT_TESTS.md` | Exact rerun commands |
| `changed_files.txt` | Files touched for 6.1 + gap pass |
| `test_output.txt` | `pytest tests/contracts` |
| `lint_output.txt` | `compileall` (empty if clean) |
| `examples/schema_versions.json` | Frozen versions |
| `examples/lesson_registry.json` | Sample manifest |
| `examples/validator_report.json` | Corpus + registry check |
| `examples/lesson_contract_v1.md` | Contract doc copy |
| `examples/corpus_example/` | Minimal lesson tree for auditors |
| `source/` | Mirrored implementation files |

## Zip for auditors

`audit/archives/stage6_1_audit_bundle_2026-03-26.zip`
