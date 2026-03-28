# MDRT — Market Data Retrieval Tool: Requirements Index

## Purpose

This folder holds the **normative requirements** for the Market Data Retrieval Tool (MDRT):
what to build, how acceptance is defined, and how implementation is sequenced.

**As-built / operational documentation** lives under `docs/` (not here).

---

## Document Map

| File | Contents |
|------|----------|
| [`root.md`](root.md) | Original high-level design document — the authoritative source of intent |
| [`01-architecture.md`](01-architecture.md) | System & layer architecture, data flow diagrams (Mermaid), partition strategy |
| [`02-data-models.md`](02-data-models.md) | All domain dataclasses, PyArrow schemas, DuckDB DDL — the complete data contract |
| [`03-adapter-interface.md`](03-adapter-interface.md) | `MarketDataProvider` ABC, adapter contract, both adapter implementations |
| [`04-core-pipeline.md`](04-core-pipeline.md) | Raw landing → Normalizer → Validator → Archive Writer → Catalog Manager specs |
| [`05-window-builder.md`](05-window-builder.md) | Window Builder and Window Orchestrator specs |
| [`06-cli.md`](06-cli.md) | CLI command specs: arguments, flags, execution flows, exit codes |
| [`07-exceptions.md`](07-exceptions.md) | Full custom exception hierarchy |
| [`08-configuration.md`](08-configuration.md) | Settings model, env vars, secrets management rules |
| [`09-testing.md`](09-testing.md) | Test strategy, test matrix, fixtures, acceptance criteria |
| [`10-phases.md`](10-phases.md) | Phased delivery plan: Phase 1 MVP → Phase 2 → Phase 3 |

---

## Scope Summary (Version 1)

**In scope:**
- Historical OHLCV bars only
- One or a few symbols / timeframes at a time
- Provider adapters: Alpaca (bootstrap), Databento (long-term)
- Parquet archive + DuckDB catalog
- Single and batch market window export
- CLI entry point (`mdrt`)

**Out of scope (not in v1):**
- Live websocket ingestion
- Full order book capture
- Execution / broker integration
- Options chains and greeks
- Distributed data lake
- Chart rendering

---

## Stack

| Concern | Technology |
|---------|-----------|
| Language | Python ≥ 3.11 |
| CLI | Typer |
| Storage format | Parquet (via PyArrow) |
| Query / catalog | DuckDB |
| Schema / IO | PyArrow |
| Providers | Alpaca (`alpaca-py`), Databento (`databento`) |
| Settings | Pydantic Settings (env vars, `.env`) |
| Testing | pytest, pytest-cov, pytest-recording |

---

## Phase Overview

| Phase | Goal | Key Deliverables |
|-------|------|-----------------|
| **1 — MVP** | One working ingest + window export | Alpaca adapter, full pipeline, `ingest-bars`, `build-window`, `list-symbols` |
| **2 — Batch** | Batch windowing + integrity reporting | `build-window-batch`, replayable manifests, `validate-archive`, `show-integrity-report` |
| **3 — Richer** | Multi-timeframe, corporate actions, futures symbology | Databento adapter, session metadata, Phase 3 CLI additions |

See [`10-phases.md`](10-phases.md) for per-phase acceptance criteria.
