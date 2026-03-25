# Missing-target protection — no bogus `materialized_tier_state` row

## Code path

1. `GET /adjudication/tier` → `api_service.get_tier_for_target(..., corpus_index=corpus_index)` (corpus required on route).
2. **Before** any read/refresh: `if corpus_index is not None and not corpus_index.contains(target_type, target_id):` → `_raise_unknown_corpus_target` → **404** with `error_code: unknown_corpus_target`.
3. `repo.refresh_materialized_tier` is **not** called when validation fails, so **no** `INSERT OR REPLACE` into `materialized_tier_state`.

## Verification

- HTTP: `test_get_tier_unknown_corpus_target_returns_404` (`test_tier_audit_integration.py`).
- Sample response: see `api_examples/tier_unknown_corpus_404.json`.

Optional manual check: query `SELECT COUNT(*) FROM materialized_tier_state WHERE target_id = 'rule:does_not_exist_in_inventory';` after a 404 — expect **0** (or unchanged from prior state if DB had unrelated data).
