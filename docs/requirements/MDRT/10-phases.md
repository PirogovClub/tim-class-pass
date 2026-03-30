# MDRT 10 — Phased Delivery Plan

> **Revision note (req-review-01):** Phase 1 is now **IB-first MVP**, not Alpaca-first.
> Alpaca and Databento move to Phase 2 as alternate provider adapters.
>
> **Revision note (combined-review):** Per-module acceptance criteria added to Phase 1.
> Schema version reference updated v2→v3. Phase 1 calendar limitation assumption made explicit.

## Overview

| Phase | Name | Goal |
|-------|------|------|
| **1** | IB-First MVP | One working IB ingest + single window export, fully correct |
| **2** | Batch + REST Providers | Batch windowing, Alpaca/Databento adapters, integrity reporting |
| **3** | Richer Metadata | Futures, options symbology, corporate actions, multi-providers |

---

## Phase 1 — IB-First MVP

### Goal

Produce a system that can connect to a local IB Gateway or TWS, ingest historical equity bars for one
US stock symbol, validate and archive them correctly, and export a single market window.

This is the minimum required to unlock real reruns of labels, features, and walk-forward evaluation
on real market data — not fixtures.

### Deliberately Restricted Scope

Phase 1 is restricted to make the first implementation correct and auditable before scaling.

| Restriction | Value |
|-------------|-------|
| Asset class | Equity only (`STK`) |
| Symbols | US stocks on SMART routing (e.g., SPY, QQQ, AAPL) |
| Bar sizes | `1m`, `5m`, `15m`, `1h`, `4h`, `1D`, `1M` |
| Session mode | `use_rth=True`, `what_to_show=TRADES` only |
| Adjustment policy | `raw` only — no adjusted prices in Phase 1 |
| Providers | IB only |
| Overlap policy | `replace` — newer ingest supersedes older for same key |
| Calendar | NYSE/Nasdaq RTH only (hardcoded full closures + exact early closes; NOT federal holidays) |
| Window export | Single window, JSONL and/or Parquet |

### Components Delivered

| Component | Included |
|-----------|----------|
| `IbSession` (ProviderSession) | ✅ |
| `IbContractResolver` | ✅ |
| `IbHistoricalDataCollector` | ✅ |
| `ChunkPlanner` (all 7 timeframes) | ✅ |
| Raw Store (transcript format) | ✅ |
| Normalizer (IB mapping, 1D/1M close semantics) | ✅ |
| Validator (session-aware, exact NYSE calendar) | ✅ |
| Archive Writer (overlap-aware, replace policy) | ✅ |
| Catalog Manager (all new DDL tables) | ✅ |
| Window Builder | ✅ |
| `ingest-bars` CLI (IB flags) | ✅ |
| `resolve-contract` CLI | ✅ |
| `build-window` CLI | ✅ |
| `list-symbols` CLI | ✅ |
| `validate-archive` CLI (basic) | ✅ |
| Unit + replay + integration tests | ✅ |
| `.env.example` with IB vars | ✅ |
| IB operational prerequisites doc | ✅ |
| Alpaca adapter | ❌ (Phase 2) |
| Databento adapter | ❌ (Phase 2) |
| `build-window-batch` CLI | ❌ (Phase 2) |
| Futures symbology | ❌ (Phase 3) |
| Adjusted prices | ❌ (Phase 3) |

### Files Produced by a Phase 1 Run

```
data/raw/provider=ib/symbol=SPY/batch_id=<uuid>/chunk_0000_transcript.jsonl.gz
data/archive/provider=ib/asset_class=equity/symbol=SPY/timeframe=1m/use_rth=1/what_to_show=TRADES/year=2024/month=1/part-0.parquet
data/catalog.duckdb  (instruments, provider_sessions, request_specs, ingestion_batches, archive_coverage, archive_file_records, window_log, data_quality_events)
outputs/manifests/ingestion_manifest_<batch_id>.json
outputs/windows/SPY_1m_<anchor>.jsonl
```

### Definition of Done — Phase 1

**Ingest:**
- [ ] `mdrt ingest-bars --provider ib --symbol SPY --timeframe 1m --start 2024-01-02 --end 2024-01-05` completes on a machine with TWS/Gateway running
- [ ] Parquet archive path contains `use_rth=1/what_to_show=TRADES/`
- [ ] Written Parquet schema exactly matches `NORMALIZED_BAR_SCHEMA` v3 (includes `session_date` NOT NULL, `session_close_ts_utc`)
- [ ] All 7 supported timeframes (`1m`, `5m`, `15m`, `1h`, `4h`, `1D`, `1M`) can be ingested end-to-end
- [ ] `catalog.duckdb` has rows in all 8 required tables
- [ ] Re-running the same command → no re-fetch (idempotent by `request_hash`)
- [ ] Raw transcript `.jsonl.gz` exists with correct `request`/`bar`/`end` structure
- [ ] Weekend bars NOT present in RTH output
- [ ] Manifest JSON contains `request_spec_id`, `session_id`, `what_to_show`, `use_rth`

**Validation:**
- [ ] Injecting duplicate timestamps → `DuplicateTimestampError`; batch marked `failed`
- [ ] Weekend gap → INFO event, not WARNING
- [ ] Intraday RTH gap → `DATA_GAP` WARNING

**Overlap:**
- [ ] Re-ingesting overlapping date range → old `ArchiveFileRecord` marked `superseded_by`
- [ ] Reading back archive after overlap re-ingest → zero duplicate timestamps

**Window:**
- [ ] `mdrt build-window --symbol SPY --timeframe 1m --anchor 2024-01-03T14:35:00Z --bars-before 60 --bars-after 20` → JSONL with exactly 82 bars
- [ ] Requesting wrong `use_rth` → `WindowAnchorNotFoundError` with helpful message
- [ ] `window_log` catalog row exists after export

**IB session:**
- [ ] `--dry-run` resolves contract and prints conId; exits 0 with no data written
- [ ] No TWS running → exits 2 with `ProviderConnectError` message
- [ ] `mdrt resolve-contract --symbol SPY` prints resolved contract details

**Tests:**
- [ ] `pytest --cov=src/market_data` passes with ≥ 85% coverage
- [ ] All tests pass with no live network connection
- [ ] `@pytest.mark.ib_live` tests excluded from default run

### Per-Module Acceptance Criteria (Implementation Handoff)

Each module below has a short "done" condition that the implementing agent and reviewer
must verify before the module is considered complete.

| Module | Done when… |
|--------|------------|
| **ProviderSession (IbSession)** | Connects via socket, waits for `nextValidId`, returns `ProviderSessionInfo` with config-driven `tws_login_timezone`, handles disconnect on errors 1100/1102, raises `ProviderReadyError` on timeout |
| **ContractResolver (IbContractResolver)** | Resolves symbol → Instrument with `con_id`, persists to `instruments` table, returns cached result on second call, raises `AmbiguousContractError` / `ContractNotFoundError` on bad input |
| **Collector (IbHistoricalDataCollector)** | Captures provider-native records via EWrapper callbacks, buffers in memory until `historicalDataEnd`, applies pacing via `PacingCoordinator`, stores raw transcripts via `RawStore`, raises `ProviderSessionError` on 1100/1102 |
| **RawStore** | Persists JSONL.GZ transcripts with `request`/`bar`/`end` structure, writes atomically, loads by batch_id for replay |
| **Normalizer** | Produces `pa.Table` conforming exactly to `NORMALIZED_BAR_SCHEMA` v3, `session_date` is NOT NULL for every row, daily bar `ts_utc` = session close, monthly bar `ts_utc` = last-trading-day close, intraday `ts_utc` = bar open, handles both epoch-int and YYYYMMDD-string `date` values from IB |
| **Validator** | Enforces all hard checks (duplicates, monotonic time, OHLC, prices, volume), classifies gaps as MARKET_CLOSED / RTH_BOUNDARY / UNEXPECTED using exact calendar (including known early closes), produces `ValidationReport` |
| **ArchiveWriter** | Writes Parquet to correct partition path, detects overlaps before write, applies replace policy, marks superseded files, produces `ArchiveFileRecord` per month partition written |
| **CatalogManager** | Exposes only active (non-superseded) bars under overlap policy, supports all 8 DDL tables, provides `find_overlapping_files`, `get_request_spec_by_hash`, `register_instrument` |
| **WindowBuilder** | Given an anchor timestamp, produces deterministic window of exactly `bars_before + 1 + bars_after` bars from the archive (not superseded bars), exports JSONL/Parquet, raises `WindowAnchorNotFoundError` / `InsufficientBarsError` |
| **PacingCoordinator** | Sleeps `IB_PACING_DELAY_SEC` between chunks, tracks request rate, returns `is_rate_safe() = False` when ≥ 30 requests in 10 minutes |

### Phase 1 Calendar — Exact Specification

> ⚠️ Phase 1 supports a hardcoded **NYSE/Nasdaq U.S. equity regular-hours trading schedule**
> for the supported years. Early closes are handled **exactly** — the calendar returns the
> correct close time (13:00 ET), not a 16:00 ET approximation.
>
> **NYSE holidays hardcoded in Phase 1:** New Year's, MLK Day, Presidents' Day, Good Friday,
> Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas.
> **Notable differences from federal holidays:** NYSE is CLOSED on Good Friday; NYSE is OPEN
> on Veterans Day and Columbus Day.
>
> **Known early closes (13:00 ET, handled exactly):** Day before Independence Day, Day after
> Thanksgiving, Christmas Eve (when on a weekday).
>
> **The only remaining limitation:** Unscheduled closures (e.g., national mourning days) are
> not in the hardcoded calendar. These produce `CALENDAR_APPROXIMATION` INFO events.
> Full `exchange_calendars` library support is a Phase 3 upgrade.

---

## Phase 2 — Batch + REST Providers

### Goal

Make the archive production-grade with batch window export, Alpaca and Databento alternate adapters,
and comprehensive integrity reporting.

### Scope

| Component | Included |
|-----------|----------|
| Alpaca adapter (RestSession + AlpacaCollector) | ✅ |
| Databento adapter (RestSession + DatabentoCollector) | ✅ |
| `build-window-batch` CLI | ✅ |
| `BatchWindowOrchestrator` (parallel) | ✅ |
| `show-integrity-report` CLI | ✅ |
| Enhanced `validate-archive` (gap report across sessions) | ✅ |
| Symbol list ingestion (multiple symbols in one run) | ✅ |
| Multi-chunk pagination for large REST ranges | ✅ |
| `use_rth=False` support (extended hours) | ✅ |
| VCR cassette tests for Alpaca and Databento | ✅ |

### Definition of Done — Phase 2

- [ ] `mdrt ingest-bars --provider alpaca --symbol SPY --timeframe 1m --start 2024-01-02 --end 2024-02-01` completes and produces correct Parquet with `provider=alpaca` partition
- [ ] `mdrt build-window-batch --manifest windows.jsonl` processes batch with parallel workers
- [ ] `mdrt show-integrity-report` renders readable summary
- [ ] Alpaca and Databento adapter cassette tests pass in CI
- [ ] All Phase 1 DoD criteria still pass

---

## Phase 3 — Richer Metadata

### Goal

Expand to futures symbology, adjusted prices, full exchange calendar support, and options groundwork.

### Scope

| Component | Included |
|-----------|----------|
| IB futures (`FUT`) asset class end-to-end | ✅ |
| Futures `localSymbol` and `expiry` handling | ✅ |
| `adjustment_policy=adjusted` support | ✅ |
| Full exchange calendar library (e.g., `exchange_calendars`) | ✅ |
| Session metadata (`session_code`: R/P/A) | ✅ |
| Options (`OPT`) symbology normalization | ✅ (basic) |
| Schema version bump if fields added | ✅ |

### Definition of Done — Phase 3

- [ ] `mdrt ingest-bars --provider ib --symbol ES --asset-class future --local-symbol ESZ4 --exchange CME --timeframe 1D` produces correct futures daily bars
- [ ] `adjustment_policy=adjusted` ingest produces dividend-adjusted `close` for SPY
- [ ] Full exchange calendar correctly classifies all NYSE-observed holidays (including Good Friday), early closes, and does not conflate federal holidays with exchange holidays
- [ ] All Phase 1 + 2 DoD criteria still pass

---

## Cross-Phase Constraints

These apply forever, not just Phase 1:

1. **No breaking changes to `NORMALIZED_BAR_SCHEMA`** after Phase 1 ships. New fields require schema version bump and a migration note in `02-data-models.md`
2. **No live network calls in CI** — regardless of provider or phase
3. **No `DROP` or `ALTER` destructive DDL** — new tables/columns use `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`
4. **Provider-agnostic core** — the normalizer, validator, archive writer, catalog, and window builder must work identically regardless of which provider session/collector is plugged in
5. **`use_rth` and `what_to_show` are always explicit** — no default assumptions after data is written; these values travel with every bar from ingestion to window export
6. **Overlap policy is immutable within a phase** — do not change from `replace` to `append` mid-phase; a policy change requires a phase transition and a migration note
7. **`session_date` is always populated** — no bar is ever written without an exchange-local `session_date`
