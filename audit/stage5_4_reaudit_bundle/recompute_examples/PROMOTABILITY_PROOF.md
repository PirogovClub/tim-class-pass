# `is_promotable_to_gold` — definition and examples

## Definition (implemented)

`pipeline/adjudication/quality_tier.py` → `_is_promotable_to_gold(tier, blockers)`:

- **False** if `tier` is `gold` or `unresolved`.
- **False** if `duplicate_not_gold_eligible` or `rejected_state` appears in `blocker_codes`.
- **False** if any structural blocker is present:  
  `no_adjudication_state`, `needs_review`, `ambiguous_state`, `deferred_state`, `unsupported_state`, `invalid_family_link`, `family_not_active`, `invalid_duplicate_link`, `missing_required_review`.
- **True** only for `silver` or `bronze` with **no** disqualifying blockers (e.g. merged + active family, empty blockers).

This is **not** a vague “could improve later” flag; duplicate-capped and rejected paths are explicitly non-promotable under current adjudicated meaning.

## Examples

| Case | Tier | Key blockers | `is_promotable_to_gold` | Test |
|------|------|--------------|-------------------------|------|
| Duplicate-capped Silver | silver | `duplicate_not_gold_eligible` | **false** | `test_rule_silver_duplicate_not_promotable`, `test_duplicate_silver_not_promotable_via_api` |
| Rejected Bronze | bronze | `rejected_state` | **false** | `test_rule_bronze_rejected_not_promotable` |
| Unresolved (ambiguous) | unresolved | `ambiguous_state` | **false** | `test_rule_unresolved_ambiguous` |
| Merged + active family | silver | `[]` | **true** | `test_silver_merged_promotable_if_clean` |
| Gold | gold | `[]` | **false** | `test_rule_gold` |
