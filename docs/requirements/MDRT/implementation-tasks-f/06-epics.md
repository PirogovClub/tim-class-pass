# MDRT Implementation Plan — Section 7: Epic Breakdown

> **Revision note:** Updated for ticket splits (012A/B, 015A/B) and new tickets (020-022). Total: 22 tickets across 5 epics.

---

## EPIC-A: Project Foundation

- **Epic ID:** EPIC-A
- **Title:** Project Foundation — Scaffold, Models, Configuration, Exceptions
- **Goal:** Create the project skeleton with all foundation modules that have no runtime dependencies
- **Why it matters:** Every downstream module imports from models, schemas, settings, and exceptions. Without this, nothing compiles
- **Source docs:** `01-architecture.md` (directory structure, pyproject.toml), `02-data-models.md` (models, schema), `07-exceptions.md` (exception hierarchy), `08-configuration.md` (settings)
- **Dependencies:** None
- **Risks:** Low. These are pure data structures with no provider interaction
- **Exit criteria:** `pyproject.toml` installable, all dataclasses importable, schema validates sample data, settings load from env, all exceptions importable, trading calendar passes regression tests

**Tickets:** MDRT-001, MDRT-002, MDRT-003, MDRT-004, MDRT-005, MDRT-006

---

## EPIC-B: IB Provider Layer

- **Epic ID:** EPIC-B
- **Title:** IB Provider Layer — Session, Resolver, Collector, Pacing
- **Goal:** Implement the three-component IB provider split (Session + ContractResolver + Collector) with ChunkPlanner and PacingCoordinator
- **Why it matters:** All data enters the system through the provider layer. Without it, no bars can be fetched
- **Source docs:** `03-adapter-interface.md` (ABCs, IB implementations, pacing rules, chunk planner), `07-exceptions.md` (IB-specific exceptions), `09-testing.md` (CallbackReplaySession, transcript fixtures)
- **Dependencies:** EPIC-A (models, schemas, exceptions, settings)
- **Risks:** Medium. `ibapi` SDK has known quirks (formatDate, callback structure). CallbackReplaySession must be implemented correctly for offline testing
- **Exit criteria:** IbSession connects and returns ProviderSessionInfo; IbContractResolver resolves SPY and caches in-memory dict; IbHistoricalDataCollector fetches bars via replay session; ChunkPlanner produces correct chunks for all 7 timeframes; PacingCoordinator enforces 15s delays

**Tickets:** MDRT-007, MDRT-008, MDRT-009, MDRT-010

---

## EPIC-C: Core Pipeline

- **Epic ID:** EPIC-C
- **Title:** Core Pipeline — Raw Store, Normalizer, Validator, Archive, Catalog
- **Goal:** Implement the data transformation pipeline from raw provider records to validated Parquet archive with DuckDB catalog
- **Why it matters:** This is where data semantics are enforced — timezone conversion, session_date, schema conformance, gap classification, overlap resolution
- **Source docs:** `04-core-pipeline.md` (all pipeline modules), `02-data-models.md` (schema), `11-overlap-policy.md` (overlap/merge)
- **Dependencies:** EPIC-A (models, schemas), EPIC-B (collector output format)
- **Risks:** Medium-High. Normalizer must handle IB formatDate quirks (split into 012A/012B for safety). Validator must correctly classify calendar gaps. ArchiveWriter must implement Unified Merge without duplicates (split into 015A/015B for safety)
- **Exit criteria:** RawStore persists and loads transcripts; Normalizer produces v3-conforming tables for all 7 timeframes including daily/monthly edge cases; Validator catches all hard errors and classifies gaps correctly; ArchiveWriter handles overlaps via Unified Merge; CatalogManager manages all 8 tables

**Tickets:** MDRT-011, MDRT-012A, MDRT-012B, MDRT-013, MDRT-014, MDRT-015A, MDRT-015B

---

## EPIC-D: Orchestration + CLI

- **Epic ID:** EPIC-D
- **Title:** Orchestration, CLI, and Operational Documentation
- **Goal:** Implement IngestionOrchestrator, WindowBuilder, all CLI commands, and operational docs
- **Why it matters:** This is what the user actually runs. Without it, the pipeline modules exist but cannot be invoked
- **Source docs:** `04-core-pipeline.md` (orchestrator), `05-window-builder.md` (window builder), `06-cli.md` (all commands), `08-configuration.md` (operational docs)
- **Dependencies:** EPIC-B (provider), EPIC-C (pipeline), EPIC-A (all foundation)
- **Risks:** Medium. Orchestrator must wire error handling correctly (try/except for ProviderSessionError). CLI must enforce Phase 1 scope restrictions
- **Exit criteria:** All 5 CLI commands work. `ingest-bars` completes full pipeline. `build-window` exports correct windows. `resolve-contract` prints conId. `list-symbols` queries catalog. `validate-archive` runs checks. `.env.example` finalized. README has operational prerequisites

**Tickets:** MDRT-016, MDRT-017, MDRT-018, MDRT-019, MDRT-020

---

## EPIC-E: Integration + DoD Verification

- **Epic ID:** EPIC-E
- **Title:** Integration Tests and Phase 1 DoD Verification
- **Goal:** Run end-to-end integration tests and verify every Phase 1 DoD checklist item from `10-phases.md`
- **Why it matters:** This proves the system works as a whole, not just as isolated modules. The DoD verification is the final gate before the system is declared "done"
- **Source docs:** `09-testing.md` (integration tests, calendar tests, timeframe tests), `10-phases.md` (DoD checklist), `11-overlap-policy.md` (acceptance criteria)
- **Dependencies:** All of EPIC-A through EPIC-D
- **Risks:** Low. By this point all modules are tested individually. Integration tests verify wiring. No production code changes allowed — only test code and verification artifacts
- **Exit criteria:** All Phase 1 DoD items checked. ≥85% coverage. All calendar regression tests pass. All 7 timeframe tests pass. Overlap acceptance criteria pass. Final pass/fail summary produced

**Tickets:** MDRT-021, MDRT-022
