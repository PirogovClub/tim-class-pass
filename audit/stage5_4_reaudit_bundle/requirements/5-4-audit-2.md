Yes — **same base requirements**, but for the **re-audit** I would want a slightly **expanded bundle** so I can verify the exact fixes that blocked 5.4.

## Base materials — still required

Please send the same core set:

* implementation summary / handoff note
* changed file list
* full code for:

  * tier enums / models / policy / resolver
  * repository / service / routes
  * refresh / materialization hooks
  * UI files changed
* schema or migration changes
* test files
* test run output
* sample API responses
* list of anything intentionally deferred

## Additional materials required for the re-audit

Because of the issues I found, I now also need these explicitly:

### 1. Corpus-wide recompute proof

Send:

* the code for full recompute
* where target inventory comes from
* one execution example
* before/after counts proving it populates the whole supported corpus, not just touched rows

### 2. Missing-target protection proof

Send:

* code path for target existence validation
* example API response for a nonexistent `rule_card`
* example showing no bogus row is inserted into materialized tier state

### 3. Family-change refresh proof

Send:

* code that recomputes dependent rule cards when family state changes
* one example:

  * family inactive → rule unresolved
  * family activated → linked rule recomputed
* before/after tier row examples

### 4. Promotability semantics proof

Send:

* exact definition of `is_promotable_to_gold`
* examples for:

  * duplicate-capped item
  * rejected item
  * unresolved blocked item
  * legitimate promotable item

### 5. Policy alignment proof

Send:

* the final tier policy document
* resolver output examples for each supported target type
* short note confirming code and docs now match exactly

### 6. Queue alignment proof

Send:

* changed queue logic, if any
* one example showing a tier-unresolved item appears correctly in the unresolved workflow
* note if you created a separate tier-driven unresolved source instead

### 7. Test evidence for the missing cases

Please include output for these exact cases:

* Silver rule-card
* Bronze rule-card
* unresolved ambiguous rule-card
* unresolved defer rule-card
* unresolved invalid-family rule-card
* Gold evidence-link
* unresolved concept-link
* unresolved related-rule relation
* tier row create/update
* full recompute
* repeated recompute stability
* missing target API case
* UI badge/blocker/missing-tier coverage, if implemented

## Best submission format

For the next audit, the cleanest bundle would be:

1. `AUDIT_HANDOFF.md`
2. `changed_files.txt`
3. migrations / schema
4. backend code
5. frontend code
6. tests
7. `test_output.txt`
8. `api_examples/`
9. `recompute_examples/`

So: **yes, same requirements overall**, but now I also need **direct proof for each blocker I raised**, not just the updated code.

**Confidence: High** — this follows directly from the 5.4 audit findings and what is needed to verify a resubmission correctly.
check