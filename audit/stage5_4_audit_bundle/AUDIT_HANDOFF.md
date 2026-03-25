# Stage 5.4 — Audit handoff (quality tiers)

**Bundle prepared:** 2026-03-24  
**Repository:** `tim-class-pass`  
**Audit request checklist:** `requirements/5-4-audit.md` (included in this zip)

This package contains: `AUDIT_HANDOFF.md`, `CHANGED_FILES.txt`, `TERMINAL_OUTPUT.txt`, `examples/tier_api_examples.json`, a copy of the audit request, and **`source/`** tree with the listed implementation and test files.

---

## 1. Stage 5.4 scope (what was in scope)

- Deterministic **Gold / Silver / Bronze / Unresolved** resolution for adjudicated targets.
- Explicit **tier_reasons** and **blocker_codes**, plus eligibility / promotable flags, **resolved_at**, **policy_version**.
- **Materialized** tier rows in SQLite, refreshed when adjudication state changes (and on-demand via tier read path).
- **HTTP APIs:** single-target tier, list by tier, counts (including breakdown by target type).
- **Light UI:** review item page panel; queue column + optional client-side tier filter (`qualityTier` query param).
- **Policy document** in repo notes.

---

## 2. What was implemented

| Area | Implementation |
|------|----------------|
| Policy | `notes/stage5_4_tier_policy.md` + `tier_policy.v1` in `quality_tier.py` |
| Resolver | `pipeline/adjudication/quality_tier.py` (`resolve_rule_card_tier`, evidence/concept/relation resolvers, `resolve_tier_for_target`) |
| Enum / model | `QualityTier` in `enums.py`; `MaterializedTierRecord` in `models.py` |
| Storage | Table `materialized_tier_state` in `storage.py` |
| Materialization | `repository.py`: upsert after `append_decision_and_refresh_state`; `get_materialized_tier`, `refresh_materialized_tier`, `list_materialized_tiers`, `materialized_tier_counts` |
| APIs | `GET /adjudication/tier`, `GET /adjudication/tiers/by-tier`, `GET /adjudication/tiers/counts` |
| Bundle / queue | `bundle_service.py` adds `quality_tier`; `queue_service.py` merges tier string from materialized table |
| UI | `QualityTierPanel.tsx`, `ReviewItemPage.tsx`, `ReviewQueuePage.tsx`, Zod types in `adjudication-schemas.ts` |
| Tests | `test_tier_routes.py`, extended `test_api_bundle.py` |

---

## 3. Intentionally not implemented (or deferred)

- **Batch corpus-wide tier recompute** (CLI, admin POST, or job): not present. Only per-target refresh and refresh-on-decision.
- **`pipeline/adjudication/docs.md`** route table: not updated with Stage 5.4 endpoints (policy lives in `notes/stage5_4_tier_policy.md`).
- **Dedicated tier row for `canonical_rule_family`:** v1 explicitly does not tier families; they still **influence** `rule_card` tiering via family existence/status.
- **Automated UI tests** (badge/blockers/missing tier): not added.
- **Full matrix** of resolver/materialization tests listed in `5-4-audit.md` § “Minimum test set”: only a **subset** is automated (see § Test results below).

---

## 4. Supported target types (tiered)

`rule_card`, `evidence_link`, `concept_link`, `related_rule_relation`  
(`TIER_MATERIALIZED_TARGET_TYPES` in `repository.py`)

---

## 5. Gold / Silver / Bronze / Unresolved — policy summary

**Policy version:** `tier_policy.v1`  
**Source of truth for branches:** `pipeline/adjudication/quality_tier.py`

### `rule_card`

| Tier | Qualifies when (simplified) |
|------|-----------------------------|
| **Unresolved** | No adjudication; OR hard blockers: ambiguous, defer, unsupported, needs_review coarse status, invalid/missing family when linked, invalid duplicate link |
| **Gold** | Approved, no hard blockers, not duplicate-of (duplicate caps below Gold) |
| **Silver** | Valid `duplicate_of` (capped below Gold with `duplicate_not_gold_eligible`); OR merged / split_required structured states |
| **Bronze** | Rejected (discovery-only with `rejected_state`); OR other adjudicated cases below Silver bar (e.g. remaining paths with weak duplicate cap only) |

Family: if `canonical_family_id` set, family row must exist and be **active**; else unresolved blockers.

### `evidence_link`

| Tier | Qualifies when |
|------|----------------|
| **Unresolved** | No adjudication; unknown support; unsupported |
| **Gold** | `support_status == strong` |
| **Silver** | `partial` |
| **Bronze** | illustrative-only / weak (`weak_evidence_only` blocker) |

### `concept_link`

| Tier | Qualifies when |
|------|----------------|
| **Unresolved** | No adjudication; invalid or unknown link |
| **Gold** | explicitly valid |

(No separate Silver/Bronze branch — valid → Gold per current v1.)

### `related_rule_relation`

| Tier | Qualifies when |
|------|----------------|
| **Unresolved** | No adjudication; invalid or unknown relation |
| **Gold** | explicitly valid |

---

## 6. Blocker codes (exact strings in code)

From `quality_tier.py` (see also policy table in `notes/stage5_4_tier_policy.md`):

- `no_adjudication_state`
- `needs_review`
- `ambiguous_state`
- `deferred_state`
- `unsupported_state`
- `rejected_state`
- `invalid_family_link`
- `family_not_active`
- `invalid_duplicate_link`
- `duplicate_not_gold_eligible`
- `weak_evidence_only`
- `missing_required_review`

---

## 7. Materialized vs on-demand

- **Materialized** in SQLite: `materialized_tier_state`.
- **When written:** after each successful `append_decision_and_refresh_state` for a tiered target type; also `refresh_materialized_tier` when `GET /adjudication/tier` runs and no row exists yet (`refresh_if_missing=True` default).

---

## 8. New HTTP routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/adjudication/tier` | Query: `target_type`, `target_id` → `TierStateResponse` |
| GET | `/adjudication/tiers/by-tier` | Query: `tier`, optional `target_type`, `limit` → `TierListResponse` |
| GET | `/adjudication/tiers/counts` | → `TierCountsResponse` (`by_target_type`, `totals_by_tier`) |

---

## 9. UI surfaces changed

- **Review item:** `QualityTierPanel` — tier badge, policy version, eligibility flags, reasons list, blocker chips; dashed placeholder when `quality_tier` is null (unsupported type).
- **Review queue:** Tier column; **Quality tier** dropdown filter (client-side); `qualityTier` preserved in links to item and back; footer “Showing X of Y”.

**Screenshots:** not included in this zip (optional follow-up).

---

## 10. Changed files list

See **`CHANGED_FILES.txt`** in this bundle. Source copies live under **`source/`** with the same relative paths.

---

## 11. Commands run & test results

See **`TERMINAL_OUTPUT.txt`**.

Summary:

- `npm run lint` / `npm run typecheck` / `npm run build` in `ui/explorer` — **pass**
- `python -m pytest tests/adjudication_api -q` — **58 passed**
- No dedicated frontend test run for tier UI (no such tests in repo).

---

## 12. Known limitations

- No **batch recompute** for all corpus targets after bulk DB or policy changes.
- **Minimum test set** in `5-4-audit.md` (Silver/Bronze rule cards, family-invalid cases, evidence/concept/relation resolver cases, materialization batch/repeat stability, UI tests) is **not fully covered** by automated tests.
- `GET /tier` for supported types **materializes** if missing rather than returning 404 (unless callers add a stricter mode later).
- `pipeline/adjudication/docs.md` does not yet list tier routes.

---

## 13. Deferred to 5.5+

- Proposal-assisted review, scoring, export manifests, training datasets, dashboards, assignment workflows (per Stage 5.4 non-goals).
- Batch tier refresh job/CLI.
- Richer Silver/Bronze gradations for concept/relation if product requires it.

---

## 14. Touching Stage 5.2 / 5.3 contracts

- **Additive only:** `ReviewBundleResponse.quality_tier` (optional), `QueueItemResponse.quality_tier` (optional). Existing clients ignoring unknown fields remain valid.
- New **GET** routes under existing `/adjudication` prefix; no change to decision POST contract beyond downstream tier refresh side effect.

---

## 15. Explicit answers (from `5-4-audit.md` § “What I need the agent to state”)

1. **Tiered target types:** `rule_card`, `evidence_link`, `concept_link`, `related_rule_relation`.
2. **Policy:** Deterministic rules in `quality_tier.py` + summary in `notes/stage5_4_tier_policy.md` (§5 above).
3. **Blocker codes:** §6 above.
4. **Materialized?** Yes — `materialized_tier_state`; lazy upsert on first tier GET if missing.
5. **Refresh after adjudication:** Upsert tier inside same transaction path as `append_decision_and_refresh_state` for tiered types.
6. **Batch recompute path?** **No.**
7. **New routes:** §8 above.
8. **UI surfaces:** §9 above.
9. **Deferred:** §13 above.
10. **5.2/5.3 contracts:** §14 above.

---

## 16. Example resolution cases (concrete)

### A — Gold rule card

- **Reviewed state:** `current_status=approved`, not duplicate, not ambiguous/defer/unsupported, family absent or linked family exists and `active`.
- **Tier:** `gold`
- **Reasons:** e.g. “Approved with no ambiguity, deferral, or unsupported flags.”
- **Blockers:** `[]`

### B — Silver rule card (duplicate)

- **Why not Gold:** valid `duplicate_of` caps tier; blocker `duplicate_not_gold_eligible` (non-hard for promotion flag semantics).
- **Why above Bronze:** structured duplicate resolution → **Silver** in resolver.

### C — Bronze rule card

- **Example:** `current_status=rejected` → **Bronze**, blocker `rejected_state`, reason “Rejected — retained for search/discovery only.”

### D — Unresolved rule card

- **Example:** `needs_review` coarse status → **Unresolved**, blocker `needs_review`, reasons include hard-blocker explanation.

### E — Non-rule target

- **Gold evidence link:** `support_status=strong`, no blockers.
- **Unresolved concept link:** no adjudication → `no_adjudication_state`; or `link_status` invalid/unknown → `missing_required_review`.

---

## 17. End-to-end refresh narrative (single item)

1. Item in corpus, no decision → `GET /tier` → **unresolved**, `no_adjudication_state`.
2. `POST /adjudication/decision` with `approve` → reviewed state updated; tier row upserted in same flow.
3. `GET /tier` → **gold** (if no blockers).
4. `GET /adjudication/review-bundle` → `quality_tier` populated.
5. Workstation **Quality tier** panel shows badge and empty blockers for Gold.

---

## 18. Small architecture note

| Concern | Location |
|---------|----------|
| Policy wording | `notes/stage5_4_tier_policy.md` |
| Resolver | `pipeline/adjudication/quality_tier.py` |
| Materialization / SQL | `storage.py`, `repository.py` |
| HTTP DTOs / mapping | `api_models.py`, `api_service.py`, `api_routes.py` |
| Bundle / queue enrichment | `bundle_service.py`, `queue_service.py` |
| UI | `QualityTierPanel.tsx`; data from `GET /adjudication/review-bundle` and queue list APIs |

---

## 19. JSON API examples

See **`examples/tier_api_examples.json`**.

---

**Statement:** This Stage 5.4 work does **not** include proposal generation, export pipelines, training-data prep, dashboards, workstation redesign, or reviewer assignment workflows.
