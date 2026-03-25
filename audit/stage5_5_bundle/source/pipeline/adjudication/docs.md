# Stage 5.1 — Adjudication domain model and storage

## What this adds

Append-only **review decisions** in SQLite, **materialized reviewed-state** rows per target type, and **canonical rule families** with explicit memberships. No HTTP review APIs, no UI, no queue, and no AI proposals (Stage 5.2+).

## Integration with existing corpus/explorer IDs

Adjudication stores opaque **`target_id` strings** that must match identifiers already used in structured knowledge and the Step 4 explorer read layer:

| `ReviewTargetType` | Use `target_id` as |
|--------------------|---------------------|
| `rule_card` | Global rule id from corpus / retrieval docs (same strings as `source_rule_ids` on rule_card documents and keys in `rule_family_index.json`). Often `rule:<lesson_slug>:<local_id>` via `pipeline.corpus.id_utils.make_global_id`. |
| `evidence_link` | Stable id for a specific evidence-to-knowledge link (e.g. provenance or linker output id). Project-specific; must stay stable for the artifact being reviewed. |
| `concept_link` | Stable id for a concept–rule (or similar) link row being reviewed. |
| `related_rule_relation` | Prefer `pipeline.corpus.id_utils.make_global_relation_id(source_id, relation_type, target_id)` for deterministic relation keys. |
| `canonical_rule_family` | Adjudication-owned `family_id` (UUID string) returned by `create_canonical_family`. Not the corpus `rule_family_index` string names—those remain export artifacts only until merged via review. |

**Explorer note:** `ExplorerRepository` / `rule_family_index.json` are **read-only corpus indexes**. This package’s `canonical_rule_families` table is the **durable adjudication** view of families.

## Persistence

- **Engine:** SQLite (`sqlite3`), same general pattern as `pipeline.orchestrator.state_store.StateStore`.
- **Default path:** Callers pass an absolute or relative path; typical default is `var/adjudication.db` (separate from `var/pipeline_state.db`).
- **Initialization:** `pipeline.adjudication.bootstrap.initialize_adjudication_storage(db_path)` — idempotent `CREATE TABLE IF NOT EXISTS`. **Not** run on import.
- **Foreign keys:** `PRAGMA foreign_keys = ON` is set on connections, but the schema does **not** declare SQLite `FOREIGN KEY` constraints for reviewers/families. **Application-level checks** enforce integrity on write (post–1st-audit).

## Write integrity (application-level)

`append_decision` and `append_decision_and_refresh_state` enforce:

1. **Reviewer exists** — `reviewer_id` must be present in `reviewers` (`ReviewerNotFoundError` if not).
2. **Decision type matches target** — strict allow-list in `pipeline/adjudication/policy.py` (`InvalidDecisionForTargetError` if not). Summary:
   - `rule_card`: `approve`, `reject`, `duplicate_of`, `merge_into`, `split_required`, `unsupported`, `ambiguous`, `needs_review`, `defer`
   - `evidence_link`: `evidence_strong`, `evidence_partial`, `evidence_illustrative_only`, `evidence_unsupported`
   - `concept_link`: `concept_valid`, `concept_invalid`
   - `related_rule_relation`: `relation_valid`, `relation_invalid`
   - `canonical_rule_family`: `approve`, `reject`, `needs_review`, `defer`, `ambiguous` (subset used for family status updates)
3. **`merge_into` family exists** — for rule cards, `related_target_id` must be a row in `canonical_rule_families` (`FamilyNotFoundError` if not).

4. **`canonical_rule_family` target exists** — for `target_type=canonical_rule_family`, **`target_id` must be an existing `family_id`** in `canonical_rule_families` before any decision append (`FamilyNotFoundError` if not). Post–audit2: same standard as reviewer and merge family checks.

`add_rule_to_family` requires the family to exist (`FamilyNotFoundError`).

**Policy note (non-blocking):** `create_canonical_family(...).created_by` is **not** required to match a `reviewers` row, so system/import identities can be recorded without a reviewer record.

Exceptions: `ReviewerNotFoundError`, `FamilyNotFoundError`, `InvalidDecisionForTargetError` (subclass `AdjudicationIntegrityError`).

## Data entities

- **`reviewers`** — Non-anonymous actor (`human` | `agent` | `system`).
- **`review_decisions`** — Append-only log; never updated or deleted by this layer.
- **`canonical_rule_families`** / **`canonical_rule_memberships`** — First-class family + role per rule (`canonical`, `member`, `variant`, `duplicate`).
- **`*_reviewed_state`** — One row per target id for rule cards, evidence links, concept links, related-rule relations (materialized cache).

## `related_target_id` contract

| `DecisionType` | Meaning of `related_target_id` |
|----------------|-------------------------------|
| `duplicate_of` | **`target_id` of the other rule card** (the duplicate-of target). |
| `merge_into` | **`family_id`** of the adjudication canonical family the rule is merged into. On append with refresh, a `canonical_rule_memberships` row is upserted (`role=member`, `added_by_decision_id` set). |

## Resolved-state policy

- **Ordering:** Decisions are applied in order of `(created_at, decision_id)`.
- **Primary rule:** **Last decision wins** for the latest typed fields (`latest_decision_type`, timestamps, reviewer, decision id).
- **Rule-card flags** (`is_duplicate`, `is_deferred`, `is_unsupported`, `is_ambiguous`) reflect **only the latest** decision type (e.g. `approve` after `duplicate_of` clears duplicate flags).
- **`canonical_family_id` on rule cards:** Taken from the latest `merge_into` decision’s `related_target_id`, **or** if that is absent, from **any** `canonical_rule_memberships` row for that `rule_id` (deterministic: smallest `family_id`), so linkage survives a later non-merge decision.

## API sketch (Python)

```python
from pathlib import Path
from pipeline.adjudication import AdjudicationRepository, initialize_adjudication_storage
from pipeline.adjudication.enums import DecisionType, ReviewTargetType, ReviewerKind
from pipeline.adjudication.models import NewReviewer, NewReviewDecision

db = Path("var/adjudication.db")
initialize_adjudication_storage(db)
repo = AdjudicationRepository(db)
repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="Ada"))
repo.append_decision_and_refresh_state(
    NewReviewDecision(
        target_type=ReviewTargetType.RULE_CARD,
        target_id="rule:lesson_a:r1",
        decision_type=DecisionType.NEEDS_REVIEW,
        reviewer_id="u1",
    )
)
```

## Stage 5.2 — Adjudication HTTP API

Mounted on the RAG FastAPI app under prefix **`/adjudication`**. Database path: environment variable **`ADJUDICATION_DB_PATH`** (default `var/adjudication.db`). Explorer-backed optional bundle context is wired when the explorer service is initialized; missing explorer data does not fail the bundle.

**Enum strings** for query bodies: `target_type` ∈ `rule_card`, `evidence_link`, `concept_link`, `related_rule_relation`, `canonical_rule_family`; `decision_type` values are defined in `pipeline.adjudication.enums.DecisionType`.

### Routes

| Method | Path | Query / body | Response |
|--------|------|----------------|----------|
| GET | `/adjudication/review-item` | `target_type`, `target_id` | `ReviewItemResponse` |
| GET | `/adjudication/review-history` | `target_type`, `target_id` | `ReviewHistoryResponse` |
| GET | `/adjudication/review-bundle` | `target_type`, `target_id` | `ReviewBundleResponse` |
| GET | `/adjudication/families/{family_id}` | — | `FamilyDetailResponse` |
| GET | `/adjudication/families/{family_id}/members` | — | `FamilyMembersResponse` |
| POST | `/adjudication/decision` | JSON `DecisionSubmissionRequest` | `DecisionSubmissionResponse` |
| GET | `/adjudication/queues/unresolved` | — | `QueueListResponse` (JSON object) |
| GET | `/adjudication/queues/by-target` | `target_type` | `QueueListResponse` |
| GET | `/adjudication/queues/next` | `queue` (default `unresolved`), optional `target_type` | `QueueItemResponse` or `null` |
| GET | `/adjudication/tier` | `target_type`, `target_id` | `TierStateResponse` (requires corpus index; **404** `unknown_corpus_target` if id not in inventory) |
| GET | `/adjudication/tiers/by-tier` | `tier`, optional `target_type`, `limit` | `TierListResponse` |
| GET | `/adjudication/tiers/counts` | — | `TierCountsResponse` |
| POST | `/adjudication/tiers/recompute-all` | — | `TierRecomputeResponse` — upserts tier rows for **all** inventory ids; deletes orphan tier rows |

Invalid `target_type` query values return **400** with `error_code: validation_error`.

**Review item (non-family):** If there is no row in the materialized `*_reviewed_state` table, the API returns a minimal `ReviewItemResponse` with only `target_type` and `target_id` (not an error). **`canonical_rule_family`:** missing `family_id` returns **404** `not_found`.

**Queues:** Only the logical queue name **`unresolved`** is implemented. `GET .../queues/next?queue=anything_else` returns **`null`**.

**Corpus inventory + queues:** Unresolved queues are built from a **`CorpusTargetIndex`** (frozen allow-lists of `target_id` values) **left-joined** to materialized `*_reviewed_state` rows:

- **Inventory source (production):** `CorpusTargetIndex.from_explorer_repository(explorer._repo)` — scans `retrieval_docs_all.jsonl` via `ExplorerRepository.get_all_docs()`: `rule_card` → `unit_type == rule_card` (`doc_id`); `evidence_link` → `evidence_ref`; `concept_link` vs `related_rule_relation` → `concept_relation` docs split by whether canonical endpoints include `rule:` / `rel:rule:` prefix (rule–rule edges vs concept-graph edges).
- **Never-reviewed** corpus targets (no adjudication state row) appear as unresolved with `queue_reason` **`no_adjudication_state`** (or type-specific “unknown_*” when a state row exists but support/link/relation is still unknown).
- **Orphan state:** Rows in `*_reviewed_state` whose `target_id` is **not** in the inventory are **omitted** from queues (guessed IDs must not surface).

`init_adjudication(db, explorer, corpus_index=...)` — if `corpus_index` is omitted and `explorer` is set, the index is built automatically. Queue endpoints **503** if no corpus index is configured. `POST /decision` for non-family targets requires a corpus index; **`canonical_rule_family`** decisions do not.

Unresolved **predicates**, **tier alignment** (inventory targets whose resolver tier is `unresolved` but state heuristics alone would skip them), and **ordering** are documented in `queue_service.py`.

**Tier materialization:** After decisions on tiered targets, and after `canonical_rule_family` or `merge_into` (family linkage) decisions, dependent rule-card tiers refresh. Run **`POST /adjudication/tiers/recompute-all`** after bulk imports or policy changes so counts/list-by-tier reflect the full corpus inventory.

### Error payload

Non-2xx adjudication errors use JSON:

```json
{
  "error_code": "not_found",
  "message": "…",
  "details": { }
}
```

Stable `error_code` values include: `not_found`, `validation_error`, `unknown_reviewer`, `unknown_family`, `unknown_corpus_target`, `corpus_index_unavailable`, `invalid_decision`, `invalid_target_decision_pair`, `bad_request`. Non-family `POST /decision` targets must exist in the corpus index (`unknown_corpus_target`, 404). **`duplicate_of`** on `rule_card` requires **`related_target_id`** to be a known corpus rule id. Pydantic request validation on `POST /decision` is handled by FastAPI (422) in addition to domain validation mapped to `validation_error` with `details.errors` (without raw exception `ctx`).

### Example workflow (JSON)

1. **Review bundle** for a rule card:

   `GET /adjudication/review-bundle?target_type=rule_card&target_id=rule:lesson_a:r1`

2. **History** (same target):

   `GET /adjudication/review-history?target_type=rule_card&target_id=rule:lesson_a:r1`

3. **Submit duplicate_of** (requires `related_target_id`):

```json
POST /adjudication/decision
{
  "target_type": "rule_card",
  "target_id": "rule:lesson_a:r1",
  "decision_type": "duplicate_of",
  "reviewer_id": "u1",
  "related_target_id": "rule:lesson_a:r2",
  "note": "Same stop-loss wording"
}
```

Response includes `decision_id` and `updated_state` (`ReviewItemResponse`).

4. **Unresolved queue:**

   `GET /adjudication/queues/unresolved`

5. **Next item** (optionally restrict):

   `GET /adjudication/queues/next?queue=unresolved&target_type=rule_card`

Later stages (5.3+): UI, AI proposals, export, and G/S/B should continue to treat `review_decisions` / repository APIs as source of truth.
