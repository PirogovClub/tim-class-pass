For this audit, I expect a **full implementation bundle**, not just a summary.

## Minimum audit package

### 1) Handoff note

A single `AUDIT_HANDOFF.md` that states:

* what step/substep this patch is for
* what was changed
* what files were added/modified
* what known limitations remain
* what commands were run
* exact results of tests/lint/typecheck/build
* anything intentionally deferred

### 2) Changed code

Please include all changed files for the patch, especially:

* `pipeline/explorer/*`
* any backend read-model or API files
* any frontend route, page, component, hook, state, or client files
* any schema/type files
* any test files added or modified

I need the **actual code**, not only diffs summarized in prose.

### 3) Exact file list

A compact file tree or explicit list like:

* `frontend/...`
* `backend/...`
* `tests/...`
* `docs/...`

This helps me verify scope creep fast.

---

## Validation evidence I expect

### 4) Lint / typecheck / test / build results

I want the raw command outputs or clearly pasted terminal output for:

* lint
* typecheck
* unit tests
* integration tests
* production build

Please include:

* exact command used
* pass/fail
* warnings
* any skipped tests

For this project, “it runs locally” is not enough.

### 5) Screenshots or UI proof

For explorer/UI work, I expect screenshots showing the actual implemented behavior.

For Step 4.3-style compare/traversal work, I want screenshots for:

* main explorer page
* detail page
* compare flow
* related-rule / traversal flow
* deep-linked compare URL
* empty state
* loading state
* error state
* mobile/narrow layout if touched

### 6) Sample API responses

If backend endpoints changed or were added, include real sample JSON responses for:

* primary read endpoints
* compare-related endpoints
* related/traversal endpoints
* any filters/query params used by UI

This lets me verify contract quality, determinism, and frontend/backend alignment.

---

## Behavior I will audit directly

### 7) Scope discipline

I will check that the patch stays inside the accepted architecture.

I expect:

* explorer reads through the approved `/browser/*` read model
* no direct UI dependency on raw retrieval or raw extraction artifacts
* no accidental drift into ML, export, graph visualization, or unrelated tooling
* no hidden “temporary” shortcuts that bypass the intended layer

### 8) Determinism

I will check whether results are stable and reproducible.

I expect:

* deterministic ordering for related rules / grouped results
* stable IDs and stable compare behavior
* no random ordering from object iteration or unsorted arrays
* consistent behavior across reloads

### 9) Deep-linkability

This is important.

If compare/traversal is part of the patch, I expect:

* route state reconstructable from URL
* compare view shareable/reload-safe
* browser back/forward works correctly
* no fragile state that disappears on refresh unless explicitly justified

### 10) Edge-case handling

I expect proof for:

* nonexistent IDs
* malformed query params
* missing evidence
* empty compare selection
* duplicate selection attempts
* partial backend failures
* slow-loading states

---

## Tests I expect

### 11) Unit tests

For logic-heavy additions, I expect unit tests for:

* query param parsing
* compare selection logic
* grouping / traversal logic
* sorting / ranking logic
* state restoration from URL
* formatter / mapper functions

### 12) Integration tests

I expect integration coverage for real workflows, not only helper logic.

Examples:

* open explorer → open detail
* select two rules → compare
* open deep link directly → compare loads correctly
* move from detail → related rules
* invalid URL param → graceful fallback
* backend contract consumed by UI without runtime mismatch

### 13) Regression tests

Because this project is built on earlier guarantees, I expect proof that earlier accepted behavior still holds.

At minimum, tell me whether the patch affects:

* Step 3.1 retrieval guarantees
* Step 4.1 accepted flows
* Step 4.2 accepted flows

If yes, include regression evidence.

---

## What I will judge in the code

### 14) Architecture quality

I will review:

* separation of concerns
* whether business logic is buried in UI components
* whether state management is clean and minimal
* whether read models are well-shaped for UI
* whether component boundaries are reasonable
* whether naming is clear and domain-correct

### 15) Type safety

I expect:

* no unsafe `any` spread through key flows
* request/response typing aligned with actual payloads
* no silent coercion around IDs, params, or evidence collections
* frontend types derived from stable contracts where practical

### 16) UX quality

I will check:

* whether the feature is understandable without explanation
* whether labels match the trading knowledge domain
* whether compare/traversal actions are discoverable
* whether the user can recover from mistakes easily
* whether the page becomes noisy or cognitively overloaded

### 17) Code hygiene

I expect:

* no dead code
* no commented-out debug blocks
* no console noise left behind
* no duplicated mapper logic in multiple places
* no lint suppressions unless justified
* no “TODO” that hides critical missing behavior

---

## For this kind of patch, I usually need these exact artifacts

Please send these by default:

1. `AUDIT_HANDOFF.md`
2. all changed source files
3. all changed test files
4. terminal output for lint/typecheck/test/build
5. screenshots
6. sample JSON responses
7. note of known issues / deferred items
8. brief statement of what command or route I should use to mentally reproduce the flow

---

## What is optional but very helpful

These are not mandatory, but they make the audit much faster and stronger:

* a short “before vs after” behavior summary
* route examples like `/compare?...`
* one or two representative fixtures
* explanation of why URL state vs local state was chosen
* explanation of sorting/grouping rules for related items
* a note on whether backend payload shape was changed for UI convenience

---

## What will cause me to fail or block the patch quickly

These are the common audit blockers:

* only summary provided, no code
* no test evidence
* UI works only through local state and breaks on refresh
* direct coupling to raw retrieval data instead of approved read model
* unstable ordering
* missing empty/error/loading states
* compare flow not deep-linkable
* hidden scope expansion
* lint/typecheck failures without explicit approval
* regression risk with no proof

---

## Best way to send it

The cleanest submission is:

* one pasted handoff file
* one pasted file list
* changed files
* command outputs
* screenshots

That is enough for me to do a serious audit without having to pull details out one by one.

**Confidence: High** — based on the current project stage and the audit standard we have been using in this trading knowledge / explorer workflow.
