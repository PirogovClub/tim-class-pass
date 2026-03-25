# Family-change refresh — dependent rule-card tiers

## Code

`pipeline/adjudication/repository.py`:

- `_refresh_rule_card_tiers_for_family(family_id)` — collects rule ids from `canonical_rule_memberships` **union** `rule_card_reviewed_state.canonical_family_id`, then upserts tier for each rule.
- Called after:
  - `append_decision_and_refresh_state` when `target_type == CANONICAL_RULE_FAMILY`
  - `merge_into` (refreshes tiers for **all** rules in `related_target_id` family)

## Example scenario (automated)

`test_family_approve_refreshes_linked_rule_tier` in `test_tier_audit_integration.py`:

1. Create family in **DRAFT**.
2. `merge_into` rule `rule:w:1` → family.
3. **Tier row:** `unresolved` with blocker `family_not_active` (family not active).
4. `approve` on **canonical_rule_family** → family **ACTIVE**.
5. **Tier row:** recomputed to **Silver** (`merged` structured state + active family).

This proves the rule’s materialized tier updates **without** a new decision on the rule itself.
