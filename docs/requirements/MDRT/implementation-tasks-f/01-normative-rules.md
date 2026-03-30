# MDRT Implementation Plan — Section 2: Normative Rules Extracted from Docs

All rules below are directly traceable to the numbered MDRT requirement docs.

---

## Scope (Source: `index.md`, `10-phases.md`)

| Rule | Source |
|------|--------|
| Phase 1: IB only, US equities (`STK`), SMART routing | `index.md` §Scope, `10-phases.md` §Phase 1 |
| Supported timeframes: `1m`, `5m`, `15m`, `1h`, `4h`, `1D`, `1M` | `index.md` §Scope, `02-data-models.md` §2.4 |
| `use_rth=True` only in Phase 1 | `10-phases.md` §Phase 1 |
| `what_to_show=TRADES` only in Phase 1 | `10-phases.md` §Phase 1 |
| `adjustment_policy=raw` only in Phase 1 | `10-phases.md` §Phase 1 |
| Overlap policy: `replace` | `11-overlap-policy.md` §11.3 |
| No Alpaca, Databento, futures, options in Phase 1 | `10-phases.md` §Phase 1 |
| `ib_insync` explicitly prohibited | `index.md` Key Decisions |

## Architecture (Source: `01-architecture.md`)

| Rule | Source |
|------|--------|
| Eight logical layers in strict linear pipeline | `01-architecture.md` §Overview |
| Provider layer split: Session + ContractResolver + Collector (not one ABC) | `01-architecture.md` §A/B/C |
| Raw landing stores provider-native transcripts (not pre-normalized) | `01-architecture.md` §D |
| Normalizer converts provider-native records to NORMALIZED_BAR_SCHEMA | `01-architecture.md` §E |
| Validator is session-aware with gap classification | `01-architecture.md` §F |
| Archive Writer is overlap-aware with replace policy | `01-architecture.md` §G |
| Catalog: 8 DuckDB tables | `01-architecture.md` §H |
| Partition keys: `provider/asset_class/symbol/timeframe/use_rth/what_to_show/year/month` | `01-architecture.md` §Partition Strategy |
| Settings at `src/market_data/config/settings.py`, NOT root `config/` | `01-architecture.md` §Directory Structure |

## Schema / Data Model (Source: `02-data-models.md`)

| Rule | Source |
|------|--------|
| Schema version: v3 | `02-data-models.md` §v3 |
| `session_date`: mandatory for ALL bars (intraday, 1D, 1M) | `02-data-models.md` §2.7 |
| `session_close_ts_utc`: null for intraday, non-null for `1D` and `1M` | `02-data-models.md` §2.7 |
| Daily bar `ts_utc` = session CLOSE time in UTC | `02-data-models.md` §Daily Bar Semantics |
| Monthly bar `ts_utc` = last trading day's session CLOSE | `02-data-models.md` §Monthly Bar Semantics |
| Intraday bar `ts_utc` = bar open time in UTC | `02-data-models.md` §Intraday Bar Semantics |
| `source_tz`: TWS login/session timezone from ProviderSessionInfo | `02-data-models.md` §Bar dataclass |
| Logical bar key: `(provider, asset_class, symbol, timeframe, use_rth, what_to_show, ts_utc)` | `11-overlap-policy.md` §11.2 |
| `request_hash` for idempotency | `11-overlap-policy.md` §11.9 |

## Provider Behavior (Source: `03-adapter-interface.md`)

| Rule | Source |
|------|--------|
| IbSession: connect, wait `nextValidId`, raise `ProviderReadyError` on timeout | `03-adapter-interface.md` §3.1 |
| IbContractResolver: `reqContractDetails()`, cache in instruments table | `03-adapter-interface.md` §3.1a |
| IbHistoricalDataCollector: `reqHistoricalData()`, buffer until `historicalDataEnd` | `03-adapter-interface.md` §3.2 |
| ChunkPlanner: decompose large ranges per timeframe limits | `03-adapter-interface.md` §3.3 |
| PacingCoordinator: 15s delay (`IB_PACING_DELAY_SEC`), track 30-in-10-min limit | `03-adapter-interface.md` §3.3a |
| `formatDate=2` (epoch seconds), but Normalizer must handle YYYYMMDD fallback | `03-adapter-interface.md` §3.2 TRAP 1 |
| IB errors 1100/1102 → `ProviderSessionError`, fail batch immediately | `07-exceptions.md` §7.3 |

## Calendar / Session Behavior (Source: `02-data-models.md`, `04-core-pipeline.md`, `10-phases.md`)

| Rule | Source |
|------|--------|
| Hardcoded NYSE/Nasdaq calendar with exact early close handling | `10-phases.md` §Calendar |
| Early closes (13:00 ET) handled exactly — NOT approximated | `04-core-pipeline.md` TRAP 4 |
| `CALENDAR_APPROXIMATION` only for unscheduled closures | `02-data-models.md` §2.3 |
| NYSE holidays: New Year's, MLK, Presidents', Good Friday, Memorial, Juneteenth, July 4th, Labor Day, Thanksgiving, Christmas | `10-phases.md` §Calendar |
| NYSE OPEN on Veterans Day and Columbus Day (federal holidays, NOT exchange holidays) | `10-phases.md` §Calendar |
| `IB_TWS_LOGIN_TIMEZONE`: config-only, NOT from API | `index.md` Key Decisions |

## CLI (Source: `06-cli.md`)

| Rule | Source |
|------|--------|
| Commands: `ingest-bars`, `resolve-contract`, `build-window`, `list-symbols`, `validate-archive` | `06-cli.md` |
| All broader options documented but annotated with target phase | `06-cli.md` Phase 1 Scope |
| Phase 1 MUST reject unsupported values with clear error message | `06-cli.md` Phase 1 Scope |
| Exit codes: 0=success, 1=validation/window error, 2=provider error, 3=IO/unhandled | `07-exceptions.md` §7.5 |

## Testing (Source: `09-testing.md`)

| Rule | Source |
|------|--------|
| Four tiers: unit, adapter/replay, integration, live (opt-in) | `09-testing.md` §9.1 |
| `CallbackReplaySession` for IB tests (no live connection) | `09-testing.md` §9.2 |
| `mock_settings` autouse fixture to prevent live .env reads | `09-testing.md` conftest |
| No live network calls in CI | `10-phases.md` Cross-Phase #2 |
| `@pytest.mark.ib_live` tests excluded from default run | `09-testing.md` §9.7 |
| ≥85% coverage target | `10-phases.md` DoD |
| Calendar regression tests: Good Friday, Veterans Day, Columbus Day, early closes | `09-testing.md` §Calendar Tests |
| Timeframe coverage tests for all 7 bar sizes | `09-testing.md` §Timeframe Tests |

## Overlap Policy (Source: `11-overlap-policy.md`)

| Rule | Source |
|------|--------|
| Phase 1 policy: `replace` (new wins) | `11-overlap-policy.md` §11.3 |
| Unified Merge: load→prune→merge→write-once (never two files on disk simultaneously) | `11-overlap-policy.md` §11.5 |
| Post-merge duplicate assert before disk write | `11-overlap-policy.md` §11.6 |
| Old `ArchiveFileRecord.superseded_by` = new file ID | `11-overlap-policy.md` §11.7 |
| `request_hash` idempotency: don't re-fetch completed specs | `11-overlap-policy.md` §11.9 |
| `--force` flag bypasses `request_hash` check | `11-overlap-policy.md` §11.9 |

## Non-Goals (Source: `index.md`, `10-phases.md`)

| Rule | Source |
|------|--------|
| No live websocket ingestion | `index.md` Out of Scope |
| No order execution | `index.md` Out of Scope |
| No chart rendering | `index.md` Out of Scope |
| No distributed data lake | `index.md` Out of Scope |
| No breaking schema changes after Phase 1 ships | `10-phases.md` Cross-Phase #1 |
| No destructive DDL | `10-phases.md` Cross-Phase #3 |
