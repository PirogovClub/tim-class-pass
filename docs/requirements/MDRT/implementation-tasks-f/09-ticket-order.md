# MDRT Implementation Plan — Section 9: Recommended Ticket Order

> **Revision note:** Updated for ticket splits (012A/B, 015A/B) and new tickets (021, 022).
> Total: 22 tickets.

## Exact Execution Order

| Order | Ticket | Title | Blocker? | Audit Gate? | Can Parallelize? |
|-------|--------|-------|----------|-------------|------------------|
| 1 | MDRT-001 | Project Scaffold | YES | No | No — must be first |
| 2 | MDRT-002 | Exception Hierarchy | No | No | YES — with 003, 004 |
| 3 | MDRT-003 | Domain Models | No | No | YES — with 002, 004 |
| 4 | MDRT-004 | Settings + conftest | No | No | YES — with 002, 003 |
| 5 | MDRT-005 | PyArrow Schema + DDL | YES | **YES** ⚠️ | No — depends on 003 |
| 6 | MDRT-006 | Trading Calendar | No | No | YES — with 005 |
| 7 | MDRT-007 | IbSession | No | No | No |
| 8 | MDRT-008 | IbContractResolver | No | No | No |
| 9 | MDRT-009 | ChunkPlanner + Pacing | No | No | YES — with 007, 008 |
| 10 | MDRT-010 | IbHistoricalDataCollector | No | No | No |
| 11 | MDRT-011 | RawStore | No | No | YES — with 010 |
| 12 | MDRT-012A | Normalizer: Intraday | YES | **YES** ⚠️ | No |
| 13 | MDRT-012B | Normalizer: Daily/Monthly | YES | **YES** ⚠️ | No |
| 14 | MDRT-013 | Validator | No | No | No |
| 15 | MDRT-014 | CatalogManager | No | No | YES — with 013 |
| 16 | MDRT-015A | ArchiveWriter: Basic Write | No | No | No |
| 17 | MDRT-015B | ArchiveWriter: Overlap Merge | YES | **YES** ⚠️ | No |
| 18 | MDRT-016 | IngestionOrchestrator | YES | **YES** ⚠️ | No |
| 19 | MDRT-017 | CLI: ingest-bars + resolve | YES | **YES** ⚠️ | No |
| 20 | MDRT-018 | WindowBuilder | No | No | No |
| 21 | MDRT-019 | CLI: remaining commands | No | No | No |
| 22 | MDRT-020 | Operational docs + .env | No | No | No |
| 23 | MDRT-021 | Integration Tests | No | No | No |
| 24 | MDRT-022 | Phase 1 DoD Verification | YES | **YES** ⚠️ | No |

---

## Dependency Graph (Simplified)

```
001 ──┬── 002 ──┐
      ├── 003 ──┼── 005 ★ ── 012A ★ ── 012B ★ ── 013 ──┐
      └── 004 ──┘     │                                   ├── 015A ── 015B ★ ── 016 ★ ── 017 ★
                      006 ──────────── 012B                │
                                                           014 ──┘
                007 ── 008 ──┐                                    018 ── 019
                             ├── 010 ── 011                       │
                009 ─────────┘                              020   021 ── 022 ★
```

★ = Audit gate — implementation MUST stop and be reviewed before continuing.

---

## Audit Gate Rules

At each audit gate, the coding agent must:

1. Run `uv run pytest --cov` and confirm all tests pass
2. Produce audit bundle in `docs/requirements/MDRT/implementation-tasks-f/audit-bundles/mdrt-NNN/`
3. Confirm changed files match ticket scope
4. **STOP AND WAIT** for reviewer approval before starting next ticket

**Do NOT skip audit gates.** If a gate fails, fix the issues before continuing.

---

## Audit Gates (Summary)

| Gate | After Ticket | Why |
|------|-------------|-----|
| 1 | MDRT-005 | Schema is the foundation for everything downstream |
| 2 | MDRT-012A | Intraday normalization must be verified before daily/monthly |
| 3 | MDRT-012B | All normalization semantics must be correct before validation |
| 4 | MDRT-015B | Overlap merge correctness is critical for data integrity |
| 5 | MDRT-016 | First end-to-end pipeline — verify orchestrator wiring |
| 6 | MDRT-017 | First CLI command — verify user-facing behavior |
| 7 | MDRT-022 | Final Phase 1 DoD verification |

---

## Parallelization Notes

In practice, tickets will likely be executed sequentially. The "Can Parallelize" column is informational — it indicates tickets that have no dependency between them, so a second coding agent _could_ work on them simultaneously. For a single-agent flow, execute in the listed order.
