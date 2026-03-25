For **Stage 5.3 audit**, I will need a **full UI implementation bundle**, not only screenshots or a summary.

Because 5.3 is the first real human adjudication workstation, I will audit both:

* **workflow usefulness**
* **frontend correctness / integration with Stage 5.2 APIs**

---

# What I need by default

## 1) `AUDIT_HANDOFF.md`

One handoff file that clearly states:

* what Stage 5.3 scope was
* what was implemented
* what was intentionally **not** implemented
* exact pages/routes added
* exact Stage 5.2 APIs used
* state-handling choices:

  * what is in URL
  * what is local state
* changed files list
* commands run
* test results
* screenshots included
* known limitations
* what is deferred to later stages

---

## 2) All changed source files

I need the actual code for all changed files.

For Stage 5.3, I expect things in areas like:

* review queue page
* review item page
* compare page/panel
* decision panel
* history panel
* family panel
* queue list/filter components
* API hooks/client helpers
* route wiring
* frontend docs

If names differ, that is fine, but I need the real files.

---

## 3) All changed test files

I need all tests added or modified for Stage 5.3.

At minimum I expect tests for:

* queue page
* review item page
* decision submission flow
* state refresh after submit
* next-item flow
* compare workflow
* loading / empty / error states

---

## 4) Exact file list

Please include a compact file tree or explicit file list.

This helps me check quickly:

* scope discipline
* whether the patch drifted into backend changes
* whether it drifted into proposal generation UI
* whether it drifted into dashboards/export/auth
* whether compare logic was isolated cleanly

---

# Validation evidence I need

## 5) Raw terminal output

Please include raw output for:

* lint
* typecheck
* frontend tests
* build
* any E2E test command if you ran it

I want:

* exact commands
* pass/fail
* warnings
* skipped tests if any

Example:

* `npm test`
* `npm run lint`
* `npm run build`
* `vitest`
* `playwright` or project equivalent

---

## 6) Exact pages/routes added

I want the exact UI routes/pages that were added or changed.

For example:

* `/review/queue`
* `/review/item/:targetType/:targetId`
* `/review/compare?...`

If your route names differ, list the real ones.

---

## 7) Screenshots

For Stage 5.3, screenshots are mandatory.

I need screenshots for:

## Queue page

* default unresolved queue
* filtered queue
* empty queue state
* queue error state

## Review item page

* review page with real data
* review page with no family
* review page with family context
* loading state
* error state

## Decision flow

* decision panel before submit
* success state after submit
* validation error example
* backend/API error example

## Compare flow

* compare view with two items
* compare flow after submitting a duplicate/merge-related action
* compare missing-item or invalid compare state if applicable

## Workflow

* next-item flow
* return-to-queue behavior if visible
* narrow/mobile layout if touched

These screenshots let me check whether the UI is actually usable, not just technically present.

---

## 8) One workflow walkthrough

I want one real end-to-end walkthrough in the handoff.

Example:

1. open unresolved queue
2. filter to `rule_card`
3. open one item
4. inspect state/history/family
5. submit `duplicate_of`
6. state refreshes
7. click next item
8. next review item loads

This is very helpful because Stage 5.3 is mostly about workflow quality.

---

# What I will audit directly

## 9) Scope discipline

I will verify that this patch stays inside Stage 5.3.

I expect:

* queue page
* review page
* decision UI
* history/family panels
* compare flow
* navigation/state handling
* tests
* docs
* screenshots

I do **not** expect:

* backend API redesign
* proposal generation UI
* analytics dashboard
* export tools
* auth system
* broad explorer rewrite
* graph view
* batch review tooling

If those appear, I will treat that as scope drift unless clearly isolated.

---

## 10) API integration quality

I will check that the UI uses Stage 5.2 APIs correctly.

I want to see clean use of:

* review bundle
* decision submission
* unresolved queue
* by-target queue if used
* next-item
* family detail/members only if needed separately

I do **not** want:

* frontend reconstructing backend rules
* raw fetch logic duplicated everywhere
* direct storage assumptions in UI code

---

## 11) Route and state design

I will check what lives in:

* URL
* local state

For Stage 5.3, I care a lot about whether:

* queue filters are stable
* review pages are reload-safe
* compare state is not fragile
* return-to-queue flow preserves useful context

Please state this clearly in the handoff.

---

## 12) Queue usefulness

This is important.

I will check:

* queue is understandable
* queue reason is visible
* filters work
* open-item action works
* empty/error/loading states exist
* the queue is actually useful as a work entry point

A queue that only renders rows is not enough.
It has to support real review flow.

---

## 13) Review page usefulness

I will check whether the page gives enough bounded context for adjudication.

At minimum, I expect it to surface clearly:

* target summary
* current status
* latest decision
* history
* family context if relevant
* decision controls

Optional context like evidence/relations/concepts is good if present, but the key question is:

## Can a reviewer make a real decision from this page?

That is the audit standard.

---

## 14) Decision panel quality

This is one of the highest-risk parts.

I will check that:

* valid decisions can be submitted
* required fields are asked for when needed
* invalid input is surfaced clearly
* the UI does not silently allow obviously invalid actions
* success/error/pending states are handled
* the page refreshes after a successful write

If submit works but the page stays stale, that is a serious issue.

---

## 15) Compare workflow quality

I do not need a huge compare system yet.

But I do need:

* a real path into compare
* two items shown clearly
* enough context to compare meaningfully
* a usable path for duplicate/merge review
* clean path back to normal review flow

I will fail “compare” if it is only a placeholder screen with two IDs.

---

## 16) Workflow ergonomics

This matters in 5.3 more than in earlier stages.

I will check:

* next-item flow
* return-to-queue
* preservation of useful context
* whether a reviewer can move through multiple items without friction

If the UI forces too much repeated navigation, it is not good enough yet.

---

## 17) Error / loading / empty states

I will explicitly audit these.

I expect graceful states for:

* queue loading
* queue empty
* queue error
* review loading
* review error
* compare missing/invalid state
* submit pending
* submit failure

No broken blank screen behavior.

---

# What I need the agent to state explicitly

Please make the agent answer these in the handoff:

1. What pages/routes were added?
2. What Stage 5.2 APIs does each page use?
3. What state is kept in URL vs local state?
4. How does the page refresh after decision submit?
5. How does next-item work?
6. How is compare entered and exited?
7. What is intentionally deferred to later UI stages?
8. Did the patch change any Stage 5.2 API assumptions?

---

# Minimum test set I expect

For Stage 5.3, I expect at least these tests or equivalent.

## Queue page

1. queue loads successfully
2. queue filter works
3. queue empty state renders
4. queue error state renders
5. open-item navigation works

## Review item page

6. review bundle loads and renders
7. history panel renders
8. family panel renders when relevant
9. missing optional context does not crash the page
10. review error state renders

## Decision flow

11. valid decision submission succeeds
12. invalid local form state is blocked or surfaced clearly
13. pending state is shown
14. success state appears
15. page refreshes or reflects updated state after submit
16. backend/API error is shown cleanly

## Next-item workflow

17. next-item action works
18. no-next-item state is handled
19. return-to-queue works

## Compare flow

20. compare renders two items
21. compare handles invalid/missing item state gracefully
22. duplicate/merge action can be submitted from compare flow

---

# Very helpful extra evidence

These are not mandatory, but very useful.

## 18) Component map

A short note showing:

* pages
* major components
* hooks/API client modules

This helps me check frontend architecture quickly.

## 19) API dependency map

A tiny mapping like:

* queue page → unresolved queue API
* review page → review bundle API
* decision panel → decision submission API
* next-item button → next-item API
* compare page → review bundle for both sides + decision submission

That makes audit faster.

---

# What will block the audit quickly

These are common blockers for 5.3:

* only screenshots, no code
* only code, no screenshots
* no tests
* queue page exists but is not useful
* review page does not show enough context
* decision panel submits but page does not refresh
* compare flow is placeholder-only
* no next-item flow
* broken or missing empty/error/loading states
* frontend reimplements backend adjudication rules
* scope drift into dashboards/proposals/export/auth

---

# Best way to send it

The cleanest Stage 5.3 audit submission is:

1. `AUDIT_HANDOFF.md`
2. changed file list
3. all changed source files
4. all changed test files
5. route/page list
6. screenshots
7. one workflow walkthrough
8. raw terminal output for lint/typecheck/tests/build
9. known limitations

That is enough for a serious audit.

All in one zip archive with proper name for the stage

**Confidence: High** — this is the right audit package for Stage 5.3 because the step is fundamentally about workflow usability, clean UI/API integration, and whether a human can actually perform adjudication efficiently on top of the accepted Stage 5.2 backend.
