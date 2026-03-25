# Stage 5.4 — Quality tier policy (v1)

**Policy version string:** `tier_policy.v1`

See [`docs/requirements/stage 5/5-4.md`](../docs/requirements/stage%205/5-4.md) for goals and blocker vocabulary.

## Supported targets (this version)

- `rule_card`, `evidence_link`, `concept_link`, `related_rule_relation`

`canonical_rule_family` is not assigned its own tier row in v1; it still affects **rule_card** tier checks (family existence / status).

## Blocker codes (stable)

| Code | Meaning |
|------|---------|
| `no_adjudication_state` | No decisions yet for this target |
| `needs_review` | Rule coarse status or explicit review-needed path |
| `ambiguous_state` | Ambiguous adjudication |
| `deferred_state` | Deferred |
| `unsupported_state` | Unsupported |
| `rejected_state` | Rejected — not trusted for downstream |
| `invalid_family_link` | `canonical_family_id` set but family row missing |
| `family_not_active` | Family exists but status is not `active` |
| `invalid_duplicate_link` | Marked duplicate without `duplicate_of_rule_id` |
| `duplicate_not_gold_eligible` | Valid duplicate — capped below Gold per policy |
| `weak_evidence_only` | Evidence not strong enough for Gold |
| `missing_required_review` | Link/relation invalid or unknown |

## Rule card (summary)

- **Unresolved** if any hard blocker above applies.
- **Gold** only if: `current_status == approved`, not duplicate/ambiguous/defer/unsupported, duplicate/family checks pass, family (if any) is `active`.
- **Silver** if: not Unresolved, not Gold, and has meaningful positive adjudication (e.g. merged, valid duplicate, approved with draft family, or split_required handled as structured).
- **Bronze** if: in corpus, reviewed or row exists, not Unresolved, below Silver bar (e.g. rejected, or approved with blockers that cap tier).

## Evidence / concept / relation (summary)

- **Unresolved**: no decisions, invalid/unsupported/unknown where policy requires clarity.
- **Gold**: strong/valid + reviewed.
- **Silver**: partial / acceptable.
- **Bronze**: weak or minimal review.

Exact branches are implemented in `pipeline/adjudication/quality_tier.py` (deterministic).
