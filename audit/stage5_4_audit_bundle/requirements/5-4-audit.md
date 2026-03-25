
For **Stage 5.4 audit**, I will need a **full tier-resolution bundle**, not just a summary.

Because 5.4 is the step where the corpus becomes **quality-stratified**, I will audit four things very carefully:

* **policy correctness**
* **resolver correctness**
* **materialization / refresh correctness**
* **UI/API usefulness of tier and blocker information**

---

# What I need by default

## 1) `AUDIT_HANDOFF.md`

One handoff file that clearly states:

* what Stage 5.4 scope was
* what was implemented
* what was intentionally **not** implemented
* supported target types
* exact Gold / Silver / Bronze / Unresolved policy
* blocker-code list
* how canonical family affects rule-card tiering
* whether tier state is materialized or computed on demand
* exact routes added
* exact UI surfaces changed
* changed files list
* commands run
* test results
* known limitations
* what is deferred to 5.5+

---

## 2) All changed source files

I need the real code for all changed files.

For Stage 5.4, I expect files in areas like:

* tier enums
* tier models
* tier policy
* tier resolver
* tier repository / materialization logic
* tier service
* tier routes
* UI integration files for tier badge / blocker display
* docs

If names differ, that is fine, but I need the actual files.

---

## 3) All changed test files

I need all tests added or modified for Stage 5.4.

At minimum I expect tests for:

* tier policy / resolver
* materialization / refresh flow
* tier APIs
* counts / by-tier filters
* UI tier badge / blocker display
* missing tier data handling

---

## 4) Exact file list

Please include a compact file tree or explicit file list.

This helps me check quickly:

* scope discipline
* whether the patch drifted into 5.5 proposal generation
* whether it drifted into export or training prep
* whether it drifted into dashboard work
* whether the UI changes stayed light

---

# Validation evidence I need

## 5) Raw terminal output

Please include raw output for:

* lint
* typecheck
* backend tests
* frontend tests if UI changed
* build
* any recompute/materialization validation command

I want:

* exact commands
* pass/fail
* warnings
* skipped tests if any

---

## 6) Tier policy summary

I want a short but explicit policy summary in the handoff.

At minimum, for each supported target type, tell me:

* what qualifies as **Gold**
* what qualifies as **Silver**
* what qualifies as **Bronze**
* what forces **Unresolved**

This is mandatory, because Stage 5.4 is mostly about policy correctness.

---

## 7) Blocker-code list

I want the final blocker codes listed explicitly.

For example, things like:

* `no_adjudication_state`
* `needs_review`
* `ambiguous_state`
* `deferred_state`
* `unsupported_state`
* `invalid_family_link`
* `missing_family`

Use the real codes implemented.
I need to see the exact list.

---

## 8) Example JSON payloads

I need real request/response examples for the main new APIs.

At minimum:

### Single-target tier

* request
* success response
* missing target / invalid target response

### By-tier list

* one `gold`
* one `silver`
* one `unresolved`

### Counts

* counts by tier
* counts by tier + target type if implemented

These examples help me verify contract quality and whether blocker reasons are exposed cleanly.

---

## 9) Example resolution cases

I strongly want a few concrete examples in the handoff.

At minimum include:

### Example A — Gold rule card

Show:

* reviewed state
* family state if relevant
* final tier
* reasons
* blockers (should be empty or non-blocking)

### Example B — Silver rule card

Show:

* why it is not Gold
* why it is still above Bronze

### Example C — Bronze rule card

Show:

* why it stays low-trust but not unresolved

### Example D — Unresolved rule card

Show:

* blocker codes
* why resolution stopped there

### Example E — non-rule target

For example:

* Gold evidence link
  or
* unresolved concept link

These examples make Stage 5.4 much easier to audit correctly.

---

# What I will audit directly

## 10) Scope discipline

I will verify that this patch stays inside Stage 5.4.

I expect:

* tier policy
* blocker codes
* resolver
* materialization / refresh
* APIs
* light UI integration
* docs
* tests

I do **not** expect:

* proposal generation
* suggestion scoring
* export manifests
* training dataset generation
* dashboards
* workstation redesign
* reviewer assignment flow

If those appear, I will treat that as scope drift unless clearly isolated.

---

## 11) Policy quality

This is one of the highest-risk audit points.

I will check whether the policy is:

* explicit
* deterministic
* strict enough for Gold
* operational for Unresolved
* consistent across target types
* explainable to a reviewer

I will fail vague policies like:

* “Gold means reviewed enough”
* “Silver means kind of okay”
* “Bronze means lower quality”

That is not enough.

---

## 12) Resolver correctness

I will check that the resolver:

* produces exactly one tier
* produces clear reasons / blockers
* uses canonical family state correctly where relevant
* handles edge cases deterministically
* does not silently ignore blocker conditions

I especially care about:

* no adjudication state
* ambiguous state
* deferred state
* unsupported state
* invalid family linkage
* conflicting state inputs

---

## 13) Materialization / refresh correctness

This is another major audit point.

I will check:

* how tier state gets written
* when it refreshes
* whether single-target refresh works
* whether batch recompute works
* whether repeated recompute is stable
* whether tier state stays in sync with adjudication state changes

If tier state is stale or inconsistently refreshed, that is a serious problem.

---

## 14) API quality

I will check that tier APIs are:

* typed
* stable
* useful
* not leaking storage internals

I want to see:

* target tier fetch
* by-tier filtering
* counts
* explicit reasons/blockers in responses

A tier API that returns only `tier = gold` without reasons is too weak.

---

## 15) UI usefulness

The UI integration can stay light, but it has to be useful.

I will check that the workstation shows:

* tier badge
* blocker summary or reasons
* enough information for a reviewer to understand why the item is not Gold

I do **not** need a new big screen.
But I do need the tier layer to be visible where review decisions happen.

---

## 16) Counts / summary usefulness

I will check that tier counts are:

* reproducible
* deterministic
* useful for operational understanding

Counts are important because 5.4 is where you start measuring corpus quality.

---

# What I need the agent to state explicitly

Please make the agent answer these in the handoff:

1. What target types are tiered now?
2. What exact policy decides Gold / Silver / Bronze / Unresolved?
3. What blocker codes exist?
4. Is tier state materialized or computed on demand?
5. How does tier refresh happen after adjudication changes?
6. Is there a batch recompute path?
7. What new routes were added?
8. What UI surfaces now show tier / blocker info?
9. What is intentionally deferred to 5.5+?
10. Did the patch touch any existing Stage 5.2 or 5.3 contracts?

---

# Minimum test set I expect

For Stage 5.4, I expect at least these tests or equivalent.

## Resolver / policy tests

1. Gold rule-card case
2. Silver rule-card case
3. Bronze rule-card case
4. Unresolved rule-card with no adjudication
5. Unresolved rule-card with ambiguous
6. Unresolved rule-card with defer
7. Unresolved rule-card with invalid family linkage
8. Gold evidence-link case
9. unresolved concept-link case
10. unresolved related-rule-relation case

## Materialization tests

11. tier row created on refresh
12. tier row updated after adjudication-state change
13. batch recompute works
14. repeated recompute is stable

## API tests

15. fetch target tier succeeds
16. missing target handled correctly
17. by-tier filtering works
18. counts endpoint works
19. blocker codes and reasons are present in response

## UI integration tests

20. tier badge renders
21. blocker summary renders
22. missing tier data handled gracefully

---

# Very helpful extra evidence

These are not mandatory, but very useful.

## 17) One end-to-end refresh example

Please include one example like:

1. item starts unresolved
2. decision changes reviewed state
3. tier refresh runs
4. item becomes Silver or Gold
5. API shows updated tier
6. UI shows updated tier badge/blockers

This helps prove the tier layer is connected to real adjudication state, not only static logic.

## 18) Small architecture note

A short note showing:

* where policy lives
* where resolver lives
* where materialization happens
* where API mapping happens
* where UI pulls the tier info from

That makes the audit faster.

---

# What will block the audit quickly

These are common blockers for 5.4:

* only summary, no code
* no clear tier policy
* no blocker-code list
* no tests
* tier results are not deterministic
* Gold is too loose
* Unresolved is vague
* no refresh/materialization proof
* APIs return too little explanation
* UI integration is missing or useless
* scope drift into proposals/export/dashboard

---

# Best way to send it

The cleanest Stage 5.4 audit submission is:

1. `AUDIT_HANDOFF.md`
2. changed file list
3. all changed source files
4. all changed test files
5. policy summary
6. blocker-code list
7. example JSON payloads
8. example resolution cases
9. raw terminal output for lint/typecheck/tests/build
10. screenshots if UI changed
11. known limitations

That is enough for a serious audit.

**Confidence: High** — this is the right audit package for Stage 5.4 because the step is fundamentally about explicit policy, deterministic resolution, durable tier state, and whether the system can now separate trusted vs provisional corpus items in a way that later proposal-assisted review and export can rely on.


create result zip package that i can upload for this stage