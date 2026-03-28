# MDRT 04 — Core Pipeline

## Overview

The core pipeline transforms raw provider data into a validated, partitioned Parquet archive
and a DuckDB metadata catalog. It has five components:

1. **Raw Store** — persists the raw provider payload before any transformation
2. **Normalizer** — maps vendor fields to the internal schema
3. **Validator** — enforces data quality gates (hard errors + soft warnings)
4. **Archive Writer** — writes validated bars to partitioned Parquet
5. **Catalog Manager** — maintains the DuckDB metadata tables

Each component is a class with no cross-dependencies at the instance level.
The **Orchestrator** wires them together and drives the full pipeline.

---

## 4.1 Raw Store

**File:** `src/market_data/core/raw_store.py`

### Purpose

Persist the raw provider response exactly as received, before normalization.
This enables debugging, replay, provider migration verification, and audit.

### Class: `RawStore`

```python
class RawStore:
    def __init__(self, raw_root: Path): ...

    def save_raw_payload(
        self,
        batch: IngestionBatch,
        page_index: int,
        table: pa.Table,
    ) -> Path: ...

    def compute_checksum(self, path: Path) -> str: ...
```

### `save_raw_payload`

**Inputs:** `IngestionBatch`, page sequence number, raw `pa.Table` from adapter

**Output:** `Path` to the saved file

**Internal logic:**
1. Build path: `raw_root/provider=<p>/symbol=<s>/batch_id=<b>/page_<NNNN>.json.gz`
2. Convert `pa.Table` → `list[dict]` via `table.to_pylist()`
3. Serialize to JSON bytes; encode with `gzip.compress()`
4. Write atomically: write to `<path>.tmp`, then `os.replace()` to final path
5. Return final `Path`
6. Raise `ArchiveWriteError` if any step fails

**Why gzip JSON (not raw Parquet):**
- Human-readable for debugging
- No schema dependency — the exact vendor payload is preserved even if our schema changes
- Gzip achieves ~70-80% compression on repetitive JSON

### `compute_checksum`

Streams the file in 1 MB chunks; returns SHA-256 hex digest.
Used by `IngestionBatch.checksum` after all pages are written.

---

## 4.2 Normalizer

**File:** `src/market_data/core/normalizer.py`

### Purpose

Convert a raw table (already in canonical column names, as returned by the adapter)
into a table that exactly conforms to `NORMALIZED_BAR_SCHEMA`, including:
- Correct column types
- Provenance columns
- Ascending time sort

### Class: `Normalizer`

```python
class Normalizer:

    REQUIRED_FIELDS = {
        "provider", "asset_class", "symbol", "timeframe",
        "ts_utc", "open", "high", "low", "close", "volume",
        "ingested_at", "source_batch_id",
    }

    def normalize(
        self,
        raw_table: pa.Table,
        provider: str,
        symbol: str,
        timeframe: str,
        asset_class: str,
        batch_id: str,
    ) -> pa.Table: ...

    def _cast_column(
        self,
        table: pa.Table,
        field: pa.Field,
    ) -> pa.ChunkedArray: ...
```

### `normalize`

**Inputs:** raw `pa.Table`, provenance metadata

**Output:** `pa.Table` conforming exactly to `NORMALIZED_BAR_SCHEMA`, sorted by `ts_utc` ASC

**Internal logic:**
1. Check that all `REQUIRED_FIELDS` are present in the table; raise `MissingRequiredFieldError` listing missing columns
2. Add `ingested_at` column (current UTC timestamp) if not present
3. Add `source_batch_id` column if not present
4. For each field in `NORMALIZED_BAR_SCHEMA`: call `_cast_column()` to ensure correct Arrow type
5. Force `ts_utc` to `pa.timestamp("us", tz="UTC")` — if incoming is naive, raise `SchemaConformanceError` (do not silently assume UTC)
6. Sort by `ts_utc` using `pc.sort_indices(table, sort_keys=[("ts_utc", "ascending")])`
7. Return `table.cast(NORMALIZED_BAR_SCHEMA)`

### `_cast_column`

Uses `pc.cast(col, target_type, safe=False)` for numeric types.
On `ArrowInvalid`: wrap and raise `SchemaConformanceError` with column name and source/target types.

---

## 4.3 Validator

**File:** `src/market_data/core/validator.py`

### Purpose

Enforce data quality gates. Hard failures immediately stop the pipeline and mark the batch as failed.
Soft warnings are recorded to the catalog but the pipeline continues.

### Class: `Validator`

```python
class Validator:

    IMPOSSIBLE_PRICE_THRESHOLD = 1_000_000.0
    LOW_VOLUME_PERCENTILE = 5

    def validate(
        self,
        table: pa.Table,
        timeframe: str,
        expected_gap_tolerance: float = 1.5,
    ) -> ValidationReport: ...

    def _parse_timeframe_to_seconds(self, timeframe: str) -> int: ...
    def _check_duplicates(self, ts: pa.ChunkedArray) -> None: ...
    def _check_monotonic(self, ts: pa.ChunkedArray) -> None: ...
    def _check_ohlc_relationships(self, table: pa.Table) -> None: ...
    def _check_negative_prices(self, table: pa.Table) -> None: ...
    def _check_negative_volume(self, table: pa.Table) -> None: ...
    def _check_gaps(self, ts: pa.ChunkedArray, timeframe: str, tolerance: float) -> list[str]: ...
```

### `validate`

**Inputs:** normalized `pa.Table`, `timeframe` string, gap tolerance multiplier

**Output:** `ValidationReport` (contains `passed: bool`, `hard_errors: list[str]`, `warnings: list[str]`)

**Execution order (HARD checks — any failure raises immediately):**
1. `_check_duplicates` → `DuplicateTimestampError`
2. `_check_monotonic` → `NonMonotonicTimeError`
3. `_check_ohlc_relationships` → `InvalidOHLCError`
4. `_check_negative_prices` → `NegativePriceError`
5. `_check_negative_volume` → `NegativeVolumeError`

**Execution order (SOFT checks — collect, do not raise):**
6. `_check_gaps` → emit `DataGapWarning` per gap; append to `ValidationReport.warnings`
7. Low-volume check: compute `pc.quantile(table["volume"], 0.05)`; flag bars below threshold

### Check Specifications

| Check | Method | Logic | Exception |
|-------|--------|-------|-----------|
| Duplicate timestamps | `_check_duplicates` | `pc.value_counts(ts)` → any count > 1 | `DuplicateTimestampError` |
| Monotonic timestamps | `_check_monotonic` | `pc.sort_indices(ts)` → compare to `range(len)` | `NonMonotonicTimeError` |
| `high >= low` | `_check_ohlc_relationships` | `pc.greater_equal(high_col, low_col)` → any False | `InvalidOHLCError` |
| Open/close in [low, high] | `_check_ohlc_relationships` | Same method | `InvalidOHLCError` |
| Prices > 0 | `_check_negative_prices` | `pc.less_equal(col, 0)` on each price column | `NegativePriceError` |
| Volume >= 0 | `_check_negative_volume` | `pc.less(volume_col, 0)` | `NegativeVolumeError` |
| Gaps | `_check_gaps` | Compute consecutive ts diffs; flag diffs > `bar_secs * tolerance` | `DataGapWarning` (soft) |
| Low volume | inline in `validate` | `pc.quantile(volume, 0.05)` | `LowVolumeWarning` (soft) |

### `_parse_timeframe_to_seconds`

```
"1m"  → 60
"5m"  → 300
"15m" → 900
"1h"  → 3600
"1d"  → 86400
```

Raise `ValueError` for unrecognized format.

---

## 4.4 Archive Writer

**File:** `src/market_data/core/archive_writer.py`

### Purpose

Write validated normalized bars into the partitioned Parquet archive.

### Class: `ArchiveWriter`

```python
class ArchiveWriter:

    COMPRESSION = "zstd"
    ROW_GROUP_SIZE = 100_000

    def __init__(self, archive_root: Path): ...

    def write(
        self,
        table: pa.Table,
        batch: IngestionBatch,
    ) -> list[Path]: ...

    def _add_partition_columns(self, table: pa.Table) -> pa.Table: ...
    def _build_partition_path(self, provider, asset_class, symbol, timeframe) -> Path: ...
```

### `write`

**Inputs:** validated `pa.Table`, `IngestionBatch`

**Output:** `list[Path]` of Parquet files written

**Internal logic:**
1. Call `_add_partition_columns()` to add integer `year` (int16) and `month` (int8) columns derived from `ts_utc`
2. Call `_build_partition_path()` and validate characters; raise `PartitionPathError` if any value contains `/`, `\`, `..`, or is empty
3. Call `pq.write_to_dataset(table, root_path=archive_root, partition_cols=["provider", "asset_class", "symbol", "timeframe", "year", "month"], compression=COMPRESSION, row_group_size=ROW_GROUP_SIZE, existing_data_behavior="overwrite_or_ignore")`
4. Collect and return paths of written files
5. Raise `ArchiveWriteError` on any `IOError`

### `_add_partition_columns`

Extracts year and month from the `ts_utc` column using `pc.year()` / `pc.month()`.
These columns are used only for Hive partitioning; they are **redundant** (derivable from `ts_utc`) but required for directory-level filter pushdown.

---

## 4.5 Catalog Manager

**File:** `src/market_data/core/catalog.py`

### Purpose

Maintain the DuckDB metadata catalog. The catalog stores no market data — only metadata
about what has been ingested and where it lives.

### Class: `CatalogManager`

```python
class CatalogManager:

    def __init__(self, db_path: Path): ...
    def connect(self) -> None: ...   # idempotent; runs CATALOG_DDL
    def close(self) -> None: ...
    def __enter__(self) -> "CatalogManager": ...
    def __exit__(self, *_) -> None: ...

    # Batch lifecycle
    def register_batch_start(self, batch: IngestionBatch) -> None: ...
    def register_batch_complete(self, batch: IngestionBatch) -> None: ...
    def register_batch_failed(self, batch_id: str, error_message: str) -> None: ...

    # Coverage
    def register_coverage(self, provider, asset_class, symbol, timeframe,
                          partition_path, first_ts, last_ts, row_count, batch_id) -> None: ...
    def get_coverage_paths(self, symbol, timeframe, start_ts, end_ts, provider=None) -> list[str]: ...

    # Quality & audit
    def log_data_quality_event(self, batch_id, symbol, timeframe, severity,
                                error_code, detail=None, ts_context=None) -> None: ...
    def log_window_export(self, request: WindowRequest, actual_bar_count: int) -> None: ...

    # Reporting
    def get_integrity_report(self, symbol: str, timeframe: str) -> dict: ...
    def list_available_symbols(self) -> list[dict]: ...
```

### Method Specifications

**`register_batch_start`**
- INSERT into `ingestion_batches` with `status='running'`
- Raise `CatalogError` on failure

**`register_batch_complete`**
- UPDATE `status='completed'`, set `completed_at`, `row_count`, `checksum`
- Raise `CatalogError` if `batch_id` not found

**`register_batch_failed`**
- UPDATE `status='failed'`, set `error_message`

**`register_coverage`**
- `coverage_id` = `uuid4()`
- `written_at` = `datetime.now(UTC)`
- INSERT OR REPLACE to handle re-ingestion of same partition

**`get_coverage_paths`**
```sql
SELECT DISTINCT partition_path
FROM archive_coverage
WHERE symbol = ?
  AND timeframe = ?
  AND first_ts <= ?   -- last_ts of coverage overlaps query start
  AND last_ts >= ?    -- first_ts of coverage overlaps query end
  [AND provider = ?]
ORDER BY partition_path
```

**`get_integrity_report`**
Returns dict:
```json
{
  "symbol": "SPY",
  "timeframe": "1m",
  "total_batches": 3,
  "total_rows": 24000,
  "first_ts": "2024-01-02T09:30:00Z",
  "last_ts": "2024-01-31T16:00:00Z",
  "error_count": 0,
  "warning_count": 2,
  "coverage_gaps": []
}
```

**`list_available_symbols`**
```sql
SELECT symbol, asset_class, timeframe, provider,
       MIN(first_ts) AS first_ts, MAX(last_ts) AS last_ts,
       SUM(row_count) AS row_count
FROM archive_coverage
GROUP BY symbol, asset_class, timeframe, provider
ORDER BY symbol, timeframe
```

---

## 4.6 Orchestrator

**File:** `src/market_data/core/orchestrator.py`

### Class: `IngestionOrchestrator`

```python
class IngestionOrchestrator:

    def __init__(
        self,
        adapter: MarketDataProvider,
        raw_store: RawStore,
        normalizer: Normalizer,
        validator: Validator,
        archive_writer: ArchiveWriter,
        catalog: CatalogManager,
        manifest_dir: Path,
    ): ...

    def run(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        asset_class: str = "equity",
        fail_on_warning: bool = False,
    ) -> IngestionBatch: ...

    def _write_manifest(self, batch: IngestionBatch, written_paths: list[Path]) -> None: ...
```

### `run` — Pipeline Steps

```
1.  Create IngestionBatch
2.  catalog.register_batch_start(batch)
3.  raw_table  = adapter.fetch_historical_bars(...)
4.  raw_store.save_raw_payload(batch, page_index=0, table=raw_table)
5.  norm_table = normalizer.normalize(raw_table, provider, symbol, timeframe, asset_class, batch_id)
6.  report     = validator.validate(norm_table, timeframe)
    6a. if not report.passed:
          catalog.register_batch_failed(batch_id, report.hard_errors)
          raise (first hard error)
    6b. for each warning: catalog.log_data_quality_event(..., severity="WARNING", ...)
    6c. if fail_on_warning and report.warnings:
          catalog.register_batch_failed(...)
          raise ValidationError
7.  written_paths = archive_writer.write(norm_table, batch)
8.  for each partition path:
        catalog.register_coverage(provider, asset_class, symbol, timeframe, path, first_ts, last_ts, row_count, batch_id)
9.  batch.row_count = len(norm_table)
    batch.raw_file_count = 1   (extend for multi-page)
    batch.checksum = raw_store.compute_checksum(raw_path)
    batch.completed_at = datetime.now(UTC)
    batch.status = "completed"
    catalog.register_batch_complete(batch)
10. _write_manifest(batch, written_paths)
11. return batch
```

### `_write_manifest`

Writes `outputs/manifests/ingestion_manifest_<batch_id>.json`:

```json
{
  "batch_id": "...",
  "provider": "alpaca",
  "symbol": "SPY",
  "timeframe": "1m",
  "start_date": "2024-01-02T00:00:00Z",
  "end_date": "2024-02-01T00:00:00Z",
  "status": "completed",
  "row_count": 8580,
  "checksum": "sha256:...",
  "written_paths": ["data/archive/provider=alpaca/..."],
  "completed_at": "2026-03-27T20:00:00Z"
}
```

---

## 4.7 Acceptance Criteria — Core Pipeline

- [ ] A full ingest run with the Alpaca adapter and `SPY 1m 2024-01-02→2024-01-05` produces Parquet files in the correct partition path
- [ ] The written Parquet schema exactly matches `NORMALIZED_BAR_SCHEMA`
- [ ] `catalog.duckdb` contains one row in `ingestion_batches` with `status='completed'`
- [ ] `catalog.duckdb` contains one or more rows in `archive_coverage` pointing to the written files
- [ ] Injecting a duplicate timestamp into the table causes `DuplicateTimestampError` before any write
- [ ] Injecting `high < low` causes `InvalidOHLCError` before any write
- [ ] A soft-warning gap triggers a row in `data_quality_events` with `severity='WARNING'`
- [ ] The manifest JSON is written to `outputs/manifests/` and contains all required fields
- [ ] The raw landing file exists at `data/raw/provider=alpaca/symbol=SPY/batch_id=<uuid>/page_0000.json.gz`
