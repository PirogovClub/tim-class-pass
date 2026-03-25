# Test evidence map — `5-4-audit-2.md` §7 checklist

Mapped to `tests/adjudication_api/` and UI tests. Run: `pytest tests/adjudication_api -q` (79 passed at bundle time).

| Required case | Test file | Test function |
|---------------|-----------|---------------|
| Silver rule-card | `test_quality_tier_unit.py` | `test_rule_silver_duplicate_not_promotable` |
| Silver rule-card (API) | `test_tier_audit_integration.py` | `test_duplicate_silver_not_promotable_via_api` |
| Bronze rule-card | `test_quality_tier_unit.py` | `test_rule_bronze_rejected_not_promotable` |
| Unresolved ambiguous | `test_quality_tier_unit.py` | `test_rule_unresolved_ambiguous` |
| Unresolved defer | `test_quality_tier_unit.py` | `test_rule_unresolved_defer` |
| Unresolved invalid-family | `test_quality_tier_unit.py` | `test_rule_unresolved_invalid_family`, `test_rule_unresolved_family_not_active` |
| Gold evidence-link | `test_quality_tier_unit.py` | `test_evidence_gold` |
| Unresolved concept-link | `test_quality_tier_unit.py` | `test_concept_unresolved_unknown`, `test_concept_tiers` |
| Unresolved related-rule relation | `test_quality_tier_unit.py` | `test_relation_unresolved_invalid` |
| Tier row create/update | `test_tier_audit_integration.py` | `test_tier_row_updates_after_decision` |
| Full recompute | `test_tier_audit_integration.py` | `test_post_recompute_all_matches_inventory` |
| Repeated recompute stability | `test_tier_audit_integration.py` | `test_recompute_idempotent` |
| Missing target API | `test_tier_audit_integration.py` | `test_get_tier_unknown_corpus_target_returns_404` |
| Tier reasons in API | `test_tier_routes.py` | `test_tier_unresolved_without_decision` (asserts `tier_reasons`) |
| UI badge / blocker / missing tier | `ui/.../QualityTierPanel.test.tsx` | `renders tier badge and blockers`, `handles missing tier data gracefully` |

Full suite also includes `test_api_bundle.py` (`quality_tier` on bundle for needs_review).
