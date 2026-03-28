# MDRT 10 — Phased Delivery Plan

## Overview

MDRT is delivered in three phases. Each phase has a clear scope, definition of done,
and a set of acceptance criteria. Do not start Phase 2 until Phase 1 is complete and verified.

---

## Phase 1 — MVP (Smallest Useful Version)

### Goal

Produce a system that can ingest real historical bars from one provider, validate them,
store them durably, and extract a single market window for downstream use.

This is the minimum required to unlock real reruns of labels, features, and walk-forward evaluation.

### Scope

| Component | Included |
|-----------|----------|
| Alpaca adapter | ✅ |
| Databento adapter | ❌ (Phase 3) |
| Raw landing layer | ✅ |
| Normalizer | ✅ |
| Validator (hard + soft checks) | ✅ |
| Parquet archive writer | ✅ |
| DuckDB catalog | ✅ |
| Single-window export (JSONL + Parquet) | ✅ |
| `ingest-bars` CLI | ✅ |
| `build-window` CLI | ✅ |
| `list-symbols` CLI | ✅ |
| `validate-archive` CLI | ✅ (basic) |
| Unit + integration tests | ✅ |
| Alpaca adapter tests (cassettes) | ✅ |
| `.env.example`, `.gitignore` | ✅ |
| `pyproject.toml` with all deps | ✅ |

### Files Produced

```
data/archive/provider=alpaca/asset_class=equity/symbol=SPY/timeframe=1m/year=2024/month=1/
data/raw/provider=alpaca/symbol=SPY/batch_id=<uuid>/page_0000.json.gz
data/catalog.duckdb
outputs/manifests/ingestion_manifest_<batch_id>.json
outputs/windows/SPY_1m_<anchor>.jsonl
```

### Definition of Done — Phase 1

- [ ] `mdrt ingest-bars --provider alpaca --symbol SPY --timeframe 1m --start 2024-01-02 --end 2024-01-05` runs to completion
- [ ] Parquet files written in correct partition path; schema matches `NORMALIZED_BAR_SCHEMA`
- [ ] `catalog.duckdb` contains correct rows in all 4 catalog tables
- [ ] Raw landing `.json.gz` file exists
- [ ] `mdrt list-symbols` shows SPY with correct date range and row count
- [ ] `mdrt validate-archive --symbol SPY` exits 0 and writes integrity report
- [ ] `mdrt build-window --symbol SPY --timeframe 1m --anchor <ts> --bars-before 60 --bars-after 20` produces JSONL with exactly 82 bars
- [ ] Injecting corrupt data → correct exception raised; batch marked `failed` in catalog
- [ ] Full pytest suite passes: `pytest --cov=src/market_data` with ≥ 85% coverage
- [ ] No API keys in any committed file

---

## Phase 2 — Batch Windowing & Integrity

### Goal

Make the archive production-grade with batch window export, replayable manifests,
and comprehensive integrity reporting.

### Scope

| Component | Included |
|-----------|----------|
| `build-window-batch` CLI | ✅ |
| Batch manifest JSONL input format | ✅ |
| `BatchWindowOrchestrator` (parallel) | ✅ |
| `show-integrity-report` CLI | ✅ |
| Enhanced `validate-archive` (gap detection across sessions) | ✅ |
| Symbol list ingestion (multiple symbols in one run) | ✅ |
| Multi-page adapter pagination (for large date ranges) | ✅ |
| `window_log` catalog table (already in DDL) | ✅ |

### Definition of Done — Phase 2

- [ ] `mdrt build-window-batch --manifest windows.jsonl` processes all requests and writes one file per window
- [ ] Batch summary JSON written with success/failure counts
- [ ] Parallel execution verified (4 workers used by default)
- [ ] `mdrt show-integrity-report` renders a human-readable table
- [ ] All Phase 1 tests still pass

---

## Phase 3 — Richer Metadata

### Goal

Expand provider coverage and add production-quality metadata handling for research-grade use.

### Scope

| Component | Included |
|-----------|----------|
| Databento adapter | ✅ |
| Multi-timeframe support in one ingest run | ✅ |
| Session metadata (`session_code`: R/P/A) | ✅ |
| Corporate action flag field (no adjustment logic yet) | ✅ |
| Futures symbology normalization | ✅ |
| `asset_class=future` end-to-end support | ✅ |

### Definition of Done — Phase 3

- [ ] `mdrt ingest-bars --provider databento --symbol ES.FUT --timeframe 1m --start ...` produces correct float64 prices (not fixed-point)
- [ ] Databento adapter test cassette suite passes
- [ ] Session codes populated where provider supplies them
- [ ] All Phase 1 + 2 tests still pass

---

## Cross-Phase Constraints

These apply to all phases:

1. **No breaking changes to the Parquet schema** after Phase 1 ships. Changes to `NORMALIZED_BAR_SCHEMA` require a schema version bump and migration note.
2. **No live network calls in CI.** All adapter tests run via cassette replay in every phase.
3. **Backward-compatible DuckDB DDL.** New tables and columns use `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`. Never `DROP` or `ALTER` destructively.
4. **Provider-agnostic core.** The core pipeline, window builder, and catalog must work identically regardless of which adapter is used.

---

## Milestone Summary

| Milestone | Outcome |
|-----------|---------|
| Phase 1 complete | First real SPY bars in archive; first windows exported for ML pipeline |
| Phase 2 complete | Batch windowing operational; archive integrity fully reportable |
| Phase 3 complete | Research-grade archive: Databento + futures + session metadata |
