# MDRT 09 — Testing Strategy

> **Revision note (req-review-01):** VCR cassettes remain the strategy for REST adapters
> (Alpaca, Databento). For IB, cassettes are replaced with **callback transcript replay**
> using a `CallbackReplaySession` test double. Integration tests against a live IB host
> are tagged `@pytest.mark.ib_live` and never run in CI.
>
> **Revision note (combined-review):** Stale 10s pacing reference fixed to `IB_PACING_DELAY_SEC`
> (default 15s). Normalizer test names updated for schema v3 and session-close convention.
> REST adapter tests (Alpaca, Databento) explicitly labeled as **Phase 2**.
> Schema fixture reference updated v2→v3.

## Overview

MDRT uses a four-tier test strategy:

| Tier | Scope | Network | CI |
|------|-------|---------|-----|
| **Unit** | Single class/function | None | ✅ Always run |
| **Replay** | IB adapter with transcript fixtures | None (replayed) | ✅ Always run |
| **Integration** | Full pipeline with mock/replay adapters | None | ✅ Always run |
| **Live IB** | Full pipeline against real TWS/Gateway | Live IB socket | ❌ Never in CI |

---

## 9.1 Test Directory Layout

```
tests/
├── conftest.py                        # Shared fixtures
├── unit/
│   ├── test_normalizer.py
│   ├── test_validator.py
│   ├── test_archive_writer.py
│   ├── test_catalog.py
│   ├── test_window_builder.py
│   ├── test_chunk_planner.py          # NEW
│   └── test_contract_resolver.py      # NEW (mock IbSession)
├── integration/
│   ├── test_ingest_pipeline.py        # Full pipeline, replay IB adapter
│   └── test_window_pipeline.py        # Ingest → window export
└── adapters/
    ├── cassettes/                     # REST cassettes (Phase 2: Alpaca, Databento)
    │   ├── alpaca_spy_1m_jan.yaml       # Phase 2
    │   ├── alpaca_auth_fail.yaml        # Phase 2
    │   ├── alpaca_holiday.yaml          # Phase 2
    │   ├── databento_spy_1m_jan.yaml    # Phase 2
    │   └── databento_auth_fail.yaml     # Phase 2
    ├── transcripts/                   # IB callback transcript fixtures
    │   ├── ib_spy_1m_rtrade_ok.jsonl      # Normal SPY 1m fetch
    │   ├── ib_spy_1m_empty.jsonl          # No data (error 162)
    │   ├── ib_spy_contract_ambiguous.jsonl
    │   ├── ib_spy_contract_ok.jsonl
    │   └── ib_es_fut_contract_ok.jsonl
    ├── test_ib_session.py             # IbSession unit tests (mocked socket)
    ├── test_ib_contract_resolver.py   # IbContractResolver replay tests
    ├── test_ib_collector.py           # IbHistoricalDataCollector replay tests
    ├── test_alpaca_adapter.py         # VCR cassette tests (Phase 2)
    ├── test_databento_adapter.py      # VCR cassette tests (Phase 2)
    └── README_IB_LIVE.md             # How to run live IB tests
```

---

## 9.2 `CallbackReplaySession` — IB Test Double

**File:** `tests/adapters/replay_session.py`

```python
class CallbackReplaySession(ProviderSession):
    """
    Test double for IbSession. Replays pre-recorded callback transcripts
    instead of opening a real TCP socket to TWS/Gateway.

    Usage:
        transcript = load_transcript("transcripts/ib_spy_1m_rtrade_ok.jsonl")
        session = CallbackReplaySession(transcript)
        resolver = IbContractResolver(session)
        collector = IbHistoricalDataCollector(session)
        # ... run test
    """

    def __init__(self, transcript: list[dict]): ...
    def connect(self) -> ProviderSessionInfo: ...
    def ensure_ready(self) -> None: ...
    def disconnect(self) -> None: ...
    def get_next_request_id(self) -> int: ...

    def replay_contract_details(self, req_id: int) -> None:
        """Inject contractDetails + contractDetailsEnd events for req_id."""
        ...

    def replay_historical_data(self, req_id: int) -> None:
        """Inject historicalData + historicalDataEnd events for req_id."""
        ...

    def replay_error(self, req_id: int, error_code: int, error_string: str) -> None:
        """Inject an IB error callback for req_id."""
        ...
```

**Transcript format** (JSONL — one event dict per line):

```jsonl
{"event": "connect_ready", "next_valid_id": 1, "tws_version": "10.19"}
{"event": "contractDetails", "req_id": 1, "con_id": 756733, "symbol": "SPY", "sec_type": "STK", "local_symbol": "SPY", "primary_exch": "ARCA", "trading_class": "SPY", "currency": "USD"}
{"event": "contractDetailsEnd", "req_id": 1}
{"event": "historicalData", "req_id": 2, "date": "1704205800", "open": 474.92, "high": 475.01, "low": 474.88, "close": 474.95, "volume": 15234, "barCount": 312, "WAP": 474.96}
{"event": "historicalData", "req_id": 2, "date": "1704205860", "open": 474.95, "high": 475.10, "low": 474.85, "close": 475.02, "volume": 12100, "barCount": 289, "WAP": 474.97}
{"event": "historicalDataEnd", "req_id": 2, "start": "20240102 09:30:00 US/Eastern", "end": "20240102 16:00:00 US/Eastern"}
```

> **Epoch verification:** `1704205800` = `2024-01-02T14:30:00Z` = `2024-01-02 09:30:00 US/Eastern` (NYSE open).
> `1704205860` = `2024-01-02T14:31:00Z` = one minute later. Verify with:
> `datetime.fromtimestamp(1704205800, tz=timezone.utc)`.

---

## 9.3 Shared Fixtures — `tests/conftest.py`

```python
@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:
    """Temporary data/raw, data/archive, outputs/ structure."""

@pytest.fixture
def sample_request_spec() -> RequestSpec:
    """Valid RequestSpec: SPY 1m RTH=True TRADES 2024-01-02→2024-01-05."""

@pytest.fixture
def sample_instrument() -> Instrument:
    """Fully-resolved SPY Instrument with con_id=756733."""

@pytest.fixture
def sample_session_info() -> ProviderSessionInfo:
    """IbSession info: host=127.0.0.1, tz=America/New_York."""

@pytest.fixture
def sample_normalized_table(sample_request_spec, sample_instrument) -> pa.Table:
    """Valid pa.Table conforming to NORMALIZED_BAR_SCHEMA v3; 10 SPY 1m bars; session_date populated."""

@pytest.fixture
def sample_native_records() -> list[dict]:
    """IB-native bar dicts matching ib_spy_1m_rtrade_ok.jsonl transcript."""

@pytest.fixture
def replay_session_ok() -> CallbackReplaySession:
    """CallbackReplaySession pre-loaded with ib_spy_1m_rtrade_ok.jsonl."""

@pytest.fixture
def replay_session_empty() -> CallbackReplaySession:
    """CallbackReplaySession that replays IB error 162 (no data)."""

@pytest.fixture
def catalog(tmp_data_dir) -> CatalogManager:
    """Live CatalogManager connected to a tmp DuckDB."""

@pytest.fixture
def archive_writer(tmp_data_dir, catalog) -> ArchiveWriter:
    """ArchiveWriter pointed at tmp_data_dir/data/archive/."""

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch) -> Settings:
    """Ensure tests never read from a real .env file.
    autouse=True guarantees complete env isolation for all tests."""
    monkeypatch.setenv("IB_HOST", "127.0.0.1")
    monkeypatch.setenv("IB_PORT", "9999")        # Dummy port — no real connection
    monkeypatch.setenv("IB_CLIENT_ID", "999")
    monkeypatch.setenv("IB_TWS_LOGIN_TIMEZONE", "America/New_York")
    monkeypatch.setenv("ALPACA_API_KEY", "")      # Blank — prevent accidental auth
    monkeypatch.setenv("ALPACA_API_SECRET", "")
    return Settings()
```

---

## 9.4 Unit Tests

### `test_chunk_planner.py` (NEW)

| Test | What it checks |
|------|---------------|
| `test_1m_90_days_produces_3_chunks` | 90-day 1m range → 3×30-day chunks |
| `test_1D_365_days_produces_1_chunk` | 365-day 1D range → 1 chunk |
| `test_1D_400_days_produces_2_chunks` | 400-day 1D range → 2 chunks |
| `test_chunks_are_reverse_chronological` | IB endDateTime style: last chunk first |
| `test_chunk_end_dates_are_utc` | All chunk_end datetimes are UTC-aware |
| `test_chunk_duration_strings_correct` | "1m"→"30 D", "1h"→"1 Y", "4h"→"1 Y", "1D"→"1 Y", "1M"→"1 Y" |
| `test_chunk_planner_supports_all_seven_timeframes` | All of `1m, 5m, 15m, 1h, 4h, 1D, 1M` produce valid chunk lists |

### `test_normalizer.py` (revised)

| Test | What it checks |
|------|---------------|
| `test_ib_normalize_returns_v3_schema` | Output includes `use_rth`, `what_to_show`, `source_tz`, `session_date` (NOT NULL) |
| `test_ib_epoch_seconds_converted_to_utc` | `date=1704205800` → `2024-01-02T14:30:00Z` |
| `test_ib_daily_bar_timestamp_is_session_close` | NYSE daily bar → `T21:00:00Z` (16:00 ET close) |
| `test_ib_daily_bar_early_close_timestamp` | Day after Thanksgiving daily bar → `T18:00:00Z` (13:00 ET close), NOT 16:00 ET |
| `test_ib_daily_bar_yyyymmdd_string_parsed` | `date="20240103"` string → same result as epoch int |
| `test_ib_monthly_bar_timestamp_is_last_session_close` | 1M bar for Jan 2024 → `ts_utc` = session close of Jan 31 |
| `test_ib_monthly_bar_session_date_is_last_trading_day` | 1M bar for Jan 2024 → `session_date = 2024-01-31` |
| `test_ib_monthly_bar_session_close_ts_utc_required` | `session_close_ts_utc` is NOT null for 1M bars |
| `test_ib_session_date_populated_for_intraday` | `session_date` is NOT null for 1m bars |
| `test_ib_session_date_populated_for_daily` | `session_date` is NOT null for 1D bars |
| `test_ib_session_date_populated_for_4h` | `session_date` is NOT null for 4h bars |
| `test_ib_wap_mapped_to_vwap` | `WAP` → `vwap` column |
| `test_ib_barcount_mapped_to_trade_count` | `barCount` → `trade_count` |
| `test_source_tz_stored_from_session_info` | `source_tz="America/New_York"` in output |
| `test_use_rth_propagated_from_spec` | `use_rth=True` in every row |
| `test_what_to_show_propagated_from_spec` | `what_to_show="TRADES"` in every row |
| `test_raises_on_naive_timestamp` | `SchemaConformanceError` |
| `test_raises_on_missing_required_field` | `MissingRequiredFieldError` |

### `test_validator.py` (revised)

| Test | What it checks |
|------|---------------|
| `test_valid_table_passes` | Clean data → `passed==True` |
| `test_duplicate_timestamp_raises` | `DuplicateTimestampError` |
| `test_non_monotonic_raises` | `NonMonotonicTimeError` |
| `test_invalid_ohlc_raises` | `InvalidOHLCError` |
| `test_negative_price_raises` | `NegativePriceError` |
| `test_negative_volume_raises` | `NegativeVolumeError` |
| `test_weekend_gap_classified_as_market_closed` | Gap Friday→Monday → INFO not WARNING |
| `test_holiday_gap_classified_as_market_closed` | Jan 1 gap → INFO |
| `test_intraday_gap_classified_as_unexpected` | Gap during RTH → `DATA_GAP` WARNING |
| `test_low_volume_emits_warning` | `LowVolumeWarning` |

#### Calendar Correctness Regression Tests

These verify the hardcoded NYSE/Nasdaq calendar handles early closes **exactly** and does NOT conflate federal holidays with exchange holidays.

| Test | What it checks |
|------|---------------|
| `test_good_friday_classified_as_market_closed` | Good Friday (NYSE closed, NOT a federal holiday) → gap classified as `MARKET_CLOSED_GAP` (INFO) |
| `test_veterans_day_not_classified_as_closed` | Veterans Day (federal holiday but NYSE OPEN) → no `MARKET_CLOSED_GAP` event; bars expected |
| `test_columbus_day_not_classified_as_closed` | Columbus Day (federal holiday but NYSE OPEN) → no `MARKET_CLOSED_GAP` event; bars expected |
| `test_day_after_thanksgiving_early_close_exact` | Day after Thanksgiving 1m bars → gap 13:00–16:00 ET classified as `MARKET_CLOSED_GAP` (INFO). No `CALENDAR_APPROXIMATION` — the calendar knows about this early close exactly |
| `test_christmas_eve_early_close_exact` | Christmas Eve (weekday) 1m bars → gap 13:00–16:00 ET classified as `MARKET_CLOSED_GAP` (INFO). No `CALENDAR_APPROXIMATION` |
| `test_daily_bar_early_close_uses_1300_et` | Daily bar on day after Thanksgiving → `session_close_ts_utc` = 13:00 ET (18:00 UTC), NOT 16:00 ET (21:00 UTC). The calendar returns the exact close |
| `test_monthly_bar_early_close_last_day` | Monthly bar where last trading day is an early-close day → `session_close_ts_utc` = 13:00 ET |
| `test_window_across_early_close_day` | Window extraction across an early-close session → no error; bars returned normally |
| `test_unscheduled_closure_produces_approximation` | Gap on a date NOT in the hardcoded calendar → `CALENDAR_APPROXIMATION` INFO emitted |

#### Timeframe Coverage Tests

Every supported timeframe must be exercised end-to-end.

| Test | What it checks |
|------|---------------|
| `test_ingest_1m_bars` | 1m bars ingested, normalized, validated, archived correctly |
| `test_ingest_5m_bars` | 5m bars ingested, normalized, validated, archived correctly |
| `test_ingest_15m_bars` | 15m bars ingested, normalized, validated, archived correctly |
| `test_ingest_1h_bars` | 1h bars ingested, normalized, validated, archived correctly |
| `test_ingest_4h_bars` | 4h bars ingested, `session_date` populated, `session_close_ts_utc = null` |
| `test_ingest_1D_bars` | 1D bars ingested, `ts_utc = session close`, `session_close_ts_utc` NOT null |
| `test_ingest_1M_bars` | 1M bars ingested, `session_date = last trading day`, `session_close_ts_utc` NOT null |

### `test_archive_writer.py` (revised)

| Test | What it checks |
|------|---------------|
| `test_partition_path_includes_use_rth_and_what_to_show` | Directory contains `use_rth=1/what_to_show=TRADES/` |
| `test_write_returns_archive_file_records` | Returns `ArchiveFileRecord` list not just paths |
| `test_archive_file_record_has_checksum` | Each record has non-empty `checksum` |
| `test_overlap_detected_before_write` | Catalog queried for existing coverage |
| `test_overlapping_write_marks_old_superseded` | Old `ArchiveFileRecord.superseded_by` set |
| `test_no_duplicate_bars_after_overlap_write` | Read back shows no dup ts_utc |
| `test_partition_path_rejects_invalid_chars` | `PartitionPathError` |

### `test_catalog.py` (revised)

| Test | What it checks |
|------|---------------|
| `test_register_instrument_stores_con_id` | `instruments` table has the row |
| `test_get_instrument_by_con_id` | Returns instrument for known con_id |
| `test_register_request_spec_stores_hash` | `request_specs` table has row; hash unique index enforced |
| `test_get_request_spec_by_hash_returns_existing` | Idempotency: same hash returns existing spec |
| `test_register_session_and_close` | `provider_sessions` row transitions correctly |
| `test_find_overlapping_files_returns_correct` | Temporal overlap query returns correct records |
| `test_find_overlapping_files_respects_use_rth` | `use_rth=0` rows not returned when querying `use_rth=1` |
| `test_mark_file_superseded` | `superseded_by` FK set correctly |
| `test_coverage_query_respects_what_to_show` | BID_ASK coverage not returned for TRADES query |
| All v1 batch/coverage/quality/window-log tests | Retained with `use_rth`/`what_to_show` passed |

### `test_window_builder.py` (unchanged core, signature update)

| Test | What it checks |
|------|---------------|
| `test_build_returns_correct_bar_count` | `bars_before + 1 + bars_after` rows |
| `test_anchor_at_correct_index` | Row at `bars_before` has `ts_utc == anchor_ts` |
| `test_wrong_use_rth_raises_anchor_not_found` | WindowRequest with mismatched `use_rth` → `WindowAnchorNotFoundError` |
| `test_wrong_what_to_show_raises_anchor_not_found` | Mismatched `what_to_show` → `WindowAnchorNotFoundError` |
| All v1 window builder tests | Retained |

---

## 9.5 Replay Tests — IB Adapter

### `test_ib_session.py`

| Test | What it checks |
|------|---------------|
| `test_connect_ready_on_next_valid_id` | `ensure_ready()` passes after `nextValidId` received |
| `test_connect_timeout_raises` | `ProviderReadyError` if `nextValidId` not received within timeout |
| `test_get_next_request_id_increments` | Each call returns previous + 1 |

### `test_ib_contract_resolver.py`

| Test | Transcript | What it checks |
|------|-----------|---------------|
| `test_resolve_spy_returns_instrument` | `ib_spy_contract_ok.jsonl` | `con_id=756733`, `primary_exchange="ARCA"` |
| `test_resolve_ambiguous_raises` | `ib_spy_contract_ambiguous.jsonl` | `AmbiguousContractError` |
| `test_resolve_not_found_raises` | `ib_empty_contract.jsonl` | `ContractNotFoundError` |
| `test_resolve_cached_skips_api` | — | If in DuckDB instruments, no replay event injected |
| `test_resolve_futures_sets_expiry` | `ib_es_fut_contract_ok.jsonl` | `expiry="202412"`, `multiplier="50"` |

### `test_ib_collector.py`

| Test | Transcript | What it checks |
|------|-----------|---------------|
| `test_fetch_chunk_returns_native_records` | `ib_spy_1m_rtrade_ok.jsonl` | Returns list of dicts with IB field names |
| `test_fetch_chunk_error_162_raises_empty` | `ib_spy_1m_empty.jsonl` | `EmptyResponseError` |
| `test_fetch_range_three_chunks` | (3× `ib_spy_1m_*`) | Concatenated; 3 chunks called |
| `test_pacing_delay_applied` | — | Timer mock verifies `IB_PACING_DELAY_SEC` (default 15s) delay between chunks |

---

## 9.6 Integration Tests

### `test_ingest_pipeline.py` (revised)

| Test | What it checks |
|------|---------------|
| `test_full_ib_ingest_creates_parquet` | End-to-end with replay adapter; Parquet path includes `use_rth=1/what_to_show=TRADES/` |
| `test_full_ib_ingest_updates_all_catalog_tables` | Rows in `instruments`, `provider_sessions`, `request_specs`, `ingestion_batches`, `archive_coverage`, `archive_file_records` |
| `test_full_ib_ingest_writes_transcript` | Raw JSONL.gz file has `request`/`bar`/`end` structure |
| `test_idempotent_on_same_request_hash` | Second run with same spec → no re-fetch; same batch returned |
| `test_overlap_rewrite_no_duplicates` | Overlapping second ingest → no dup timestamps in read-back |
| `test_ingest_fails_on_bad_data` | Dup timestamp → `DuplicateTimestampError`; batch `failed` |
| `test_weekend_gap_not_warning` | Weekend gap → INFO event, not WARNING |

### `test_window_pipeline.py` (revised)

| Test | What it checks |
|------|---------------|
| `test_ingest_then_build_window` | Ingest 100 bars → build window → JSONL with 82 bars |
| `test_window_respects_use_rth_filter` | Window with `use_rth=False` when only `use_rth=True` → `WindowAnchorNotFoundError` |
| `test_window_logged_in_catalog` | `window_log` has row with `use_rth`, `what_to_show` |

---

## 9.7 Live IB Tests

**File:** `tests/adapters/README_IB_LIVE.md`

```markdown
# Running Live IB Tests

These tests require:
1. TWS or IB Gateway running locally
2. Logged-in IB account with market data subscriptions
3. Correct IB_HOST, IB_PORT, IB_CLIENT_ID in .env

Run with:
    pytest tests/adapters/test_ib_live.py -m ib_live -v

DO NOT run in CI. DO NOT commit API keys or account numbers.
```

```python
@pytest.mark.ib_live
def test_live_connect_and_resolve_spy():
    """Real socket connect to local TWS; resolve SPY; assert con_id matches expected."""
    ...

@pytest.mark.ib_live
def test_live_fetch_spy_1m_5days():
    """Real fetch of 5 days of SPY 1m bars; assert row count and schema."""
    ...
```

---

## 9.8 Test Commands

```bash
# Full suite (unit + replay + integration; no live IB)
pytest --cov=src/market_data --cov-report=term-missing

# Unit only
pytest tests/unit/ -v

# IB adapter replay only (no live network)
pytest tests/adapters/test_ib_*.py -v

# REST adapter cassette tests (Phase 2 — do NOT implement in Phase 1)
pytest tests/adapters/test_alpaca_adapter.py tests/adapters/test_databento_adapter.py -v

# Integration
pytest tests/integration/ -v

# Live IB (local only — not CI)
pytest tests/adapters/test_ib_live.py -m ib_live -v
```

---

## 9.9 Coverage Targets

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
| `adapters/chunk_planner.py` | ≥ 95% |
| `adapters/ib_*` (unit + replay) | ≥ 80% |
| `adapters/alpaca_*` (cassette) | ≥ 80% | *(Phase 2)* |
| `cli/` | ≥ 70% |
| **Overall** | **≥ 85%** |

---

## 9.10 CI Requirements

- All tests at tiers **Unit**, **Replay**, **Integration** MUST pass without any live network connection
- No test may write outside `tmp_path`
- No test may read a live `.env` (mock `Settings`)
- Cassettes and transcripts must not contain real API keys or IB account numbers
- IB transcript fixtures must be manually created by running a live session once and saving output; reviewed before commit
- Test suite MUST complete in under 90 seconds on CI hardware
- `pytest.mark.ib_live` tests are explicitly excluded from the default run via `pytest.ini`:
  ```ini
  [pytest]
  markers =
      ib_live: marks tests requiring a live IB session (deselect with `-m "not ib_live"`)
  addopts = -m "not ib_live"
  ```
