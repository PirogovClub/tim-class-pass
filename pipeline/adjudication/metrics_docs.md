# Stage 5.7 — Review metrics definitions

Read-only metrics over adjudication SQLite, corpus inventory, and (when configured) explorer corpus documents. No metric path mutates adjudication, tier, or proposal state.

HTTP paths and response model names: **`metrics_routes_contract.md`**.

## Corpus inventory

**Supported review target** — Any `target_id` present in `CorpusTargetIndex` for `rule_card`, `evidence_link`, `concept_link`, or `related_rule_relation`.

**Total supported review targets** — Sum of inventory set sizes across those four types.

## Tier counts (summary)

**Gold / Silver / Bronze counts** — Rows in `materialized_tier_state` whose `(target_type, target_id)` is in the corpus inventory, grouped by `tier`. Uses the same materialized tier semantics as Stage 5.4 (no relaxed Gold).

**Tier unresolved count** — Inventory targets whose materialized row exists with `tier = unresolved`. Targets with **no** materialized row yet are not included here; they may still appear in the unresolved **queue** until tiers are recomputed.

**Unresolved count (summary)** — Size of the **unresolved queue** from `list_unresolved_queue` (inventory + state overlay + tier-unresolved alignment). This is the operational backlog, not only `tier = unresolved`.

## Rejected vs unsupported

**Rejected count** — `rule_card` inventory ids with `rule_card_reviewed_state.current_status = rejected`.

**Unsupported count** — Union of:
- `rule_card` in inventory with `is_unsupported = 1` **or** `current_status = unsupported`;
- `evidence_link` in inventory with `support_status = unsupported`.

## Canonical families & merge decisions

**Canonical family count** — `COUNT(*)` from `canonical_rule_families` (all statuses).

**Merge decision count** — `COUNT(*)` from `review_decisions` where `decision_type = merge_into`.

## Queue health

**Unresolved queue size** — Same as summary unresolved count.

**Deferred queue size** — `rule_card` inventory rows with `rule_card_reviewed_state.is_deferred = 1`.

**Proposal queue sizes** — Open proposals (`proposal_status = new`) per proposal queue name, using repository `count_open_proposals_by_queue` (same filters as `/adjudication/queues/proposals`).

**Unresolved by target type** — Counts of unresolved queue items by `target_type`.

**Unresolved backlog by tier** — Counts of unresolved queue items by `quality_tier` (nullable → `none`).

**Oldest unresolved activity** — Among unresolved items with `last_reviewed_at` set, the minimum timestamp; **age_seconds** is seconds from that instant to metric computation time (UTC). Null when no such timestamps exist.

## Proposal usefulness

**Total proposals** — Rows in `adjudication_proposal`.

**Open** — `proposal_status = new`.

**Accepted / Dismissed / Stale** — `accepted`, `dismissed`, and `stale` respectively.

**Superseded** — Counted separately (`proposal_status = superseded`); included in **stale_total** for high-level “no longer actionable” volume.

**Terminal disposition** — `accepted | dismissed | stale | superseded`.

**acceptance_rate_closed** — `accepted / terminal` (null if `terminal = 0`).

**acceptance_rate_all** — `accepted / total` (null if `total = 0`).

Same rates are repeated **by proposal_type** (`duplicate_candidate`, `merge_candidate`, `canonical_family_candidate`).

**Median seconds to disposition** — For terminal proposals, median of `(updated_at - created_at)` in seconds when both parse as ISO-8601; null if none.

## Throughput

**Window** — `7d` or `30d` ending at computation time (UTC).

**Decision count** — Rows in `review_decisions` with `created_at >= window_start` (ISO string comparison aligned with stored UTC timestamps).

**By decision_type** — Grouped counts within the window.

**By reviewer_id** — Grouped counts within the window.

## Coverage by lesson / concept

**Denominator** — Supported inventory targets that map to a **lesson_id** (or concept key) via explorer corpus documents (`explorer._repo.get_all_docs()`): `doc_id` must equal `target_id` for that target’s type. Targets with no matching doc fall into bucket `unknown_doc`.

**Not unresolved (numerator)** — Target has a materialized tier row with `tier != unresolved`, **or** is treated as unresolved if there is **no** tier row.

**coverage_ratio** — `reviewed_not_unresolved / total_targets` for that bucket; null if denominator is 0.

**Lesson id** — From document `lesson_id`; missing → `unknown`.

**Concept key** — First of `canonical_concept_ids[0]`, else string `concept` field, else `unknown`.

When the explorer is not configured (`get_explorer_optional` is `None`), coverage endpoints return empty buckets and `explorer_available: false` (see API responses).

## Ambiguity / conflict flags

**Ambiguity (rules)** — Inventory `rule_card` with `is_ambiguous = 1` **or** `current_status = ambiguous`.

**Conflict — split required** — `current_status = split_required`.

**Conflict — concept invalid** — Inventory `concept_link` with `link_status = invalid`.

**Conflict — relation invalid** — Inventory `related_rule_relation` with `relation_status = invalid`.

**By lesson / concept** — For rule_card ambiguity and split_required rows, distribution of `lesson_id` / concept key from corpus docs (same mapping as coverage). Empty when explorer unavailable.
