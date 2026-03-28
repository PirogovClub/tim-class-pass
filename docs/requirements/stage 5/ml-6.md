You are implementing the next roadmap step after ML Step 5.

IMPORTANT:
This is roadmap Step 6:
IMPLEMENT DETERMINISTIC LABEL GENERATION FROM RULE SPECS + MARKET DATA.

Read this entire prompt before touching code.

================================
MISSION
================================

Implement a deterministic, point-in-time-safe labeling layer that converts:

- the approved Step 5 ML task contract
- rule/class mappings
- confidence-tier policy
- market-window inputs

into structured generated labels.

This step is about:
- compiling label specs into executable logic
- deterministic label assignment
- exclusion handling
- ambiguity handling
- confidence tier assignment
- generated label artifacts
- dataset manifest/reporting
- validator/tests/docs/audit packaging

This step is NOT about:
- feature store implementation
- model training
- backtests
- live scoring
- “learning from RAG text”
- broad market-data platform design

The system must remain:
- knowledge base defines tasks, classes, rules, invalidations, guidance
- deterministic label generator produces labels from market data windows
- model training happens later in Step 7+

================================
PRIMARY OBJECTIVE
================================

Take the Step 5 task definition and make it executable.

After this step, the next engineer should be able to:
- feed candidate level-interaction windows into the label generator
- get deterministic labels
- get confidence tiers
- get exclusions/ambiguity reasons
- inspect why a label was assigned
- use those labels later for feature-store and baseline model work

================================
EXACT TASK TO IMPLEMENT
================================

Use the Step 5 task as the only target task:

task_id:
- level_interaction_rule_satisfaction_v1

Target labels:
- acceptance_above
- acceptance_below
- false_breakout_up
- false_breakout_down
- rejection
- no_setup
- ambiguous

You are implementing the deterministic label generator for THIS task.

Do not broaden scope to all future tasks.

================================
DEFINITION OF DONE — READ FIRST
================================

You are NOT done when you write label logic.
You are NOT done when one fixture works.
You are NOT done when JSON files exist.

You are done ONLY when ALL of the following are true:

1. The generator consumes the Step 5 task definition and associated spec files.
2. Deterministic label-spec compilation exists.
3. The generator accepts point-in-time-safe market-window inputs.
4. All target classes are supported.
5. Exclusions are handled explicitly.
6. Ambiguous cases are handled explicitly.
7. Confidence tiers are assigned explicitly.
8. Generated label artifacts are produced.
9. A dataset/label manifest is produced.
10. Validation logic exists.
11. Tests exist and pass.
12. Docs are updated.
13. Audit handoff docs are prepared.
14. Final audit zip is created and verified.

If any one of these is missing, the task is NOT COMPLETE.

At the end, repeat this Definition of Done and mark each item PASS or FAIL.

================================
STRICT SCOPE
================================

IN SCOPE:
- deterministic label generation
- rule-spec to executable-label-spec compilation
- market-window schema / loader / adapter as needed
- confidence-tier assignment
- ambiguity/exclusion handling
- generated labels artifact(s)
- manifest/report artifact(s)
- tests
- docs
- audit packaging

OUT OF SCOPE:
- no feature builder
- no feature_spec.yaml for Step 7
- no model training
- no XGBoost / LightGBM
- no backtests
- no walk-forward evaluation
- no live production scorer
- no chart-image labeling system
- no full historical dataset platform
- no broad refactor unrelated to labeling

Keep this step narrow and operational.

================================
INPUTS YOU MUST USE
================================

Treat the Step 5 outputs as source of truth.

At minimum use or extend the equivalents of:
- task_definition.yaml
- class_ontology.json
- window_contract.yaml
- rule_to_class_mapping.json
- task_examples.json

Also inspect existing repo ML-prep helpers and manifests.
Do not create a second disconnected ML contract universe.

If the repo already has:
- ml manifest helpers
- labeling manifest helpers
- enrichment or readiness helpers
- schema validation patterns

reuse them where reasonable.

================================
WHAT THIS STEP MUST BUILD
================================

You must build a deterministic pipeline with these conceptual layers:

1. SPEC LOADER
   - loads Step 5 machine-readable specs

2. LABEL-SPEC COMPILER
   - converts ontology/task/mapping/window-contract into executable labeling rules

3. MARKET WINDOW ADAPTER
   - validates and normalizes candidate market windows
   - enforces point-in-time-safe input assumptions

4. LABEL GENERATOR
   - evaluates the window against label rules
   - assigns:
     - label
     - confidence tier
     - matched conditions
     - invalidations
     - ambiguity/exclusion reasons
     - supporting rule/class references

5. LABEL ARTIFACT WRITER
   - writes generated labels
   - writes label manifest/report
   - preserves provenance

================================
REQUIRED DELIVERABLES
================================

Create the equivalent of the following deliverables.
If the repo already has a better naming/location pattern, follow that pattern exactly.

1. ml/label_specs.json
2. ml/label_generation.py
3. ml/generated_labels.schema.json  (or equivalent schema file)
4. ml/label_manifest_builder.py  (if not better integrated elsewhere)
5. ml/fixtures/market_windows/*.json
6. tests/test_label_generation.py
7. tests/test_label_specs.py
8. docs/ml_step6_label_generation.md
9. RUN_ML_STEP6_AUDIT.md
10. ML_STEP6_HANDOFF.md

If the repo already has an ml_prep area or a manifest module, integrate there instead of scattering files.

================================
REQUIRED OUTPUT ARTIFACTS
================================

This step must produce structured output artifacts.

At minimum produce the equivalent of:

1. generated_labels.jsonl
   Each row should represent one labeled candidate window.

2. label_generation_report.json
   Summary/report including counts by:
   - class
   - confidence tier
   - excluded
   - ambiguous
   - source lesson/rule family if available

3. label_dataset_manifest.json
   Manifest including:
   - task_id
   - spec versions
   - generator version
   - counts
   - confidence distribution
   - input sources
   - point-in-time safety declaration
   - known limitations

If the repo already has manifest conventions, align with them.

================================
REQUIRED SCHEMA OF A GENERATED LABEL
================================

Each generated label record must include, at minimum:

- generated_label_id
- task_id
- candidate_id
- label
- confidence_tier
- status
- decision_order_path
- matched_rule_refs
- matched_concept_ids
- matched_conditions
- invalidation_hits
- ambiguity_reason
- exclusion_reason
- market_window_ref
- anchor_timestamp
- timeframe
- label_horizon
- point_in_time_safe
- metadata / notes

Suggested status values:
- assigned
- excluded
- ambiguous
- skipped_invalid_input

Rules:
- if status=assigned, label must be one of the target classes except ambiguous
- if status=ambiguous, ambiguity_reason must be present
- if status=excluded, exclusion_reason must be present
- no_setup is a valid assigned class, not an exclusion and not ambiguous

================================
REQUIRED LABELING LOGIC
================================

You must implement deterministic logic for these classes:

1. acceptance_above
2. acceptance_below
3. false_breakout_up
4. false_breakout_down
5. rejection
6. no_setup
7. ambiguous

You do NOT need a perfect production trading definition here.
You DO need:
- consistent
- documented
- executable
- auditable
- point-in-time-safe logic

================================
CLASS LOGIC REQUIREMENTS
================================

Use the Step 5 semantics as your starting contract, then make them executable.

acceptance_above:
- requires break and persistence above level within allowed horizon
- immediate failure back below invalidates

acceptance_below:
- mirror of acceptance_above

false_breakout_up:
- break above level occurs
- then fails back below within allowed horizon

false_breakout_down:
- mirror of false_breakout_up

rejection:
- level is tested
- move rejects away without meeting acceptance logic

no_setup:
- task is applicable
- no defined setup class is satisfied
- must not be used as an ambiguity bucket

ambiguous:
- overlapping class evidence
- unclear anchor/level relation
- insufficient signal under deterministic policy
- task should be withheld, not silently forced

You must encode clean conflict resolution.

================================
DECISION ORDER
================================

You must implement a deterministic class decision order.

Example direction:
1. input validation / exclusion
2. ambiguity pre-checks
3. false_breakout checks
4. acceptance checks
5. rejection checks
6. no_setup fallback

You may refine this, but:
- it must be explicit
- it must be documented
- it must be used in code
- it must be exposed in output artifacts

================================
CONFIDENCE TIER POLICY
================================

Implement the future label tiers defined in roadmap guidance:
- gold
- silver
- weak

Interpretation direction:

gold:
- deterministic
- clear anchor
- clean level interaction
- no conflicting signals
- all required fields present
- no major heuristic fallback used

silver:
- mostly deterministic
- small heuristic assumptions allowed
- still good enough for many training/eval uses

weak:
- heuristic fallback used
- borderline or partially specified case
- useful for analysis / weak supervision
- not highest-trust training target

You must encode explicit rules for assigning these tiers.
Do not assign them manually in examples only.

================================
POINT-IN-TIME SAFETY — MANDATORY
================================

This is a critical requirement.

The generator must explicitly enforce point-in-time safety.

You must define and implement:
- what fields from the market window are allowed
- what lookforward horizon is allowed for labeling
- what future information is forbidden
- what happens when required PIT-safe structure is missing

Examples of forbidden leakage:
- using bars outside the declared decision horizon
- using later-session outcome beyond allowed label horizon
- using future extrema not available under the task contract
- using human hindsight notes unavailable at anchor time

Every generated label record must indicate:
- point_in_time_safe = true/false

And the generator should fail or mark invalid if PIT requirements are violated.

================================
MARKET WINDOW CONTRACT
================================

You must implement or reuse a strict input schema for candidate windows.

Each candidate window should include at minimum:
- candidate_id
- anchor_timestamp
- timeframe
- reference_level
- bars_before_anchor
- bars_after_anchor_within_allowed_horizon
- optional higher_timeframe_context
- optional session/time-of-day metadata
- source metadata

The generator must validate:
- required OHLCV structure
- window length
- horizon length
- timestamp ordering
- anchor inclusion
- level presence

If the repo does not yet have a real market dataset wired in, implement this against:
- fixture-based windows
- a clear adapter interface for future real data sources

Do NOT build a giant ingestion platform in this step.

================================
LABEL-SPEC COMPILER REQUIREMENTS
================================

You must implement a compiler or builder that turns Step 5 spec files into executable label specs.

This does NOT need to be fancy.
It DOES need to be real.

At minimum compile:
- class definitions
- decision order
- exclusions
- ambiguity policy
- confidence-tier rules
- rule-to-class mapping references
- applicable rule families / concept ids

Output should become a structured runtime spec used by the generator.

Do not hardcode everything deep inside one long function.

================================
RULE / CONCEPT PROVENANCE
================================

Generated labels must preserve knowledge-layer linkage where possible.

At minimum preserve:
- matched rule refs
- matched concept ids
- task_id
- spec version / generator version
- mapping references used

This matters for later explanation and auditing.

================================
REQUIRED FIXTURE DATA
================================

Create fixture market windows for deterministic tests and examples.

At minimum include positive-path and negative-path windows for:
- acceptance_above
- acceptance_below
- false_breakout_up
- false_breakout_down
- rejection
- no_setup
- ambiguous
- excluded/invalid input

These fixtures must follow the same input schema expected by the real generator.

Do not use free-form notes as the fixture format.
Use machine-readable structured files.

================================
VALIDATION REQUIREMENTS
================================

Add validation logic for:
- loaded Step 5 specs
- compiled label specs
- input market windows
- generated label records
- manifest/report integrity

If the repo already has validation utilities or manifest-integrity style helpers, extend them rather than inventing a completely different validation approach.

================================
TESTING REQUIREMENTS
================================

You must add tests.
Manual inspection alone is not enough.

Minimum required test groups:

1. SPEC TESTS
- Step 5 spec files load correctly
- label spec compiler output is valid
- decision order is stable
- every class in compiler output exists in ontology

2. MARKET WINDOW VALIDATION TESTS
- valid window accepted
- missing level rejected
- malformed bar ordering rejected
- invalid horizon rejected
- missing anchor rejected

3. LABEL ASSIGNMENT TESTS
At minimum:
- acceptance_above fixture -> acceptance_above
- acceptance_below fixture -> acceptance_below
- false_breakout_up fixture -> false_breakout_up
- false_breakout_down fixture -> false_breakout_down
- rejection fixture -> rejection
- no_setup fixture -> no_setup
- ambiguous fixture -> ambiguous
- invalid fixture -> excluded or skipped_invalid_input

4. CONFIDENCE TIER TESTS
- gold case assigned correctly
- silver case assigned correctly
- weak case assigned correctly

5. PIT SAFETY TESTS
- future leakage outside allowed horizon is rejected/flagged
- PIT-safe window passes

6. MANIFEST / REPORT TESTS
- generation report is created
- manifest counts align with produced labels
- class counts sum correctly
- confidence counts sum correctly

7. REGRESSION TESTS
- no_setup is not treated as ambiguous
- ambiguous requires explicit reason
- excluded cases do not receive normal class label

Use the repo’s existing test style and runner patterns.

================================
REQUIRED COMMAND-LINE / SCRIPT ENTRY
================================

Expose a practical way to run label generation.

This can be:
- a CLI entry
- a script
- a module main
- or an existing pipeline hook if that is already the local pattern

It must allow:
- loading specs
- loading fixture/input windows
- writing generated labels
- writing report/manifest

Do not force the auditor to manually call library functions from a REPL.

================================
DOCUMENTATION REQUIREMENTS
================================

Create or update:

1. docs/ml_step6_label_generation.md
   Must explain:
   - purpose
   - inputs
   - compiled label spec concept
   - decision order
   - class logic
   - confidence policy
   - PIT safety policy
   - outputs
   - known limitations

2. RUN_ML_STEP6_AUDIT.md
   Must include exact commands to:
   - validate specs
   - run tests
   - run label generation on fixtures or provided sample inputs
   - inspect outputs
   - build final audit zip

3. ML_STEP6_HANDOFF.md
   Must summarize:
   - what was implemented
   - what inputs are expected
   - what outputs are produced
   - what Step 7 should do next
   - what is deferred
   - what the auditor should check

================================
AUDIT ARTIFACT REQUIREMENTS
================================

Create a final audit zip.

Include at minimum:

1. source/
   - changed code
   - spec compiler
   - label generator
   - validators
   - tests
   - docs
   - fixture input files

2. examples/
   - compiled label spec snapshot
   - example input windows
   - generated_labels.jsonl
   - label_generation_report.json
   - label_dataset_manifest.json

3. test_output.txt
4. RUN_ML_STEP6_AUDIT.md
5. ML_STEP6_HANDOFF.md

If the project already has a standard audit bundle shape, follow it exactly.

================================
WHAT YOU MUST NOT DO
================================

Do NOT:
- build the feature store
- train a model
- add fake backtest results
- implement broad data ingestion infrastructure
- broaden the task beyond level_interaction_rule_satisfaction_v1
- silently use future data beyond allowed horizon
- collapse ambiguous into no_setup
- collapse excluded into no_setup
- stop after coding
- skip tests
- skip docs
- skip audit zip

================================
RECOMMENDED IMPLEMENTATION ORDER
================================

Follow this order:

STEP 1
Inspect existing Step 5 specs and existing ML-prep/manifest helpers in the repo.

STEP 2
Define the runtime compiled label spec structure.

STEP 3
Implement spec loading + spec compiler.

STEP 4
Implement market-window schema/adapter and validation.

STEP 5
Implement label assignment logic with explicit decision order.

STEP 6
Implement confidence-tier logic.

STEP 7
Implement output writers for generated labels, report, and manifest.

STEP 8
Add tests.

STEP 9
Write docs and handoff.

STEP 10
Run tests, run generator, capture outputs, and build audit zip.

================================
MANUAL VERIFICATION CHECKLIST
================================

Before you stop, manually verify ALL of these:

1. Step 5 specs are actually consumed, not duplicated manually.
2. One runtime compiled label spec is produced for the task.
3. Generator works on fixture windows.
4. All classes can be emitted in controlled tests.
5. no_setup is distinct from ambiguous.
6. excluded invalid input is distinct from normal class assignment.
7. confidence tiers are assigned by logic, not by hand.
8. point-in-time-safe flag is present and meaningful.
9. manifest/report align with generated labels.
10. tests pass.
11. audit zip exists and contains required files.

================================
ACCEPTANCE STANDARD
================================

This step will be considered successful if:
- the Step 5 task is now executable
- labels are generated deterministically from market-window inputs
- confidence and ambiguity are explicit
- point-in-time safety is explicit and enforced
- output artifacts are structured and reviewable
- tests exist and pass
- the system is ready for Step 7 feature-store/model work without major guessing

This step will be rejected if:
- it is mostly prose
- it skips executable label logic
- it uses future leakage
- class boundaries remain hand-wavy in code
- confidence tiers are not encoded
- tests are missing
- audit zip is missing

================================
REQUIRED FINAL RESPONSE FORMAT
================================

When you finish, do NOT just say “done”.

Return a completion report with these sections:

1. Summary of what was implemented
2. Files added/changed
3. Exact task_id and supported classes
4. Exact commands run
5. Test results summary
6. Label-generation run summary
7. Docs added/updated
8. Audit bundle zip path/name
9. Known limitations / deferred items
10. Definition of Done checklist with PASS/FAIL per item

If any Definition of Done item is FAIL, say clearly that the task is not complete.

================================
FINAL DEFINITION OF DONE — READ AGAIN
================================

You are NOT done until ALL are true:

- Step 5 specs are consumed
- label-spec compiler exists
- market-window validation exists
- deterministic label generation exists
- all target classes are supported
- confidence policy is encoded
- ambiguity policy is encoded
- PIT safety is encoded
- output artifacts are produced
- manifest/report are produced
- tests pass
- docs are updated
- handoff is prepared
- audit zip is created and verified

If you finish coding but do not run tests and do not create the audit zip, the task is NOT COMPLETE.