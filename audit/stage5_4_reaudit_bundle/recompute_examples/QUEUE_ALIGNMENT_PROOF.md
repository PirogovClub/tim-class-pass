# Queue alignment with tier-unresolved

## Change

`pipeline/adjudication/queue_service.py`:

- After collecting items via legacy **state heuristics**, `_collect_tier_only_unresolved` scans **full inventory** per tiered type.
- For each `(target_type, target_id)` **not** already in the queue, if `resolve_tier_for_target(...).tier == UNRESOLVED`, append a `QueueItemResponse` with `queue_reason` = first `blocker_codes` entry or `tier_unresolved`.

## No separate queue endpoint

Single unresolved queue (`GET /adjudication/queues/unresolved`, `.../by-target`, `.../next`) — **not** a second tier-only feed.

## Example

`test_queue_includes_tier_only_unresolved_evidence`:

- Evidence `ev:1` marked `evidence_unsupported` → support status no longer `unknown`, so legacy heuristic **drops** it from the “unknown support” bucket.
- Resolver tier = **unresolved** (`unsupported_state`).
- Tier-only pass **adds** `ev:1` back with `queue_reason == "unsupported_state"`.
