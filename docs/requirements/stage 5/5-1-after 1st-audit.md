I audited the Stage 5.1 bundle.

## Verdict

**Not accepted yet.**
The bundle is strong structurally, but I found **foundation-level integrity gaps** that should be fixed before Stage 5.2 builds on it.

## What is good

The patch is disciplined and mostly stays inside Stage 5.1:

* clear `pipeline/adjudication/*` module split
* append-only `review_decisions`
* materialized reviewed-state tables
* canonical family + membership tables
* resolver layer is clean and understandable
* tests are present and targeted
* the handoff is well prepared

I also re-ran the included Stage 5.1 tests locally and they passed.
One caveat: the bundle is **not fully standalone runnable** because it imports `pipeline.orchestrator.models.utc_now_iso`, which is not included in the zip, so I had to stub that import to run the tests.

## Blocking issues

### 1) Referential integrity is claimed, but not actually enforced

This is the biggest issue.

The handoff says integrity is application-level, but the code currently allows invalid family links.

I confirmed all of these are accepted right now:

* `merge_into` with a **nonexistent family_id**
* `add_rule_to_family(...)` with a **nonexistent family_id**
* resulting reviewed state stores that bogus family id as if it were valid

That means canonical structure is not trustworthy yet.

Why this blocks Stage 5.1:

* Step 5.1 is the persistence foundation
* canonical family structure must be durable and meaningful
* allowing orphan memberships and fake merges weakens the whole adjudication layer

### 2) Decisions can be written with a nonexistent reviewer

I confirmed the repository accepts a decision whose `reviewer_id` does not exist in `reviewers`.

That means supposedly non-anonymous review history is not actually enforced.

Why this blocks Stage 5.1:

* reviewer identity is part of the audit trail
* if reviewer existence is optional in practice, the audit trail is weaker than the design claims

### 3) Invalid target/decision combinations are accepted

The models validate that `duplicate_of` and `merge_into` require `related_target_id`, but they do **not** validate whether a decision type is semantically allowed for a given target type.

I confirmed an example like this is currently accepted:

* `target_type = evidence_link`
* `decision_type = duplicate_of`

The system does not reject it. It materializes an `UNKNOWN` evidence state instead.

Why this blocks Stage 5.1:

* typed enums are not enough if nonsensical combinations are allowed into durable storage
* Stage 5.1 should protect the adjudication layer from invalid states, not just store them politely

---

## Non-blocking issues

These are not the reason for failure, but they should be cleaned up.

### 1) Bundle hygiene

The zip includes:

* `__pycache__/`
* `.pyc`

These should not be in audit bundles.

### 2) Validation is incomplete from the bundle alone

The provided tests pass, but the zip is missing the dependency that provides `utc_now_iso`.
So the bundle is not fully self-contained for independent rerun.

### 3) Lint/typecheck were skipped

Not fatal for this patch, but still worth improving later.

---

## Why I am failing this patch instead of accepting with notes

If this were a UI patch, I would be more willing to accept with non-blocking notes.

But this is **Stage 5.1**, the **domain and storage foundation** for all future adjudication work.

At this stage, the system must prevent obviously invalid adjudication state from being persisted.

Right now it does not.

---

## Exact next patch I want

### Required fixes

#### A. Enforce reviewer existence before decision insert

Before `append_decision(...)` or `append_decision_and_refresh_state(...)` writes a row:

* verify `reviewer_id` exists in `reviewers`
* if not, raise a clear exception

#### B. Enforce canonical family existence

Before:

* `add_rule_to_family(...)`
* `merge_into` decision handling

verify that the target family exists in `canonical_rule_families`.

If not, raise a clear exception.

#### C. Enforce allowed decision types per target type

Add a strict compatibility map, for example:

* `rule_card` may allow:

  * `approve`, `reject`, `duplicate_of`, `merge_into`, `split_required`, `unsupported`, `ambiguous`, `needs_review`, `defer`
* `evidence_link` may allow:

  * `evidence_strong`, `evidence_partial`, `evidence_illustrative_only`, `evidence_unsupported`
* `concept_link` may allow:

  * `concept_valid`, `concept_invalid`
* `related_rule_relation` may allow:

  * `relation_valid`, `relation_invalid`
* `canonical_rule_family` may allow only the subset you actually support now

Reject invalid combinations early.

#### D. Add tests for those rules

At minimum I want new tests for:

* decision append fails for nonexistent reviewer
* `merge_into` fails for nonexistent family
* `add_rule_to_family` fails for nonexistent family
* invalid target/decision combo is rejected
* valid target/decision combos still pass

---

## Optional stronger fix

If you want the storage layer to be stronger, add real foreign keys where practical.

At minimum, note this clearly:

* right now `PRAGMA foreign_keys=ON` does nothing useful for the family/reviewer relationships because the schema does not define those foreign keys

You do not have to switch to full FK enforcement immediately, but then application-level checks must really exist.

---

## After that patch, I expect acceptance to be likely

Because the rest of the bundle is solid:

* architecture is clean
* resolver policy is understandable
* append-only history is correct
* canonical family structure is first-class
* durability tests are already there

So this is not a large rework.
It is one integrity patch.

## What to send for the re-audit

Send:

* updated source files
* updated tests
* handoff note describing the new integrity rules
* terminal output for the updated test run

**Confidence: High** — I verified the main failure cases directly by exercising the bundle logic, and these are true foundation-level integrity gaps rather than style preferences.
