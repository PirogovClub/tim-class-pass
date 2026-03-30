# MDRT Implementation Plan — Section 4: Repo/Folder Structure

## Source: `01-architecture.md` (Authoritative)

The directory structure below is defined by the normative architecture doc.
All implementation tickets MUST place code in these exact locations.

```
market_data/                              # Project root
├── pyproject.toml                        # Package definition, deps, entry point
├── README.md                             # Project overview + operational prereqs
├── .env.example                          # IB connection config template
│
├── src/                                  # SOURCE CODE
│   └── market_data/                      # Python package root
│       ├── __init__.py
│       ├── cli/                          # CLI commands
│       │   ├── __init__.py
│       │   └── main.py                   # Typer app: ingest-bars, build-window, etc.
│       ├── adapters/                     # Provider layer
│       │   ├── __init__.py
│       │   ├── base.py                   # Re-exports: ProviderSession, ContractResolver, HistoricalDataCollector ABCs
│       │   ├── session.py               # ProviderSession ABC + IbSession
│       │   ├── contract_resolver.py     # ContractResolver ABC + IbContractResolver
│       │   ├── collector.py             # HistoricalDataCollector ABC + IbHistoricalDataCollector
│       │   ├── pacing.py                # PacingCoordinator
│       │   ├── chunk_planner.py         # IB request chunk planning logic
│       │   └── ib_adapter.py            # IB: wires Session + Resolver + Collector
│       ├── core/                         # Core pipeline
│       │   ├── __init__.py
│       │   ├── orchestrator.py          # IngestionOrchestrator + WindowOrchestrator
│       │   ├── normalizer.py            # IB field mapping, tz conversion
│       │   ├── validator.py             # Session-aware validation + gap classification
│       │   ├── raw_store.py             # JSONL.GZ transcript persistence
│       │   ├── archive_writer.py        # Overlap-aware Parquet writer
│       │   ├── catalog.py               # DuckDB catalog manager
│       │   ├── window_builder.py        # Window extraction + export
│       │   └── trading_calendar.py      # NYSE/Nasdaq hardcoded calendar ★
│       ├── models/                       # Domain models + schemas
│       │   ├── __init__.py
│       │   ├── domain.py                # All dataclasses (Bar, Instrument, RequestSpec, etc.)
│       │   ├── schemas.py               # PyArrow NORMALIZED_BAR_SCHEMA v3
│       │   └── catalog_sql.py           # DuckDB DDL statements
│       ├── config/                       # Configuration
│       │   ├── __init__.py
│       │   └── settings.py              # Pydantic Settings (CANONICAL location)
│       └── exceptions.py                # Full exception hierarchy
│
├── data/                                 # Runtime data (GITIGNORED)
│   ├── raw/                             # Provider transcripts
│   │   └── provider=ib/symbol=.../batch_id=.../chunk_N_transcript.jsonl.gz
│   ├── archive/                         # Partitioned Parquet archive
│   │   └── provider=ib/asset_class=equity/symbol=.../timeframe=.../...
│   └── catalog.duckdb                   # Metadata catalog
│
├── outputs/                              # Exports (GITIGNORED)
│   ├── windows/                         # Window export files
│   ├── integrity_reports/               # Validation reports
│   └── manifests/                       # Ingestion manifests
│
├── tests/                                # TEST CODE
│   ├── conftest.py                      # mock_settings autouse fixture
│   ├── unit/                            # Unit tests per module
│   │   ├── test_domain.py
│   │   ├── test_schemas.py
│   │   ├── test_settings.py
│   │   ├── test_exceptions.py
│   │   ├── test_chunk_planner.py
│   │   ├── test_pacing.py
│   │   ├── test_normalizer.py
│   │   ├── test_validator.py
│   │   ├── test_trading_calendar.py
│   │   ├── test_archive_writer.py
│   │   ├── test_catalog.py
│   │   ├── test_raw_store.py
│   │   └── test_window_builder.py
│   ├── integration/                     # Integration / orchestrator tests
│   │   ├── test_ingest_pipeline.py
│   │   └── test_cli.py
│   └── adapters/                        # Provider-specific tests
│       ├── transcripts/                 # IB callback transcript fixtures
│       │   ├── spy_1m_2024_01_03.jsonl
│       │   └── spy_1D_2024_01_normal_close.jsonl
│       └── test_ib_session.py
│
└── docs/                                 # Documentation
    └── requirements/
        └── MDRT/                        # Normative requirement docs
            └── implementation-tasks-f/  # THIS planning output
```

### ★ Recommendation Beyond Current Docs

`trading_calendar.py` at `src/market_data/core/trading_calendar.py` is not explicitly listed in the directory tree in `01-architecture.md`, but is required by the calendar specification in `04-core-pipeline.md` and `10-phases.md`. The Validator and Normalizer both reference `TradingCalendar`. This is the recommended location.

---

## Area Purposes

| Area | Purpose |
|------|---------|
| `src/market_data/` | All production Python code. Every module has a defined file in `01-architecture.md` |
| `tests/` | All test code. Mirrors code structure with `unit/`, `integration/`, `adapters/` |
| `tests/adapters/transcripts/` | IB callback replay fixtures (JSONL) for `CallbackReplaySession` |
| `data/` | Runtime-generated data (gitignored). Parquet archive, raw transcripts, DuckDB catalog |
| `outputs/` | Runtime-generated exports (gitignored). Windows, reports, manifests |
| `docs/requirements/MDRT/` | Normative requirement docs |
| `docs/requirements/MDRT/implementation-tasks-f/` | Implementation plan and ticket docs (this output) |

---

## Audit Artifacts

> **Recommendation beyond current docs:** The docs do not define an audit bundle structure.
> The following is proposed for per-ticket audit evidence.

```
docs/requirements/MDRT/implementation-tasks-f/
├── audit-bundles/
│   ├── mdrt-001/
│   │   ├── summary.md
│   │   ├── changed-files.txt
│   │   ├── test-results.txt
│   │   └── artifacts-manifest.json
│   ├── mdrt-002/
│   └── ...
```
