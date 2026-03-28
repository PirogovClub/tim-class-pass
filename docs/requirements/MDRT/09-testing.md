# MDRT 09 — Testing Strategy

## Overview

MDRT uses a three-tier test strategy: **unit**, **integration**, and **adapter** tests.
All tests run with `pytest`. CI runs the full suite without a live network connection.

---

## 9.1 Test Directory Layout

```
tests/
├── conftest.py                  # Shared fixtures
├── unit/
│   ├── test_normalizer.py
│   ├── test_validator.py
│   ├── test_archive_writer.py
│   ├── test_catalog.py
│   └── test_window_builder.py
├── integration/
│   ├── test_ingest_pipeline.py  # Full pipeline, mock adapter
│   └── test_window_pipeline.py  # Ingest → window export
└── adapters/
    ├── cassettes/               # VCR cassettes (recorded API responses)
    ├── test_alpaca_adapter.py
    └── test_databento_adapter.py
```

---

## 9.2 Shared Fixtures — `tests/conftest.py`

```python
@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:
    """Temporary directory structure: tmp/data/{raw,archive}/ and tmp/outputs/."""

@pytest.fixture
def sample_normalized_table() -> pa.Table:
    """A small valid pa.Table conforming to NORMALIZED_BAR_SCHEMA.
    Contains 10 SPY 1m bars, sorted ASC, no nulls in required fields."""

@pytest.fixture
def sample_table_with_duplicate_ts(sample_normalized_table) -> pa.Table:
    """sample_normalized_table with the first row duplicated."""

@pytest.fixture
def sample_table_with_gap(sample_normalized_table) -> pa.Table:
    """sample_normalized_table with a 5-bar gap injected."""

@pytest.fixture
def sample_table_bad_ohlc(sample_normalized_table) -> pa.Table:
    """sample_normalized_table with high < low on one row."""

@pytest.fixture
def mock_adapter(sample_normalized_table) -> MarketDataProvider:
    """A mock MarketDataProvider that returns sample_normalized_table on fetch."""

@pytest.fixture
def catalog(tmp_data_dir) -> CatalogManager:
    """Live CatalogManager connected to a fresh in-memory (or tmp) DuckDB."""

@pytest.fixture
def archive_writer(tmp_data_dir) -> ArchiveWriter:
    """ArchiveWriter pointed at tmp_data_dir/data/archive/."""
```

---

## 9.3 Unit Tests

### `test_normalizer.py`

| Test | What it checks |
|------|---------------|
| `test_normalize_returns_correct_schema` | Output table schema matches `NORMALIZED_BAR_SCHEMA` exactly |
| `test_normalize_adds_provenance_columns` | `ingested_at` and `source_batch_id` are added if absent |
| `test_normalize_sorts_ascending` | Output is sorted by `ts_utc` ASC regardless of input order |
| `test_normalize_raises_on_missing_field` | `MissingRequiredFieldError` when required column absent |
| `test_normalize_raises_on_naive_timestamp` | `SchemaConformanceError` when `ts_utc` is timezone-naive |
| `test_normalize_casts_float_columns` | Integer columns in input are cast to float64 without error |

### `test_validator.py`

| Test | What it checks |
|------|---------------|
| `test_valid_table_passes` | Clean data → `ValidationReport.passed == True` |
| `test_duplicate_timestamp_raises` | `DuplicateTimestampError` on dup ts |
| `test_non_monotonic_raises` | `NonMonotonicTimeError` on unsorted ts |
| `test_high_less_than_low_raises` | `InvalidOHLCError` |
| `test_open_outside_range_raises` | `InvalidOHLCError` |
| `test_negative_price_raises` | `NegativePriceError` |
| `test_negative_volume_raises` | `NegativeVolumeError` |
| `test_gap_emits_warning` | `DataGapWarning` and entry in `ValidationReport.warnings` |
| `test_low_volume_emits_warning` | `LowVolumeWarning` for anomalous bar |
| `test_parse_timeframe_to_seconds` | "1m"→60, "1h"→3600, "1d"→86400, bad→ValueError |

### `test_archive_writer.py`

| Test | What it checks |
|------|---------------|
| `test_write_creates_parquet_files` | Files exist in expected partition path |
| `test_partition_path_shape` | Directory structure matches `provider=.../asset_class=.../symbol=.../timeframe=.../year=.../month=...` |
| `test_written_schema_matches` | Written Parquet schema equals `NORMALIZED_BAR_SCHEMA` |
| `test_parquet_roundtrip` | Data read back equals data written |
| `test_partition_path_rejects_invalid_chars` | `PartitionPathError` on `/` in symbol |
| `test_write_returns_path_list` | Return value is a non-empty list of Paths |

### `test_catalog.py`

| Test | What it checks |
|------|---------------|
| `test_connect_creates_tables` | All 4 DDL tables exist after `connect()` |
| `test_register_batch_lifecycle` | `start → complete` transitions status correctly |
| `test_register_batch_failed` | Status set to 'failed', error_message stored |
| `test_register_coverage` | Row inserted; `get_coverage_paths` returns it |
| `test_get_coverage_paths_overlap` | Returns paths whose ranges overlap the query window |
| `test_get_coverage_paths_no_overlap` | Returns empty list when nothing overlaps |
| `test_log_quality_event` | Row inserted in `data_quality_events` with correct severity |
| `test_log_window_export` | Row inserted in `window_log` |
| `test_list_available_symbols` | Returns aggregated rows after coverage registered |
| `test_integrity_report_fields` | Report dict contains all required keys |

### `test_window_builder.py`

| Test | What it checks |
|------|---------------|
| `test_build_returns_correct_bar_count` | `bars_before + 1 + bars_after` rows returned |
| `test_anchor_at_correct_index` | Row at index `bars_before` has `ts_utc == anchor_ts` |
| `test_output_sorted_ascending` | `ts_utc` is strictly ascending |
| `test_anchor_not_found_raises` | `WindowAnchorNotFoundError` |
| `test_insufficient_bars_before_raises` | `InsufficientBarsError` |
| `test_insufficient_bars_after_raises` | `InsufficientBarsError` |
| `test_export_jsonl_produces_valid_json` | Every line of JSONL is valid JSON |
| `test_export_jsonl_bar_count` | Line count equals row count |
| `test_export_parquet_one_row_group` | Single row group in output |
| `test_export_parquet_roundtrip` | Data read back equals data exported |

---

## 9.4 Integration Tests

### `test_ingest_pipeline.py`

Full pipeline with `mock_adapter`. No network calls.

| Test | What it checks |
|------|---------------|
| `test_full_ingest_creates_parquet` | End-to-end: Parquet files exist after `orchestrator.run()` |
| `test_full_ingest_updates_catalog` | `ingestion_batches` and `archive_coverage` rows exist in DuckDB |
| `test_full_ingest_writes_manifest` | Manifest JSON file exists and contains all required fields |
| `test_full_ingest_writes_raw_landing` | Raw `.json.gz` file exists |
| `test_ingest_fails_on_bad_data` | Injecting duplicate timestamps → `DuplicateTimestampError`; batch marked `failed` in catalog |
| `test_ingest_warns_on_gap` | Warning in `data_quality_events`; batch still `completed` |
| `test_fail_on_warning_flag` | `fail_on_warning=True` + gap → batch fails |

### `test_window_pipeline.py`

Full pipeline: ingest first, then build a window.

| Test | What it checks |
|------|---------------|
| `test_ingest_then_build_window_jsonl` | Ingest 100 bars → build window → JSONL exists |
| `test_window_bar_count_correct` | Window JSONL has exactly N bars |
| `test_window_logged_in_catalog` | `window_log` row exists after export |
| `test_window_anchor_not_in_archive` | `WindowAnchorNotFoundError` raised correctly |

---

## 9.5 Adapter Tests

**Tool:** `pytest-recording` (VCR cassettes)
**Location:** `tests/adapters/cassettes/`

### `test_alpaca_adapter.py`

| Test | Cassette | What it checks |
|------|----------|---------------|
| `test_fetch_returns_normalized_schema` | `alpaca_spy_1m_jan.yaml` | Schema matches `NORMALIZED_BAR_SCHEMA` |
| `test_fetch_sorted_ascending` | `alpaca_spy_1m_jan.yaml` | `ts_utc` ascending |
| `test_fetch_no_naive_timestamps` | `alpaca_spy_1m_jan.yaml` | All timestamps are UTC-aware |
| `test_unsupported_timeframe_raises` | (no network) | `UnsupportedTimeframeError` for "3m" |
| `test_auth_error_raises` | `alpaca_auth_fail.yaml` | `ProviderAuthError` |
| `test_empty_response_raises` | `alpaca_holiday.yaml` | `EmptyResponseError` |

### `test_databento_adapter.py`

| Test | Cassette | What it checks |
|------|----------|---------------|
| `test_fetch_returns_normalized_schema` | `databento_spy_1m_jan.yaml` | Schema matches |
| `test_prices_are_float_dollars` | `databento_spy_1m_jan.yaml` | Prices not in fixed-point; `open` ≈ 470.0 not 470_000_000_000 |
| `test_unsupported_timeframe_raises` | (no network) | `UnsupportedTimeframeError` for "3m" |
| `test_auth_error_raises` | `databento_auth_fail.yaml` | `ProviderAuthError` |

---

## 9.6 Test Commands

```bash
# Full suite with coverage
pytest --cov=src/market_data --cov-report=term-missing

# Unit only
pytest tests/unit/ -v

# Integration only
pytest tests/integration/ -v

# Adapter only (cassette replay, no live network)
pytest tests/adapters/ -v --block-network

# Fast: skip integration
pytest tests/unit/ tests/adapters/ -v
```

---

## 9.7 Coverage Targets

| Layer | Target |
|-------|--------|
| `exceptions.py` | 100% |
| `models/` | 100% |
| `core/validator.py` | ≥ 95% |
| `core/normalizer.py` | ≥ 95% |
| `core/archive_writer.py` | ≥ 90% |
| `core/catalog.py` | ≥ 90% |
| `core/window_builder.py` | ≥ 90% |
| `core/orchestrator.py` | ≥ 85% |
| `adapters/` | ≥ 80% |
| `cli/` | ≥ 70% |
| **Overall** | **≥ 85%** |

---

## 9.8 CI Requirements

- All tests MUST pass without a live network connection (`--block-network`)
- No test may write to a path outside `tmp_path` (use the `tmp_data_dir` fixture)
- No test may read from a real `.env` file (mock or monkeypatch Settings)
- All cassettes must be sanitized of real API keys before commit
- Test suite MUST complete in under 60 seconds on CI hardware
