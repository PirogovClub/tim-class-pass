# Stage 5.2 — Adjudication HTTP API — Audit handoff

This document is the **full implementation bundle index** for the Stage 5.2 audit. **Verbatim copies** of every listed source and test file, plus raw test output, live under:

`audit/stage5_2_api_bundle/`

See `audit/stage5_2_api_bundle/FILES_MANIFEST.txt` for the explicit file list (note: that snapshot predates the **corpus inventory** patch; canonical sources are in the repo paths below).

### Re-audit delta — corpus inventory + write validation (2026-03-24)

Addresses audit **Blocker 1** (queues must surface never-reviewed corpus items) and **Blocker 2** (non-family writes must reject unknown corpus targets).

| Change | Detail |
|--------|--------|
| `corpus_inventory.py` | `CorpusTargetIndex` + `from_explorer_repository(ExplorerRepository)` |
| `queue_service.py` | Unresolved queues = **inventory ∪ state overlay**; orphans (state without inventory id) **hidden**; never-reviewed inventory ids get `queue_reason=no_adjudication_state` |
| `api_service.py` | `validate_corpus_targets_for_write`; `submit_decision(..., corpus_index)`; `duplicate_of` checks **related** rule id in index |
| `api_routes.py` | `init_adjudication(..., corpus_index=...)`; auto-build index from explorer when omitted; `get_corpus_index` for queues; optional corpus for `POST /decision` (family-only works with `None`) |
| `api_errors.py` | `unknown_corpus_target`, `corpus_index_unavailable` |
| Tests | `test_corpus_queue_and_writes.py`, `test_corpus_index_from_explorer.py` (optional local build), `corpus_index_fixtures.py`, updated queue/write/route fixtures |

**Commands (post-patch):** `python -m pytest tests/adjudication_api/ tests/test_adjudication_*.py` → **85 passed** (including Stage 5.1 adjudication tests and optional explorer index test when artifacts exist).

---

## 1) Stage 5.2 scope (requirements)

**In scope:** Backend-only adjudication **read/write HTTP APIs**, **review bundle**, **queue APIs** (unresolved / by-target / next), **DTOs**, **API error mapping**, **tests**, **docs**. Thin FastAPI routes delegating to services. Wiring into the existing RAG FastAPI app (`pipeline/rag/api.py`). Optional explorer context for the bundle when the explorer service exists.

**Out of scope (intentionally not implemented):** Review UI, AI proposal generation, export pipeline, Gold/Silver/Bronze logic, authentication/authorization, broad explorer refactors, changes to browser JSON contracts under `/browser/*` (except one small helper; see below).

---

## 2) What was implemented

| Layer | Role |
|--------|------|
| `api_models.py` | Pydantic request/response DTOs (separate from `models.py` storage types). |
| `api_errors.py` | `ApiErrorResponse`, `AdjudicationApiError`, `ErrorCode`, `map_integrity_error`, FastAPI exception handler. |
| `api_service.py` | Reads (`get_review_item`, `get_review_history`, family getters), `submit_decision` → `NewReviewDecision` + `append_decision_and_refresh_state`, optional rule context for bundle. |
| `bundle_service.py` | `get_review_bundle`: state + history + family slice + optional explorer context. |
| `queue_service.py` | Deterministic **unresolved** queue: **corpus `CorpusTargetIndex` + `*_reviewed_state` overlay** (see §4). |
| `corpus_inventory.py` | Frozen allow-lists of reviewable target ids; built from explorer retrieval docs. |
| `api_routes.py` | `APIRouter` prefix `/adjudication`, `init_adjudication(db_path, explorer, corpus_index=...)`. |
| `docs.md` | Stage 5.1 persistence notes + Stage 5.2 route/error/queue documentation. |
| `pipeline/rag/api.py` | Registers adjudication router + error handler; `init_adjudication` after `init_explorer`; `ADJUDICATION_DB_PATH` (default `var/adjudication.db`). |
| `pipeline/explorer/api.py` | **`get_explorer_service_optional()`** only — no new explorer routes. |
| `tests/adjudication_api/*` | DTO, service reads, bundle, write, queues, HTTP routes, error mapping. |

**Stage 5.1** repository/resolver/bootstrap (unchanged by this handoff’s intent) remain the **single write path**: `POST /decision` calls `append_decision_and_refresh_state` after domain validation.

---

## 3) Exact routes added (`/adjudication` prefix)

All are on the same FastAPI `app` as RAG/explorer (see `pipeline/rag/api.py`).

| Method | Path |
|--------|------|
| GET | `/adjudication/review-item` |
| GET | `/adjudication/review-history` |
| GET | `/adjudication/review-bundle` |
| GET | `/adjudication/families/{family_id}` |
| GET | `/adjudication/families/{family_id}/members` |
| POST | `/adjudication/decision` |
| GET | `/adjudication/queues/unresolved` |
| GET | `/adjudication/queues/by-target` |
| GET | `/adjudication/queues/next` |

**Query parameters (summary):**

- `review-item`, `review-history`, `review-bundle`: `target_type` (enum string), `target_id` (string, min length 1).
- `queues/by-target`: `target_type`.
- `queues/next`: `queue` (default `unresolved`; other values yield `null` body), optional `target_type` to filter.

---

## 4) Queue policy (explicit)

Implemented in `queue_service.py` + `corpus_inventory.py` (authoritative).

**Inventory:** `CorpusTargetIndex` lists valid `target_id` values per type. **Production:** built once from `ExplorerRepository.get_all_docs()` (`from_explorer_repository`): `rule_card` ← `unit_type == rule_card` (`doc_id`); `evidence_link` ← `evidence_ref`; `concept_link` / `related_rule_relation` ← `concept_relation` split by rule vs concept endpoints (see `corpus_inventory.py`).

**Membership — “unresolved” includes** (for ids **in the inventory**):

- **rule_card:** No state row (**never reviewed**) **or** state matches: `latest_decision_type` is null **or** `current_status` ∈ {`needs_review`, `ambiguous`} **or** `is_ambiguous` **or** `is_deferred`. Never-reviewed rows use `queue_reason=no_adjudication_state`.
- **evidence_link:** No state row **or** `support_status` is null or `unknown`.
- **concept_link:** No state row **or** `link_status` is null or `unknown`.
- **related_rule_relation:** No state row **or** `relation_status` is null or `unknown`.

**Orphans:** State-table rows whose `target_id` is **not** in the inventory are **not** listed (prevents guessed ids from appearing).

**Global ordering** (deterministic, stable across calls for unchanged DB):

- Sort key `(has_ts, last_reviewed_at, target_type, target_id)` where `has_ts` is `0` if `last_reviewed_at` is set, else `1` — rows **with** a timestamp sort **before** rows **without**.
- Then ascending `last_reviewed_at` (ISO-8601 string order).
- Then ascending `target_type` value, then ascending `target_id`.

**`queues/next`:** First item after the same ordering; optional filter by `target_type`. **`queue` ≠ `unresolved`:** returns **`null`** (no item).

---

## 5) Review bundle contents

`ReviewBundleResponse` (`api_models.py` + `bundle_service.py`):

| Field | Content |
|--------|---------|
| `target_type`, `target_id` | Requested target. |
| `target_summary` | From reviewed state (`summary` / family title where applicable). |
| `reviewed_state` | Full `ReviewItemResponse` for the target. |
| `history` | List of `DecisionHistoryEntry` (append-only log for that target). |
| `family` | `FamilySummary` when target is `canonical_rule_family`, or when `rule_card` has `canonical_family_id` and family fetch succeeds. |
| `family_members_preview` | Up to 20 member rows as dicts when family is loaded. |
| `optional_context` | For `rule_card`, optional `rule_detail` from explorer `get_rule_detail` when explorer is wired; **any explorer failure → `{}`** (bundle still succeeds). |

This is intended to be enough for a Stage 5.3 review screen without AI ranking.

---

## 6) Error codes (`AdjudicationApiError` → JSON)

Response shape: `{ "error_code": str, "message": str, "details": object | omitted }`.

| `error_code` | Typical HTTP | When |
|----------------|-------------|------|
| `not_found` | 404 | Missing canonical family where a family row is required (e.g. family detail, family target review item). |
| `validation_error` | 400 or 422 | Bad `target_type` query; invalid `NewReviewDecision` construction (e.g. `duplicate_of` without `related_target_id`) — **422** with `details.errors` (Pydantic errors **without** non-JSON `ctx`). |
| `unknown_reviewer` | 404 | Reviewer not in `reviewers` table. |
| `unknown_family` | 404 | Missing family for `merge_into` / family-as-target. |
| `unknown_corpus_target` | 404 | Primary `target_id` or `duplicate_of` **related** rule id not in `CorpusTargetIndex`. |
| `corpus_index_unavailable` | 503 | Queues called with no index configured, or non-family decision submitted with no index. |
| `invalid_target_decision_pair` | 400 | Policy: decision type not allowed for target type. |
| `invalid_decision` | (reserved in enum; map as needed) | Defined in `ErrorCode`; primary path uses `invalid_target_decision_pair` for policy violations. |
| `bad_request` | 400 | Fallback for other integrity errors after mapping. |

**FastAPI/Pydantic** may return **422** for malformed JSON body on `POST /decision` (framework validation) in addition to adjudication’s own **422** for domain `NewReviewDecision` validation.

Raw `AdjudicationIntegrityError` subclasses are **not** returned directly; they go through `map_integrity_error` in `submit_decision`.

---

## 7) Write path correctness (`POST /adjudication/decision`)

1. Request body validated as `DecisionSubmissionRequest` (Pydantic).
2. Built into `NewReviewDecision`; Pydantic on that model enforces cross-field rules (e.g. `duplicate_of` / `merge_into` need `related_target_id`) → `AdjudicationApiError` **validation_error** if invalid.
3. For non-**`canonical_rule_family`** targets: **`CorpusTargetIndex`** must be present; primary target id must be in the index; **`duplicate_of`** on **`rule_card`** requires **`related_target_id`** ∈ index rule ids (**`unknown_corpus_target`** / **`corpus_index_unavailable`** otherwise). Family targets skip corpus checks.
4. `repo.append_decision_and_refresh_state(payload)` performs Stage 5.1 integrity checks (reviewer exists, target/decision pairing, family exists for merge, family target exists, etc.).
5. On success, response includes **`updated_state`** from `get_review_item` (refreshed materialized state).

---

## 8) Explicit answers (auditor checklist)

1. **Routes added?** — See §3.
2. **DTOs added?** — `api_models.py`: request types (`DecisionSubmissionRequest`, etc.), responses (`ReviewItemResponse`, `ReviewHistoryResponse`, `ReviewBundleResponse`, `DecisionSubmissionResponse`, family types, queue types), `ApiErrorResponse` in `api_errors.py`.
3. **Queue policy?** — See §4.
4. **Bundle context?** — See §5.
5. **Error codes?** — See §6.
6. **Deferred to 5.3+?** — Operator UI, AI proposals, export, G/S/B, auth, non-unresolved queue names, any ranking of candidates.
7. **Explorer / browser contracts touched?** — **No new or changed `/browser/*` routes or response schemas.** Only `get_explorer_service_optional()` added for optional adjudication bundle enrichment.
8. **Thin handlers?** — `api_routes.py` parses query/body, calls service/bundle/queue functions, returns models or `model_dump()`. Business logic lives in **`api_service.py`**, **`bundle_service.py`**, **`queue_service.py`**, and the **repository** (Stage 5.1).

---

## 9) Changed file list (compact tree)

```
pipeline/adjudication/api_errors.py      # new
pipeline/adjudication/api_models.py      # new
pipeline/adjudication/api_routes.py      # new
pipeline/adjudication/api_service.py       # new
pipeline/adjudication/bundle_service.py    # new
pipeline/adjudication/queue_service.py     # corpus inventory + state overlay
pipeline/adjudication/corpus_inventory.py  # CorpusTargetIndex + from_explorer_repository
pipeline/adjudication/docs.md              # extended (Stage 5.2 section)
pipeline/explorer/api.py                   # + get_explorer_service_optional()
pipeline/rag/api.py                        # + adjudication router, handler, init_adjudication
tests/adjudication_api/conftest.py
tests/adjudication_api/test_api_bundle.py
tests/adjudication_api/test_api_errors.py
tests/adjudication_api/test_api_models.py
tests/adjudication_api/test_api_queues.py
tests/adjudication_api/test_api_reads.py
tests/adjudication_api/test_api_routes.py
tests/adjudication_api/test_api_write.py
tests/adjudication_api/corpus_index_fixtures.py
tests/adjudication_api/test_corpus_queue_and_writes.py
tests/adjudication_api/test_corpus_index_from_explorer.py
AUDIT_HANDOFF.md                           # this file (audit deliverable)
audit/stage5_2_api_bundle/                 # snapshot copies + pytest output (see FILES_MANIFEST.txt)
```

**Not listed:** Stage 5.1 core (`repository.py`, `resolver.py`, etc.) except where already present before 5.2; this handoff does not re-copy them into the bundle (5.2 audit focuses on API surface + integration touch points).

---

## 10) Commands run (validation evidence)

Exact commands used for this handoff:

```text
python -m pytest tests/adjudication_api/ tests/test_adjudication_models.py tests/test_adjudication_resolver.py tests/test_adjudication_storage.py tests/test_adjudication_restart.py tests/test_adjudication_integrity.py -v --tb=short
```

```text
python -m compileall -q pipeline/adjudication pipeline/rag/api.py pipeline/explorer/api.py
```

```text
python -c "from pipeline.rag.api import app; print('import app: OK')"
```

```text
ruff check pipeline/adjudication tests/adjudication_api   # not available in this environment
python -m mypy pipeline/adjudication                      # mypy not installed (see raw output files)
```

**Raw transcripts:** `audit/stage5_2_api_bundle/STAGE5_2_PYTEST_OUTPUT.txt`, `STAGE5_2_RUFF_OUTPUT.txt`, `STAGE5_2_MYPY_OUTPUT.txt`, `STAGE5_2_IMPORT_APP.txt`.

---

## 11) Test results summary

| Suite | Result |
|--------|--------|
| `tests/adjudication_api/` + Stage 5.1 adjudication tests (see command above) | **85 passed**, **0 failed**, **0 skipped** when local `output_rag` / `output_corpus` exist; **84 passed** with that optional test skipped. |

Full per-test lines: `audit/stage5_2_api_bundle/STAGE5_2_PYTEST_OUTPUT.txt`.

---

## 12) Minimum test matrix (requirements §14) — mapping

| # | Expectation | Covered by |
|---|-------------|------------|
| 1 | Valid decision request DTO | `test_valid_decision_request` |
| 2 | Invalid target type rejected | `test_decision_request_invalid_target_type_string` |
| 3 | Malformed queue params | `NextQueueItemRequest` defaults; route invalid `target_type` → `test_bad_target_type_query` |
| 4 | Malformed payload rejected | `test_malformed_decision_missing_reviewer`, `test_malformed_json_decision` |
| 5–6 | Review item / history | `test_review_item_ok`, `test_review_history_ok`, `test_review_item_rule_empty`, `test_review_history_empty` |
| 7–8 | Family detail / members | `test_family_round_trip`, `test_family_404`, `test_family_members_404` |
| 9 | “Missing target” | **Note:** For `rule_card` (and non-family types), **no state row → 200** minimal `ReviewItemResponse`, not 404 (`test_review_item_rule_empty`). **404** applies to **unknown `canonical_rule_family`** (`test_review_item_canonical_family_missing`). |
| 10 | Missing family | `test_family_detail_missing`, `test_family_members_missing` |
| 11–13 | Bundle | `test_review_bundle_ok`, `test_bundle_rule_no_family`, `test_bundle_rule_with_family`, `test_bundle_optional_context_absent_without_explorer` |
| 14–19 | Write API | `test_decision_post_ok`, `test_submit_*`, `test_decision_unknown_reviewer`, `test_decision_invalid_pair`, `test_submit_missing_family_merge`, `test_submit_family_target_missing_family` |
| 20–23 | Queues | `test_unresolved_deterministic_order`, `test_by_target_filter`, `test_next_first_item` / `test_queues_next`, `test_empty_queue_stable` |
| 24–26 | Errors | `test_decision_missing_related_duplicate_of`, `test_family_404`, `test_map_*` (integrity → API error); raw storage exceptions are not asserted end-to-end but mapping is unit-tested. |

---

## 13) Example JSON payloads

Illustrative samples (field sets match DTOs; timestamps and IDs are examples).

### GET `/adjudication/review-item?target_type=rule_card&target_id=rule:lesson_a:r1`

**200** — rule with prior `needs_review`:

```json
{
  "target_type": "rule_card",
  "target_id": "rule:lesson_a:r1",
  "current_status": "needs_review",
  "latest_decision_type": "needs_review",
  "last_reviewed_at": "2026-03-24T12:00:00+00:00",
  "last_reviewer_id": "u1",
  "canonical_family_id": null,
  "summary": null,
  "is_duplicate": false,
  "duplicate_of_rule_id": null,
  "is_ambiguous": false,
  "is_deferred": false,
  "is_unsupported": false,
  "support_status": null,
  "link_status": null,
  "relation_status": null
}
```

**200** — never adjudicated (no state row): minimal shell with only `target_type` and `target_id` (other fields omitted or null).

### GET `/adjudication/review-history?target_type=rule_card&target_id=rule:lesson_a:r1`

```json
{
  "target_type": "rule_card",
  "target_id": "rule:lesson_a:r1",
  "decisions": [
    {
      "decision_id": "dec-uuid-1",
      "target_type": "rule_card",
      "target_id": "rule:lesson_a:r1",
      "decision_type": "needs_review",
      "reviewer_id": "u1",
      "created_at": "2026-03-24T12:00:00+00:00",
      "note": null,
      "reason_code": null,
      "related_target_id": null,
      "artifact_version": null,
      "proposal_id": null
    }
  ]
}
```

### GET `/adjudication/review-bundle?target_type=rule_card&target_id=rule:lesson_a:r1`

```json
{
  "target_type": "rule_card",
  "target_id": "rule:lesson_a:r1",
  "target_summary": null,
  "reviewed_state": { },
  "history": [ ],
  "family": null,
  "family_members_preview": [],
  "optional_context": {}
}
```

(`reviewed_state` and `history` mirror the item + history responses; `optional_context` may contain `rule_detail` when explorer is available.)

### GET `/adjudication/families/{family_id}`

**200:**

```json
{
  "family_id": "550e8400-e29b-41d4-a716-446655440000",
  "canonical_title": "Stop loss family",
  "normalized_summary": null,
  "status": "draft",
  "created_at": "2026-03-24T10:00:00+00:00",
  "updated_at": "2026-03-24T10:00:00+00:00",
  "created_by": "u1",
  "primary_concept": null,
  "primary_subconcept": null,
  "review_completeness": null
}
```

**404:**

```json
{
  "error_code": "not_found",
  "message": "Family 'missing-id' not found",
  "details": { "family_id": "missing-id" }
}
```

### GET `/adjudication/families/{family_id}/members`

**200 (empty members):**

```json
{
  "family_id": "550e8400-e29b-41d4-a716-446655440000",
  "members": []
}
```

### POST `/adjudication/decision` — success

**Request:**

```json
{
  "target_type": "rule_card",
  "target_id": "rule:lesson_a:r1",
  "decision_type": "duplicate_of",
  "reviewer_id": "u1",
  "related_target_id": "rule:lesson_a:r2",
  "note": "Same wording"
}
```

**200:**

```json
{
  "success": true,
  "decision_id": "dec-new",
  "target_type": "rule_card",
  "target_id": "rule:lesson_a:r1",
  "updated_state": { },
  "family_linkage_summary": null
}
```

(`updated_state` is a full `ReviewItemResponse` after refresh.)

### POST `/adjudication/decision` — failure examples

**Unknown reviewer (404):**

```json
{
  "error_code": "unknown_reviewer",
  "message": "Unknown reviewer_id='nobody'; create reviewer first.",
  "details": { "reviewer_id": "nobody" }
}
```

**Invalid target/decision pair (400):**

```json
{
  "error_code": "invalid_target_decision_pair",
  "message": "Decision type 'duplicate_of' is not allowed for target_type='evidence_link'.",
  "details": {
    "target_type": "evidence_link",
    "decision_type": "duplicate_of"
  }
}
```

**Missing `related_target_id` for `duplicate_of` (422, adjudication handler):**

```json
{
  "error_code": "validation_error",
  "message": "Invalid decision payload",
  "details": {
    "errors": [
      {
        "type": "value_error",
        "loc": ["related_target_id"],
        "msg": "Value error, related_target_id required for duplicate_of",
        "input": null
      }
    ]
  }
}
```

(Exact `msg`/`loc` may vary slightly with Pydantic version.)

### GET `/adjudication/queues/unresolved`

```json
{
  "queue": "unresolved",
  "items": [
    {
      "target_type": "rule_card",
      "target_id": "rule:qq:1",
      "current_status": "needs_review",
      "latest_decision_type": "needs_review",
      "last_reviewed_at": "2026-03-24T12:00:00+00:00",
      "canonical_family_id": null,
      "queue_reason": "needs_review",
      "summary": null
    }
  ],
  "total": 1
}
```

### GET `/adjudication/queues/by-target?target_type=rule_card`

Same shape as above; `items` filtered to `rule_card` only.

### GET `/adjudication/queues/next?queue=unresolved&target_type=rule_card`

**200** — first queue item as a single `QueueItemResponse` object, or **`null`** if empty / filtered empty.

### Empty queue

```json
{
  "queue": "unresolved",
  "items": [],
  "total": 0
}
```

---

## 14) End-to-end walkthrough (API sequence)

1. `GET /adjudication/review-bundle?target_type=rule_card&target_id=rule_123` — load state, history, optional family and `optional_context`.
2. `GET /adjudication/review-history?...` — same target; confirm decision log matches bundle `history`.
3. `POST /adjudication/decision` with `duplicate_of` and `related_target_id` — persist via `append_decision_and_refresh_state`.
4. Response includes `updated_state` with duplicate flags / linkage as resolved by Stage 5.1 resolver.
5. `GET /adjudication/queues/unresolved` — see remaining work; ordering deterministic.
6. `GET /adjudication/queues/next?queue=unresolved&target_type=rule_card` — pop first item for a rule-only workflow.

---

## 15) Service-layer architecture (short)

| Concern | Location |
|---------|-----------|
| HTTP parsing, dependency injection | `api_routes.py` |
| Read models, decision submit, `get_review_item` projection | `api_service.py` |
| Bundle orchestration | `bundle_service.py` |
| Unresolved selection + ordering | `queue_service.py` |
| Integrity → HTTP error mapping | `api_errors.py` (`map_integrity_error`, handler) |
| Persistence + materialized state | `repository.py` / Stage 5.1 (not duplicated in bundle) |

---

## 16) Known limitations

- Only queue name **`unresolved`** is implemented; `queues/next` with other `queue` values returns **`null`**.
- Targets never written through `append_decision_and_refresh_state` **do not appear** in queues (no state row).
- **`rule_card` “unknown” id** returns a **minimal** review item (200), not 404 — by design for opaque ids; **canonical families** use strict 404 when the family row is missing.
- **Lint / mypy:** not configured in `pyproject.toml`; see raw output files for this environment.
- **Full `uvicorn` smoke** with real corpus paths is environment-dependent; import check confirms app construction.

---

## 17) Scope discipline confirmation

No review UI, no AI proposals, no export, no G/S/B, no auth system, no broad refactors. Integration touch points: **`pipeline/rag/api.py`** and **`get_explorer_service_optional()`** in **`pipeline/explorer/api.py`** only.

---

*End of Stage 5.2 audit handoff.*
