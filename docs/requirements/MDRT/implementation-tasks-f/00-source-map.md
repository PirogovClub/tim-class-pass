# MDRT Implementation Plan — Section 1: Document Source Map

## Normative Status Declaration

Per `index.md`, the normative hierarchy is:

1. **`index.md`** — master index, scope summary, key design decisions, stack, phase overview
2. **Numbered requirement docs (`01-` through `11-`)** — authoritative implementation specs
3. **`root.md`** — ⚠️ SUPERSEDED. Historical background only. Conflicts with IB-first architecture
4. **`req-review-01.md`** and **`req-review-02.md`** — reference only. Record of review decisions that drove revisions

**Conflict resolution rule:** If `root.md` or `req-review-*.md` contradict any numbered requirement doc, the numbered doc wins.

---

## Source Map

| File | Role | Normative? | Governs |
|------|------|-----------|---------|
| `index.md` | Master index | **YES** | Scope, stack, key decisions, phase overview, doc hierarchy |
| `01-architecture.md` | System architecture | **YES** | Layer responsibilities, directory structure, partition strategy, dependency list, data flow diagrams |
| `02-data-models.md` | Domain models + schema | **YES** | All dataclasses (Bar, Instrument, RequestSpec, ProviderSessionInfo, etc.), PyArrow v3 schema, DuckDB DDL, timeframe strings, session_date rules, calendar model, ML guidance |
| `03-adapter-interface.md` | Provider layer ABCs + IB implementation | **YES** | ProviderSession/ContractResolver/Collector ABCs, IbSession, IbContractResolver, IbHistoricalDataCollector, ChunkPlanner, PacingCoordinator, IB callback mapping, IB pacing rules |
| `04-core-pipeline.md` | Core pipeline modules | **YES** | RawStore, Normalizer, Validator, ArchiveWriter, CatalogManager, Orchestrator, TradingCalendar, gap classification |
| `05-window-builder.md` | Window extraction | **YES** | WindowBuilder, WindowOrchestrator, JSONL/Parquet export, catalog query, acceptance criteria |
| `06-cli.md` | CLI specification | **YES** | All CLI commands (ingest-bars, resolve-contract, build-window, list-symbols, validate-archive), flags, examples, exit codes |
| `07-exceptions.md` | Exception hierarchy | **YES** | Full exception class tree, IB error code mapping, CLI exit code mapping |
| `08-configuration.md` | Settings model | **YES** | Pydantic Settings, env vars, .env.example, IB connection config, operational prerequisites |
| `09-testing.md` | Test strategy | **YES** | Four-tier test strategy, CallbackReplaySession, transcript fixtures, test tables per module, mock_settings, calendar regression tests, timeframe coverage tests |
| `10-phases.md` | Phased delivery plan | **YES** | Phase 1/2/3 scope, DoD checklists, per-module acceptance criteria, calendar specification, cross-phase constraints |
| `11-overlap-policy.md` | Overlap and deduplication | **YES** | Logical bar key, replace policy, overlap detection SQL, Unified Merge algorithm, catalog lineage, request_hash idempotency |
| `root.md` | Historical background | **NO** | Pre-IB concept. Superseded. Do NOT implement from this |
| `req-review-01.md` | Review record | **NO** | IB-first architecture audit. Reference only |
| `req-review-02.md` | Review record | **NO** | Pacing/timezone/daily-bar audit. Reference only |

---

## Folder Structure Already Defined by the Docs

`01-architecture.md` defines the authoritative directory structure at lines 215–278.
This is the structure all tickets MUST follow. See Section 4 for the full layout.

## Naming Rules Already Defined by the Docs

- **Python modules**: lowercase `snake_case` — defined by directory tree in `01-architecture.md`
- **Test directories**: `tests/unit/`, `tests/integration/`, `tests/adapters/` — defined in `01-architecture.md`
- **Fixture directories**: `tests/adapters/transcripts/`, `tests/adapters/cassettes/` — defined in `01-architecture.md`
- **Data paths**: defined in `01-architecture.md` and `10-phases.md`
- **Ticket IDs**: NOT defined by the docs — proposed in this plan (Section 5)
- **Audit bundle naming**: NOT defined by the docs — proposed in this plan (Section 5)
