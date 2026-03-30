# MDRT 02 — Data Models & Schemas

> **Revision note (req-review-01):** Major expansion. `Instrument` replaced with full IB-grade
> model. New: `RequestSpec`, `ProviderSessionInfo`, `ContractResolutionRecord`, `ArchiveFileRecord`.
> Schema v2: `use_rth`, `what_to_show`, `source_tz`, `request_spec_id`.
> DuckDB DDL expanded to 8 tables.
>
> **Revision note (req-review-02):** (1) `instrument_id` wording corrected: provider-scoped ID.
> (2) `session_date` and `session_close_ts_utc` added. Schema bumped to v3.
> (3) Phase 1 calendar limitation explicitly labelled.
>
> **Revision note (combined-review):** (1) `session_date` made **mandatory for ALL bars** (not
> just daily) — it is the exchange-local trading date for every bar, enabling clean session-based
> research, labeling, and debugging. (2) Daily bar semantics tightened: `session_date` is the
> primary session identity; `session_close_ts_utc` is the explicit close marker for `1D` and `1M` bars.
> (3) Restart window wording made user-configurable. (4) Read-Only API note narrowed.
> (5) Phase 1 calendar limitations called out more explicitly. (6) Per-module acceptance criteria.

## Overview

This document is the **complete data contract** for MDRT v1.
All code must conform to these definitions. Any deviation is a defect.

---

## 2.1 Domain Dataclasses

**File:** `src/market_data/models/domain.py`

### `Instrument`

Represents a fully-resolved tradable instrument. For IB, all fields marked `ib_required`
are mandatory — they are part of the contract identity, not optional metadata.

```python
@dataclass(frozen=True)
class Instrument:
    # ── Canonical identity ─────────────────────────────────────────────
    instrument_id: str          # UUID4; stable MDRT instrument registry ID;
                                # scoped to ONE provider identity — not a cross-provider canonical ID.
                                # SPY@IB and SPY@Alpaca are TWO Instrument rows with TWO instrument_ids.
    symbol: str                 # Canonical symbol (e.g., "SPY", "ES")
    asset_class: str            # "equity" | "future" | "crypto" | "option"
    currency: str               # ISO 4217 (e.g., "USD")
    exchange: str               # Primary exchange MIC or IB routing code (e.g., "SMART", "CME")
    timezone: str               # Trading timezone (e.g., "America/New_York")

    # ── IB contract fields (required for IB provider) ──────────────────
    provider: str               # "ib" | "alpaca" | "databento"
    provider_symbol: str        # Vendor-specific symbol (e.g., "XNAS.SPY", "ES")
    con_id: Optional[int]       # IB conId — stable IB contract identifier; ib_required
    sec_type: Optional[str]     # IB secType: "STK" | "FUT" | "CASH" | "OPT"; ib_required
    local_symbol: Optional[str] # IB localSymbol (e.g., "ESZ4"); ib_required for futures
    primary_exchange: Optional[str]  # IB primaryExch (e.g., "NASDAQ", "CME"); ib_required
    trading_class: Optional[str]     # IB tradingClass (e.g., "ES"); ib_required for futures
    multiplier: Optional[str]   # IB multiplier (e.g., "50" for ES); ib_required for futures
    expiry: Optional[str]       # YYYYMM or YYYYMMDD for futures/options
    include_expired: bool = False  # IB includeExpired flag for historical expired contracts
```

**Rules:**
- `instrument_id` is generated once at first resolution and stored in the `instruments` catalog table
- `instrument_id` is **provider-scoped**: the same real-world instrument at two different providers produces two separate `Instrument` rows with different `instrument_id` values. This is intentional — provider data semantics differ.
- For IB: `con_id` is the authoritative IB identity within the IB provider scope. If two symbols map to the same `con_id`, they are the same IB instrument
- For REST providers: `con_id` is `None` and `provider_symbol` is the primary identity
- `exchange` for IB equity should typically be `"SMART"` (IB routing); `primary_exchange` carries the actual venue (e.g., `"NASDAQ"`)

---

### `Bar`

Represents one time-bucket of OHLCV data.

```python
@dataclass(frozen=True)
class Bar:
    # ── Partition keys ─────────────────────────────────────────────────
    provider: str           # "ib" | "alpaca" | "databento"
    symbol: str             # Canonical symbol
    timeframe: str          # "1m" | "5m" | "15m" | "1h" | "4h" | "1D" | "1M"
    asset_class: str
    use_rth: bool           # True = regular trading hours only; False = extended hours included
    what_to_show: str       # "TRADES" | "MIDPOINT" | "BID" | "ASK" | "BID_ASK" | "ADJUSTED_LAST"

    # ── Core time ──────────────────────────────────────────────────────
     ts_utc: datetime        # PRIMARY SORT KEY. For intraday bars: bar open time, UTC.
                            # For 1D bars: ts_utc = session CLOSE time in UTC.
                            # For 1M bars: ts_utc = last trading day's session CLOSE in UTC.
                            # e.g., NYSE session 2024-01-03 → 2024-01-03T21:00:00Z (16:00 ET)
    session_date: date              # MANDATORY for ALL bars (intraday, 1D, and 1M).
                                    # The exchange-local trading date for this bar's session.
                                    # For intraday: the calendar date in the exchange timezone
                                    # when this bar's session is considered active.
                                    # For 1D: the session date (e.g., date(2024, 1, 3)).
                                    # For 1M: the last trading day of the month.
                                    # This is the primary session identity for research,
                                    # labeling, and debugging — never ambiguous.
    session_close_ts_utc: Optional[datetime] = None  # For 1D and 1M bars: explicit session close in UTC. Null for intraday.
                                                      # Equals ts_utc for 1D and 1M bars.
                                                      # Null for intraday bars (1m, 5m, 15m, 1h, 4h).

    # ── OHLCV ──────────────────────────────────────────────────────────
    open: float
    high: float
    low: float
    close: float
    volume: float           # 0.0 for bars where volume is not applicable (e.g., BID_ASK)

    # ── Optional enrichment ────────────────────────────────────────────
    trade_count: Optional[int] = None    # IB barCount / Alpaca n
    vwap: Optional[float] = None         # IB WAP / Alpaca vw
    session_code: Optional[str] = None   # "R" | "P" | "A"

    # ── Provenance ─────────────────────────────────────────────────────
    source_tz: str = "UTC"               # TWS login/session timezone captured from ProviderSessionInfo
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_batch_id: str  = field(default_factory=lambda: str(uuid.uuid4()))
    request_spec_id: Optional[str] = None  # Links bar back to RequestSpec
```

**Invariants (enforced by Validator):**
- `ts_utc` is UTC-aware; no naive datetimes ever stored
- `high >= low`; `open` and `close` within `[low, high]`
- `open`, `high`, `low`, `close` all > 0
- `volume >= 0`
- `use_rth` and `what_to_show` match the values in the parent `RequestSpec`
- `session_date` MUST be non-null for ALL bars (daily and intraday)
- `session_date` is the exchange-local trading date (YYYY-MM-DD)
- For `1D` and `1M` bars: `session_close_ts_utc` MUST be non-null and equal `ts_utc`
- For intraday bars (`1m`, `5m`, `15m`, `1h`, `4h`): `session_close_ts_utc` is null

---

### `RequestSpec`

Captures the **complete semantic specification** of a historical data request.
Separate from `IngestionBatch` (which tracks job execution state).
A single `RequestSpec` can be re-executed multiple times (each execution = one `IngestionBatch`).

```python
@dataclass
class RequestSpec:
    request_spec_id: str    # UUID4; stable identifier for this logical request
    provider: str           # "ib" | "alpaca" | "databento"
    instrument_id: str      # FK → Instrument.instrument_id
    symbol: str             # Canonical symbol (denormalized for convenience)
    timeframe: str          # e.g. "1m"
    start_date: datetime    # Inclusive, UTC
    end_date: datetime      # Exclusive, UTC

    # ── IB-specific request parameters ────────────────────────────────
    what_to_show: str = "TRADES"  # IB whatToShow; determines price semantics
    use_rth: bool = True          # IB useRTH; True = regular hours only
    format_date: int = 2          # IB formatDate: 1=string, 2=epoch seconds (always use 2)
    adjustment_policy: str = "raw"  # "raw" | "adjusted" | "split_only"

    # ── Chunking lineage ───────────────────────────────────────────────
    chunk_planner_version: str = "v1"  # Version of ChunkPlanner logic used
    total_chunks: int = 0              # How many IB sub-requests this decomposes into

    # ── Reproducibility ────────────────────────────────────────────────
    request_hash: str = ""    # SHA-256 of (provider + instrument_id + timeframe + start + end
                               # + what_to_show + use_rth + adjustment_policy)
                               # Enables dedup of identical re-requests
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

**Rules:**
- `request_hash` must be computed and stored at creation time
- If a `RequestSpec` with the same `request_hash` already exists in the catalog, do not re-fetch — link the new `IngestionBatch` to the existing spec instead
- `what_to_show` and `use_rth` directly determine the meaning of the bars and the partition path

---

### `IngestionBatch`

Tracks one **execution** of a `RequestSpec`.

```python
@dataclass
class IngestionBatch:
    batch_id: str              # UUID4
    request_spec_id: str       # FK → RequestSpec.request_spec_id
    provider: str
    symbol: str
    timeframe: str
    start_date: datetime       # UTC
    end_date: datetime         # UTC
    requested_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "pending"    # "pending" | "running" | "completed" | "failed"
    row_count: int = 0
    chunk_count: int = 0       # How many provider sub-requests were made
    raw_file_count: int = 0
    checksum: Optional[str] = None
    error_message: Optional[str] = None
    session_id: Optional[str] = None  # FK → ProviderSessionInfo.session_id
```

---

### `ProviderSessionInfo`

Records metadata about the provider session (TWS/Gateway) at the time of ingestion.
Critical for IB: the TWS login timezone determines how daily bar timestamps must be converted.

```python
@dataclass
class ProviderSessionInfo:
    session_id: str             # UUID4
    provider: str               # "ib" | "alpaca" | "databento"
    host: Optional[str] = None  # IB host address (e.g., "127.0.0.1")
    port: Optional[int] = None  # IB port (e.g., 7497 TWS paper, 4001 Gateway)
    client_id: Optional[int] = None
    host_type: Optional[str] = None  # "tws" | "gateway"
    tws_login_timezone: Optional[str] = None  # Config-only (IB_TWS_LOGIN_TIMEZONE); NOT derived from API.
                                               # The timezone selected on the TWS/Gateway login screen.
                                               # Used by Normalizer to compute daily bar session-close time.
                                               # Intraday bars (formatDate=2) are epoch-seconds UTC and
                                               # do NOT require this timezone for conversion.
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    tws_version: Optional[str] = None  # Reported TWS/Gateway version string
```

---

### `ContractResolutionRecord`

Stores the result of a contract resolution call, for audit and replay.

```python
@dataclass
class ContractResolutionRecord:
    resolution_id: str          # UUID4
    instrument_id: str          # FK → Instrument.instrument_id
    provider: str
    request_symbol: str         # What the user typed
    resolved_at: datetime
    con_id: Optional[int]       # IB conId returned
    local_symbol: Optional[str]
    primary_exchange: Optional[str]
    trading_class: Optional[str]
    multiplier: Optional[str]
    expiry: Optional[str]
    raw_response: Optional[str] = None  # JSON of full IB ContractDetails for audit
```

---

### `ArchiveFileRecord`

Tracks individual Parquet files written, for overlap detection and lineage.

```python
@dataclass
class ArchiveFileRecord:
    file_id: str                # UUID4
    batch_id: str               # FK → IngestionBatch.batch_id
    partition_path: str         # Relative Parquet file path
    provider: str
    asset_class: str
    symbol: str
    timeframe: str
    use_rth: bool
    what_to_show: str
    year: int
    month: int
    first_ts: datetime          # UTC
    last_ts: datetime           # UTC
    row_count: int
    checksum: str               # SHA-256 of file bytes
    written_at: datetime
    superseded_by: Optional[str] = None  # file_id of the file that replaced this one
```

---

### `WindowRequest`

```python
@dataclass
class WindowRequest:
    symbol: str
    timeframe: str
    anchor_ts: datetime         # UTC; this bar is included in the window
    bars_before: int
    bars_after: int
    what_to_show: str = "TRADES"  # Must match archive partition to avoid mixing semantics
    use_rth: bool = True
    provider: Optional[str] = None
    reference_level: Optional[float] = None
    export_path: Optional[str] = None
    window_id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

---

## 2.2 PyArrow Schemas

**File:** `src/market_data/models/schemas.py`

### `NORMALIZED_BAR_SCHEMA`

```python
NORMALIZED_BAR_SCHEMA = pa.schema([
    # ── Partition keys ─────────────────────────────────────────────────
    pa.field("provider",        pa.string(),                  nullable=False),
    pa.field("asset_class",     pa.string(),                  nullable=False),
    pa.field("symbol",          pa.string(),                  nullable=False),
    pa.field("timeframe",       pa.string(),                  nullable=False),
    pa.field("use_rth",         pa.bool_(),                   nullable=False),
    pa.field("what_to_show",    pa.string(),                  nullable=False),

    # ── Core time ──────────────────────────────────────────────────────
    pa.field("ts_utc",               pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("session_date",         pa.date32(),                  nullable=False),  # MANDATORY for all bars
    pa.field("session_close_ts_utc", pa.timestamp("us", tz="UTC"), nullable=True),   # Non-null for 1D and 1M bars

    # ── OHLCV ──────────────────────────────────────────────────────────
    pa.field("open",            pa.float64(),                 nullable=False),
    pa.field("high",            pa.float64(),                 nullable=False),
    pa.field("low",             pa.float64(),                 nullable=False),
    pa.field("close",           pa.float64(),                 nullable=False),
    pa.field("volume",          pa.float64(),                 nullable=False),

    # ── Optional enrichment ────────────────────────────────────────────
    pa.field("trade_count",     pa.int64(),                   nullable=True),
    pa.field("vwap",            pa.float64(),                 nullable=True),
    pa.field("session_code",    pa.string(),                  nullable=True),

    # ── Provenance ─────────────────────────────────────────────────────
    pa.field("source_tz",       pa.string(),                  nullable=False),
    pa.field("request_spec_id", pa.string(),                  nullable=True),
    pa.field("ingested_at",     pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("source_batch_id", pa.string(),                  nullable=False),
],
metadata={
    b"description":    b"Normalized OHLCV bar — MDRT internal schema v3",
    b"schema_version": b"3",
})
```

**Schema version history:**
- v1: initial schema
- v2 additions: `use_rth`, `what_to_show`, `source_tz`, `request_spec_id`
- v3 additions: `session_date` (NOT NULL — mandatory for all bars), `session_close_ts_utc` (nullable — non-null for `1D` and `1M` bars); daily bar `ts_utc` convention changed to session CLOSE (not open)

---

## 2.3 DuckDB Catalog DDL

**File:** `src/market_data/models/catalog_sql.py`

### `instruments`

```sql
CREATE TABLE IF NOT EXISTS instruments (
    instrument_id    VARCHAR      PRIMARY KEY,
    symbol           VARCHAR      NOT NULL,
    asset_class      VARCHAR      NOT NULL,
    currency         VARCHAR      NOT NULL,
    exchange         VARCHAR      NOT NULL,
    timezone         VARCHAR      NOT NULL,
    provider         VARCHAR      NOT NULL,
    provider_symbol  VARCHAR      NOT NULL,
    con_id           INTEGER,
    sec_type         VARCHAR,
    local_symbol     VARCHAR,
    primary_exchange VARCHAR,
    trading_class    VARCHAR,
    multiplier       VARCHAR,
    expiry           VARCHAR,
    include_expired  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_instruments_symbol_provider
    ON instruments (symbol, provider);
CREATE UNIQUE INDEX IF NOT EXISTS idx_instruments_con_id
    ON instruments (con_id) WHERE con_id IS NOT NULL;
```

### `provider_sessions`

```sql
CREATE TABLE IF NOT EXISTS provider_sessions (
    session_id       VARCHAR      PRIMARY KEY,
    provider         VARCHAR      NOT NULL,
    host             VARCHAR,
    port             INTEGER,
    client_id        INTEGER,
    host_type        VARCHAR,
    tws_login_timezone VARCHAR,
    connected_at     TIMESTAMPTZ,
    disconnected_at  TIMESTAMPTZ,
    tws_version      VARCHAR
);
```

### `request_specs`

```sql
CREATE TABLE IF NOT EXISTS request_specs (
    request_spec_id      VARCHAR      PRIMARY KEY,
    provider             VARCHAR      NOT NULL,
    instrument_id        VARCHAR      REFERENCES instruments(instrument_id),
    symbol               VARCHAR      NOT NULL,
    timeframe            VARCHAR      NOT NULL,
    start_date           TIMESTAMPTZ  NOT NULL,
    end_date             TIMESTAMPTZ  NOT NULL,
    what_to_show         VARCHAR      NOT NULL DEFAULT 'TRADES',
    use_rth              BOOLEAN      NOT NULL DEFAULT TRUE,
    format_date          INTEGER      NOT NULL DEFAULT 2,
    adjustment_policy    VARCHAR      NOT NULL DEFAULT 'raw',
    chunk_planner_version VARCHAR     NOT NULL DEFAULT 'v1',
    total_chunks         INTEGER      NOT NULL DEFAULT 0,
    request_hash         VARCHAR      NOT NULL,
    created_at           TIMESTAMPTZ  NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_request_specs_hash
    ON request_specs (request_hash);
```

### `ingestion_batches`

```sql
CREATE TABLE IF NOT EXISTS ingestion_batches (
    batch_id             VARCHAR      PRIMARY KEY,
    request_spec_id      VARCHAR      REFERENCES request_specs(request_spec_id),
    session_id           VARCHAR      REFERENCES provider_sessions(session_id),
    provider             VARCHAR      NOT NULL,
    symbol               VARCHAR      NOT NULL,
    asset_class          VARCHAR      NOT NULL,
    timeframe            VARCHAR      NOT NULL,
    start_date           TIMESTAMPTZ  NOT NULL,
    end_date             TIMESTAMPTZ  NOT NULL,
    requested_at         TIMESTAMPTZ  NOT NULL,
    completed_at         TIMESTAMPTZ,
    status               VARCHAR      NOT NULL DEFAULT 'pending',
    row_count            BIGINT       NOT NULL DEFAULT 0,
    chunk_count          INTEGER      NOT NULL DEFAULT 0,
    raw_file_count       INTEGER      NOT NULL DEFAULT 0,
    checksum             VARCHAR,
    error_message        VARCHAR
);
```

### `archive_file_records`

Tracks individual Parquet files for overlap detection and lineage.

```sql
CREATE TABLE IF NOT EXISTS archive_file_records (
    file_id          VARCHAR      PRIMARY KEY,
    batch_id         VARCHAR      REFERENCES ingestion_batches(batch_id),
    partition_path   VARCHAR      NOT NULL,
    provider         VARCHAR      NOT NULL,
    asset_class      VARCHAR      NOT NULL,
    symbol           VARCHAR      NOT NULL,
    timeframe        VARCHAR      NOT NULL,
    use_rth          BOOLEAN      NOT NULL,
    what_to_show     VARCHAR      NOT NULL,
    year             INTEGER      NOT NULL,
    month            INTEGER      NOT NULL,
    first_ts         TIMESTAMPTZ  NOT NULL,
    last_ts          TIMESTAMPTZ  NOT NULL,
    row_count        BIGINT       NOT NULL,
    checksum         VARCHAR      NOT NULL,
    written_at       TIMESTAMPTZ  NOT NULL,
    superseded_by    VARCHAR      REFERENCES archive_file_records(file_id)
);

CREATE INDEX IF NOT EXISTS idx_afr_symbol_tf_session
    ON archive_file_records (symbol, timeframe, use_rth, what_to_show);
```

### `archive_coverage` (revised)

```sql
CREATE TABLE IF NOT EXISTS archive_coverage (
    coverage_id      VARCHAR      PRIMARY KEY,
    provider         VARCHAR      NOT NULL,
    asset_class      VARCHAR      NOT NULL,
    symbol           VARCHAR      NOT NULL,
    timeframe        VARCHAR      NOT NULL,
    use_rth          BOOLEAN      NOT NULL,
    what_to_show     VARCHAR      NOT NULL,
    partition_path   VARCHAR      NOT NULL,
    first_ts         TIMESTAMPTZ  NOT NULL,
    last_ts          TIMESTAMPTZ  NOT NULL,
    row_count        BIGINT       NOT NULL,
    batch_id         VARCHAR      REFERENCES ingestion_batches(batch_id),
    written_at       TIMESTAMPTZ  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_coverage_symbol_tf_session
    ON archive_coverage (symbol, timeframe, use_rth, what_to_show);
```

### `window_log` (revised)

```sql
CREATE TABLE IF NOT EXISTS window_log (
    window_id        VARCHAR      PRIMARY KEY,
    symbol           VARCHAR      NOT NULL,
    timeframe        VARCHAR      NOT NULL,
    provider         VARCHAR,
    use_rth          BOOLEAN      NOT NULL,
    what_to_show     VARCHAR      NOT NULL,
    anchor_ts        TIMESTAMPTZ  NOT NULL,
    bars_before      INTEGER      NOT NULL,
    bars_after       INTEGER      NOT NULL,
    reference_level  DOUBLE,
    export_path      VARCHAR      NOT NULL,
    actual_bar_count INTEGER      NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL
);
```

### `data_quality_events` (revised)

```sql
CREATE TABLE IF NOT EXISTS data_quality_events (
    event_id         VARCHAR      PRIMARY KEY,
    batch_id         VARCHAR      REFERENCES ingestion_batches(batch_id),
    symbol           VARCHAR      NOT NULL,
    timeframe        VARCHAR      NOT NULL,
    use_rth          BOOLEAN,
    what_to_show     VARCHAR,
    severity         VARCHAR      NOT NULL,   -- ERROR | WARNING | INFO
    error_code       VARCHAR      NOT NULL,
    detail           VARCHAR,
    ts_context       TIMESTAMPTZ,
    recorded_at      TIMESTAMPTZ  NOT NULL
);
```

**Extended `error_code` values:**

| Code | Severity | Description |
|------|----------|-------------|
| `DUPLICATE_TIMESTAMP` | ERROR | Two bars share the same `ts_utc` |
| `NON_MONOTONIC_TIME` | ERROR | `ts_utc` not strictly ascending |
| `INVALID_OHLC` | ERROR | `high < low` or price outside `[low, high]` |
| `NEGATIVE_PRICE` | ERROR | Price column ≤ 0 |
| `NEGATIVE_VOLUME` | ERROR | `volume < 0` |
| `UNEXPECTED_GAP` | WARNING | Gap within expected trading hours |
| `PROVIDER_ERROR_GAP` | WARNING | Gap matches a provider error in transcript |
| `LOW_VOLUME` | WARNING | Bar volume below 5th percentile for batch |
| `TIMEZONE_INCONSISTENCY` | WARNING | Source timezone mismatch |
| `MARKET_CLOSED_GAP` | INFO | Gap is a known market closure (weekend/holiday) |
| `RTH_BOUNDARY` | INFO | Gap is expected at RTH open/close boundary |
| `CALENDAR_APPROXIMATION` | INFO | Session close time may be inexact for an **unscheduled** closure (e.g., national mourning). Known early closes (13:00 ET) are handled exactly and do NOT trigger this event |
| `OVERLAP_RESOLVED` | INFO | Overlap detected and resolved via replace policy during archive write (see §11) |

---

## 2.4 Canonical Timeframe Strings (IB mapping)

| String | Duration | IB `barSizeSetting` | Max IB request range | Notes |
|--------|----------|---------------------|---------------------|-------|
| `"1m"` | 1 minute | `"1 min"` | 30 calendar days | |
| `"5m"` | 5 minutes | `"5 mins"` | 60 calendar days | |
| `"15m"` | 15 minutes | `"15 mins"` | 60 calendar days | |
| `"1h"` | 1 hour | `"1 hour"` | 365 calendar days | |
| `"4h"` | 4 hours | `"4 hours"` | 365 calendar days | May span overnight if `use_rth=False` |
| `"1D"` | 1 day | `"1 day"` | 365 calendar days | Timestamp = session CLOSE; see §2.7 |
| `"1M"` | 1 month | `"1 month"` | 365 calendar days | Timestamp = last session CLOSE of month; see §2.7 |

---

## 2.5 Asset Class Values (IB `secType` mapping added)

| String | IB `secType` | Meaning |
|--------|-------------|---------|
| `"equity"` | `"STK"` | Stocks / ETFs |
| `"crypto"` | `"CRYPTO"` | Cryptocurrency |
| `"future"` | `"FUT"` | Futures contract |
| `"option"` | `"OPT"` | Options (Phase 3+) |
| `"fx"` | `"CASH"` | Forex |

---

## 2.6 Session Code Values

| Code | Meaning |
|------|---------|
| `"R"` | Regular session |
| `"P"` | Pre-market |
| `"A"` | After-hours |

---

## 2.7 Timestamp Convention — All Bar Types

**This is a normative rule. Tightened in combined-review pass.**

### `session_date` — Universal Session Identity

`session_date` is **mandatory for all bars** (daily AND intraday). It is the exchange-local
trading date (YYYY-MM-DD) for the session that produced this bar. This is the primary key
for research, labeling, and debugging — it is never ambiguous.

| Bar type | `session_date` value | Example |
|----------|---------------------|---------|
| Intraday (1m, 5m, 15m, 1h, 4h) | The calendar date in the exchange timezone when this bar's session is active | A bar at `2024-01-03T14:35:00Z` on NYSE → `session_date = 2024-01-03` |
| Daily (1D) | The session date for the completed trading day | NYSE session 2024-01-03 → `session_date = 2024-01-03` |
| Monthly (1M) | The last trading day of the month | January 2024 → `session_date = 2024-01-31` |

### Daily Bar Semantics (`1D`)

IB returns daily bars with timestamps in the **TWS login timezone**. Alpaca returns daily bars
with a timestamp of `00:00:00` in the exchange timezone. Both are ambiguous.

**MDRT canonical form for daily bars:**

| Field | Value | Notes |
|-------|-------|-------|
| `ts_utc` | Session **close** time in UTC | Primary sort key; semantically represents the completed session |
| `session_date` | Trading date as `date` object | Exchange-local date; **the main daily bar identity** |
| `session_close_ts_utc` | Session close time in UTC | Equals `ts_utc` for `1D` and `1M` bars; explicit copy for clarity |

Example: NYSE daily bar for 2024-01-03 (normal close):
- `ts_utc = 2024-01-03T21:00:00Z` (16:00 ET = UTC-5 in winter)
- `session_date = 2024-01-03`
- `session_close_ts_utc = 2024-01-03T21:00:00Z`

Example: NYSE daily bar for 2024-11-29 (day after Thanksgiving, early close at 13:00 ET):
- `ts_utc = 2024-11-29T18:00:00Z` (13:00 ET = UTC-5)
- `session_date = 2024-11-29`
- `session_close_ts_utc = 2024-11-29T18:00:00Z`

**The daily bar represents the completed session**, not the session start. Storing the bar at
close time is consistent with futures settlement values and end-of-day signals.
Downstream models SHOULD join and filter on `session_date`, not on `ts_utc`, for daily bars.

### Monthly Bar Semantics (`1M`)

| Field | Value | Notes |
|-------|-------|-------|
| `ts_utc` | Session close time of the **last trading day of the month** in UTC | Sort key; represents the completed month |
| `session_date` | Last trading day of the month as `date` object | The canonical month identity |
| `session_close_ts_utc` | Same as `ts_utc` | Required (non-null), same as daily bars |

Example: NYSE monthly bar for January 2024 (last trading day = Jan 31):
- `ts_utc = 2024-01-31T21:00:00Z` (16:00 ET = UTC-5)
- `session_date = 2024-01-31`
- `session_close_ts_utc = 2024-01-31T21:00:00Z`

> **Partial-month bars:** IB may return a partial bar for the current (incomplete) month.
> MDRT ingests it as-is. The `session_date` is the last trading day within the returned data.
> On the next ingest, the overlap policy will replace the partial bar with the complete month.

### Intraday Bar Semantics

| Field | Value |
|-------|-------|
| `ts_utc` | Bar open time in UTC (unchanged from all prior versions) |
| `session_date` | The exchange-local trading date (MANDATORY; NOT null) |
| `session_close_ts_utc` | `null` (only populated for `1D` and `1M` bars) |

Example: A 1m bar for SPY at 09:35 ET on 2024-01-03:
- `ts_utc = 2024-01-03T14:35:00Z`
- `session_date = 2024-01-03`
- `session_close_ts_utc = null`

> **4h bars:** Treated identically to other intraday bars. `session_date` = exchange-local trading
> date. `session_close_ts_utc = null`. A 4h bar may span across multiple clock-hours within a single session.

This rule MUST be applied by the Normalizer, not the adapter. The adapter may receive any
timestamp format from the provider; the Normalizer converts to the canonical form.

> ⚠️ **Phase 1 Calendar:**
>
> Phase 1 supports a hardcoded **NYSE/Nasdaq U.S. equity regular-hours trading schedule**
> for the supported years, including:
> - **Full closures:** All NYSE-observed holidays (New Year's, MLK Day, Presidents' Day,
>   Good Friday, Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving,
>   Christmas). NYSE observes **Good Friday** (not a federal holiday) and does
>   **NOT** close on Veterans Day or Columbus Day.
> - **Known early closes** (13:00 ET): Day before Independence Day (if weekday),
>   Day after Thanksgiving, Christmas Eve (if weekday), and other NYSE-published early closes.
>   These are handled **exactly** — the `TradingCalendar` returns 13:00 ET, not 16:00 ET.
>
> It does **NOT** use U.S. federal holidays as a proxy calendar.
> It does **NOT** model non-NYSE/Nasdaq exchange schedules.
> It does **NOT** model unscheduled closures (e.g., national mourning days) — these produce
> `CALENDAR_APPROXIMATION` INFO events.
>
> **Upgrade path:** Phase 3 replaces the hardcoded calendar with the `exchange_calendars`
> library, adding full global exchange support.

> 📊 **ML / Research Guidance:**
>
> Sessions tagged with `CALENDAR_APPROXIMATION` in `data_quality_events` should be
> **excluded or separately bucketed** in gold research and training datasets until
> exact exchange-calendar handling is confirmed. This affects:
> - Walk-forward evaluation boundaries
> - Close-sensitive labels (e.g., daily return labels on early-close days)
> - Training-set cleanliness and reproducibility
> - Any feature derived from `session_close_ts_utc` on approximation-tagged days
>
> Downstream pipelines should filter on `data_quality_events.error_code != 'CALENDAR_APPROXIMATION'`
> when building gold-standard datasets, or group these sessions into a separate validation fold.

---

## 2.8 `what_to_show` Values

| Value | IB name | Meaning |
|-------|---------|---------|
| `"TRADES"` | `TRADES` | Last sale prices (default for most instruments) |
| `"MIDPOINT"` | `MIDPOINT` | Midpoint of bid/ask |
| `"BID"` | `BID` | Bid prices |
| `"ASK"` | `ASK` | Ask prices |
| `"BID_ASK"` | `BID_ASK` | OHLC of bid and ask spread |
| `"ADJUSTED_LAST"` | `ADJUSTED_LAST` | Dividend/split-adjusted prices; equities only |

**Default for Phase 1:** `"TRADES"` with `use_rth=True`.
