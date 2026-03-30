# MDRT Implementation Plan — Section 6: Executive Implementation Strategy

> **Revision note:** Updated for ticket splits (012A/B, 015A/B) and new tickets (020-022). Total: 22 tickets, 7 audit gates.

## Build Order Rationale

The MDRT pipeline is **strictly linear**: data flows from Provider → Raw → Normalizer → Validator → Archive → Catalog → Window. This means the build order MUST follow the data flow — upstream modules must exist before downstream ones can be tested meaningfully.

However, **foundation modules** (models, schemas, exceptions, configuration, calendar) have no runtime dependencies and should be built first. Then the pipeline is built layer by layer.

---

## Critical Path

```
MDRT-001 (Scaffold)
    ↓
MDRT-002 (Exceptions)    MDRT-003 (Domain Models)    MDRT-004 (Settings)
    ↓                         ↓                            ↓
MDRT-005 (PyArrow Schema + DDL) ★
    ↓
MDRT-006 (Trading Calendar)
    ↓
MDRT-007 (IbSession)
    ↓
MDRT-008 (IbContractResolver)
    ↓
MDRT-009 (ChunkPlanner + PacingCoordinator)
    ↓
MDRT-010 (IbHistoricalDataCollector)
    ↓
MDRT-011 (RawStore)
    ↓
MDRT-012A (Normalizer: Intraday) ★
    ↓
MDRT-012B (Normalizer: Daily/Monthly) ★
    ↓
MDRT-013 (Validator)
    ↓
MDRT-014 (CatalogManager)
    ↓
MDRT-015A (ArchiveWriter: Basic Write)
    ↓
MDRT-015B (ArchiveWriter: Overlap Merge) ★
    ↓
MDRT-016 (IngestionOrchestrator) ★
    ↓
MDRT-017 (CLI: ingest-bars + resolve-contract) ★
    ↓
MDRT-018 (WindowBuilder)
    ↓
MDRT-019 (CLI: build-window + list-symbols + validate-archive)
    ↓
MDRT-020 (Operational docs + .env)
    ↓
MDRT-021 (Integration Tests — full pipeline regression)
    ↓
MDRT-022 (Phase 1 DoD Verification) ★
```

★ = Audit gate

---

## Sequential vs. Parallelizable

### Must Be Sequential (Critical Path)

Every ticket from MDRT-001 through MDRT-022 is on the critical path.
Each ticket depends on at least one upstream ticket.

The **only parallelism** is between foundation tickets MDRT-002, MDRT-003, and MDRT-004 (no dependencies on each other).

### Cannot Be Parallelized

- Pipeline modules (MDRT-010 through MDRT-016): strict data-flow dependency
- Normalizer split (012A → 012B): sequential by design
- ArchiveWriter split (015A → 015B): sequential by design
- CLI (MDRT-017, MDRT-019): depends on the modules they wire
- Integration tests (MDRT-021): depends on everything
- DoD verification (MDRT-022): depends on everything

---

## Audit Gates (7 Total)

After each audit gate ticket, the coding agent must:

1. Run `pytest --cov` for all modules completed so far
2. Verify changed files match the ticket's expected scope
3. Produce audit bundle with test results at the canonical path
4. NOT proceed to the next ticket until the audit gate passes

| Gate | After Ticket | Why |
|------|-------------|-----|
| 1 | MDRT-005 (Schema + DDL) | Schema is the foundation for everything downstream |
| 2 | MDRT-012A (Normalizer: Intraday) | Intraday semantics must be verified before daily/monthly |
| 3 | MDRT-012B (Normalizer: Daily/Monthly) | All normalization semantics must be correct before validation |
| 4 | MDRT-015B (ArchiveWriter: Overlap) | Overlap policy correctness is critical for data integrity |
| 5 | MDRT-016 (Orchestrator) | First end-to-end pipeline wiring — verify all components connect |
| 6 | MDRT-017 (CLI: ingest-bars) | First user-facing command — verify against DoD |
| 7 | MDRT-022 (DoD Verification) | Final Phase 1 DoD checklist — full pass/fail report |

---

## Risk Summary

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| `ibapi` SDK quirks (formatDate, YYYYMMDD fallback) | High | Medium | Explicit TRAP handling in Normalizer (MDRT-012A) |
| IB pacing violations during live tests | Medium | Low | PacingCoordinator + 15s conservative delay |
| Calendar edge cases (early close dates) | Medium | Medium | Hardcoded calendar with regression tests (MDRT-006) |
| Overlap merge producing duplicates | Low | High | Post-merge assert + integration test (MDRT-015B) |
| Schema drift between modules | Low | High | Single source of truth in `schemas.py` (MDRT-005) |
| Daily/monthly bar semantics errors | Medium | High | Normalizer split isolates risk (MDRT-012A then 012B) |
| Late ticket ambiguity | Low | Medium | All tickets now at full template quality |
