# Stage 5.4 — Quality tier policy (v1)

**Policy version string:** `tier_policy.v1`  
**Source of truth:** `pipeline/adjudication/quality_tier.py` (this note must match that file).

See [`docs/requirements/stage 5/5-4.md`](../docs/requirements/stage%205/5-4.md) for product goals.

## Supported targets

Materialized tiers exist for:

- `rule_card`, `evidence_link`, `concept_link`, `related_rule_relation`

`canonical_rule_family` has **no** tier row in v1. Family **status** and **existence** still affect **rule_card** resolution (`invalid_family_link`, `family_not_active`).

## Corpus and materialization

- **Inventory:** Only `target_id` values in `CorpusTargetIndex` are tierable for HTTP reads and batch recompute.
- **`GET /adjudication/tier`:** Rejects unknown inventory ids (`unknown_corpus_target`, 404). Does not create rows for arbitrary strings.
- **`POST /adjudication/tiers/recompute-all`:** Upserts one tier row per inventory id for all four types; **deletes** tier rows for ids not in inventory (orphan cleanup).
- **After `canonical_rule_family` decisions:** All rule cards linked to that family (memberships + `canonical_family_id`) get tier rows recomputed.
- **After `merge_into`:** All rules in the target family get tier rows recomputed.

## `is_promotable_to_gold` (strict)

Means: the **current** adjudicated state could reach **Gold** without contradicting that state (e.g. not duplicate-capped, not rejected, no hard blockers).

- **Always false** for `gold`, `unresolved`, valid **duplicate** (Silver with `duplicate_not_gold_eligible`), **rejected** Bronze, and any hard blocker (`needs_review`, `ambiguous_state`, `invalid_family_link`, etc.).
- **May be true** only for **Silver** or **Bronze** with no disqualifying blockers (e.g. merged/split Silver with clean family/duplicate posture).

## Blocker codes (stable)

| Code | Meaning |
|------|---------|
| `no_adjudication_state` | No decisions yet for this target |
| `needs_review` | Rule coarse status needs_review |
| `ambiguous_state` | Ambiguous adjudication |
| `deferred_state` | Deferred |
| `unsupported_state` | Unsupported |
| `rejected_state` | Rejected rule card |
| `invalid_family_link` | `canonical_family_id` set but family row missing |
| `family_not_active` | Family exists but status is not `active` (v1 → **unresolved**, not Silver) |
| `invalid_duplicate_link` | Marked duplicate without `duplicate_of_rule_id` |
| `duplicate_not_gold_eligible` | Valid duplicate — tier capped at Silver |
| `weak_evidence_only` | Illustrative / weak evidence (Bronze path) |
| `missing_required_review` | Link/relation invalid or unknown |

## Rule card

| Tier | When (v1 resolver) |
|------|---------------------|
| **Unresolved** | No adjudication; OR any hard blocker (ambiguous, defer, unsupported, needs_review, invalid/missing family when linked, non-active family, invalid duplicate) |
| **Gold** | Approved, not duplicate, no hard blockers |
| **Silver** | Valid `duplicate_of` (capped below Gold); OR `merged` / `split_required` |
| **Bronze** | Rejected; OR other adjudicated paths below Silver bar |

## Evidence link

| Tier | When |
|------|------|
| **Unresolved** | No adjudication; unknown support; unsupported |
| **Gold** | `support_status == strong` |
| **Silver** | `partial` |
| **Bronze** | illustrative-only path (`weak_evidence_only`) |

## Concept link (v1)

| Tier | When |
|------|------|
| **Unresolved** | No adjudication; `link_status` invalid or unknown |
| **Gold** | `link_status == valid` |

There is **no** separate Silver/Bronze branch for concept links in v1.

## Related-rule relation (v1)

| Tier | When |
|------|------|
| **Unresolved** | No adjudication; `relation_status` invalid or unknown |
| **Gold** | `relation_status == valid` |

There is **no** separate Silver/Bronze branch for relations in v1.

## Unresolved queue alignment

The unresolved queue includes both (1) legacy state heuristics and (2) any inventory target whose **tier resolver** returns `unresolved`, so tier-only blockers (e.g. `family_not_active`, unsupported evidence) still surface as queue work.
