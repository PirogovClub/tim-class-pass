# Step 4.3 — Comparison & traversal — audit handoff

This document satisfies the structure in `docs/requirements/rag/4-3-audit.md`. **Raw command transcripts** live in `AUDIT_VALIDATION_OUTPUT.txt` (same folder). **Explicit paths** live in `AUDIT_FILE_LIST_STEP43.md`. **Index:** [`README.md`](README.md).

---

## 1) Step / substep

- **Step 4.3** — Compare (rules & lessons) and traversal (related rules, concept-scoped rules/lessons) on top of the accepted Step 4.2 explorer read model.

---

## 2) What changed (summary)

- **Backend:** New Pydantic contracts, repository helpers, view builders, `ExplorerService` methods, and FastAPI routes under `/browser/*` for compare and traversal. Search post-processing preserves the **timeframe + rules** Step 3.1 ordering guarantee (see regression test below).
- **Frontend:** New routes and pages for rule/lesson compare, related rules, and concept rules/lessons; URL-driven `?ids=` compare state; session-backed selection with a global compare launch bar; traversal links from rule and concept detail; Zod schemas, API client, React Query hooks; Vitest + Playwright coverage.
- **Docs:** `docs/step4_explorer_contracts.md` and `docs/step4_explorer_notes.md` updated for new endpoints and behavior.

---

## 3) Files added or modified

The **complete path list** is in `AUDIT_FILE_LIST_STEP43.md`. **Source code** is in the repository at those paths (this handoff does not duplicate full file contents).

---

## 4) Known limitations & deferred work

- **No write-back:** Compare selection is convenience state; shareable state is the URL. No server-side analyst notes or persistence.
- **No graph visualization, export pipelines, or auth.**
- **Compare cap:** Up to four IDs per entity type in the UI selection flow.
- **Screenshots:** Expected filenames and capture steps are in `AUDIT_SCREENSHOT_CHECKLIST.md` in this folder. Files live in `screenshots/` here. Regenerate with `npm run audit:screenshots` from `ui/explorer` after `npm run build`.

---

## 5) Commands run & exact results

| Layer | Command | Result |
|--------|---------|--------|
| Backend | `python -m pytest tests/explorer -v --tb=no` | **27 passed** (~86 s) |
| Frontend | `npm run lint` | **pass** (no issues on stdout) |
| Frontend | `npm run typecheck` | **pass** |
| Frontend | `npm run build` | **pass** (Vite production build) |
| Frontend | `npm run test` | **35 passed** (26 files, Vitest) |
| Frontend | `npm run test:e2e` | **23 passed** (Playwright; includes audit screenshot spec) |

Full console capture: **`AUDIT_VALIDATION_OUTPUT.txt`**.

---

## 6) Sample API responses (real JSON)

Under repo root `browser_api_samples/`:

| File | Endpoint / role |
|------|------------------|
| `compare_rules.json` | `POST /browser/compare/rules` |
| `compare_lessons.json` | `POST /browser/compare/lessons` |
| `related_rules_rule_2025_09_29_sviatoslav_chornyi_rule_2025_09_29_sviatoslav_chornyi_trade_management_stop_loss_3.json` | `GET /browser/rule/{doc_id}/related` |
| `concept_rules_node_stop_loss.json` | `GET /browser/concept/node:stop_loss/rules` |
| `concept_lessons_node_stop_loss.json` | `GET /browser/concept/node:stop_loss/lessons` |

Existing Step 4.x samples (search, detail, errors, facets, health) remain alongside these.

**IDs used for those samples:**

- Concept: `node:stop_loss`
- Compare rules:  
  `rule:2025_09_29_sviatoslav_chornyi:rule_2025_09_29_sviatoslav_chornyi_trade_management_stop_loss_3`,  
  `rule:2025_09_29_sviatoslav_chornyi:rule_2025_09_29_sviatoslav_chornyi_trade_management_stop_loss_4`
- Compare lessons: `2025-09-29-sviatoslav-chornyi`, `2025_09_29_sviatoslav_chornyi`

---

## 7) Screenshots / UI proof

**Regenerate (mocked API, production preview):** from `ui/explorer` run `npm run build` then `npm run audit:screenshots`. PNGs and `audit-03-compare-deeplink-URL.txt` are written to **`audit/step4-3-explorer/screenshots/`**.

**Minimum bundle (happy path):**

- `audit/step4-3-explorer/screenshots/rule-compare.png`
- `audit/step4-3-explorer/screenshots/lesson-compare.png`
- `audit/step4-3-explorer/screenshots/related-rules.png`
- `audit/step4-3-explorer/screenshots/concept-rules.png`
- `audit/step4-3-explorer/screenshots/concept-lessons.png`

**Extended checklist** (main search, detail, deep link, empty, loading, error, narrow viewport):  
`AUDIT_SCREENSHOT_CHECKLIST.md` in this folder — files `audit-01-*.png` through `audit-07-*.png` (plus optional `audit-07-mobile-compare.png`).

**Submission zip:** `audit/step4-3-explorer/audit_step4_3_2026-03-24.zip` (rebuild with `powershell -File audit/step4-3-explorer/package_bundle.ps1` or `powershell -File scripts/package_audit_step43.ps1`). Contents are listed in `ZIP_CONTENTS.txt` inside the archive. Step 4.3 scope excludes `pipeline/rag/cli.py` and `tests/rag/conftest.py` unless you add them deliberately.

---

## 8) Scope discipline (for auditor)

- All new reads go through **`/browser/*`** FastAPI routes and the explorer service; the UI does not call raw retrieval or extraction artifacts directly.
- Explorer remains **read-only** for this step.

---

## 9) Determinism

- Related-rule groups and ordering are covered by `tests/explorer/test_views.py::test_build_related_rules_and_concept_lists_are_stable` and service/repository tests.
- Compare summaries are built from explicit fields in the read model (no random iteration order in exposed payloads).

---

## 10) Deep-linkability

- Rule compare: `/compare/rules?ids=<comma-separated doc_ids>` (each id URL-encoded as needed).
- Lesson compare: `/compare/lessons?ids=<comma-separated lesson_ids>`.
- Related rules: `/rule/:docId/related` (`docId` is the same encoded form as elsewhere, e.g. `rule%3A...`).
- Concept lists: `/concept/:conceptId/rules`, `/concept/:conceptId/lessons`.

Playwright proves reload/deep-link for rule compare in `tests/e2e/compare-traversal.spec.ts` (“deep-link directly to rule compare URL”) and back/forward from search → compare.

---

## 11) Edge-case handling (where proof lives)

| Case | Proof |
|------|--------|
| Nonexistent / bad IDs | API tests in `tests/explorer/test_api.py` (detail errors); `test_service_compare_validates_ids` |
| Malformed compare query | `compare-params` unit tests; compare pages handle empty/partial `ids` |
| Empty compare selection | UI messaging + launch bar; e2e selects before opening compare |
| Duplicate add-to-compare | Selection hook dedupes; covered by UX + unit behavior |
| Backend failure | `ErrorPanel` / query error paths on new pages (Vitest page tests with mocks) |
| Slow loading | React Query pending states on new pages (auditor can screenshot per checklist) |

---

## 12) Test mapping

**Unit / focused**

- `ui/explorer/src/lib/url/compare-params.test.ts` — URL parsing & restoration for compare `ids`.
- `tests/explorer/test_views.py` — rule/lesson compare view builders; related + concept list stability.
- `tests/explorer/test_service.py` — compare & traversal service methods; ID validation; related grouping helpers.

**Integration (API + service stack)**

- `tests/explorer/test_api.py` — `test_browser_compare_and_traversal_endpoints_work`, error paths, frame endpoint, search regressions below.

**E2E (Playwright)**

- `ui/explorer/tests/e2e/compare-traversal.spec.ts` — search → compare → back; rule → related; concept → rules; lesson compare overlap; deep link rule compare.

**Regression (earlier steps)**

- Step **3.1** retrieval ordering: `tests/explorer/test_api.py` — `test_browser_stoploss_query_keeps_evidence_first`, `test_browser_timeframe_query_keeps_rule_first`, `test_browser_daily_level_query_keeps_knowledge_event_first`, `test_browser_visual_support_query_keeps_evidence_first`, `test_browser_transcript_support_query_keeps_transcript_primary_first`.
- Same scenarios mirrored in `ui/explorer/tests/e2e/search-regressions.spec.ts` (Chromium).
- Step **4.1 / 4.2** flows: existing e2e specs (`search.spec.ts`, `detail-rule.spec.ts`, `concept.spec.ts`, etc.) still pass together with compare/traversal and audit screenshot specs (**23** Playwright tests total).

---

## 13) Optional context (audit speed)

- **URL vs session:** `?ids=` is authoritative for sharing and reload; session storage only seeds the launch bar until the user opens compare or copies the URL.
- **Related-rule grouping:** Groups use explicit relation reasons from the read model (e.g. same lesson, family, shared concept), with stable sort within groups — see `loader.py` / `views.py` and tests above.

---

## 14) How to reproduce the flow manually

1. Run the browser API (your usual `RAGConfig` + app) and point `ui/explorer` `VITE_BROWSER_API_BASE` at it (see `ui/explorer/.env.example`).
2. `npm run dev` in `ui/explorer`.
3. **Search:** `/search` — run a query, use **Add to compare** on two rules, **Open compare**.
4. **Deep link:** open `/compare/rules?ids=` with two real `rule:...` ids from search results.
5. **Related:** open a rule detail → **Related rules**.
6. **Concept:** open a concept → **All rules** / **All lessons**.

Concrete example query params (encode for the URL bar):

- `/compare/rules?ids=rule%3A2025_09_29_sviatoslav_chornyi%3Arule_2025_09_29_sviatoslav_chornyi_trade_management_stop_loss_3,rule%3A2025_09_29_sviatoslav_chornyi%3Arule_2025_09_29_sviatoslav_chornyi_trade_management_stop_loss_4`
- `/compare/lessons?ids=2025-09-29-sviatoslav-chornyi,2025_09_29_sviatoslav_chornyi`
- `/concept/node%3Astop_loss/rules` and `/concept/node%3Astop_loss/lessons`

---

## 15) Submission bundle (per audit)

1. This folder: `audit/step4-3-explorer/` (this file, file list, validation log, checklist, UI index, `screenshots/`)
2. `AUDIT_FILE_LIST_STEP43.md`
3. `AUDIT_VALIDATION_OUTPUT.txt`
4. All paths listed in the file list (source + tests + fixtures + samples)
5. Screenshots per `AUDIT_SCREENSHOT_CHECKLIST.md` in this folder
6. Sample JSON under repo root `browser_api_samples/` (listed above)
