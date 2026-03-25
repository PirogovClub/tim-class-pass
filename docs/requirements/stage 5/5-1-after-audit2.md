I re-audited the revised Stage 5.1 bundle.

## Verdict

**Closer, but still not accepted yet.**

The original blockers were fixed well, but I found **one remaining integrity gap** that is still serious enough to block Stage 5.2.

## What is now fixed

The revised bundle correctly addresses the issues from the first audit:

* decisions now reject **unknown reviewers**
* `merge_into` now rejects **missing family IDs**
* `add_rule_to_family(...)` now rejects **missing family IDs**
* invalid **target/decision combinations** are now blocked by policy
* the integrity tests for those cases are present and pass

I also re-ran the included test suite locally after stubbing the missing `utc_now_iso` helper, and got:

* **30 passed**

So the patch clearly improved the foundation.

---

## Remaining blocker

### Decisions targeting `canonical_rule_family` still allow nonexistent families

This still works right now:

* create reviewer
* append decision with

  * `target_type = canonical_rule_family`
  * `target_id = "missingfam"`
  * `decision_type = approve`
* decision is stored successfully
* no family exists with that id
* status refresh runs, but updates zero rows

So the system accepts a durable adjudication decision for a family that does not exist.

That means Stage 5.1 still allows invalid adjudication history for one of its supported review target types.

### Why this is blocking

Because `canonical_rule_family` is explicitly listed as a supported review target in the handoff and policy.
Once that target type exists, decisions against it should have the same integrity standard as other first-class entities.

Right now:

* reviewer existence is enforced
* rule-card `merge_into` family existence is enforced
* membership family existence is enforced

But:

* direct family-target decisions do **not** enforce family existence

That leaves the adjudication layer internally inconsistent.

---

## Exact fix I want

Add family existence validation when:

* `payload.target_type == ReviewTargetType.CANONICAL_RULE_FAMILY`

before allowing:

* `append_decision(...)`
* `append_decision_and_refresh_state(...)`

In practice, `_prepare_decision_append(...)` should also do:

* if target type is `CANONICAL_RULE_FAMILY`, assert `target_id` exists in `canonical_rule_families`

### Add tests for this

At minimum:

1. `append_decision(...)` rejects nonexistent canonical family target
2. `append_decision_and_refresh_state(...)` rejects nonexistent canonical family target
3. valid family-target decisions still succeed for existing family rows

---

## Non-blocking notes

These are not the reason for failure, but they are still true:

### 1) Bundle is still not standalone

It still depends on `pipeline.orchestrator.models.utc_now_iso`, which is not included in the zip.
So I had to stub that helper again to rerun tests.

### 2) Bundle hygiene is still not clean

The zip still contains:

* `__pycache__/`
* `.pyc`

Not a blocker, but the packaging script is not actually producing the clean bundle it claims.

### 3) Optional policy question

`create_canonical_family(...)` still allows `created_by` values that do not exist in `reviewers`.

I am **not** treating that as a blocker right now, because you may want `created_by` to support system/import identities later.
But you should decide that policy explicitly.

---

## Conclusion

So the revised patch is **better and very close**, but I still cannot accept it as the Stage 5.1 foundation.

### Required re-audit patch

Please send one small integrity patch that does:

* enforce existence of `canonical_rule_family` target rows for family-target decisions
* add the 2–3 tests above
* update the handoff note to mention that rule explicitly

Once that is fixed, acceptance is likely.

**Confidence: High** — I directly verified that the first-round blockers are fixed and that the remaining family-target integrity gap is still real in the current code path.
