Yes — **Task 14 should be a serious testing and validation task**, and it should go beyond unit tests.

**Confidence: High**

At this point your pipeline has many transformation steps:

* raw dense visual extraction
* filtered visual events
* chunk sync
* knowledge extraction
* evidence linking
* rule reduction
* confidence scoring
* provenance
* concept graph
* ML-prep
* exporters

So Task 14 should be about making sure the **whole chain is reliable**, not just that individual functions return something.

# Task 14 — Integration Testing and Acceptance Checks

## Goal

Build a strong testing layer that validates the pipeline **end to end** and **across module boundaries**, so you can trust that changes in one stage do not silently break downstream artifacts.

Task 14 should ensure:

* each stage writes valid outputs
* downstream stages can consume upstream outputs without fragile assumptions
* provenance survives the whole pipeline
* confidence, evidence, rule cards, and exporters remain internally consistent
* final markdown is clean and does not regress into transcript or visual spam
* the same input produces stable outputs

---

## Why this task matters

By now, the pipeline is no longer “just one script.”

It is a multi-stage system with contracts between stages. The biggest risks are no longer syntax errors. The biggest risks are:

* field drift between stages
* missing provenance after merge/split
* weak evidence linking breaking rule cards
* exporters silently rendering bad or incomplete content
* path/layout regressions
* confidence/ML-prep fields becoming inconsistent
* output still “looking okay” while being structurally wrong

So yes — Task 14 should include **solid integration testing across all modules**.

---

# What Task 14 should cover

## 1. Contract-level integration tests

These tests verify that outputs from one stage are valid inputs to the next.

Examples:

* `knowledge_events.json` produced by Step 3 is accepted by Step 4
* `evidence_index.json` produced by Step 4 is accepted by Step 5
* `rule_cards.json` produced by Step 5 is accepted by Task 12, Task 13, and exporters
* exporters can render from structured artifacts without raw chunks

This is the minimum required layer.

## 2. End-to-end lesson pipeline tests

These should run a representative lesson fixture through the structured pipeline:

* chunks
* knowledge events
* evidence index
* rule cards
* concept graph
* ML-prep
* exporters

Then validate:

* all expected files exist
* all JSON loads cleanly
* markdown outputs are non-empty and structurally sane
* key invariants hold

This is the most important part of Task 14.

## 3. Invariant tests

These validate rules that must always hold.

Examples:

* every `RuleCard` has `source_event_ids`
* every `EvidenceRef` has `frame_ids` or `raw_visual_event_ids`
* every `KnowledgeEvent` has chunk provenance
* no raw visual blobs leak into structured outputs
* `RuleCard.visual_summary` stays compact
* review markdown and RAG markdown are not identical
* RAG markdown does not contain frame-by-frame narration

## 4. Regression tests

These protect against future drift.

Examples:

* same fixture input → stable artifact counts
* same fixture input → stable rule ids
* same fixture input → stable concept graph nodes/edges
* same fixture input → stable confidence labels within tolerance
* same fixture input → stable exporter structure

This is critical because your pipeline will keep evolving.

---

# Deliverables for Task 14

Create:

* `tests/test_pipeline_integration.py`
* `tests/test_pipeline_invariants.py`
* `tests/test_pipeline_regression.py`

Possibly also:

* `tests/fixtures/`
* `tests/golden/`

And optionally:

* `pipeline/validation.py`

---

# Recommended fixture strategy

Task 14 should use **small but realistic fixtures**, not huge production data.

You should have at least:

## Fixture A — minimal happy-path lesson

A small lesson fixture with:

* 2–4 chunks
* some visual events
* at least one clear rule
* at least one linked evidence ref

Use this for fast end-to-end tests.

## Fixture B — richer trading lesson

A slightly more realistic fixture that exercises:

* multiple concepts/subconcepts
* positive and negative examples
* merge/split behavior
* exporter output

Use this for stronger integration tests.

## Fixture C — edge-case lesson

A fixture with:

* sparse transcript
* weak visuals
* missing concept in some events
* ambiguous examples

Use this to ensure the system fails gracefully and still preserves outputs.

---

# What the integration tests should verify

## A. File existence and layout

For an end-to-end run, verify:

* `knowledge_events.json`
* `evidence_index.json`
* `rule_cards.json`
* `concept_graph.json` when enabled
* `ml_manifest.json` when enabled
* `review_markdown.md`
* `rag_ready.md`

Also verify they are written to the correct folders from Task 9.

## B. Schema validity

Every produced JSON artifact should successfully validate against its schema.

This should be explicit:

* load file
* validate with Pydantic model
* fail if invalid

## C. Cross-artifact consistency

Examples:

* every `RuleCard.source_event_ids` must exist in `knowledge_events.json`
* every `RuleCard.evidence_refs` must exist in `evidence_index.json`
* every `EvidenceRef.source_event_ids` must exist in `knowledge_events.json`
* every ML example ref in a rule must exist in the evidence index
* every concept graph node/relation refers to valid normalized ids

## D. Provenance coverage

You already planned provenance helpers earlier. Task 14 should assert provenance coverage on the full pipeline.

Examples:

* nearly all knowledge events have chunk indexes
* all evidence refs have frame/raw ids
* all rule cards have source event ids

## E. Confidence presence

Verify:

* every `KnowledgeEvent` has confidence fields
* every `RuleCard` has confidence fields
* scores are bounded `[0,1]`
* labels are valid (`low|medium|high`)

## F. No raw blob leakage

This is very important.

Assert that final structured outputs do **not** contain keys like:

* `current_state`
* `previous_visual_state`
* `visual_facts`
* full raw visual event blobs

## G. Exporter quality checks

Verify:

* `review_markdown.md` contains rule-oriented structure
* `rag_ready.md` is more compact than review markdown
* review markdown may include provenance
* RAG markdown does not include verbose provenance
* final markdown does not contain visual spam or transcript replay

---

# Test categories I would include

## 1. Module-boundary integration tests

Examples:

* Step 3 output → Step 4 input
* Step 4 output → Step 5 input
* Step 5 output → Task 12 / Task 13 / exporters input

These are targeted and fast.

## 2. Full pipeline smoke test

One test that runs the full structured path and checks all files exist and validate.

This should run in CI.

## 3. Full pipeline golden-output test

For one fixed fixture, compare against “golden” expectations such as:

* number of rule cards
* number of evidence refs
* number of concept graph nodes
* expected rule ids or concepts present

Do not compare full markdown byte-for-byte unless you want very brittle tests. Prefer structural assertions.

## 4. Negative / degraded input tests

Ensure the pipeline handles:

* missing evidence
* sparse transcript
* weak chunk metadata
* ambiguous rules

without crashing and without corrupt outputs.

---

# I would also add validation helpers

Task 14 becomes much stronger if you add a shared validation module, for example:

* `pipeline/validation.py`

This can expose helpers like:

```python
validate_rule_card_integrity(...)
validate_evidence_index_integrity(...)
validate_cross_artifact_references(...)
validate_export_quality(...)
```

That way tests and runtime QA can reuse the same checks.

---

# Strong invariants I would explicitly test

I would put these in `tests/test_pipeline_invariants.py`.

## Structured artifact invariants

* every `KnowledgeEvent` has `event_id`
* every `EvidenceRef` has `evidence_id`
* every `RuleCard` has `rule_id`
* every `RuleCard` has `source_event_ids`
* every `EvidenceRef` has `source_event_ids`
* every `RuleCard.evidence_refs` points to valid evidence ids

## Provenance invariants

* no rule card without source provenance
* no evidence ref without visual provenance
* no loss of source ids after merge/split

## Confidence invariants

* score in `[0,1]`
* label matches threshold rules

## Visual compaction invariants

* no raw visual blobs in final JSON
* rule visual summary stays compact
* review and RAG markdown pass visual-spam validator

## Export invariants

* review markdown and RAG markdown both non-empty
* review markdown includes more detail than RAG markdown
* RAG markdown is rule-centric

---

# Suggested test file structure

```text
tests/
  fixtures/
    lesson_minimal/
      Lesson 2. Levels part 1.chunks.json
      dense_analysis.json
      knowledge_events.json   # optional prebuilt for targeted tests
      evidence_index.json     # optional prebuilt
      rule_cards.json         # optional prebuilt
  golden/
    lesson_minimal_expected.json

  test_pipeline_integration.py
  test_pipeline_invariants.py
  test_pipeline_regression.py
```

---

# What Task 14 should not do

Task 14 should **not**:

* depend on live external APIs in CI
* depend on unstable LLM output for every test
* compare giant markdown files byte-for-byte unless necessary
* only test happy path
* skip cross-artifact consistency checks

I would strongly separate:

* deterministic tests
* optional provider-backed tests

---

# Important point: two testing modes

I recommend Task 14 define two test layers.

## A. Default CI-safe tests

These should:

* use mocks or prebuilt structured fixtures
* not call real providers
* run fast and reliably

## B. Optional extended tests

These may:

* run with real provider calls
* validate live integration
* be manually triggered or nightly

This is important because your pipeline uses LLM/provider components, and you do not want ordinary CI to become flaky.

---

# So yes — your interpretation is right

Task 14 **should absolutely be about strong integration testing across all modules**.

Not just unit tests.
Not just schema validation.
Not just file existence.

It should verify that the **whole structured pipeline behaves like one coherent system**.

---

# Copy-paste formulation for Task 14

```text
Task 14 — Integration Testing and Acceptance Checks

Goal:
Build a strong testing layer that validates the structured pipeline end to end and across module boundaries.

This task must verify:
- outputs from one stage are valid inputs to the next
- all structured artifacts validate against schema
- cross-artifact references are consistent
- provenance survives through transformations
- confidence fields are present and valid
- no raw visual blobs leak into final structured outputs
- exported markdown stays clean, compact, and rule-centric
- the same input produces stable outputs

Create:
- tests/test_pipeline_integration.py
- tests/test_pipeline_invariants.py
- tests/test_pipeline_regression.py
- optional pipeline/validation.py

Include:
1. module-boundary integration tests
2. full pipeline smoke tests
3. invariant tests
4. regression/golden tests
5. degraded-input tests
6. CI-safe deterministic tests
7. optional extended provider-backed tests

Do not:
- rely only on unit tests
- depend on live provider calls for all CI tests
- skip cross-artifact consistency checks
- allow raw visual blobs or weak provenance to pass silently
```

The only thing I cannot do right now is inspect some older expired uploads unless you upload them again, but for Task 14 that is not a blocker because the testing design can be specified from the architecture we already built.

**Confidence: High**

Yes — Task 14 should be treated as a **serious test architecture task**, not just “add a few tests.”

At this point, the pipeline is a multi-stage system with contracts between components. Task 14 should give you confidence that:

* each stage produces valid outputs,
* downstream stages consume upstream artifacts correctly,
* invariants hold across the whole chain,
* regressions are caught early,
* and the final outputs remain useful for RAG, algorithms, and future ML.

Below is a **full implementation plan for Task 14**.

---

# Task 14 — Integration Testing and Acceptance Checks

## Goal

Build a broad and robust testing layer that validates the structured pipeline:

* **within each stage**
* **between stages**
* **across the full end-to-end path**
* **under degraded or ambiguous inputs**
* **with stable regression expectations**

This task should cover:

1. schema validation
2. cross-artifact consistency
3. provenance integrity
4. confidence integrity
5. visual-compaction integrity
6. exporter quality
7. deterministic regression behavior
8. optional provider-backed integration tests

---

# What Task 14 should produce

Create:

```text
tests/
  conftest.py
  fixtures/
    lesson_minimal/
      Lesson 2. Levels part 1.chunks.json
      dense_analysis.json
      knowledge_events.json          # optional staged fixture
      evidence_index.json            # optional staged fixture
      rule_cards.json                # optional staged fixture
    lesson_edge_sparse/
      ...
    lesson_multi_concept/
      ...

  golden/
    lesson_minimal_expected.json
    lesson_multi_concept_expected.json

  test_pipeline_integration.py
  test_pipeline_invariants.py
  test_pipeline_regression.py
  test_pipeline_degraded_inputs.py
  test_pipeline_exports.py
  test_pipeline_cross_artifact_refs.py
  test_pipeline_optional_live.py     # optional / marked integration-live
```

Optional but strongly recommended:

```text
pipeline/
  validation.py
```

---

# Testing philosophy

Task 14 should use **three layers of testing**.

## Layer 1 — fast deterministic tests

These run in normal CI and do **not** depend on real LLM/provider calls.

They should use:

* staged JSON fixtures
* mocked LLM outputs
* deterministic exporters
* static expected counts and invariants

## Layer 2 — end-to-end structured pipeline tests

These run the structured pipeline from:

* chunks
* to knowledge events
* to evidence
* to rule cards
* to concept graph
* to ML-prep
* to exporters

Still preferably mocked at the LLM boundary.

## Layer 3 — optional live provider integration tests

These are not required for every CI run.

They should:

* run only when credentials are present
* be marked with `pytest.mark.live_provider`
* validate actual provider wiring, not core business logic

---

# Core test coverage areas

## 1. Stage-boundary integration

These tests validate that outputs from one stage are valid inputs to the next.

### Required boundaries

* Step 3 output → Step 4 input
* Step 4 output → Step 5 input
* Step 5 output → Task 12 input
* Step 5 output → Task 13 input
* Step 5 output → Task 7 exporters
* Task 13 enriched rule cards → exporters

### Example assertions

* `knowledge_events.json` loads into `KnowledgeEventCollection`
* `evidence_index.json` loads into `EvidenceIndex`
* `rule_cards.json` loads into `RuleCardCollection`
* all ids referenced downstream exist upstream

---

## 2. Full structured-pipeline smoke test

This should be the most important integration test.

It should run one representative lesson fixture through the full structured path:

```text
chunks
→ knowledge builder
→ evidence linker
→ rule reducer
→ confidence
→ provenance
→ concept graph
→ ML prep
→ exporters
```

### Required assertions

* all expected output files exist
* each JSON validates against schema
* markdown files are non-empty
* output folders match Task 9 contract
* no stage crashes on a realistic fixture

---

## 3. Cross-artifact consistency tests

These are critical.

### Must verify

#### Rule cards ↔ knowledge events

Every `RuleCard.source_event_ids` must exist in `knowledge_events.json`.

#### Rule cards ↔ evidence

Every `RuleCard.evidence_refs` must exist in `evidence_index.json`.

#### Evidence ↔ knowledge events

Every `EvidenceRef.source_event_ids` must exist in `knowledge_events.json`.

#### ML fields ↔ evidence

Every:

* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`

must exist in `evidence_index.json`.

#### Concept graph ↔ rules

Concept/subconcept ids used in graph nodes/relations must correspond to normalized values derivable from rules.

---

## 4. Provenance integrity tests

This deserves its own file.

### Must verify

#### Knowledge events

* every event has `lesson_id`
* every event has `metadata.chunk_index`
* every event has at least chunk timing or event timing
* candidate visual provenance is compact and present when expected

#### Evidence refs

* every evidence ref has `lesson_id`
* every evidence ref has `frame_ids` or `raw_visual_event_ids`
* every evidence ref has `source_event_ids`

#### Rule cards

* every rule card has `lesson_id`
* every rule card has `source_event_ids`
* evidence refs survive merge/split
* provenance is not lost when rule candidates are merged

---

## 5. Confidence integrity tests

These should validate both structure and logic.

### Must verify

* every `KnowledgeEvent` has:

  * `confidence`
  * `confidence_score`
* every `RuleCard` has:

  * `confidence`
  * `confidence_score`
* scores are in `[0, 1]`
* labels are only:

  * `low`
  * `medium`
  * `high`

### Also verify relative behavior

* strong explicit rules score higher than vague examples
* well-supported rule cards score higher than example-only ones

---

## 6. Visual compaction integrity tests

This is very important because visual noise is one of your main risk areas.

### Must verify

* no raw visual blobs leak into:

  * `knowledge_events.json`
  * `evidence_index.json`
  * `rule_cards.json`
* keys like these must not appear in final structured artifacts:

  * `current_state`
  * `previous_visual_state`
  * `visual_facts`
  * full dense-analysis frame payloads

### Also verify

* `RuleCard.visual_summary` is short
* review markdown uses compact visual bullets
* RAG markdown is more compact than review markdown
* final markdown passes the visual-spam validator

---

## 7. Export quality tests

Task 7 made markdown a derived projection. Task 14 should verify that quality.

### Review markdown

Must contain:

* concept grouping
* rule text
* conditions/invalidation when present
* compact evidence summary
* optionally confidence
* optionally compact provenance

### RAG markdown

Must:

* be shorter / more compact
* remain rule-centric
* avoid verbose provenance
* avoid transcript replay
* avoid frame-by-frame narration

### Must also verify

* review markdown and RAG markdown are **not identical**
* both are non-empty
* both are stable for the same fixture

---

## 8. Degraded-input tests

The pipeline should not only work on clean happy-path data.

Create a dedicated degraded-input test file.

### Cases to cover

#### Sparse transcript

Very little transcript, but some visuals.

Expected:

* knowledge events may be fewer
* evidence refs still valid
* pipeline does not crash

#### Weak visuals

Transcript strong, visuals weak.

Expected:

* lower evidence density
* rule cards still form
* ML-positive refs may be sparse

#### Missing concept in some events

Expected:

* graph smaller
* rules may still exist
* confidence lower, not crash

#### Ambiguous examples

Expected:

* ambiguous example refs populated
* not forced into positive bucket

#### Minimal lesson

One or two chunks only.

Expected:

* valid but small outputs

---

# Recommended `pipeline/validation.py`

I strongly recommend adding a reusable validation module.

Create:

```text
pipeline/validation.py
```

It should contain validators that both tests and runtime QA can reuse.

## Suggested functions

```python
def validate_knowledge_event_collection_integrity(...)
def validate_evidence_index_integrity(...)
def validate_rule_card_collection_integrity(...)
def validate_cross_artifact_references(...)
def validate_concept_graph_integrity(...)
def validate_ml_manifest_integrity(...)
def validate_export_quality(...)
def validate_no_visual_blob_leakage(...)
```

These should return:

* list of warnings / errors
  or
* structured validation result

instead of only booleans.

That makes debugging much easier.

---

# Exact test file plan

## `tests/test_pipeline_integration.py`

This file should contain the stage-boundary and end-to-end structured pipeline tests.

### Key tests

* `test_step3_to_step4_integration`
* `test_step4_to_step5_integration`
* `test_rule_cards_to_concept_graph_integration`
* `test_rule_cards_to_ml_prep_integration`
* `test_rule_cards_to_exporters_integration`
* `test_full_structured_pipeline_smoke`

---

## `tests/test_pipeline_invariants.py`

This file should contain hard invariants.

### Key tests

* `test_every_rule_card_has_source_event_ids`
* `test_every_evidence_ref_has_visual_provenance`
* `test_every_rule_card_evidence_ref_exists`
* `test_every_ml_example_ref_exists_in_evidence_index`
* `test_no_raw_visual_blob_leakage`
* `test_confidence_fields_valid`
* `test_visual_summary_is_compact`
* `test_export_outputs_are_distinct`

---

## `tests/test_pipeline_regression.py`

This file should contain stable regression checks against golden expectations.

### Golden checks should include

* counts of:

  * knowledge events
  * evidence refs
  * rule cards
  * graph nodes
  * graph relations
* stable presence of key concepts
* stable presence of expected rule ids or prefixes
* stable exporter structure

### Important

Do **not** compare entire markdown byte-for-byte unless you truly want brittle tests.

Prefer structural checks like:

* line count range
* concept headers present
* rule titles present
* no banned patterns

---

## `tests/test_pipeline_degraded_inputs.py`

This file should ensure graceful handling of poor inputs.

### Key tests

* sparse transcript fixture
* missing or weak visuals fixture
* ambiguous fixture
* concept-missing fixture

---

## `tests/test_pipeline_exports.py`

Focused on markdown and manifest quality.

### Key tests

* review markdown structure
* rag markdown structure
* export manifest correctness
* review vs rag size/structure difference
* no transcript replay in new exporters

---

## `tests/test_pipeline_cross_artifact_refs.py`

Focused on cross-artifact consistency.

### Key tests

* source event ids resolve
* evidence refs resolve
* ML refs resolve
* graph ids normalize consistently

---

## `tests/test_pipeline_optional_live.py`

Optional, provider-backed.

Mark with:

```python
@pytest.mark.live_provider
```

These tests should only run when:

* env vars are present
* explicitly requested

This keeps CI stable.

---

# Fixture strategy in detail

## Fixture 1 — `lesson_minimal`

Use for:

* fast smoke tests
* schema tests
* exporter sanity

Should include:

* a few chunks
* one clear level rule
* one evidence ref
* one rule card

## Fixture 2 — `lesson_multi_concept`

Use for:

* concept graph
* merge/split
* ML-prep
* review/RAG exporter difference

Should include:

* at least 2 concepts or subconcepts
* positive and counterexample evidence
* multiple rule cards

## Fixture 3 — `lesson_edge_sparse`

Use for:

* degraded input tests
* ambiguity handling
* low-confidence rules

---

# Golden file strategy

I recommend golden files for **structural expectations**, not giant raw outputs.

Example `golden/lesson_minimal_expected.json`:

```json id="akhk45"
{
  "min_knowledge_events": 3,
  "min_evidence_refs": 1,
  "min_rule_cards": 1,
  "required_concepts": ["level"],
  "required_rule_prefixes": ["rule_"],
  "max_rag_markdown_lines": 80
}
```

This is much less brittle than comparing full markdown output byte-for-byte.

---

# Strong invariant list

I would explicitly encode these invariants.

## Structured artifact invariants

* every `KnowledgeEvent` has `event_id`
* every `EvidenceRef` has `evidence_id`
* every `RuleCard` has `rule_id`

## Provenance invariants

* every `RuleCard.source_event_ids` is non-empty
* every `EvidenceRef` has `frame_ids` or `raw_visual_event_ids`
* every `EvidenceRef.source_event_ids` resolves
* knowledge events carry chunk provenance

## Confidence invariants

* labels valid
* scores bounded
* stronger structured rules generally outscore weaker examples

## Visual compaction invariants

* no raw visual blobs in final structured outputs
* rule visual summaries compact
* markdown passes visual-spam validation

## Export invariants

* review and rag outputs both non-empty
* review more detailed than rag
* rag rule-centric and compact

## ML-prep invariants

* ML example refs point to valid evidence ids
* illustrations are not auto-promoted to positive examples

---

# Suggested helper implementations in `pipeline/validation.py`

## Example cross-artifact validator

```python id="coghty"
def validate_cross_artifact_references(
    knowledge_events,
    evidence_index,
    rule_cards,
) -> list[str]:
    errors: list[str] = []

    event_ids = {ev.event_id for ev in knowledge_events.events}
    evidence_ids = {ev.evidence_id for ev in evidence_index.evidence}

    for evidence in evidence_index.evidence:
        for source_event_id in evidence.source_event_ids or []:
            if source_event_id not in event_ids:
                errors.append(
                    f"EvidenceRef {evidence.evidence_id} references missing source event {source_event_id}"
                )

    for rule in rule_cards.rules:
        for source_event_id in rule.source_event_ids or []:
            if source_event_id not in event_ids:
                errors.append(
                    f"RuleCard {rule.rule_id} references missing source event {source_event_id}"
                )
        for evidence_id in rule.evidence_refs or []:
            if evidence_id not in evidence_ids:
                errors.append(
                    f"RuleCard {rule.rule_id} references missing evidence {evidence_id}"
                )

    return errors
```

## Example visual-blob leakage validator

```python id="11sg6w"
FORBIDDEN_KEYS = {
    "current_state",
    "previous_visual_state",
    "visual_facts",
    "dense_analysis_frame",
    "raw_visual_events",
}

def _walk_forbidden_keys(obj, path="root"):
    errors = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_KEYS:
                errors.append(f"Forbidden key {key} found at {path}")
            errors.extend(_walk_forbidden_keys(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            errors.extend(_walk_forbidden_keys(item, f"{path}[{idx}]"))
    return errors
```

---

# CI and execution strategy

## Default CI

Run:

* unit tests
* integration tests
* invariant tests
* regression tests
* no live provider tests

## Optional nightly / manual

Run:

* `pytest -m live_provider`

This should validate:

* real provider wiring
* schema parsing still works
* prompt/render paths still function

---

# Important implementation rules for Task 14

## Do

* test across stage boundaries
* test full structured path
* test degraded inputs
* test invariants and regressions
* keep provider-backed tests optional
* use fixtures and golden expectations

## Do not

* rely only on unit tests
* compare full markdown byte-for-byte unless necessary
* let CI depend on live providers
* skip cross-artifact validation
* assume schema-valid means system-valid

---

# Definition of done

Task 14 is complete when:

1. there are dedicated integration test files across the pipeline
2. there is at least one full structured-pipeline smoke test
3. cross-artifact consistency is tested
4. provenance and confidence invariants are enforced
5. degraded-input behavior is covered
6. exporter quality is validated
7. regression expectations are captured with golden fixtures
8. optional live provider tests are separated from default CI

---

# Copy-paste instruction for the coding agent

```text id="6g8c49"
Implement Task 14 only: Integration Testing and Acceptance Checks.

Create:
- tests/test_pipeline_integration.py
- tests/test_pipeline_invariants.py
- tests/test_pipeline_regression.py
- tests/test_pipeline_degraded_inputs.py
- tests/test_pipeline_exports.py
- tests/test_pipeline_cross_artifact_refs.py
- optional tests/test_pipeline_optional_live.py
- optional pipeline/validation.py

Goal:
Build a robust testing layer that validates the structured pipeline end to end and across module boundaries.

Test coverage must include:
1. stage-boundary integration:
   - knowledge events -> evidence linking
   - evidence index -> rule cards
   - rule cards -> concept graph / ML prep / exporters
2. full structured-pipeline smoke test
3. cross-artifact consistency checks
4. provenance invariants
5. confidence invariants
6. no raw visual blob leakage
7. exporter quality checks
8. degraded-input behavior
9. regression/golden expectations
10. optional live provider integration tests marked separately

Use:
- small realistic fixtures
- deterministic CI-safe tests by default
- optional provider-backed tests only when explicitly enabled

Do not:
- rely only on unit tests
- depend on live providers in normal CI
- skip cross-artifact reference validation
- assume schema-valid means system-valid
```

If you want, I can now give you the **detailed implementation plan for Task 14**, including exact test names, helper functions, fixture structure, and validation utilities.

Yes — below is the **detailed implementation plan for Task 14**.

**Confidence: High**

This is written as a real testing architecture, not just a checklist.

---

# Task 14 — Detailed implementation plan

## Objective

Build a test suite that proves the pipeline is reliable:

* per module
* across stage boundaries
* across the full structured path
* under degraded inputs
* under regression checks

The suite should validate both:

* **artifact correctness**
* **system behavior**

---

# 1. Create a shared validation module

Create:

```text
pipeline/validation.py
```

This should contain reusable validators used by both:

* tests
* optional runtime QA/debug

## Recommended functions

```python
def validate_knowledge_event_collection_integrity(collection) -> list[str]: ...
def validate_evidence_index_integrity(index) -> list[str]: ...
def validate_rule_card_collection_integrity(collection) -> list[str]: ...
def validate_concept_graph_integrity(graph) -> list[str]: ...
def validate_ml_manifest_integrity(payload: dict) -> list[str]: ...
def validate_cross_artifact_references(
    knowledge_events,
    evidence_index,
    rule_cards,
) -> list[str]: ...
def validate_no_visual_blob_leakage(payload: dict | list) -> list[str]: ...
def validate_export_quality(review_markdown: str, rag_markdown: str) -> list[str]: ...
```

## Why

This avoids duplicating fragile validation logic across tests.

---

# 2. Fixture structure

Create:

```text
tests/
  conftest.py
  fixtures/
    lesson_minimal/
      Lesson 2. Levels part 1.chunks.json
      dense_analysis.json
    lesson_multi_concept/
      chunks.json
      dense_analysis.json
    lesson_edge_sparse/
      chunks.json
      dense_analysis.json
  golden/
    lesson_minimal_expected.json
    lesson_multi_concept_expected.json
```

## Fixture roles

### `lesson_minimal`

Use for:

* smoke tests
* schema tests
* fast integration

### `lesson_multi_concept`

Use for:

* merge/split logic
* concept graph
* ML prep
* exporters

### `lesson_edge_sparse`

Use for:

* degraded input
* ambiguity handling
* low-confidence behavior

---

# 3. `tests/conftest.py`

This should provide reusable fixture loaders and helpers.

## Recommended helpers

```python
from pathlib import Path
import json
import pytest

from pipeline.schemas import (
    KnowledgeEventCollection,
    EvidenceIndex,
    RuleCardCollection,
    ConceptGraph,
)

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
GOLDEN_ROOT = Path(__file__).parent / "golden"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def lesson_minimal_root():
    return FIXTURES_ROOT / "lesson_minimal"


@pytest.fixture
def lesson_multi_concept_root():
    return FIXTURES_ROOT / "lesson_multi_concept"


@pytest.fixture
def lesson_edge_sparse_root():
    return FIXTURES_ROOT / "lesson_edge_sparse"
```

## Optional temp output root fixture

```python
@pytest.fixture
def temp_video_root(tmp_path):
    root = tmp_path / "video_case"
    root.mkdir(parents=True, exist_ok=True)
    return root
```

---

# 4. `tests/test_pipeline_integration.py`

This file tests stage boundaries and one full smoke path.

## Test 1 — Step 3 to Step 4 integration

### Goal

Ensure `knowledge_events.json` produced by Task 3 is usable by Task 4.

### Pattern

* run knowledge builder on fixture chunks
* write `knowledge_events.json`
* run evidence linker
* assert `EvidenceIndex` produced

### Example structure

```python
def test_step3_to_step4_integration(...):
    ...
    assert knowledge_collection.events
    assert evidence_index.evidence is not None
```

## Test 2 — Step 4 to Step 5 integration

### Goal

Ensure evidence-linked events can become rule cards.

Assertions:

* `RuleCardCollection.rules` not empty
* every rule has `source_event_ids`

## Test 3 — Rule cards to concept graph

Assertions:

* graph nodes exist
* graph relations valid
* no invalid ids

## Test 4 — Rule cards to ML prep

Assertions:

* enriched rules still preserve provenance
* ML fields populated conservatively

## Test 5 — Rule cards to exporters

Assertions:

* review markdown non-empty
* rag markdown non-empty
* deterministic renderer works without raw chunks

## Test 6 — full structured pipeline smoke test

This is the main test.

### Suggested flow

* load fixture chunks + dense analysis
* run Step 3
* run Step 4
* run Step 5
* run Task 12
* run Task 13
* run exporters

### Assertions

* all core artifacts exist in memory or on disk
* schema-valid
* cross-artifact references valid

---

# 5. `tests/test_pipeline_invariants.py`

This file should contain hard invariants.

## Test categories

### A. IDs exist

* every `KnowledgeEvent` has `event_id`
* every `EvidenceRef` has `evidence_id`
* every `RuleCard` has `rule_id`

### B. Provenance invariants

* every rule card has non-empty `source_event_ids`
* every evidence ref has `frame_ids` or `raw_visual_event_ids`
* every evidence ref has `source_event_ids`
* knowledge events have chunk provenance

### C. Confidence invariants

* scores are in `[0, 1]`
* labels are valid
* no missing confidence fields

### D. Visual compaction invariants

* no raw blobs in final structured artifacts
* visual summaries compact

### E. Export invariants

* review markdown non-empty
* rag markdown non-empty
* they are not identical

## Example test

```python
def test_every_rule_card_has_source_event_ids(rule_cards):
    for rule in rule_cards.rules:
        assert rule.source_event_ids, f"{rule.rule_id} missing source_event_ids"
```

---

# 6. `tests/test_pipeline_cross_artifact_refs.py`

This file should test consistency across artifacts.

## Recommended validations

### A. Evidence source events resolve

Every `EvidenceRef.source_event_ids` must exist in `KnowledgeEventCollection`.

### B. Rule source events resolve

Every `RuleCard.source_event_ids` must exist in `KnowledgeEventCollection`.

### C. Rule evidence refs resolve

Every `RuleCard.evidence_refs` must exist in `EvidenceIndex`.

### D. ML refs resolve

Every:

* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`

must exist in `EvidenceIndex`.

## Example helper usage

```python
from pipeline.validation import validate_cross_artifact_references

def test_cross_artifact_references(...):
    errors = validate_cross_artifact_references(
        knowledge_events,
        evidence_index,
        rule_cards,
    )
    assert not errors, errors
```

---

# 7. `tests/test_pipeline_exports.py`

This file focuses on review/RAG outputs and exporter integrity.

## Test 1 — review markdown structure

Check presence of:

* lesson header
* concept sections
* rule text

## Test 2 — RAG markdown compactness

Check:

* fewer lines than review
* no verbose provenance
* still includes rule text

## Test 3 — exporter distinction

Ensure review and rag outputs are meaningfully different.

## Test 4 — no transcript replay

Assert final markdown does not contain raw chunk transcript markers or replay-like content.

## Test 5 — no visual spam

Use Task 8 validator.

```python
from pipeline.component2.visual_compaction import validate_markdown_visual_compaction
```

---

# 8. `tests/test_pipeline_degraded_inputs.py`

This file proves graceful failure behavior.

## Case 1 — sparse transcript

Expected:

* fewer knowledge events
* pipeline still completes

## Case 2 — weak visuals

Expected:

* evidence may be sparse
* rule cards still possible if transcript strong

## Case 3 — ambiguous example-heavy lesson

Expected:

* ambiguous refs populated
* no forced positives

## Case 4 — missing concepts

Expected:

* some rules may remain partially unclassified
* no crash

## Important

These tests should assert **graceful degradation**, not perfection.

---

# 9. `tests/test_pipeline_regression.py`

This file should use golden expectations.

## Use structural golden files, not full output snapshots

Example `golden/lesson_minimal_expected.json`:

```json
{
  "min_knowledge_events": 3,
  "min_evidence_refs": 1,
  "min_rule_cards": 1,
  "required_concepts": ["level"],
  "required_rule_prefixes": ["rule_"],
  "max_rag_markdown_lines": 80
}
```

## Recommended checks

* artifact counts
* required concepts present
* required ids/prefixes present
* markdown size bounds
* graph node counts in expected range

This keeps regression tests stable without being brittle.

---

# 10. `pipeline/validation.py` — concrete implementation plan

## A. JSON/blob leakage validator

```python
FORBIDDEN_KEYS = {
    "current_state",
    "previous_visual_state",
    "visual_facts",
    "dense_analysis_frame",
    "raw_visual_events",
}

def validate_no_visual_blob_leakage(payload, path="root") -> list[str]:
    errors = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_KEYS:
                errors.append(f"Forbidden key {key} found at {path}")
            errors.extend(validate_no_visual_blob_leakage(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            errors.extend(validate_no_visual_blob_leakage(item, f"{path}[{i}]"))
    return errors
```

## B. Rule-card integrity validator

```python
def validate_rule_card_collection_integrity(collection) -> list[str]:
    errors = []
    seen_ids = set()

    for rule in collection.rules:
        if not rule.rule_id:
            errors.append("RuleCard missing rule_id")
        elif rule.rule_id in seen_ids:
            errors.append(f"Duplicate rule_id: {rule.rule_id}")
        else:
            seen_ids.add(rule.rule_id)

        if not rule.source_event_ids:
            errors.append(f"RuleCard {rule.rule_id} missing source_event_ids")

        if rule.confidence_score is None or not (0.0 <= rule.confidence_score <= 1.0):
            errors.append(f"RuleCard {rule.rule_id} has invalid confidence_score")

        if rule.confidence not in {"low", "medium", "high"}:
            errors.append(f"RuleCard {rule.rule_id} has invalid confidence label")

    return errors
```

## C. Export quality validator

```python
def validate_export_quality(review_markdown: str, rag_markdown: str) -> list[str]:
    errors = []

    if not review_markdown.strip():
        errors.append("review markdown is empty")
    if not rag_markdown.strip():
        errors.append("rag markdown is empty")

    if review_markdown.strip() == rag_markdown.strip():
        errors.append("review markdown and rag markdown are identical")

    if len(rag_markdown.splitlines()) > len(review_markdown.splitlines()):
        errors.append("rag markdown is not more compact than review markdown")

    return errors
```

---

# 11. Mocking strategy for LLM/provider boundaries

Task 14 should keep default CI deterministic.

## Recommendation

For tests touching Task 6 or exporters with LLM option:

* default to deterministic rendering
* or mock `process_rule_cards_markdown_render(...)`

For Step 3 extraction:

* either use a prebuilt `knowledge_events.json`
* or mock the extraction response

## Do not

Make standard CI depend on:

* Gemini
* OpenAI
* live API credentials

---

# 12. Optional live-provider tests

Create:

```text
tests/test_pipeline_optional_live.py
```

Mark them:

```python
import pytest

pytestmark = pytest.mark.live_provider
```

### Suggested tests

* one chunk extraction with live provider
* one markdown render with live provider

### Guard

Skip when env vars are missing.

These tests should validate:

* provider wiring
* schema parsing
* request usage handling

They should **not** be the main correctness test suite.

---

# 13. Suggested exact test names

I would use names like:

## `test_pipeline_integration.py`

* `test_step3_to_step4_integration`
* `test_step4_to_step5_integration`
* `test_rule_cards_to_concept_graph_integration`
* `test_rule_cards_to_ml_prep_integration`
* `test_rule_cards_to_exporters_integration`
* `test_full_structured_pipeline_smoke`

## `test_pipeline_invariants.py`

* `test_every_rule_card_has_source_event_ids`
* `test_every_evidence_ref_has_visual_provenance`
* `test_confidence_fields_are_valid`
* `test_no_visual_blob_leakage_in_structured_outputs`
* `test_visual_summaries_are_compact`
* `test_export_outputs_are_distinct`

## `test_pipeline_cross_artifact_refs.py`

* `test_evidence_source_events_resolve`
* `test_rule_source_events_resolve`
* `test_rule_evidence_refs_resolve`
* `test_ml_example_refs_resolve`

## `test_pipeline_degraded_inputs.py`

* `test_sparse_transcript_pipeline_survives`
* `test_weak_visuals_pipeline_survives`
* `test_ambiguous_examples_do_not_become_positive`
* `test_missing_concepts_do_not_crash_pipeline`

## `test_pipeline_regression.py`

* `test_lesson_minimal_regression_counts`
* `test_lesson_multi_concept_regression_counts`
* `test_exporter_output_structure_regression`

---

# 14. Minimum end-to-end smoke test shape

Here is the kind of end-to-end test I would want.

```python
def test_full_structured_pipeline_smoke(...):
    # 1. load fixture chunks + dense analysis
    # 2. run knowledge builder
    # 3. run evidence linker
    # 4. run rule reducer
    # 5. run concept graph
    # 6. run ml prep
    # 7. run exporters
    # 8. validate schemas
    # 9. validate references
    # 10. validate exports
```

## Assertions

* no stage returns empty when it shouldn’t
* all collections validate
* all references resolve
* exporters produce expected output files/strings
* no forbidden visual blobs
* no invariant violations

---

# 15. One important rule to add to Task 14

I would explicitly add this sentence:

```text
A passing test suite for Task 14 must prove not only that artifacts exist and validate individually, but also that the relationships between artifacts remain internally consistent across the full structured pipeline.
```

That is the core of the task.

---

# My recommendation

Yes — Task 14 should be **wide-range integration testing across all components**, and it should be one of the strongest parts of the whole implementation effort.

Because once this pipeline grows, your biggest risk is not any one function failing.
Your biggest risk is the **contracts between stages drifting silently**.

If you want, next I can turn this into a **copy-paste coding-agent instruction for Task 14**, just like we did for Tasks 9–13.
