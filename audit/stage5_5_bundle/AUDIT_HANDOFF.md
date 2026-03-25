# Stage 5.5 — audit handoff

## Scope covered in this delta

- **§7 `ProposalQueueItem`:** added in `pipeline/adjudication/models.py`; built via `build_proposal_queue_item` in `queue_service.py` (queue HTTP responses still use `QueueItemResponse`).
- **§10.3 / text helpers:** merge condition/invalidation compatibility uses per-phrase `normalize_text_for_match` before `simple_text_similarity` in `proposal_generation.py`.
- **§13 staleness:** (1) **Decision-driven:** `mark_new_proposals_stale_after_decision` after `append_decision_and_refresh_state` (`adjudication_decision_on_target`; excludes payload `proposal_id`). (2) **Inventory / DB:** `mark_new_proposals_stale_when_missing_from_inventory` runs at the start of each persisted `POST …/proposals/generate` — stales `NEW` rows whose `rule_card` source/related id is not in `CorpusTargetIndex`, or whose `canonical_rule_family` related id is missing from `canonical_rule_families` (`target_not_in_inventory`). Canonical branch uses `NOT EXISTS` so an empty families table does not false-positive.
- **§14 list `total`:** `GET /adjudication/proposals` returns full matching row count via `count_proposals`, independent of `limit`/`offset`.
- **§19 tests:** HTTP happy-path `POST /proposals/generate` with stub explorer; list total pagination; inventory stale; unsupported / duplicate-of exclusion unit tests; `ReviewQueuePage.test.tsx` for proposal queue row content.
- **Proposal queue `total` (re-audit fix):** `GET /adjudication/queues/proposals` returns `total` from `count_open_proposals_by_queue` (same filters as the paged list, no pagination on the count). See `repository.py` / `queue_service.py` / `api_routes.py`.
- **Review UI back navigation (re-audit fix):** `ReviewItemPage` builds “Back to queue” with `buildReviewQueueBackHref(searchParams)` so `reviewQueue`, `qualityTier`, and `queueFilter`→`targetType` survive reloads. Extra: if only `targetType` is present on the item URL, it is forwarded too (`reviewQueueBackHref.ts`).
- **Docs:** `proposal_docs.md` updated for decision-time and inventory staleness.
- **`source/`** in this bundle mirrors the listed paths for auditors without repo checkout.

## Key files

| Area | Path |
|------|------|
| Stale-after-decision | `repository.py`: `_decision_stale_touch_pairs`, `mark_new_proposals_stale_after_decision`, call from `append_decision_and_refresh_state` |
| Queue item model | `models.py`: `ProposalQueueItem`; `queue_service.py`: `build_proposal_queue_item` |
| Generation | `proposal_generation.py`: `_merge_condition_compat` |
| Proposal queue totals | `repository.py`: `count_open_proposals_by_queue`, `list_open_proposals_by_queue`; `queue_service.py`: `list_proposal_queue` |
| Back to queue URL | `ui/explorer/src/lib/reviewQueueBackHref.ts`; `ui/explorer/src/pages/ReviewItemPage.tsx` |

## Carry-forward 5.4 tests

Orphan materialized tier purge and full-table recompute idempotence remain in `tests/adjudication_api/test_tier_audit_integration.py` (§4 of 5-5).

## Manual proof (queue total + back link)

**Back link**

- Open review item with query string, for example:  
  `/review/item/rule_card/rule%3Amerge%3Aaudit%3A1?reviewQueue=merge_candidates&queueFilter=rule_card&qualityTier=silver`
- “Back to queue” resolves to:  
  `/review/queue?reviewQueue=merge_candidates&qualityTier=silver&targetType=rule_card`  
  (order of query keys may vary; all three params must be present.)

**Queue API**

- Request: `GET /adjudication/queues/proposals?queue=merge_candidates&limit=10&offset=0` with enough open rows in SQLite.
- Expect: `items.length <= 10` and `total` equal to the count of open proposals matching that queue and filters (e.g. 37 when 37 exist), not `items.length`.

Example JSON shape: `api_examples/queues_proposals_total_pagination.json`.

## Screenshots

PNG files under `screenshots/` were generated with Playwright (`ui/explorer/tests/e2e/stage5-5-audit-screenshots.spec.ts`); see `RUN_AUDIT_TESTS.md`.

## Deferred (explicit)

- Evidence / concept / related-rule proposals
- Ambiguity or conflict proposals
- Advanced acceptance analytics
