# Stage 5.5 — Proposal-assisted review

## Types

| `ProposalType` | Meaning |
|----------------|---------|
| `duplicate_candidate` | Pair of rule cards with very high deterministic text/signal overlap; reviewer may mark `duplicate_of`. |
| `merge_candidate` | Similar rules that may belong in one canonical family (mid confidence band). |
| `canonical_family_candidate` | Rule not linked to an active family but matching an active family’s summary/members. |

## Status

`new` → open in queues. `dismissed` / `accepted` / `stale` / `superseded` are terminal or non-queue states. Regeneration refreshes `new` / `stale` rows; `dismissed` and `accepted` rows are not overwritten by upsert.

## Scores and thresholds

Weights and thresholds live in `proposal_policy.py` and are applied in `proposal_generation.py` using `simple_text_similarity` and `normalize_text_for_match` from `pipeline/component2/rule_reducer.py` (per-phrase normalization for condition/invalidation compatibility; token overlap elsewhere).

- Duplicate: score ≥ **0.88** (after clamping).
- Merge: **0.72** ≤ score **&lt; 0.88**.
- Canonical family: score ≥ **0.75** against an **active** family only.

**Precedence:** for the same rule pair, duplicate suppresses merge.

## Dedupe keys

Stable logical keys (sorted rule ids for pairs):

- `duplicate|rule_card|<low>|rule_card|<high>`
- `merge|rule_card|<low>|rule_card|<high>`
- `canonical|rule_card|<rule_id>|canonical_rule_family|<family_id>`

## Staleness

After each persisted generation run, `NEW` rows for the same `generator_version` whose `dedupe_key` is absent from the latest output are marked `stale` with reason `no_longer_generated`. Rows are not hard-deleted.

After each successful `append_decision_and_refresh_state`, any other `NEW` proposal whose **source** or **related** endpoint matches a target touched by that decision is marked `stale` with reason `adjudication_decision_on_target`. The decision’s own `proposal_id` (when present) is excluded from that update so the row can immediately transition to `accepted` via `mark_proposal_accepted`. Touch pairs for rule cards: the decided rule, plus `related_target_id` as another `rule_card` for `duplicate_of`, or as `canonical_rule_family` for `merge_into`.

On each persisted `POST /adjudication/proposals/generate`, before upserting the new batch, `NEW` rows are also staled when a **rule_card** source or related id is not in the current `CorpusTargetIndex`, or when `related_target_type` is `canonical_rule_family` but that family id no longer exists (`target_not_in_inventory`).

## Queue names

| Queue | `ProposalType` |
|-------|----------------|
| `high_confidence_duplicates` | `duplicate_candidate` |
| `merge_candidates` | `merge_candidate` |
| `canonical_family_candidates` | `canonical_family_candidate` |

Ordering: `queue_priority` DESC, `score` DESC, `updated_at` DESC, `proposal_id`.

## Proposal acceptance vs curated state

Submitting a decision with `proposal_id` validates the proposal (`NEW`, target matches source or related). The **normal** `append_decision_and_refresh_state` path updates reviewed/tier state. Only **after** a successful write does the API call `mark_proposal_accepted`. There is no endpoint that applies adjudication state from “accept proposal” alone.

## Deferred (later 5.5.x)

Evidence/concept/related-rule proposals, ambiguity policies, auto-approval, export, metrics, background workers — see parent Stage 5 requirements.
