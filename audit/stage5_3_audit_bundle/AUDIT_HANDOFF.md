# Stage 5.3 audit handoff — human adjudication workstation (explorer UI)

**Requirement sources:** [`docs/requirements/stage 5/5-3.md`](../../docs/requirements/stage%205/5-3.md), [`docs/requirements/stage 5/5-3-audit-request.md`](../../docs/requirements/stage%205/5-3-audit-request.md).

**UI contract note:** [`notes/stage5_3_ui_contract.md`](../../notes/stage5_3_ui_contract.md).

---

## 1. Stage 5.3 scope (what it was)

Minimal **review workstation** in the existing explorer SPA: unresolved queue, single-item review driven by **review bundle**, **decision submission**, **next-item** navigation, and **side-by-side compare** via two bundle fetches. No proposal-generation UI, no new auth, no backend redesign.

---

## 2. What was implemented

- **Queue page** (`/review/queue`): table with type, id, queue reason, summary, status, latest decision, family id; filter via `targetType` query (`all` or `ReviewTargetType`); refresh; “Open next item” (calls next API then navigates).
- **Item page** (`/review/item/:targetType/:targetId`): summary + reviewed state, history, family panel (or “no family”), optional context JSON, rule-only compare shortcut → compare URL; **DecisionPanel**; back to queue / next in queue.
- **Compare page** (`/review/compare`): query params `aType`, `aId`, `bType`, `bId`; two columns each showing bundle summary, history, family, optional context, link to full review; when **both sides are `rule_card`** and loads succeed, **Decide from compare** (`CompareDecisionPanel`) submits `duplicate_of` or `merge_into` with related id prefilled from the opposite column, then refetches both bundles; invalid params → `ErrorPanel`.
- **API module** `adjudication.ts` + Zod schemas; **decision allow-lists** mirroring `pipeline/adjudication/policy.py` in `decisions.ts`.
- **Vite proxy** `/adjudication` → same base as `/browser` (`VITE_BROWSER_API_BASE`).
- **Top bar** link to review queue.
- **Playwright audit spec** with JSON fixtures and **20 screenshots** under `audit/stage5_3_audit_bundle/screenshots/`.

---

## 3. Intentionally not implemented

- Dedicated Vitest/RTL tests for queue, item, compare, and full decision flow (see **Test coverage gap** below).
- Separate `GET /adjudication/families/{id}` UI (bundle family slice is enough for 5.3 minimum).
- Batch review, graph view, analytics, export, auth, proposal UI.
- Mobile-specific layout work beyond default responsive grid (one narrow screenshot documents current behavior).

---

## 4. Pages / routes added or changed

| Route | Component |
|-------|-----------|
| `/review/queue` | `ReviewQueuePage` |
| `/review/item/:targetType/:targetId` | `ReviewItemPage` |
| `/review/compare` | `ReviewComparePage` |

**Query / URL state**

- Queue: `?targetType=` (`all` default when omitted).
- Item: path params + `?queueFilter=&queueReason=` (preserved from queue links / next).
- Compare: `?aType=&aId=&bType=&bId=`.

---

## 5. Stage 5.2 adjudication APIs used (by screen)

| Screen | HTTP |
|--------|------|
| Queue (all) | `GET /adjudication/queues/unresolved` |
| Queue (filter ≠ all) | `GET /adjudication/queues/by-target?target_type=` |
| Open next item | `GET /adjudication/queues/next?queue=unresolved` (+ optional `target_type=` when filtered) |
| Item + compare columns | `GET /adjudication/review-bundle?target_type=&target_id=` |
| Decision panel (item + compare) | `POST /adjudication/decision` |

No frontend duplication of persistence rules beyond **decision type allow-list** and **related_target_id** requirement for `duplicate_of` / `merge_into` (aligned with backend policy).

---

## 6. URL vs local state

**In URL (reload-safe):** queue filter, item identity, compare participants, queue filter/reason on item links.

**Local:** reviewer id (`localStorage` key `adjudication_reviewer_id`), decision form fields, loading/error for fetches, submit spinner/messages.

---

## 7. Refresh after decision submit

`DecisionPanel` calls `postDecision`, then `onSubmitted()` which is **`load()` on `ReviewItemPage`** — `load()` sets `loading`, refetches bundle, replaces `bundle`. **Note:** while `loading` is true the main grid (including `DecisionPanel`) unmounts, so the inline **“Decision recorded.”** line may disappear immediately; the refreshed bundle (status, history) is the durable signal. See screenshot `12-decision-success-refreshed.png`.

---

## 8. Next-item flow

- **From queue:** `getNextQueueItem(filter)` → navigate to `/review/item/...` with `queueFilter` + `queueReason`.
- **From item:** same API + navigate with `replace: true` on item page.

If the API returns no item, the queue page surfaces an error message; the item page surfaces “No next item in queue.”

---

## 9. Compare: enter, adjudicate, exit

- **Enter (rule_card):** “Compare with another rule” on item page → `/review/compare?...` or from queue item links indirectly via item page.
- **Enter (compare page):** paste/deeplink query params.
- **Adjudicate (rule_card pair):** choose primary side (A/B), `duplicate_of` (related = other rule id) or `merge_into` (related = other side’s family id when known); submit → `POST /adjudication/decision` → parallel refetch of both bundles.
- **Exit:** “Back to queue” on compare page → `/review/queue`; or “Open full review” per column → item page.

---

## 10. Deferred to later UI stages

- Rich diffing, evidence thumbnails, batch actions, reviewer auth/roles, offline queue, keyboard-first navigation, dedicated family drill-down API.

---

## 11. Stage 5.2 API assumptions changed?

**No.** The UI consumes documented adjudication endpoints and JSON shapes; it does not change server contracts.

---

## 12. Component map (extra)

- **Pages:** `ReviewQueuePage`, `ReviewItemPage`, `ReviewComparePage`
- **Panels:** `DecisionPanel`, `CompareDecisionPanel`, `HistoryPanel`, `FamilyPanel`, `OptionalContextPanel`, compare `BundleColumn` / `CompareFetch` (in `ReviewComparePage.tsx`)
- **API:** `adjudication.ts`, `adjudication-schemas.ts`, shared `client.ts`

---

## 13. API dependency map (extra)

- Queue page → unresolved / by-target queue, next
- Item page → review bundle, next, decision POST
- Compare page → two review bundles (parallel GETs) + optional compare decision POST + refetch

---

## 14. Workflow walkthrough (example)

1. Open `/review/queue` — unresolved rows and queue reasons.
2. Set filter to **Rule cards** (`?targetType=rule_card`).
3. Click **Open** on a row → `/review/item/rule_card/<id>?queueFilter=...&queueReason=...`.
4. Read **Summary**, **Reviewed state**, **Decision history**, **Canonical family** (if any), **Optional context**.
5. Choose **duplicate_of**, enter **Related target id**, submit — or choose **approve** if appropriate.
6. After submit, page refetches; **Latest decision** / **history** update (see note on toast above).
7. Click **Next in queue** → next item loads with same filter context.
8. Use **Compare with another rule** → compare view → **Back to queue** or **Open full review**.

*(With a live backend + corpus index and a registered reviewer id, the same flow hits real APIs; screenshots in this bundle use mocks for reproducibility.)*

---

## 15. Screenshots

**20 PNG files** in `screenshots/` with index in [`SCREENSHOT_INDEX.md`](SCREENSHOT_INDEX.md). Captured via `npm run audit:screenshots:5.3` after `npm run build`.

---

## 16. Commands run & results

Raw logs: `terminal/lint.txt`, `terminal/typecheck.txt`, `terminal/vitest.txt`, `terminal/build.txt`, `terminal/playwright-stage5-3-screenshots.txt`.

**Recorded in this bundle (explorer):**

| Command | Result |
|---------|--------|
| `npm run lint` | Pass (exit 0) |
| `npm run typecheck` | Pass (exit 0) |
| `npm run test` (Vitest) | Pass — full unit/component suite |
| `npm run build` | Pass (Vite chunk size warning only) |
| `npx playwright test stage5-3-audit-screenshots.spec.ts` | Pass — 6 tests, 20 screenshots |

**Full** `npm run test:e2e` (all Playwright specs) may fail if a spec expects a live or differently mocked browser API (see `terminal/playwright-default-e2e.txt` if present); Stage 5.3 evidence uses the **dedicated** screenshot spec above.

---

## 17. Test coverage vs 5-3-audit-request “minimum test set”

**Implemented today**

- `ui/explorer/src/lib/review/decisions.test.ts` — policy mirror (`decisionsForTarget`, `decisionRequiresRelatedTarget`).

**Not implemented (gap)**

- Vitest/RTL tests for queue page, item page, compare page, decision submit, next-item, and loading/empty/error as listed in §“Minimum test set” of `5-3-audit-request.md`.

**Mitigation for audit**

- Playwright **`stage5-3-audit-screenshots.spec.ts`** exercises mocked HTTP and captures **workflow + UI states** corresponding to many of those scenarios visually.
- Playwright **`compare-adjudication.spec.ts`** covers compare decision panel, prefill, submit + refreshed state, mixed-type pair (no panel), invalid params.

---

## 18. Known limitations

- Reviewer must exist server-side for real POST success; UI defaults `localStorage` to `workstation-reviewer`.
- Success toast on decision panel may not remain visible after refetch (unmount during loading).
- `merge_into` on compare needs a family id on the **opposite** bundle when prefill is empty; reviewer can paste manually.

---

## 19. Changed files list

See [`FILE_LIST.md`](FILE_LIST.md). Zip script copies the same paths into `sources/` for offline review: [`package_bundle.ps1`](package_bundle.ps1).

---

## 20. Explicit answers (audit-request checklist)

1. **Routes added:** `/review/queue`, `/review/item/:targetType/:targetId`, `/review/compare`.
2. **APIs per page:** see §5 table.
3. **URL vs local state:** see §6.
4. **Refresh after submit:** `onSubmitted` → `load()` refetch; see §7.
5. **Next-item:** `getNextQueueItem` + navigate; see §8.
6. **Compare enter/exit:** see §9.
7. **Deferred:** see §10.
8. **API assumptions changed:** no (§11).

---

**Confidence:** This bundle matches the requested package: handoff, file list, source snapshot (via script), tests/logs, routes, screenshots, walkthrough, and stated limitations (including the Vitest gap).
