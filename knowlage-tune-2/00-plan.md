Below is the concrete fix plan I would use.

**Confidence: High — based on the current lesson outputs and your original pipeline spec.**

The plan is driven by four hard failures visible in this run:

1. Rule reduction is not canonicalizing correctly: the false-breakout concept is emitted as multiple near-duplicate rules instead of one canonical rule.  
2. Placeholder rules are surviving into final artifacts, including `"No rule text extracted."` in both debug and exported rule cards.  
3. Evidence assignment is too broad and often wrong: intro frames and generic teaching visuals are marked as `counterexample`, while `linked_rule_ids` remain empty.  
4. Provenance is incomplete at the event level: many `KnowledgeEvent`s and rule candidates still have empty `source_event_ids` / `evidence_refs`, while the original spec requires full traceability and warns against aggressive ML-population. 

## Phase 1 — Stabilize the schemas and validity gates

This phase is about preventing bad records from flowing downstream.

### 1.1 KnowledgeEvent validity rules

Add hard validation in `schemas.py` and `knowledge_builder.py`:

* `event_id`, `lesson_id`, `event_type`, `normalized_text` required
* reject empty / placeholder normalized text
* add `chunk_index`, `timestamp_start`, `timestamp_end` as required unless the source genuinely has none
* keep `source_event_ids` optional for events, but never for derived rules

### 1.2 RuleCard validity rules

In `schemas.py` and `rule_reducer.py`:

Reject a rule card if any of these are true:

* `rule_text` is empty
* `rule_text == "No rule text extracted."`
* no `source_event_ids`
* concept/subconcept exist but there is no usable primary statement

Quarantine these to `rule_debug.json` only.

### 1.3 EvidenceRef validity rules

In `schemas.py` and `evidence_linker.py`:

* `example_role` must be one of the controlled enums
* `linked_rule_ids` may be empty only before rule reduction
* after reduction, every retained evidence record linked into final outputs must either have at least one `linked_rule_id` or be explicitly marked as `unassigned`

### Acceptance criteria

* `rule_cards.json` contains **zero** placeholder `rule_text` values.
* `rule_cards.json` contains **zero** rules with empty `source_event_ids`.
* invalid or placeholder rule candidates remain only in debug artifacts.
* schema validation fails fast on malformed rule/evidence objects.

## Phase 2 — Tighten `knowledge_builder.py`

Right now the event layer is too broad. Events are being extracted with long chunk-wide spans and weak local grounding.

### 2.1 Narrow timestamp anchoring

Instead of assigning the whole chunk window to every event, add local anchoring:

* nearest transcript line range
* local sentence offsets
* local visual window around the extracted statement

The goal is not frame-perfect timing yet, but not `12:31–14:36` for every idea in the chunk.

### 2.2 Event role separation

Prevent mixing of:

* rule
* condition
* example
* algorithm hint
* warning

The spec already requires atomic typed knowledge events.

Add a deterministic post-pass:

* if extracted statement starts with “when / if / only when” → prefer `condition`
* if it describes “look for / identify / detect” → prefer `algorithm_hint`
* if it describes a concrete case → prefer `example`
* never promote a condition into a rule candidate by default

### 2.3 Canonical text cleanup

Normalize text before reduction:

* strip rhetorical phrasing
* remove duplicated explanatory tails
* normalize “cannot update high / cannot close above” patterns into consistent wording
* preserve ambiguity in `ambiguity_notes`, not in rule text

### Acceptance criteria

* For a sampled lesson, at least 90% of events have a usable local time window smaller than the full chunk.
* At least 95% of events have non-empty `normalized_text`.
* Rule-like and condition-like statements are no longer mixed in the same event type.

## Phase 3 — Rewrite the core merge logic in `rule_reducer.py`

This is the most important phase.

Your own spec says merge only when concept/subconcept, semantic overlap, and teaching intent align, and do not merge across rule vs condition vs exception boundaries.
The current outputs violate that.

### 3.1 Introduce a real `RuleCandidate` assembly model

Build candidates from:

* one primary rule statement or definition
* supporting conditions
* supporting examples
* supporting algorithm hints
* linked evidence ids

Do not create a `RuleCard` from conditions alone.

### 3.2 Add a canonicalization signature

For each candidate, build a merge key from:

* normalized concept
* normalized subconcept
* normalized rule skeleton
* teaching intent

Example for false breakout:

* concept: `false_breakout`
* skeleton: `breach_level -> fail_acceptance -> close_back_through_or_fail_close_beyond`

This would collapse `unknown_3`, `unknown_4`, and similar paraphrases into one rule instead of many.

### 3.3 Split only when semantic intent differs

Example: keep separate if these are genuinely distinct:

* definition of false breakout
* bullish false breakout
* bearish false breakout
* algorithmic detection note

But do not split into multiple rules just because the wording changes.

### 3.4 Confidence recalibration

Use confidence inputs closer to your spec:

* explicit rule statement present
* repeated reinforcement
* good concept anchor
* supporting evidence linked
* ambiguity low

Do not let placeholder rules keep medium confidence.

### Acceptance criteria

* False-breakout outputs reduce to 1 canonical general rule plus, at most, 2 directional variants if supported.
* No final `RuleCard` is created from condition-only clusters.
* Duplicate-rule rate on a reviewed lesson drops below 10%.
* Confidence for invalid/quarantined candidates is never emitted into final rule cards.

## Phase 4 — Fix `evidence_linker.py`

The current evidence linking is the second-biggest problem. Intro slides and generic diagrams are being assigned as `counterexample`, and `linked_rule_ids` are often empty.

### 4.1 Add role-gating before role assignment

Default role should be `illustration`, not `counterexample`.

Promote to:

* `positive_example` only if the visual clearly demonstrates the rule
* `counterexample` only if the lesson explicitly frames it as a failure or opposite case
* `ambiguous_example` if it may be relevant but is not decisive

### 4.2 Add rule-visual compatibility checks

Before linking evidence to a rule, require at least two of:

* overlapping time window
* concept keyword overlap
* local chunk match
* visual type compatible with rule type
* example wording nearby

### 4.3 Keep rich raw evidence, compress final evidence

Your original spec explicitly says keep dense first-pass data, but store compact evidence refs downstream.
So:

* preserve raw visual event ids and frame ids
* final `compact_visual_summary` must be short and rule-relevant
* remove frame-by-frame narration from evidence summaries

### 4.4 Backfill `linked_rule_ids` after reduction

After final rule ids exist:

* re-run a deterministic evidence-to-rule link pass
* populate `linked_rule_ids`
* optionally prune evidence with no valid final rule link

### Acceptance criteria

* Intro/title frames are never labeled `positive_example`, `negative_example`, or `counterexample`.
* At least 90% of evidence refs attached to final rule cards have non-empty `linked_rule_ids`.
* `counterexample` usage is rare and justified, not the default.
* Final evidence summaries are compact and non-narrative.

## Phase 5 — Make ML-prep conservative in `ml_prep.py`

Your Task 13 spec explicitly says not to populate aggressively unless the data clearly supports it.
The current run is too aggressive.

### 5.1 Candidate features only from recognized templates

Maintain a concept-to-feature template map.

Examples:

* false breakout → `max_distance_beyond_level`, `time_beyond_level`, `return_through_level_flag`
* level strength → `reaction_count`, `zone_width`, `reversal_magnitude`

If concept is unknown or rule text is placeholder, emit no features.

### 5.2 Example ref distribution

Map evidence roles conservatively:

* `positive_example` → `positive_example_refs`
* `negative_example` / `counterexample` → `negative_example_refs`
* `ambiguous_example` → `ambiguous_example_refs`
* `illustration` → excluded from ML training refs by default

### 5.3 Labeling guidance templating

Generate guidance only when the rule is valid.

Bad:

* “Label positive only when the setup clearly matches this rule: No rule text extracted.” 

Good:

* “Label positive only when price moves beyond the level, fails to hold beyond it, and closes back through the level.”

### Acceptance criteria

* No ML fields are populated for placeholder or quarantined rules.
* `illustration` evidence never becomes a positive training example by default.
* Labeling guidance is absent for invalid rules and operational for valid rules.
* Candidate feature coverage is lower but more trustworthy.

## Phase 6 — Constrain `concept_graph.py`

The concept graph should be simple and faithful, per your spec. 
Right now some parent relationships look auto-invented, like `historical_levels -> price_action_scenario`. 

### 6.1 Edge-generation rules

Only create:

* concept → subconcept
* concept ↔ related concept when supported by co-occurring rule cards
* parent-child only from explicit hierarchy or stable normalization map

Do not invent parents from lexical similarity alone.

### 6.2 Rule-backed graphing

Every edge should be supported by at least one rule id or explicit schema relation.

### Acceptance criteria

* Every parent-child edge can be traced to either a normalization map or supporting rule card.
* No orphan invented parents remain.
* Graph size shrinks, but semantic trust improves.

## Phase 7 — Exporters and final artifacts

Your spec says markdown must be derived from rule cards and evidence refs, never from dense narration.

### 7.1 `review_markdown.md`

Include:

* canonical rule text
* conditions
* invalidations
* compact evidence refs
* provenance line

### 7.2 `rag_ready.md`

Keep only:

* concise canonical rules
* condition/invalidation snippets
* short visual note only if helpful

### 7.3 Export quarantine metrics

Add a small QA footer:

* total events
* valid rules
* quarantined candidates
* evidence linked
* evidence unassigned

### Acceptance criteria

* `rag_ready.md` contains no frame-by-frame narration.
* Every rendered rule in markdown exists in `rule_cards.json`.
* Quarantined rules never leak into markdown exports.

## Phase 8 — Regression tests

These should be real acceptance tests, not only file-exists tests.

### 8.1 Schema tests

* placeholder rule text rejected
* missing `source_event_ids` rejected for final RuleCards
* invalid evidence role rejected

### 8.2 Dedup tests

* given five false-breakout paraphrases, reducer emits one canonical rule
* conditions remain attached, not promoted to separate rules

### 8.3 Evidence tests

* intro slide maps to `illustration` or stays unassigned
* `counterexample` requires explicit negative framing
* linked final evidence has `linked_rule_ids`

### 8.4 ML-prep tests

* illustrations do not become positive examples
* placeholder rules get no labeling guidance or candidate features

### 8.5 Export tests

* final markdown contains no “No rule text extracted.”
* final markdown contains no long narrative visual summary

## Recommended implementation order

Do it in this order:

1. Schema gates
2. KnowledgeEvent cleanup
3. Rule reducer rewrite
4. Evidence linker rewrite
5. ML-prep conservatism
6. Concept graph constraints
7. Export cleanup
8. Regression tests

That order matches your original incremental design and keeps the rewrite controlled.

## What “done” looks like for this lesson

For **Lesson 2. Levels part 1**, I would consider the iteration successful when:

* false-breakout is reduced to a clean canonical set, not a paraphrase cluster
* there are zero placeholder rules in final artifacts
* evidence refs are mostly illustration or properly linked examples, not generic counterexamples
* final rules all have provenance
* concept graph is smaller and cleaner
* ML fields are sparse but believable

If you want, I can next turn this into a **JIRA-style implementation epic with sub-tasks and story-level acceptance criteria**.
