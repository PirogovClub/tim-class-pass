For **Stage 5.1 audit**, I need a **full implementation bundle**, not only summary.

## What I need by default

### 1) Handoff note

One `AUDIT_HANDOFF.md` with:

* what exactly was implemented in Stage 5.1
* what was intentionally **not** implemented
* storage choice and why
* resolved-state policy and why
* changed files list
* commands run
* test results
* known limitations
* anything deferred to Stage 5.2+

---

## 2) All changed source files

Please include the actual code for all changed files, especially if you added:

* `pipeline/adjudication/enums.py`
* `pipeline/adjudication/models.py`
* `pipeline/adjudication/storage.py`
* `pipeline/adjudication/bootstrap.py`
* `pipeline/adjudication/repository.py`
* `pipeline/adjudication/resolver.py`
* `pipeline/adjudication/docs.md`

If names differ, that is fine, but I need the real files.

---

## 3) All changed test files

I need all tests added or modified for Stage 5.1.

At minimum I expect tests covering:

* schema/bootstrap
* append-only decisions
* resolver/current-state behavior
* canonical family persistence
* restart/reload durability
* invalid decision validation

---

## 4) Exact file list

Please include a compact tree or explicit file list so I can check scope fast.

Example:

* `pipeline/adjudication/...`
* `tests/...`
* `docs/...`

This helps me detect scope drift immediately.

---

# Validation evidence I need

## 5) Raw terminal output

Please include terminal output for:

* lint
* typecheck
* unit tests
* integration tests, if any were touched
* any DB/bootstrap validation command

I want:

* exact commands
* pass/fail
* warning text
* skipped tests if any

For example:

* `pytest ...`
* `ruff ...`
* `mypy ...` or project equivalent

---

## 6) Storage proof

Because Stage 5.1 is about durable storage, I need proof of that behavior.

Please include evidence for:

* schema creation from empty state
* idempotent bootstrap
* append decision -> reload -> data still present
* resolved state survives restart
* canonical family survives restart

This can be shown through tests and/or short reproducible logs.

---

## 7) Small sample data walkthrough

I want one concrete example, ideally pasted in the handoff, showing something like this:

### Example A — rule review history

* create reviewer
* append `needs_review`
* append `ambiguous`
* append `duplicate_of -> rule_123`
* show stored decisions
* show resolved state row

### Example B — evidence link

* append `evidence_partial`
* append `evidence_strong`
* show final resolved support state

### Example C — canonical family

* create family
* add canonical member
* add duplicate member
* reload
* show family + memberships still present

This makes audit much faster and more reliable.

---

# What I will check in the code

## 8) Scope discipline

I will verify that the patch stays inside Stage 5.1.

I expect:

* domain model
* storage
* repository
* resolver
* docs
* tests

I do **not** expect:

* review UI
* queue APIs
* AI proposal logic
* export logic
* Gold/Silver/Bronze resolution
* major explorer refactor

If those appear, I will treat that as scope drift unless clearly isolated.

---

## 9) Model quality

I will check whether the models are explicit and typed.

I expect:

* explicit enums for target types
* explicit enums for decision types
* no vague free-text-only state
* canonical family represented as first-class data
* resolved state represented cleanly

I will reject designs where important meaning exists only in notes.

---

## 10) Append-only correctness

This is one of the main audit points.

I will check that:

* review history is append-only
* later decisions do not destroy earlier decisions
* current state is derived from history
* decision order is deterministic

If the code silently overwrites history, that is a blocker.

---

## 11) Resolver policy

I need the agent to tell me clearly:

* is it **last-decision-wins**?
* or aggregated logic?
* what derived flags remain active?
* how duplicate/merge/family linkage is resolved?

I will audit whether the implemented behavior matches the documented policy.

---

## 12) Canonical family design

I will check that canonical family structure is explicit.

I expect:

* family object
* membership object/table
* member role
* linkage to rule reviewed state where relevant

I do not want “merged into family” existing only as a note or arbitrary JSON blob.

---

## 13) Durability and restart behavior

This is critical.

I will look for proof that:

* empty DB can be initialized
* data persists after connection close/reopen
* resolved state can be reconstructed after restart
* canonical memberships remain stable after restart

If this is missing, Stage 5.1 is not complete.

---

## 14) Documentation quality

I need a short internal doc explaining:

* what Stage 5.1 adds
* storage layout
* decision model
* resolved-state policy
* canonical family model
* how later Stage 5.2 can use this

It does not need to be long, but it must be clear.

---

# What I need the agent to state explicitly

Please make the agent answer these in the handoff:

1. **What DB/storage was used?**
2. **Why was that storage chosen?**
3. **What is the resolved-state policy?**
4. **How are canonical families represented?**
5. **What target types are supported now?**
6. **What decision types are supported now?**
7. **What was intentionally left for Stage 5.2 or later?**
8. **Did this patch touch any existing explorer behavior? If yes, how?**

---

# Minimum test set I expect

For Stage 5.1, I expect at least these tests or equivalent:

1. schema bootstrap from empty DB
2. bootstrap is idempotent
3. append-only decisions remain preserved
4. rule state resolves correctly across multiple decisions
5. evidence state resolves correctly across multiple decisions
6. canonical family persists and reloads
7. restart/reload keeps history and state intact
8. invalid decision inputs are rejected

---

# Helpful, but optional

These are not mandatory, but they help a lot:

* small SQLite file example or temp DB log
* schema diagram
* before/after note of what did not exist before
* one short explanation of tradeoffs made for simplicity

---

# What will block the audit quickly

These are common blockers:

* only summary, no code
* no tests
* no restart/durability proof
* history is overwritten instead of append-only
* resolved state exists only in memory
* canonical family is not first-class
* decision types are vague/free-form
* patch drifts into Stage 5.2+ without clear isolation
* no documentation of resolver policy

---

# Best way to send it

The cleanest audit submission is:

1. `AUDIT_HANDOFF.md`
2. changed file list
3. all changed source files
4. all changed test files
5. terminal output for lint/typecheck/tests
6. one small sample decision walkthrough
7. short note on known limitations

That is enough for me to do a serious audit.

**Confidence: High** — this is the right audit package for Stage 5.1 because the step is fundamentally about durable backend state, typed adjudication models, and restart-safe resolution behavior.
