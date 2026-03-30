# MDRT — Market Data Retrieval Tool: Requirements Index

> **Revision note (req-review-01):** Architecture revised for IB-first implementation.
> Provider layer split into Session + ContractResolver + HistoricalDataCollector.
> Phase 1 is IB-first MVP (not Alpaca-first). New document: `11-overlap-policy.md`.
>
> **Revision note (req-review-02):** Five remaining spec defects addressed:
> (1) IB pacing rules corrected; `IB_PACING_DELAY_SEC` default changed to 15s.
> (2) `serverVersion()` removed as timezone source; `IB_TWS_LOGIN_TIMEZONE` (renamed from `IB_HOST_TIMEZONE`) is config-only.
> (3) Daily bar convention changed to session close; schema bumped v2 → v3.
> (4) Phase 1 calendar limitation explicitly labelled.
> (5) `instrument_id` wording corrected to provider-scoped MDRT registry ID.
>
> **Revision note (combined-review):** Final cleanup pass before implementation handoff:
> (1) `session_date` made mandatory for ALL bars (not just daily).
> (2) Daily bar semantics: `session_date` is the universal session identity; `session_close_ts_utc` is the explicit close marker.
> (3) Restart window wording made user-configurable (not hardcoded).
> (4) Read-Only API claim narrowed — acceptable for data-only MDRT.
> (5) Phase 1 calendar limitations called out in `02-data-models.md`, `04-core-pipeline.md`, `10-phases.md`.
> (6) Per-module acceptance criteria added to `10-phases.md`.
>
> **Revision note (final-review):** Three correctness fixes:
> (1) **CRITICAL:** `11-overlap-policy.md` §11.5 rewritten — old algorithm wrote pruned data to disk then merged, causing archive duplication. Replaced with Unified Merge (load→prune→merge→write-once).
> (2) Epoch timestamp in `09-testing.md` transcript fixture corrected: `1704196200` (11:50 UTC) → `1704205800` (14:30 UTC = 09:30 ET NYSE open).
> (3) `mock_settings` autouse fixture added to `09-testing.md` conftest to enforce `.env` isolation.
>
> **Revision note (truth-pass):** Final truth-and-consistency pass:
> (1) Calendar model corrected: "federal holidays" replaced with NYSE/Nasdaq trading calendar (full closures incl. Good Friday + known early closes). NYSE is NOT a federal-holiday calendar.
> (2) Timezone renamed: `host_timezone` / `IB_HOST_TIMEZONE` → `tws_login_timezone` / `IB_TWS_LOGIN_TIMEZONE` to clarify this is the TWS session timezone, not the machine/OS timezone.
> (3) `session_date` consistency verified pack-wide.
> (4) Calendar correctness tests added (Good Friday, Veterans Day, early closes).
> (5) ML/research approximation-day handling rule added.
>
> **Revision note (scope-pass):** Scope and final unification:
> (1) Supported timeframes expanded: `1m, 5m, 15m, 1h, 4h, 1D, 1M` — all promoted to Phase 1.
> (2) Calendar behavior unified to ONE truth: early closes are handled **exactly** (13:00 ET), not approximately. `CALENDAR_APPROXIMATION` now only fires for unscheduled closures.
> (3) Monthly bar semantics defined: `session_date` = last trading day of month, `session_close_ts_utc` required.
> (4) Timeframe coverage tests added for all 7 bar sizes.
> (5) `1d` renamed to `1D` for disambiguation from `1m` (minute) / `1M` (month).

## Purpose

This folder holds the **normative requirements** for the Market Data Retrieval Tool (MDRT):
what to build, how acceptance is defined, and how implementation is sequenced.

**As-built / operational documentation** lives under `docs/` (not here).

---

## Document Map

| File | Status | Contents |
|------|--------|----------|
| [`root.md`](root.md) | ⚠️ Superseded | **Historical background only** — original pre-IB concept document. Superseded by all numbered requirements below. Do NOT treat as normative or authoritative. Conflicts with current IB-first architecture |
| [`req-review-01.md`](req-review-01.md) | ✅ Reference | IB-first architecture audit — drove all revisions in session 1 |
| [`req-review-02.md`](req-review-02.md) | ✅ Reference | Pacing/timezone/daily-bar/calendar/instrument_id audit — drove final corrections |
| [`01-architecture.md`](01-architecture.md) | 🔄 Revised | System & layer architecture, IB-first provider split, data flow diagrams, partition strategy |
| [`02-data-models.md`](02-data-models.md) | 🔄 Revised | Full domain models (Instrument, Bar, RequestSpec, ProviderSessionInfo, ContractResolutionRecord, ArchiveFileRecord), PyArrow schema **v3** (+ session_date, session_close_ts_utc), DuckDB DDL |
| [`03-adapter-interface.md`](03-adapter-interface.md) | 🔄 Revised | Three-component ABCs; IbSession/IbContractResolver/IbHistoricalDataCollector; **PacingCoordinator** (§3.3a); corrected IB pacing rules |
| [`04-core-pipeline.md`](04-core-pipeline.md) | 🔄 Revised | Raw Store (transcript format), Normalizer (IB field mapping, source-tz conversion), Validator (session-aware gap classification), Archive Writer (overlap-aware), Catalog Manager (extended), Orchestrator (three-component wiring) |
| [`05-window-builder.md`](05-window-builder.md) | 🔄 Minor revision | Window Builder + Orchestrator, `use_rth`/`what_to_show` catalog filter, export formats |
| [`06-cli.md`](06-cli.md) | 🔄 Revised | All commands with IB flags; new `resolve-contract` command |
| [`07-exceptions.md`](07-exceptions.md) | 🔄 Revised | Full exception hierarchy including IB session + contract exceptions |
| [`08-configuration.md`](08-configuration.md) | 🔄 Revised | IB connection config, IB port reference, operational prerequisites |
| [`09-testing.md`](09-testing.md) | 🔄 Revised | Four-tier test strategy, CallbackReplaySession, IB transcript fixtures, live IB test tier |
| [`10-phases.md`](10-phases.md) | 🔄 Revised | Phase 1 = IB-first MVP (restricted scope + DoD checklist), Phase 2 = REST providers + batch, Phase 3 = futures/adjusted |
| [`11-overlap-policy.md`](11-overlap-policy.md) | 🆕 New | Logical bar key, replace policy, overlap detection, dedupe, catalog lineage, idempotency |

---

## Scope Summary (Version 1 — IB-First MVP)

**In scope (Phase 1):**
- IB (Interactive Brokers) as primary provider via official `ibapi` SDK
- US equity bars only (`STK`, SMART routing)
- All 7 supported timeframes (`1m`, `5m`, `15m`, `1h`, `4h`, `1D`, `1M`)
- `use_rth=True`, `what_to_show=TRADES` only
- `adjustment_policy=raw` only
- Parquet archive + DuckDB catalog
- Single market window export (JSONL + Parquet)
- CLI: `ingest-bars`, `resolve-contract`, `build-window`, `list-symbols`, `validate-archive`

**Out of scope (Phase 1):**
- Alpaca, Databento adapters (Phase 2)
- Batch window export (Phase 2)
- `use_rth=False` / extended hours (Phase 2)
- Futures, options, forex asset classes (Phase 3)
- Adjusted prices (Phase 3)
- Live websocket ingestion (never in v1)
- Order execution, chart rendering, distributed data lake (never in v1)

---

## Stack

| Concern | Technology |
|---------|-----------|
| Language | Python ≥ 3.11 |
| IB SDK | `ibapi` (official TWS API — not `ib_insync`) |
| CLI | Typer |
| Storage format | Parquet via PyArrow |
| Query / catalog | DuckDB |
| Schema / IO | PyArrow |
| REST providers (Phase 2) | `alpaca-py`, `databento` |
| Settings | Pydantic Settings (env vars, `.env`) |
| Testing | pytest, pytest-cov; `CallbackReplaySession` for IB; `pytest-recording` for REST |

---

## Key Design Decisions (Normative)

| Decision | Ruling |
|----------|--------|
| IB SDK | Use `ibapi` (official). `ib_insync` is archived and not maintained |
| Provider layer structure | Split: Session + ContractResolver + Collector (not one ABC) |
| Adapter return type | Provider-native records (raw); normalizer converts |
| `use_rth` + `what_to_show` | Partition keys AND catalog filter keys — never mixed |
| Overlap policy v1 | `replace`: newer ingest wins for overlapping bars |
| Archive dedup guarantee | Post-merge duplicate assert before every disk write |
| IB pacing | MDRT conservative: 15s inter-chunk delay minimum. See §3.3a for full IB pacing rules |
| IB TWS login timezone | Config-only via `IB_TWS_LOGIN_TIMEZONE` — NOT the machine/OS timezone; it is the timezone selected on the TWS/Gateway login screen |
| Daily bar `ts_utc` | Session CLOSE time in UTC (not open). `session_date` + `session_close_ts_utc` also stored |
| `session_date` | **Mandatory for ALL bars** (intraday, `1D`, and `1M`). Exchange-local trading date. Never null |
| Schema version | v3 — `session_date` NOT NULL, `session_close_ts_utc` nullable (non-null for `1D` and `1M`) |
| Phase 1 calendar | Hardcoded NYSE/Nasdaq full closures + **exact** early closes (13:00 ET). `CALENDAR_APPROXIMATION` only for unscheduled closures |
| Supported timeframes | `1m`, `5m`, `15m`, `1h`, `4h`, `1D`, `1M` — all in Phase 1 |
| `instrument_id` scope | Provider-scoped MDRT registry ID. SPY@IB ≠ SPY@Alpaca — two separate rows |
| IB restart window | User-configurable; MDRT must not schedule ingestion during operator's configured window |
| Read-Only API | Acceptable for MDRT (data-only). Must be unchecked if future order workflows are added |
| Re-execution idempotency | `request_hash` prevents re-fetch of identical completed specs |
| ib_insync | Explicitly prohibited |

---

## Phase Overview

| Phase | Goal | Primary Provider | Key CLI Commands |
|-------|------|-----------------|-----------------|
| **1 — IB MVP** | One working IB ingest + window export | IB only | `ingest-bars`, `resolve-contract`, `build-window`, `list-symbols`, `validate-archive` |
| **2 — Batch + REST** | Batch windowing + REST providers + integrity | IB + Alpaca + Databento | + `build-window-batch`, `show-integrity-report` |
| **3 — Futures/Richer** | Futures, adjusted prices, full calendar | All providers | Phase 3 CLI additions |

See [`10-phases.md`](10-phases.md) for per-phase DoD checklists and **per-module acceptance criteria**.
See [`11-overlap-policy.md`](11-overlap-policy.md) for the full overlap and deduplication specification.
