# Stage 6.4 — Rule browser / analyst tooling

## Purpose

Stage 6.4 expands the read-only **analyst browser** on top of the Stage 6.3 hybrid RAG stack and existing `/browser` explorer API. It does **not** add new extraction, adjudication writes, or ML training.

## Pages and routes

| Route | Role |
|-------|------|
| `/search` | Primary hybrid search: URL-synced query and filters, hit scores, “why retrieved”, multi-unit compare selection, **Explain retrieval** (`POST /rag/search/explain`). |
| `/rag` | Stable alias → redirects to `/search`. |
| `/rule/:docId` | Rule detail (text, evidence, events, related rules, **provenance**). |
| `/evidence/:docId` | Evidence detail (linked rules/events, **provenance**). |
| `/event/:docId` | **Knowledge event** detail (linked evidence/rules/events, **provenance**). |
| `/concept/:conceptId` | Concept graph summary, aliases, top rules/events, lessons. |
| `/lesson/:lessonId` | Grouped top rules, **knowledge events**, evidence, concepts. |
| `/compare/units` | Side-by-side compare for **2–4** retrieval units (mixed types via `POST /browser/compare/units`). |
| `/compare/rules`, `/compare/lessons` | Preserved rule-only and lesson-only compares. |

## Backend additions

- `GET /browser/event/{doc_id}` — `knowledge_event` detail payload.
- `POST /browser/compare/units` — mixed-type compare rows (`UnitCompareRequest` / `UnitCompareResponse`).
- Explorer search now passes **`concept_ids`** into the hybrid retriever (fixes filtered search with concept facets).
- `RuleDetailResponse`, `EvidenceDetailResponse`, and event payloads include a **`provenance`** object when present on stored docs.
- `LessonDetailResponse` includes **`top_events`**.

## Workflows

1. **Search → detail**: from `/search`, open rule, evidence, event, concept, or lesson via result links.
2. **Compare**: use **Add to unit compare** on result cards (or build selection elsewhere), then **Compare selected (N)** → `/compare/units`.
3. **Explain**: enter a query and click **Explain retrieval** to view lexical / vector / graph trace from `/rag/search/explain`.

## Limitations

- Multi-unit compare is stored in **`sessionStorage`** while browsing; use **Copy compare link** on `/compare/units` (or hand-build `?units=` JSON) to share a set.
- Frame image requests still proxy to the API server; offline e2e may log proxy errors without failing the page.
- `ConceptPage` still fetches neighbors from the live API unless mocked (e2e mocks this).

## Test strategy

- **Python**: `tests/explorer/test_api.py` covers event detail, unit compare, lesson `top_events`, provenance keys on detail payloads, and error paths.
- **Vitest**: page and component tests under `ui/explorer/src`.
- **Playwright (mock)**: `tests/e2e/stage6-4-audit-screenshots.spec.ts` — build + preview + mocked `/browser/*` JSON → `stage6-4-screenshots-out/` (bundle: `screenshots/mock/`).
- **Playwright (live)**: `tests/e2e/stage6-4-live-audit-screenshots.spec.ts` — no mocks; `vite preview` proxies to `VITE_BROWSER_API_BASE` → `stage6-4-screenshots-live-out/` (bundle: `screenshots/live/`). Requires `STAGE64_LIVE_E2E=1` and a running API.
- **Audit examples**: `scripts/stage64_browser_example_capture.py` discovers ids from live `TestClient` search/rule chain when packaging with `output_rag` (see `RUN_STAGE6_4_AUDIT.md`).
