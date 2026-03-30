# MDRT Implementation Task Pack — Master Index

> **Revision note:** Updated for review feedback. Normalizer split (012A/B), ArchiveWriter split (015A/B),
> late tickets expanded to full template quality, total tickets: 22.
>
> **Revision note (Option B — monorepo):** Tickets and planning docs now match package-local
> `src/market_data/.env.example` and `src/market_data/README.md`, `tests/market_data/conftest.py`,
> **`uv`** / `uv run` for sync, pytest, and CLI, and **`ibapi>=9.81`** as the PyPI baseline in MDRT-001.

This folder contains the complete implementation plan for the Market Data Retrieval Tool (MDRT) Phase 1.

## Document Source
- Generated from the normative MDRT requirement docs (`index.md` + `01-` through `11-` docs)
- Governed by the ticket creation requirements in `requiremnt-for-tickets-creation.md`

## Contents

| File | Section | Contents |
|------|---------|----------|
| [`00-source-map.md`](00-source-map.md) | §1 | Document source map — normative vs. non-normative classification |
| [`01-normative-rules.md`](01-normative-rules.md) | §2 | Key implementation rules extracted from the MDRT docs, grouped by domain |
| [`02-contradictions.md`](02-contradictions.md) | §3 | Open contradictions and ambiguities — all resolved |
| [`03-folder-structure.md`](03-folder-structure.md) | §4 | Repo/folder structure (from `01-architecture.md`) |
| [`04-naming-conventions.md`](04-naming-conventions.md) | §5 | Naming conventions — docs-defined vs. proposed |
| [`05-strategy.md`](05-strategy.md) | §6 | Executive implementation strategy, critical path, audit gates |
| [`06-epics.md`](06-epics.md) | §7 | Five epic breakdown: Foundation, IB Provider, Core Pipeline, Orchestration+CLI, Integration |
| [`07-tickets-001-010.md`](07-tickets-001-010.md) | §8+§12 | First 10 tickets — fully specified with tests, file targets, audit bundles |
| [`08-tickets-011-020.md`](08-tickets-011-020.md) | §8 cont. | Tickets 011–022: pipeline, CLI, integration, DoD — all at full template quality |
| [`09-ticket-order.md`](09-ticket-order.md) | §9 | Exact execution order with dependency graph (22 tickets) |
| [`10-handoff-template.md`](10-handoff-template.md) | §10 | Reusable work-order template for coding agent tickets |
| [`11-anti-drift-rules.md`](11-anti-drift-rules.md) | §11 | 31 anti-drift rules to prevent scope creep and spec divergence |

## Ticket Summary

| ID | Title | Epic | Risk | Audit Gate? |
|----|-------|------|------|-------------|
| MDRT-001 | Project Scaffold | A | Low | No |
| MDRT-002 | Exception Hierarchy | A | Low | No |
| MDRT-003 | Domain Models | A | Low | No |
| MDRT-004 | Settings + conftest | A | Low | No |
| MDRT-005 | PyArrow Schema + DDL | A | Low | **YES** |
| MDRT-006 | Trading Calendar | A | Medium | No |
| MDRT-007 | IbSession | B | Medium | No |
| MDRT-008 | IbContractResolver | B | Low-Med | No |
| MDRT-009 | ChunkPlanner + Pacing | B | Low | No |
| MDRT-010 | IbHistoricalDataCollector | B | Medium | No |
| MDRT-011 | RawStore | C | Low | No |
| MDRT-012A | Normalizer: Intraday | C | Medium | **YES** |
| MDRT-012B | Normalizer: Daily/Monthly | C | Med-High | **YES** |
| MDRT-013 | Validator | C | Medium | No |
| MDRT-014 | CatalogManager | C | Medium | No |
| MDRT-015A | ArchiveWriter: Basic Write | C | Low-Med | No |
| MDRT-015B | ArchiveWriter: Overlap Merge | C | Med-High | **YES** |
| MDRT-016 | IngestionOrchestrator | D | Medium | **YES** |
| MDRT-017 | CLI: ingest-bars + resolve | D | Medium | **YES** |
| MDRT-018 | WindowBuilder | D | Low-Med | No |
| MDRT-019 | CLI: remaining commands | D | Low | No |
| MDRT-020 | Operational docs + .env | D | Low | No |
| MDRT-021 | Integration Tests | E | Low | No |
| MDRT-022 | Phase 1 DoD Verification | E | Low | **YES** |

## How to Use This Pack

1. **Start with the source map** (`00-source-map.md`) to understand which docs are normative
2. **Read the strategy** (`05-strategy.md`) for the critical path and audit gates
3. **Execute tickets in order** from `09-ticket-order.md`
4. **Use the handoff template** (`10-handoff-template.md`) for each coding agent work order
5. **Follow anti-drift rules** (`11-anti-drift-rules.md`, 31 rules) on every ticket
6. **STOP at audit gates** (7 total) and wait for review before continuing
