# MDRT 02 — Data Models & Schemas

## Overview

This document is the **complete data contract** for MDRT v1.
All code must conform to these definitions. Any deviation is a defect.

---

## 2.1 Domain Dataclasses

**File:** `src/market_data/models/domain.py`

### `Instrument`

Represents a tradable instrument.

```python
@dataclass(frozen=True)
class Instrument:
    symbol: str            # Canonical symbol (e.g., "SPY")
    provider_symbol: str   # Vendor-specific symbol (e.g., "XNAS.SPY" for Databento)
    asset_class: str       # "equity" | "future" | "crypto" | "option"
    exchange: Optional[str]  # Exchange MIC code (e.g., "XNAS")
    timezone: str = "UTC"  # Relevant trading timezone (e.g., "America/New_York")
```

### `Bar`

Represents one time-bucket of OHLCV data.

```python
@dataclass(frozen=True)
class Bar:
    # Partition keys
    provider: str          # "alpaca" | "databento"
    symbol: str
    timeframe: str         # "1m" | "5m" | "15m" | "1h" | "1d"
    asset_class: str

    # Core OHLCV
    ts_utc: datetime       # Must be timezone-aware UTC
    open: float
    high: float
    low: float
    close: float
    volume: float

    # Optional enrichment
    trade_count: Optional[int] = None
    vwap: Optional[float] = None
    session_code: Optional[str] = None  # "R" | "P" | "A"

    # Provenance
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_batch_id: str  = field(default_factory=lambda: str(uuid.uuid4()))
```

**Invariants (enforced by Validator):**
- `ts_utc` is UTC-aware; no naive datetimes allowed
- `high >= low`
- `open` and `close` are within `[low, high]`
- `open`, `high`, `low`, `close` all > 0
- `volume >= 0`

### `IngestionBatch`

Tracks one retrieval job from start to completion.

```python
@dataclass
class IngestionBatch:
    batch_id: str          # UUID4, auto-generated
    provider: str          # Provider slug
    symbol: str
    timeframe: str
    start_date: datetime   # Inclusive, UTC
    end_date: datetime     # Exclusive, UTC
    requested_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    row_count: int = 0
    raw_file_count: int = 0
    checksum: Optional[str] = None   # SHA-256 of normalized Parquet bytes
    error_message: Optional[str] = None
```

### `WindowRequest`

Defines a reusable market window extraction job.

```python
@dataclass
class WindowRequest:
    symbol: str
    timeframe: str
    anchor_ts: datetime    # UTC; this bar is included in the window
    bars_before: int       # Number of bars before anchor (exclusive of anchor)
    bars_after: int        # Number of bars after anchor (exclusive of anchor)
    provider: Optional[str] = None        # Prefer specific provider; None = any
    reference_level: Optional[float] = None  # Reference price (e.g., entry) stored in metadata
    export_path: Optional[str] = None     # Override default output path
    window_id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

---

## 2.2 PyArrow Schemas

**File:** `src/market_data/models/schemas.py`

### `NORMALIZED_BAR_SCHEMA`

This is the **single source of truth** for Parquet file structure and DuckDB scan compatibility.

```python
NORMALIZED_BAR_SCHEMA = pa.schema([
    # Partition keys
    pa.field("provider",        pa.string(),                  nullable=False),
    pa.field("asset_class",     pa.string(),                  nullable=False),
    pa.field("symbol",          pa.string(),                  nullable=False),
    pa.field("timeframe",       pa.string(),                  nullable=False),

    # Core time
    pa.field("ts_utc",          pa.timestamp("us", tz="UTC"), nullable=False),

    # OHLCV
    pa.field("open",            pa.float64(),                 nullable=False),
    pa.field("high",            pa.float64(),                 nullable=False),
    pa.field("low",             pa.float64(),                 nullable=False),
    pa.field("close",           pa.float64(),                 nullable=False),
    pa.field("volume",          pa.float64(),                 nullable=False),

    # Optional enrichment
    pa.field("trade_count",     pa.int64(),                   nullable=True),
    pa.field("vwap",            pa.float64(),                 nullable=True),
    pa.field("session_code",    pa.string(),                  nullable=True),

    # Provenance
    pa.field("ingested_at",     pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("source_batch_id", pa.string(),                  nullable=False),
],
metadata={
    b"description":     b"Normalized OHLCV bar — MDRT internal schema v1",
    b"schema_version":  b"1",
})
```

**Rules:**
- All adapters MUST produce tables that can be cast to this schema without data loss
- `ts_utc` MUST be `pa.timestamp("us", tz="UTC")` — never naive
- Optional fields (`trade_count`, `vwap`, `session_code`) may be `null`; non-optional fields may not
- Schema version is stored in Parquet metadata for future migration safety

### `RAW_LANDING_SCHEMA`

Lightweight index of raw files stored in DuckDB (not itself a Parquet schema).

```python
RAW_LANDING_SCHEMA = pa.schema([
    pa.field("batch_id",   pa.string(),                  nullable=False),
    pa.field("provider",   pa.string(),                  nullable=False),
    pa.field("symbol",     pa.string(),                  nullable=False),
    pa.field("timeframe",  pa.string(),                  nullable=False),
    pa.field("file_path",  pa.string(),                  nullable=False),
    pa.field("saved_at",   pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("byte_size",  pa.int64(),                   nullable=False),
])
```

---

## 2.3 DuckDB Catalog DDL

**File:** `src/market_data/models/catalog_sql.py`

Run once at startup via `CatalogManager.connect()`. All statements use `CREATE TABLE IF NOT EXISTS` — idempotent.

### `ingestion_batches`

Tracks every retrieval job.

```sql
CREATE TABLE IF NOT EXISTS ingestion_batches (
    batch_id         VARCHAR      PRIMARY KEY,
    provider         VARCHAR      NOT NULL,
    symbol           VARCHAR      NOT NULL,
    asset_class      VARCHAR      NOT NULL,
    timeframe        VARCHAR      NOT NULL,
    start_date       TIMESTAMPTZ  NOT NULL,
    end_date         TIMESTAMPTZ  NOT NULL,
    requested_at     TIMESTAMPTZ  NOT NULL,
    completed_at     TIMESTAMPTZ,
    status           VARCHAR      NOT NULL DEFAULT 'pending',
    row_count        BIGINT       NOT NULL DEFAULT 0,
    raw_file_count   INTEGER      NOT NULL DEFAULT 0,
    checksum         VARCHAR,
    error_message    VARCHAR
);
```

**`status` values:** `pending` → `running` → `completed` | `failed`

### `archive_coverage`

Maps (symbol, timeframe) to Parquet partition paths and date ranges.
Used by the Window Builder to find files without scanning the filesystem.

```sql
CREATE TABLE IF NOT EXISTS archive_coverage (
    coverage_id    VARCHAR      PRIMARY KEY,
    provider       VARCHAR      NOT NULL,
    asset_class    VARCHAR      NOT NULL,
    symbol         VARCHAR      NOT NULL,
    timeframe      VARCHAR      NOT NULL,
    partition_path VARCHAR      NOT NULL,
    first_ts       TIMESTAMPTZ  NOT NULL,
    last_ts        TIMESTAMPTZ  NOT NULL,
    row_count      BIGINT       NOT NULL,
    batch_id       VARCHAR      REFERENCES ingestion_batches(batch_id),
    written_at     TIMESTAMPTZ  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_coverage_symbol_tf
    ON archive_coverage (symbol, timeframe);
```

### `window_log`

Tracks every window export for reproducibility.

```sql
CREATE TABLE IF NOT EXISTS window_log (
    window_id        VARCHAR      PRIMARY KEY,
    symbol           VARCHAR      NOT NULL,
    timeframe        VARCHAR      NOT NULL,
    provider         VARCHAR,
    anchor_ts        TIMESTAMPTZ  NOT NULL,
    bars_before      INTEGER      NOT NULL,
    bars_after       INTEGER      NOT NULL,
    reference_level  DOUBLE,
    export_path      VARCHAR      NOT NULL,
    actual_bar_count INTEGER      NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL
);
```

### `data_quality_events`

Records every validator warning or error for audit.

```sql
CREATE TABLE IF NOT EXISTS data_quality_events (
    event_id     VARCHAR      PRIMARY KEY,
    batch_id     VARCHAR      REFERENCES ingestion_batches(batch_id),
    symbol       VARCHAR      NOT NULL,
    timeframe    VARCHAR      NOT NULL,
    severity     VARCHAR      NOT NULL,   -- ERROR | WARNING
    error_code   VARCHAR      NOT NULL,   -- e.g. DUPLICATE_TIMESTAMP
    detail       VARCHAR,
    ts_context   TIMESTAMPTZ,             -- relevant bar timestamp if applicable
    recorded_at  TIMESTAMPTZ  NOT NULL
);
```

**`error_code` values:**

| Code | Severity | Description |
|------|----------|-------------|
| `DUPLICATE_TIMESTAMP` | ERROR | Two bars share the same `ts_utc` |
| `NON_MONOTONIC_TIME` | ERROR | `ts_utc` not strictly ascending |
| `INVALID_OHLC` | ERROR | `high < low` or price outside `[low, high]` |
| `NEGATIVE_PRICE` | ERROR | Price column ≤ 0 |
| `NEGATIVE_VOLUME` | ERROR | `volume < 0` |
| `DATA_GAP` | WARNING | Gap larger than `tolerance × bar_duration` |
| `LOW_VOLUME` | WARNING | Bar volume below 5th percentile for the batch |
| `TIMEZONE_INCONSISTENCY` | WARNING | Timestamp timezone mismatch detected |

---

## 2.4 Canonical Timeframe Strings

| String | Duration | Notes |
|--------|----------|-------|
| `"1m"` | 1 minute | Standard intraday bar |
| `"5m"` | 5 minutes | |
| `"15m"` | 15 minutes | |
| `"1h"` | 1 hour | |
| `"1d"` | 1 day | Session bar; timezone handling required |

Adapters that use different notation (e.g., Databento uses `"ohlcv-1m"`) **must** map to these canonical strings before returning data. See `MarketDataProvider.normalize_timeframe()`.

---

## 2.5 Asset Class Values

| String | Meaning |
|--------|---------|
| `"equity"` | Stocks / ETFs |
| `"crypto"` | Cryptocurrency |
| `"future"` | Futures contract |
| `"option"` | Options (Phase 3+) |

---

## 2.6 Session Code Values

| Code | Meaning |
|------|---------|
| `"R"` | Regular session |
| `"P"` | Pre-market / extended hours before open |
| `"A"` | After-hours / extended hours after close |

`session_code` is optional in v1. Leave `null` if the provider does not supply it.
