# Policy alignment — docs vs code

## Authoritative policy text

`notes/stage5_4_tier_policy.md` (bundled under `source/notes/`).

## Resolver implementation

`pipeline/adjudication/quality_tier.py` — `tier_policy.v1`, deterministic branches per target type.

## Confirmation

| Topic | Documented in policy note | Implemented in `quality_tier.py` |
|-------|---------------------------|-----------------------------------|
| Rule card G/S/B/U | Yes | Yes (`resolve_rule_card_tier`) |
| Non-active family → unresolved (not Silver) | Yes | Yes (`family_not_active` hard blocker) |
| Evidence G/S/B/U | Yes | Yes (`resolve_evidence_link_tier`) |
| Concept: only Gold or Unresolved in v1 | Yes | Yes (`resolve_concept_link_tier`) |
| Relation: only Gold or Unresolved in v1 | Yes | Yes (`resolve_related_rule_relation_tier`) |
| Blocker code set | Table in note | Constants + `_record` / resolvers |
| Strict `is_promotable_to_gold` | Yes | `_is_promotable_to_gold` |

## Resolver examples by target type (abbreviated)

See `api_examples/resolver_outputs_by_type.json` for illustrative `MaterializedTierRecord`-style outcomes.
