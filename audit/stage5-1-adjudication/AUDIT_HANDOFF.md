# Stage 5.1 audit handoff — Adjudication domain model and storage

This bundle satisfies [`docs/requirements/stage 5/5-1-audit.md`](../../docs/requirements/stage%205/5-1-audit.md), [`5-1-after 1st-audit.md`](../../docs/requirements/stage%205/5-1-after%201st-audit.md), and [**`5-1-after-audit2.md`**](../../docs/requirements/stage%205/5-1-after-audit2.md) (family-as-target existence + clean zip + local timestamps).

**Regenerate this bundle + zip:** `powershell -File audit/stage5-1-adjudication/package_bundle.ps1` — syncs snapshot `pipeline/` + `tests/`, runs pytest + compileall → `AUDIT_VALIDATION_OUTPUT.txt`, builds `audit/archives/stage5_1_adjudication_bundle.zip` from the **manifest** in the script (`$ArchiveRelativePaths`, must match [`AUDIT_FILE_LIST.md`](AUDIT_FILE_LIST.md)), strips bytecode on the **staging** tree only, then **verifies** the zip contains exactly those paths (no extras, no `__pycache__` / `.pyc`).

---

## 1) What was implemented (Stage 5.1 + integrity patch)

- **Typed domain layer:** `ReviewTargetType`, `DecisionType`, reviewer/membership/family/resolution enums; Pydantic models (`enums.py`, `models.py`).
- **Durable SQLite storage:** `reviewers`, `review_decisions`, `canonical_rule_families`, `canonical_rule_memberships`, four `*_reviewed_state` tables (`storage.py`, `bootstrap.initialize_adjudication_storage`).
- **Repository:** Append-only decisions; family CRUD; `append_decision_and_refresh_state` (transaction: validate → append → optional `merge_into` membership → resolve → upsert state); getters (`repository.py`).
- **Resolver:** Per-target pure functions; order `(created_at, decision_id)`; **last-decision-wins** (`resolver.py`).
- **Write integrity (post–1st-audit):**
  - `pipeline/adjudication/errors.py` — `ReviewerNotFoundError`, `FamilyNotFoundError`, `InvalidDecisionForTargetError`, base `AdjudicationIntegrityError`.
  - `pipeline/adjudication/policy.py` — strict allow-list of `DecisionType` per `ReviewTargetType`; `assert_decision_allowed_for_target`.
  - `append_decision` / `append_decision_and_refresh_state` require **existing reviewer**; **`merge_into`** (rule card) requires **existing family** in `canonical_rule_families`; **`add_rule_to_family`** requires **existing family**.
  - **Post–2nd-audit:** for `target_type=canonical_rule_family`, **`target_id` must be an existing `family_id`** before append (`FamilyNotFoundError` otherwise). Decisions cannot target a missing family row.
- **`time_utils.py`:** `utc_now_iso()` lives under `pipeline/adjudication/` so the adjudication package does not import `pipeline.orchestrator` (cleaner audit zip / stubs not required for timestamps).
- **Documentation:** `pipeline/adjudication/docs.md` (IDs, storage, resolver policy, **write integrity**, `created_by` policy note, FK pragma note).

---

## 2) What was intentionally not implemented

- Review **UI**, **`/review/*` HTTP APIs**, **queue**, **AI proposal** generation, **ranking**, **Gold/Silver/Bronze**, **export** pipelines.
- Wiring adjudication into the **explorer** read path (explorer unchanged).
- **SQLite FOREIGN KEY** constraints on `review_decisions.reviewer_id` / family ids (optional stronger fix deferred; application checks enforce writes).
- **Ruff / mypy** in default project config; this bundle records **pytest + compileall** (see `AUDIT_VALIDATION_OUTPUT.txt`).

---

## 3) Storage choice and why

- **SQLite** via `sqlite3`, aligned with `pipeline/orchestrator/state_store.py`.
- **Why:** Stage 5.1 spec; no ORM in deps; durable indexed tables; configurable path (e.g. `var/adjudication.db`).

---

## 4) Resolved-state policy and why

- **Ordering:** `(created_at, decision_id)` ascending.
- **Last-decision-wins** for latest fields and rule-card booleans (`is_duplicate`, `is_deferred`, `is_unsupported`, `is_ambiguous`).
- **`canonical_family_id`:** From latest `merge_into` **or** enrichment from `canonical_rule_memberships` (deterministic `family_id` order) so linkage survives a later non-merge decision.
- **Evidence / concept / relation:** Latest allowed decision for that target sets materialized status columns.

---

## 5) Append-only correctness

- `review_decisions`: **INSERT-only** (no update/delete of history).
- Reviewed state: **`INSERT OR REPLACE`** on state tables only.

---

## 6) Canonical family design

- Tables `canonical_rule_families` + `canonical_rule_memberships` with roles `canonical` | `member` | `variant` | `duplicate`, **`UNIQUE(family_id, rule_id)`**.
- `merge_into`: `related_target_id` = **`family_id`**; membership upsert with `added_by_decision_id`.

---

## 7) Explicit answers (audit checklist)

1. **DB/storage?** SQLite file + `sqlite3`; `initialize_adjudication_storage(db_path)`.
2. **Why?** Spec, project pattern, no extra ORM.
3. **Resolved-state policy?** Last-decision-wins + membership enrichment for `canonical_family_id` (see §4).
4. **Canonical families?** First-class relational rows, not JSON blobs.
5. **Target types?** `rule_card`, `evidence_link`, `concept_link`, `related_rule_relation`, `canonical_rule_family`.
6. **Decision types?** Full enum exists in code; **each target type only accepts an allow-list** on append (see `policy.py` and `docs.md`). Family targets: `approve`, `reject`, `needs_review`, `defer`, `ambiguous` (drives status refresh).
7. **Stage 5.2+?** HTTP APIs, UI, queue, proposals, export, ranking, G/S/B, explorer wiring.
8. **Explorer touched?** **No.**

---

## 8) Changed files list

See [`AUDIT_FILE_LIST.md`](AUDIT_FILE_LIST.md). The bundle mirrors `pipeline/adjudication/*` and `tests/test_adjudication_*.py`.

---

## 9) Commands run (see `AUDIT_VALIDATION_OUTPUT.txt` for latest)

```text
python -m pytest tests/test_adjudication_models.py tests/test_adjudication_resolver.py tests/test_adjudication_storage.py tests/test_adjudication_restart.py tests/test_adjudication_integrity.py -v --tb=short
python -m compileall -q pipeline/adjudication
```

(`package_bundle.ps1` runs these and refreshes the log.)

---

## 10) Test results

- **32 passed** (23 core + **9 integrity** tests in `test_adjudication_integrity.py`).
- **Integrity tests:** unknown reviewer; missing family on `merge_into` / `add_rule_to_family`; invalid target/decision combo; **missing family as `canonical_rule_family.target_id`** on `append_decision` and `append_decision_and_refresh_state`; valid cross-type combo including existing family-target approve.
- **Minimum audit set:** schema bootstrap, idempotent init, append-only history, rule/evidence resolution, family persist + reload, restart durability, invalid model/repo inputs — all covered.

---

## 11) Storage proof (evidence mapping)

| Requirement | Evidence |
|-------------|----------|
| Schema from empty DB | `initialize_adjudication_storage` + `test_schema_bootstrap_all_tables` |
| Idempotent bootstrap | `test_initialize_idempotent` |
| Append → reload | `test_restart_reloads_history_and_state`, `test_canonical_family_persistence_reload` |
| Resolved state survives restart | `test_restart_reloads_history_and_state` |
| Integrity on write | `test_adjudication_integrity.py` |

---

## 12) Sample walkthroughs

### Example A — rule review (reviewer must exist first)

1. `create_reviewer(...)`
2. `append_decision_and_refresh_state(RULE_CARD, needs_review, reviewer_id="u1")`
3. `append_decision_and_refresh_state(..., AMBIGUOUS, ...)`
4. `append_decision_and_refresh_state(..., DUPLICATE_OF, related_target_id="rule:lesson:r2", ...)`
5. `get_decisions_for_target` → 3 rows; `get_rule_card_state` → duplicate flags set.

### Example B — evidence link

1. After reviewer exists: `EVIDENCE_PARTIAL` then `EVIDENCE_STRONG` on same `target_id` → `get_evidence_link_state` → `STRONG`.

### Example C — canonical family

1. `create_canonical_family` → `family_id`
2. `add_rule_to_family` ×2 (e.g. canonical + duplicate roles)
3. New repository on same DB path → family + memberships unchanged.

---

## 13) Known limitations

- **No DDL foreign keys**; integrity enforced **on write** in repository + policy.
- **duplicate_of** does not require the related rule row to exist (only `related_target_id` format / non-empty).
- **Multi-family** per rule: enrichment picks one `family_id` deterministically.
- **Lint/typecheck:** not part of default dev deps; see validation log.
- **Full test run** still expects repo layout (`pipeline.*` imports, `pyproject` pytest config); the zip is a **source snapshot**, not a separate installable package.

---

## 14) Documentation for auditors

- Spec: [`docs/requirements/stage 5/5-1.md`](../../docs/requirements/stage%205/5-1.md).
- Post–1st-audit: [`5-1-after 1st-audit.md`](../../docs/requirements/stage%205/5-1-after%201st-audit.md).
- Post–2nd-audit: [`5-1-after-audit2.md`](../../docs/requirements/stage%205/5-1-after-audit2.md).
- Implementation: `pipeline/adjudication/docs.md` in this bundle.

---

## 15) Scope discipline

Domain + storage + repository + resolver + integrity + docs + tests only. No review UI, queue APIs, AI, export, G/S/B, explorer refactor.
