# MDRT 04 — Core Pipeline

> **Revision note (req-review-01):** Raw Store revised to store provider-native transcripts.
> Normalizer now receives native records, applies source-timezone → UTC conversion, handles IB-specific field names.
> Validator receives `RequestSpec` for session-aware gap classification. Archive Writer enforces
> overlap policy. Orchestrator wires three-component provider layer.
>
> **Revision note (req-review-02):** Daily bar convention updated: `ts_utc` = session CLOSE (not open);
> Normalizer must populate `session_date` and `session_close_ts_utc`. Phase 1 calendar limitation
> prominently labeled. Pacing language updated to reference §3.3a.
>
> **Revision note (combined-review):** `session_date` is now **mandatory for ALL bars** (not just
> daily). This is the exchange-local trading date — always populated, never null. Phase 1 calendar
> limitation made fully explicit with quantified impact and upgrade path.

## Overview

The core pipeline transforms provider-native transcripts into a validated, partitioned Parquet
archive and DuckDB metadata catalog. Five components in strict order:

```
Raw Store → Normalizer → Validator → Archive Writer → Catalog Manager
```

The Orchestrator drives the full sequence after the Provider Layer has resolved the contract
and collected the native records.

---

## 4.1 Raw Store (revised)

**File:** `src/market_data/core/raw_store.py`

### Purpose

Persist the **provider-native request/response transcript** before any transformation.
This enables debugging, replay, provider migration verification, and audit.

The raw store no longer receives pre-normalized tables. It receives provider-native records
as returned by the `HistoricalDataCollector`.

### Class: `RawStore`

```python
class RawStore:
    def __init__(self, raw_root: Path): ...

    def save_chunk_transcript(
        self,
        batch: IngestionBatch,
        chunk_index: int,
        request_params: dict,
        native_records: list[dict],
    ) -> Path: ...

    def load_chunk_transcripts(
        self,
        batch_id: str,
    ) -> list[dict]: ...

    def compute_checksum(self, path: Path) -> str: ...
```

### `save_chunk_transcript`

**Input:** batch metadata, chunk index, IB request parameters dict, native bar records list

**Output:** `Path` to the saved file

**Path pattern:**
`raw_root/provider=<p>/symbol=<s>/batch_id=<b>/chunk_<NNNN>_transcript.jsonl.gz`

**File format (JSONL, one JSON object per line):**
```
{"type": "request", "chunk_index": 0, "end_datetime": "...", "duration_str": "30 D", "bar_size": "1 min", "what_to_show": "TRADES", "use_rth": 1, "format_date": 2, "req_id": 1}
{"type": "bar", "date": 1704205800, "open": 474.92, "high": 475.01, "low": 474.88, "close": 474.95, "volume": 15234, "barCount": 312, "WAP": 474.96}
{"type": "bar", ...}
{"type": "end", "req_id": 1, "start": "20240102 09:30:00 US/Eastern", "end": "20240102 16:00:00 US/Eastern"}
```

**Rules:**
- Always write `{"type": "request", ...}` as first line (captures full request params for replay)
- Write one `{"type": "bar", ...}` line per native bar record
- Write `{"type": "end", ...}` as final line with IB's reported date range
- Atomic write: temp file → `os.replace()`
- Compress with gzip
- Raise `ArchiveWriteError` on failure

### `load_chunk_transcripts`

Reads all chunk transcript files for a batch and returns the concatenated list of native bar
dicts (only `{"type": "bar"}` records). Used for normalizer replay in tests.

---

## 4.2 Normalizer (revised)

**File:** `src/market_data/core/normalizer.py`

### Purpose

Convert provider-native records (as loaded from raw store transcripts) into a table conforming
to `NORMALIZED_BAR_SCHEMA`. The normalizer is provider-aware for field mapping but provider-agnostic
for the output schema.

### Class: `Normalizer`

```python
class Normalizer:

    REQUIRED_OUTPUT_FIELDS = {
        "provider", "asset_class", "symbol", "timeframe",
        "use_rth", "what_to_show",
        "ts_utc", "session_date",           # session_date required for all bars
        "open", "high", "low", "close", "volume",
        "source_tz", "ingested_at", "source_batch_id",
        # session_close_ts_utc required for 1D and 1M bars (nullable for intraday)
    }

    def normalize(
        self,
        native_records: list[dict],
        spec: RequestSpec,
        instrument: Instrument,
        session_info: ProviderSessionInfo,
        batch_id: str,
    ) -> pa.Table: ...

    def _normalize_ib(
        self,
        native_records: list[dict],
        spec: RequestSpec,
        instrument: Instrument,
        session_info: ProviderSessionInfo,
        batch_id: str,
    ) -> pa.Table: ...

    def _normalize_alpaca(self, ...) -> pa.Table: ...
    def _normalize_databento(self, ...) -> pa.Table: ...

    def _convert_timestamp_to_utc(
        self,
        raw_ts: Any,
        source_tz: str,
        timeframe: str,
    ) -> datetime: ...

    def _cast_column(self, table: pa.Table, field: pa.Field) -> pa.ChunkedArray: ...
```

### `normalize` — dispatch logic

1. Route to provider-specific normalizer based on `spec.provider`
2. All provider normalizers must return a `pa.Table` conforming to `NORMALIZED_BAR_SCHEMA`
3. Sort output by `ts_utc` ascending
4. Raise `MissingRequiredFieldError` if any required output field is missing
5. Raise `SchemaConformanceError` if any column cannot be cast

### `_normalize_ib` — IB-specific logic

1. Filter `native_records` to only `{"type": "bar"}` entries
2. Map IB native fields:

| IB native field | MDRT field | Transform |
|----------------|------------|-----------|
| `date` | `ts_utc` | Epoch seconds → UTC datetime; see timestamp rule below |
| `open` | `open` | float as-is |
| `high` | `high` | float as-is |
| `low` | `low` | float as-is |
| `close` | `close` | float as-is |
| `volume` | `volume` | int → float64 |
| `barCount` | `trade_count` | int |
| `WAP` | `vwap` | float |

3. **IB timestamp conversion (revised for schema v3):**
   - For intraday bars (`formatDate=2`): `date` is epoch seconds in UTC.
     `ts_utc = datetime.fromtimestamp(int(date), tz=timezone.utc)` (bar open time in UTC)
     `session_date = ts_utc.astimezone(instrument.timezone).date()`
     `session_close_ts_utc = None`
   - For daily bars (`"1D"`): `date` is typically a date string from IB.
     `ts_utc = session_close_time_utc(date, instrument.timezone, calendar)` — the session CLOSE time in UTC
     `session_date = parsed date`
     `session_close_ts_utc = ts_utc` (same value; explicit copy for clarity)
   - For monthly bars (`"1M"`): `date` is typically a YYYYMM or YYYYMMDD string.
     `session_date = last_trading_day_of_month(parsed_date, calendar)`
     `ts_utc = session_close_time_utc(session_date, instrument.timezone, calendar)`
     `session_close_ts_utc = ts_utc`
4. Set `source_tz = session_info.tws_login_timezone`
5. Set `use_rth = spec.use_rth`, `what_to_show = spec.what_to_show`
6. Add provenance: `ingested_at`, `source_batch_id`, `request_spec_id`

### `_convert_timestamp_to_utc` / `session_close_time_utc`

For **intraday bars** from IB (`formatDate=2`): timestamp is epoch seconds in UTC. No conversion needed.

For **daily bars**: given a raw date string (e.g., IB may return `"20240103"` or similar),
compute the session CLOSE time in UTC using `instrument.timezone` and a trading calendar lookup:
1. Parse the date → `date(2024, 1, 3)`
2. Look up session close time from `TradingCalendar` → e.g., 16:00 ET
3. Convert to UTC → `2024-01-03T21:00:00Z`
4. Set `ts_utc = session_close_ts_utc = 2024-01-03T21:00:00Z`
5. Set `session_date = date(2024, 1, 3)`

> ⚠️ **Phase 1 Calendar:** The Phase 1 `TradingCalendar` hardcodes the NYSE/Nasdaq
> U.S. equity regular-hours schedule (09:30–16:00 ET on normal days, 09:30–13:00 ET on
> known early-close days). Early closes are handled **exactly** — the calendar returns
> 13:00 ET (not 16:00 ET) for day-after-Thanksgiving, Christmas Eve, etc.
> Only unscheduled closures (e.g., national mourning) produce `CALENDAR_APPROXIMATION`.
> Full exchange calendar support is a Phase 3 requirement.

> ⚠️ **TRAP 1 note (Normalizer responsibility):** When the IB `date` field in a native bar dict
> is a YYYYMMDD string (IB ignored `formatDate=2`), the Normalizer's `_parse_ib_date()` helper
> MUST handle both types. See §3.2 for the required defensive parse pattern.
> The collector stores whatever IB returned; the Normalizer repairs it.

---

## 4.3 Validator (session-aware, revised)

**File:** `src/market_data/core/validator.py`

### Purpose

Enforce data quality gates. Now session-aware: gap classification uses `RequestSpec` context
to distinguish expected market closures from real data gaps.

### Extended `ValidationReport`

```python
@dataclass
class ValidationReport:
    symbol: str
    timeframe: str
    use_rth: bool
    what_to_show: str
    total_bars: int
    hard_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)  # market-closed gaps, RTH boundaries
    passed: bool = True
```

### `validate` (revised signature)

```python
def validate(
    self,
    table: pa.Table,
    spec: RequestSpec,
    session_calendar: Optional[TradingCalendar] = None,
    expected_gap_tolerance: float = 1.5,
) -> ValidationReport:
```

**Gap classification logic:**

When a gap is detected between two consecutive bars:
1. Compute gap duration
2. If `session_calendar` is provided: check if the gap falls entirely within a known market closure (weekend, holiday, overnight when `use_rth=True`) → classify as `MARKET_CLOSED_GAP` (INFO, not WARNING)
3. If gap falls at an RTH boundary (e.g., 16:00 → next day 09:30) → classify as `RTH_BOUNDARY` (INFO)
4. Otherwise → classify as `UNEXPECTED_GAP` (WARNING)

> ⚠️ **TRAP 4 — Early-Close Session Handling:**
> The Phase 1 `TradingCalendar` hardcodes known NYSE early-close sessions (13:00 ET).
> On these days, the calendar returns the **correct** close time (13:00 ET, not 16:00 ET).
>
> **Rules:**
> - If `timeframe = '1D'` or `'1M'`, the Normalizer already sets `session_close_ts_utc`
>   using the calendar's close time, which is exact for known early closes.
> - If `timeframe` is intraday and `use_rth=True` and a gap occurs between **13:00 ET and
>   16:00 ET** on a known early-close day, classify it as `MARKET_CLOSED_GAP` (INFO).
> - On **unscheduled** closures (not in the hardcoded calendar), gaps may be classified
>   as `UNEXPECTED_GAP` (WARNING) with a `CALENDAR_APPROXIMATION` INFO event.

All other hard checks remain unchanged (see v1 spec §4.3).

### `TradingCalendar` (new dependency)

A simple trading calendar object for gap classification:
```python
class TradingCalendar:
    def is_market_closed(self, ts_start: datetime, ts_end: datetime,
                          timezone: str, use_rth: bool) -> bool: ...
```

Phase 1 implementation: hardcode NYSE/Nasdaq regular hours (09:30–16:00 ET on normal days,
09:30–13:00 ET on known early-close days), NYSE-observed full closures (including Good Friday;
excluding Veterans Day and Columbus Day). Early closes are handled **exactly**.
Do NOT use U.S. federal holidays as a proxy calendar.

> ⚠️ **Known Phase 1 Limitation:** This hardcoded calendar does NOT recognize:
> - Unscheduled closures (e.g., national mourning days)
> - Non-NYSE/Nasdaq exchange schedules
>
> **Impact:** On unscheduled closure days, gaps will be classified as `UNEXPECTED_GAP`,
> with a `CALENDAR_APPROXIMATION` INFO event emitted.
> Full exchange calendar support (`exchange_calendars` library) is a Phase 3 requirement.

---

## 4.4 Archive Writer (overlap-aware, revised)

**File:** `src/market_data/core/archive_writer.py`

### Purpose

Write validated normalized bars to the partitioned Parquet archive, enforcing the
overlap and deduplication policy defined in §11.

### Updated partition hierarchy

```
provider / asset_class / symbol / timeframe / use_rth / what_to_show / year / month
```

`use_rth` and `what_to_show` are partition columns.

### Overlap detection before write

Before writing, the archive writer MUST query the catalog:

```python
def _detect_overlap(
    self,
    catalog: CatalogManager,
    batch: IngestionBatch,
    spec: RequestSpec,
    first_ts: datetime,
    last_ts: datetime,
) -> list[ArchiveFileRecord]:
    """
    Return list of existing ArchiveFileRecords whose time range overlaps
    with [first_ts, last_ts] for the same (symbol, timeframe, use_rth, what_to_show).
    """
    ...
```

### Overlap policy (Phase 1: replace)

If overlap is detected, Phase 1 uses **replace** semantics:
1. Delete overlapping rows from the affected Parquet partition(s) using DuckDB DELETE + rewrite
2. Append the new rows
3. Mark superseded `ArchiveFileRecord` rows: set `superseded_by = new_file_id`
4. Insert new `ArchiveFileRecord` row
5. Update `archive_coverage` to reflect the new time range

See §11 (Overlap & Deduplication Policy) for full policy specification.

### Revised `write` signature

```python
def write(
    self,
    table: pa.Table,
    batch: IngestionBatch,
    spec: RequestSpec,
    catalog: CatalogManager,
) -> list[ArchiveFileRecord]:
```

Returns list of `ArchiveFileRecord` (one per month partition written).

---

## 4.5 Catalog Manager (revised)

**File:** `src/market_data/core/catalog.py`

Extended to support all new DDL tables and IB-specific operations.

### New methods

```python
# Instrument registry
def register_instrument(self, instrument: Instrument) -> None: ...
def get_instrument(self, symbol: str, provider: str) -> Optional[Instrument]: ...
def get_instrument_by_con_id(self, con_id: int) -> Optional[Instrument]: ...

# Session tracking
def register_session(self, session_info: ProviderSessionInfo) -> None: ...
def close_session(self, session_id: str, disconnected_at: datetime) -> None: ...

# Request spec management
def register_request_spec(self, spec: RequestSpec) -> None: ...
def get_request_spec_by_hash(self, request_hash: str) -> Optional[RequestSpec]: ...

# Archive file records (for overlap detection)
def register_archive_file(self, record: ArchiveFileRecord) -> None: ...
def find_overlapping_files(
    self,
    symbol: str,
    timeframe: str,
    use_rth: bool,
    what_to_show: str,
    first_ts: datetime,
    last_ts: datetime,
) -> list[ArchiveFileRecord]: ...
def mark_file_superseded(self, file_id: str, superseded_by: str) -> None: ...
```

All existing methods from v1 (`register_batch_start`, `register_batch_complete`,
`register_coverage`, `get_coverage_paths`, `log_data_quality_event`, etc.) are retained
with updated signatures that include `use_rth` and `what_to_show` where relevant.

---

## 4.6 Orchestrator (revised)

**File:** `src/market_data/core/orchestrator.py`

### Updated `IngestionOrchestrator`

```python
class IngestionOrchestrator:

    def __init__(
        self,
        session: ProviderSession,
        resolver: ContractResolver,
        collector: HistoricalDataCollector,
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
        exchange: str = "SMART",
        currency: str = "USD",
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        adjustment_policy: str = "raw",
        fail_on_warning: bool = False,
    ) -> IngestionBatch: ...
```

### Revised pipeline steps

```
1.  session.connect() → session_info
    catalog.register_session(session_info)

2.  session.ensure_ready()

3.  instrument, resolution_record = resolver.resolve(symbol, asset_class, exchange, currency)
    catalog.register_instrument(instrument)

4.  request_hash = compute_request_hash(...)
    existing_spec = catalog.get_request_spec_by_hash(request_hash)
    if existing_spec AND not force_re_fetch:
        log("Request already completed, skipping fetch"); return existing batch
    spec = RequestSpec(..., request_hash=request_hash)
    catalog.register_request_spec(spec)

5.  batch = IngestionBatch(request_spec_id=spec.request_spec_id, session_id=session_info.session_id, ...)
    catalog.register_batch_start(batch)

6.  chunk_requests = ChunkPlanner().plan(spec)
    all_native_records = []
    for i, chunk in enumerate(chunk_requests):
        try:
            native_records = collector.fetch_chunk(instrument, spec, chunk.chunk_end, chunk.duration_str)
        except ProviderSessionError:
            # TRAP 3: IB mid-batch disconnect (error 1100/1102).
            # Phase 1 policy: fail fast. Do NOT attempt state-machine resume.
            # Mark batch failed; write partial manifest; let operator re-run.
            # The request_hash guard ensures re-runs skip already-completed chunks
            # IF per-chunk completion is tracked (Phase 2). In Phase 1, the full
            # batch is re-fetched from the start. Accept this trade-off.
            batch.status = "failed"
            batch.error_message = "IB session dropped mid-batch"
            catalog.register_batch_complete(batch)  # record failure
            raise  # propagate ProviderSessionError to CLI (exit code 2)
        raw_store.save_chunk_transcript(batch, i, chunk_params_dict, native_records)
        all_native_records.extend(native_records)

7.  norm_table = normalizer.normalize(all_native_records, spec, instrument, session_info, batch.batch_id)

8.  report = validator.validate(norm_table, spec, session_calendar)
    [handle hard errors / soft warnings as before]

9.  archive_records = archive_writer.write(norm_table, batch, spec, catalog)
       [overlap detection + replace policy inside archive_writer]

10. for record in archive_records:
        catalog.register_archive_file(record)
        catalog.register_coverage(...)

11. batch.row_count, batch.chunk_count, batch.status, batch.completed_at = ...
    catalog.register_batch_complete(batch)

12. _write_manifest(batch, spec, archive_records)

13. session.disconnect()
    catalog.close_session(session_info.session_id, datetime.now(UTC))

14. return batch
```

---

## 4.7 Acceptance Criteria — Core Pipeline

- [ ] Full IB ingest run for `SPY 1m useRTH=1 whatToShow=TRADES 2024-01-02→2024-01-05` produces Parquet files in `data/archive/provider=ib/.../use_rth=1/what_to_show=TRADES/...`
- [ ] Written Parquet schema exactly matches `NORMALIZED_BAR_SCHEMA` v3 (includes `use_rth`, `what_to_show`, `source_tz`, `session_date`, `session_close_ts_utc`)
- [ ] Raw transcript `.jsonl.gz` files exist with `{"type": "request"}`, `{"type": "bar"}`, `{"type": "end"}` structure
- [ ] IB daily bar with `date` returned as `"20240103"` string (YYYYMMDD) is correctly re-parsed to `2024-01-03T21:00:00Z` by the Normalizer
- [ ] IB daily bar with `date` returned as epoch int is correctly parsed to the same result
- [ ] `catalog.duckdb` contains rows in `instruments`, `provider_sessions`, `request_specs`, `ingestion_batches`, `archive_coverage`, `archive_file_records`
- [ ] Re-running the same ingest with the same `request_hash` → no re-fetch (idempotent)
- [ ] Weekend/holiday gaps classified as `MARKET_CLOSED_GAP` (INFO), not `UNEXPECTED_GAP` (WARNING)
- [ ] Intraday gap between 13:00–16:00 ET on a trading weekday classified as `MARKET_CLOSED_GAP` (INFO), not `UNEXPECTED_GAP` (WARNING)
- [ ] Overlapping re-ingest (same symbol, overlapping date range) → old file marked `superseded_by`; new data wins; no duplicate bars visible to window builder
- [ ] IB session drop (error 1100) mid-batch → `ProviderSessionError` raised; batch marked `failed`; CLI exits 2
- [ ] Missing `nextValidId` within timeout → `ProviderSessionError` raised before any data fetch
- [ ] Manifest JSON written with all new fields (`request_spec_id`, `session_id`, `what_to_show`, `use_rth`)
