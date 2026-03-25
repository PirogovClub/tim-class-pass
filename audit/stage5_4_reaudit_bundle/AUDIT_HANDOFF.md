# Stage 5.4 — Re-audit handoff (post–first-audit fixes)

**Prepared for:** `docs/requirements/stage 5/5-4-audit-2.md` (copy in `requirements/5-4-audit-2.md`)  
**Bundle layout:** `AUDIT_HANDOFF.md`, `changed_files.txt`, `TEST_EVIDENCE_MAP.md`, `test_output.txt`, `api_examples/`, `recompute_examples/`, `source/` (code mirrors).

---

## Implementation summary

This resubmission addresses the **first 5.4 audit blockers**:

1. **Corpus-wide tier materialization** — `recompute_all_materialized_tiers` + `POST /adjudication/tiers/recompute-all`; counts/list-by-tier reflect full inventory after recompute; orphan tier rows purged.
2. **Missing-target protection** — `GET /adjudication/tier` validates `CorpusTargetIndex` **before** refresh; **404** `unknown_corpus_target`; no spurious inserts.
3. **Family-dependent refresh** — On `canonical_rule_family` decisions and on `merge_into`, all linked rule cards get tier rows recomputed.
4. **Promotability semantics** — `_is_promotable_to_gold` is strict (duplicate-capped and rejected are **false**).
5. **Policy/docs/code** — `notes/stage5_4_tier_policy.md` aligned with `quality_tier.py` (incl. concept/relation v1 = Gold or Unresolved only; non-active family → unresolved).
6. **Queue / tier alignment** — `_collect_tier_only_unresolved` adds inventory items that are tier-unresolved but skipped by legacy state heuristics.
7. **Tests** — Unit + HTTP + UI coverage mapped in `TEST_EVIDENCE_MAP.md`.

---

## Deferred / out of scope

- Separate “tier-only” queue endpoint (not added; merged into existing unresolved queue).
- CLI wrapper for recompute (HTTP `POST .../recompute-all` is the supported entry point).
- Silver/Bronze branches for concept/relation beyond v1 (explicitly documented as not implemented).

---

## Proof index (maps to `5-4-audit-2.md`)

| Audit § | Evidence in this zip |
|---------|----------------------|
| §1 Corpus-wide recompute | `recompute_examples/RECOMPUTE_PROOF.md`, `api_examples/post_recompute_all_response.json`, `source/.../repository.py` |
| §2 Missing-target protection | `recompute_examples/MISSING_TARGET_NO_INSERT.md`, `api_examples/tier_unknown_corpus_404.json`, `source/.../api_service.py` |
| §3 Family refresh | `recompute_examples/FAMILY_REFRESH_PROOF.md`, `test_tier_audit_integration.py` (family test) |
| §4 Promotability | `recompute_examples/PROMOTABILITY_PROOF.md`, `source/.../quality_tier.py` |
| §5 Policy alignment | `recompute_examples/POLICY_ALIGNMENT.md`, `source/notes/stage5_4_tier_policy.md`, `api_examples/resolver_outputs_by_type.json` |
| §6 Queue alignment | `recompute_examples/QUEUE_ALIGNMENT_PROOF.md`, `source/.../queue_service.py` |
| §7 Test evidence | `TEST_EVIDENCE_MAP.md`, `test_output.txt`, `source/tests/adjudication_api/*.py`, `source/ui/.../QualityTierPanel.test.tsx` |

---

## Schema / migrations

SQLite: `materialized_tier_state` defined in `source/pipeline/adjudication/storage.py` (`CREATE TABLE IF NOT EXISTS` + indexes). No Flyway-style migration artifact; `initialize_adjudication_storage` is idempotent.

---

## Commands to reproduce tests

```bash
cd tim-class-pass
python -m pytest tests/adjudication_api -q

cd ui/explorer
npm run test
```

---

## Statement

No proposal generation, export pipeline, training-data prep, dashboards, or workstation redesign included in this patch set.
