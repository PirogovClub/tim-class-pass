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

## Stage 5.2+

HTTP `/review/*` routes, queues, proposals, and export should call `AdjudicationRepository` and treat `review_decisions` as the source of truth.
