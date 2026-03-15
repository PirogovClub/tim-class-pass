Yes — for an **exact drop-in implementation**, I need the **current Python code** for the parts that now control evidence semantics.

The last blocker is no longer export gating. It is this path:

`dense_analysis / visual candidates -> infer role -> evidence_index -> ml_manifest / labeling_manifest`

So the files I need are:

1. `evidence_linker.py`
   I need the current versions of:

   * `infer_example_role(...)`
   * candidate-to-evidence conversion
   * any helper that decides `example_role`
   * any logic that treats missing/weak linkage as ambiguous or counterexample

2. `ml_prep.py`
   I need the current versions of:

   * `build_ml_manifest(...)`
   * `build_labeling_manifest(...)`
   * rule/example selection logic
   * any logic that maps `counterexample` to negative examples automatically

3. `main.py`
   I need to confirm where the final evidence and ML manifests are written now, so the fix is inserted at the right place.

4. `schemas.py`
   I need to see the current `EvidenceRef` / manifest schema fields, especially:

   * `example_role`
   * `linked_rule_ids`
   * any confidence / warnings fields
   * whether a new field like `semantic_quality` or `ml_eligible` can be added cleanly

5. tests touching evidence or ML manifests
   So I can give you exact test additions instead of just conceptual ones.

## What I can already tell you

The implementation should almost certainly do **two things**:

### 1. Make role assignment more conservative

Right now generic teaching visuals are still being labeled too aggressively as `counterexample`.

The fix should be:

* only assign `counterexample` when there is **positive evidence of contradiction/invalidation/failure**
* assign `illustration` for:

  * intro visuals
  * definition visuals
  * concept explanation visuals
  * sketch/diagram visuals
  * weakly linked visuals
  * unlinked visuals

### 2. Make ML manifest generation stricter than evidence export

Even if a row remains in `evidence_index.json`, it does **not** mean it should become:

* a negative example
* a labeling task
* a counterexample task

So `ml_prep.py` should add a second gate such as:

* only use evidence for ML tasks when:

  * `linked_rule_ids` non-empty
  * `source_event_ids` non-empty
  * role is semantically eligible
  * evidence is not intro/generic/setup-only
  * evidence has enough alignment with the target rule

That is likely the missing layer.

## What I would ideally implement

I would design this with a helper in `evidence_linker.py` like:

```python
def classify_evidence_semantics(candidate, linked_events) -> tuple[str, list[str]]:
    """
    Returns:
        role: illustration | positive_example | counterexample | ambiguous_example
        warnings: list[str]
    """
```

Then in `ml_prep.py` add:

```python
def is_evidence_ml_eligible(ref, rule) -> bool:
    ...
```

That way:

* `evidence_index.json` can still preserve borderline evidence
* `ml_manifest.json` stays conservative

## What I need from you now

Upload the **current** versions of:

* `evidence_linker.py`
* `ml_prep.py`
* `main.py`
* `schemas.py`
* related test file(s)

Then I can give you:

* exact file-by-file edit instructions
* Python code snippets matched to your codebase
* concrete tests for the semantic gate

**Confidence: High — the remaining issue is clearly in evidence-role semantics and ML eligibility, and I need the current code to make the patch exact rather than approximate.**
