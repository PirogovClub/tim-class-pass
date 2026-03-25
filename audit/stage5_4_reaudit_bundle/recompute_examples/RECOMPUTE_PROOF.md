# Corpus-wide recompute — proof (Stage 5.4 re-audit)

## Code entry points

| Location | Role |
|----------|------|
| `pipeline/adjudication/repository.py` → `recompute_all_materialized_tiers(corpus_index)` | Iterates **all** `target_id` values in `CorpusTargetIndex` for `rule_card`, `evidence_link`, `concept_link`, `related_rule_relation`; upserts each via `resolve_tier_for_target`; **deletes** rows in `materialized_tier_state` whose `(target_type, target_id)` is not in inventory. |
| `pipeline/adjudication/api_service.py` → `recompute_all_tier_rows` | Wraps repository return as `TierRecomputeResponse`. |
| `pipeline/adjudication/api_routes.py` | `POST /adjudication/tiers/recompute-all` (requires corpus index). |

## Where inventory comes from

| Source | API |
|--------|-----|
| `CorpusTargetIndex` | `pipeline/adjudication/corpus_inventory.py` — frozen `frozenset` per type; production: `CorpusTargetIndex.from_explorer_repository(explorer._repo)`. |
| App wiring | `init_adjudication(..., corpus_index=...)` in `api_routes.py`; queues and tier GET already depend on the same index. |

## Execution example

```http
POST /adjudication/tiers/recompute-all
```

No body. Requires configured corpus index (503 if missing).

## Before / after counts (test corpus)

Using `STANDARD_TEST_CORPUS_INDEX` in `tests/adjudication_api/corpus_index_fixtures.py`:

- **Inventory size:** 20 rule_card + 2 evidence_link + 1 concept_link + 1 related_rule_relation = **24** targets.
- **Before recompute:** `materialized_tier_state` may only contain rows for “touched” targets (decisions or prior lazy GET /tier).
- **After `POST .../recompute-all`:** `GET /adjudication/tiers/counts` — sum of `totals_by_tier` values equals **24**; every inventory id has exactly one row.

Automated check: `test_post_recompute_all_matches_inventory` in `test_tier_audit_integration.py`.

## Stability

`test_recompute_idempotent` runs `recompute_all_materialized_tiers` twice and compares tier for a sample id — identical results.
