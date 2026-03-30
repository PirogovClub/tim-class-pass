# MDRT Implementation Plan — Section 5: Naming Conventions

## What is defined by the docs vs. proposed

| Category | Defined by docs? | Convention |
|----------|-----------------|------------|
| Python module names | ✅ Yes (`01-architecture.md`) | `snake_case.py` |
| Test file names | ✅ Yes (`09-testing.md`) | `test_*.py` |
| Fixture directories | ✅ Yes (`01-architecture.md`) | `tests/adapters/transcripts/` |
| Data partition paths | ✅ Yes (`01-architecture.md`) | `provider=ib/asset_class=equity/...` |
| Ticket IDs | ❌ Proposed | `MDRT-NNN` |
| Ticket docs | ❌ Proposed | `ticket-mdrt-NNN-short-title.md` |
| Audit bundles | ❌ Proposed | `audit-bundles/mdrt-NNN/` |

---

## Naming Rules

### 1. Ticket IDs

Format: `MDRT-NNN` (three-digit, zero-padded)

Examples:
- `MDRT-001` — Project scaffold
- `MDRT-002` — Exception hierarchy
- `MDRT-010` — IbHistoricalDataCollector
- `MDRT-012A` — Normalizer (Intraday)

Used consistently in:
- Plan references
- Ticket doc filenames
- Audit bundle folder names
- Implementation logs and commit messages

### 2. Markdown Docs

- Lowercase kebab-case
- Numbered docs use zero-padded numeric prefix
- Ticket docs: `ticket-mdrt-NNN-short-title.md`

### 3. Python Modules

- Lowercase `snake_case.py`
- Names from `01-architecture.md` directory tree exactly

### 4. Test Files

- `test_*.py` matching the module under test
- Located in `tests/unit/`, `tests/integration/`, or `tests/adapters/`

### 5. Fixtures

- Descriptive `snake_case` with provider prefix where applicable
- Located in `tests/adapters/transcripts/`
- Examples:
  - `spy_1m_2024_01_03.jsonl`
  - `spy_1D_early_close_2024_11_29.jsonl`
  - `spy_1M_2024_01.jsonl`

### 6. Audit Bundles

- Directory: `audit-bundles/mdrt-NNN/`
- Contents:
  - `summary.md` — what was done, what was tested
  - `changed-files.txt` — list of files created/modified
  - `test-results.txt` — pytest output
  - `artifacts-manifest.json` — machine-readable file list

### 7. Generated Manifests (Runtime)

- Located in `outputs/manifests/`
- Format: `ingestion_manifest_<batch_id>.json`
- Per `01-architecture.md` §Outputs

### 8. Generated Reports (Runtime)

- Located in `outputs/integrity_reports/`
- Format: `integrity_report_<timestamp>.json`
