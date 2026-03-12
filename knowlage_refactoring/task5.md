Task 5 — Rule Normalization and Merge Logic

Implement Task 5 of the redesigned pipeline.

Goal

Add a new stage that runs after Step 4 evidence linking and produces normalized, retrievable RuleCard objects.

This stage must:

merge overlapping KnowledgeEvents into rule-level knowledge

keep rules atomic

split rules that are too broad

preserve provenance

attach supporting evidence refs

write:

output_intermediate/<lesson>.rule_cards.json

optionally output_intermediate/<lesson>.rule_debug.json

This stage must not replace the current markdown pipeline yet.

Why this stage exists

After Step 3 and Step 4, the system has:

atomic extracted statements (KnowledgeEvent)

linked visual evidence (EvidenceRef)

But those are still too granular for:

retrieval

algorithm design

future ML labeling

Task 5 creates the first canonical rule objects.

These rule objects are the real core of the trading knowledge base.

Inputs

Task 5 must consume:

Required

output_intermediate/<lesson>.knowledge_events.json

output_intermediate/<lesson>.evidence_index.json

Optional

output_intermediate/<lesson>.knowledge_debug.json

output_intermediate/<lesson>.evidence_debug.json

The optional files are for debugging only.

Outputs

Write:

output_intermediate/<lesson>.rule_cards.json

optionally output_intermediate/<lesson>.rule_debug.json

Deliverables

Create:

pipeline/component2/rule_reducer.py

tests/test_rule_reducer.py

Update:

pipeline/component2/main.py

Use Task 2 schemas:

KnowledgeEvent

KnowledgeEventCollection

EvidenceRef

EvidenceIndex

RuleCard

RuleCardCollection

Core design principles
1. Normalize into atomic rules

A RuleCard should represent one rule, not an entire topic.

Good:

“A level becomes stronger when price reacts to it multiple times.”

Bad:

“All important things about levels, strength, breakouts, and false breakouts.”

2. Deterministic first, LLM optional

First pass should be:

clustering

grouping

splitting

merging

field assembly

Use deterministic heuristics first.

Optional LLM summarization can be added later, but should not be required for V1.

3. Preserve provenance

Every RuleCard must preserve:

source KnowledgeEvent.event_ids

linked EvidenceRef.evidence_ids

lesson id

section/subsection where possible

4. Merge carefully

Do not merge just because two statements are semantically similar.

You must distinguish:

rule vs condition

rule vs invalidation

rule vs exception

rule vs comparison

positive vs counterexample evidence

5. Split aggressively when needed

If a grouped cluster contains multiple distinct rules, split it.

Atomicity is more important than aggressive merging.

Functional requirements
1. Create pipeline/component2/rule_reducer.py

This module is responsible for:

loading knowledge events

loading evidence refs

grouping compatible events

merging them into rule candidates

splitting overly broad candidates

producing validated RuleCards

writing RuleCardCollection

2. Load and validate inputs

Implement:

def load_knowledge_events(path: Path) -> KnowledgeEventCollection:
    ...

def load_evidence_index(path: Path) -> EvidenceIndex:
    ...
Requirements

validate via Pydantic schemas

fail early on invalid schema

tolerate empty but valid collections

3. Add internal grouping model

Create an internal model for grouped rule candidates before final RuleCard conversion.

Suggested structure:

from dataclasses import dataclass, field


@dataclass
class RuleCandidate:
    candidate_id: str
    lesson_id: str
    concept: str | None
    subconcept: str | None
    title_hint: str | None
    primary_events: list[KnowledgeEvent] = field(default_factory=list)
    condition_events: list[KnowledgeEvent] = field(default_factory=list)
    invalidation_events: list[KnowledgeEvent] = field(default_factory=list)
    exception_events: list[KnowledgeEvent] = field(default_factory=list)
    comparison_events: list[KnowledgeEvent] = field(default_factory=list)
    warning_events: list[KnowledgeEvent] = field(default_factory=list)
    process_events: list[KnowledgeEvent] = field(default_factory=list)
    algorithm_hint_events: list[KnowledgeEvent] = field(default_factory=list)
    example_events: list[KnowledgeEvent] = field(default_factory=list)
    linked_evidence: list[EvidenceRef] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
Notes

primary_events should mainly come from:

definition

rule_statement

other event types enrich the rule

this is not a public schema

4. Group KnowledgeEvents into candidate rule clusters

Implement:

def group_events_into_rule_candidates(
    knowledge_events: list[KnowledgeEvent],
    evidence_index: EvidenceIndex,
) -> tuple[list[RuleCandidate], list[dict]]:
    ...

This is the heart of Task 5.

Grouping dimensions

Group events together only when most of these align:

A. same lesson

Must match.

B. same concept

Strong requirement unless one side has concept=None.

C. same subconcept

Strong positive signal, but not mandatory.

D. same local area

Strong boost if:

same section

same subsection

same chunk index or neighboring chunk indexes

E. compatible event roles

Examples:

rule_statement and condition can belong together

rule_statement and invalidation can belong together

two rule_statements can belong together if semantically the same

unrelated comparison or different definitions should not be merged blindly

F. semantic similarity

Use lightweight text similarity to detect near-duplicate rule phrasing.

5. Add a rule-candidate match scorer

Implement:

def score_event_candidate_match(
    event: KnowledgeEvent,
    candidate: RuleCandidate,
) -> tuple[float, dict]:
    ...
Suggested scoring weights

Start with a simple additive score:

same concept: +0.35

same subconcept: +0.20

same section/subsection: +0.15

same chunk or adjacent chunk: +0.10

compatible event role: +0.10

strong text similarity to primary event(s): +0.10

Cap at 1.0.

Thresholds

attach to existing candidate if score >= 0.60

otherwise create new candidate

Make threshold configurable.

Debug output

Return breakdown like:

{
  "concept_match": 0.35,
  "subconcept_match": 0.20,
  "section_match": 0.15,
  "chunk_proximity": 0.10,
  "role_compatibility": 0.10,
  "text_similarity": 0.05,
  "total": 0.95
}
6. Define role compatibility rules

Implement:

def is_role_compatible(event_type: str, candidate: RuleCandidate) -> bool:
    ...
Suggested compatibility logic
Strong fits

rule_statement with candidate having primary_events

condition with same concept/subconcept

invalidation with same concept/subconcept

exception with same concept/subconcept

algorithm_hint with same concept/subconcept

Weak but allowed

example if there is linked evidence and same concept

comparison if clearly contrasting the same rule family

Usually disallow

two unrelated definitions under same broad concept if they describe different subtopics

events with conflicting subconcepts unless one is null

7. Use evidence to strengthen or separate candidates

Implement:

def attach_evidence_to_candidates(
    candidates: list[RuleCandidate],
    evidence_index: EvidenceIndex,
) -> list[RuleCandidate]:
    ...
Logic

A candidate should receive evidence refs when:

evidence source_event_ids overlaps candidate event ids

or evidence concept hints align strongly with candidate concept/subconcept

Important

Evidence can help:

strengthen a candidate

separate two nearby but distinct rule groups

later classify example role

But evidence should not force unrelated events together.

8. Merge duplicate primary rule statements

Inside a candidate, you may have multiple rule_statements that are really the same rule phrased differently.

Implement:

def merge_duplicate_primary_events(
    primary_events: list[KnowledgeEvent],
) -> list[KnowledgeEvent]:
    ...
Step 1 logic

Keep this simple:

normalize whitespace

lowercase

remove trivial punctuation differences

exact or near-exact match only

Do not do aggressive paraphrase collapsing yet unless you add an optional text-similarity helper.

9. Split over-broad candidates

This is very important.

Implement:

def split_overbroad_candidate(candidate: RuleCandidate) -> list[RuleCandidate]:
    ...
Split when
A. multiple primary rule ideas exist

Example:

one primary event says how to recognize a level

another says how to rate a level’s strength

These should be separate.

B. conflicting subconcepts

Example:

level_rating

false_breakout

Do not keep them in one rule card.

C. conditions/invalidation clearly belong to different primary rules
D. comparison events introduce a different rule rather than clarifying the same one
Initial implementation

Use these split heuristics:

if candidate has multiple distinct non-null subconcepts → split by subconcept

if candidate has multiple primary events with low text similarity → split

if evidence refs cluster into clearly different example types and align to different primary events → split

Be conservative.
Prefer over-splitting to bad mega-rules.

10. Build final RuleCard fields

Implement:

def candidate_to_rule_card(candidate: RuleCandidate) -> RuleCard:
    ...
Populate
Required

rule_id

lesson_id

concept

subconcept

rule_text

Optional / derived

title

conditions

context

invalidation

exceptions

comparisons

algorithm_notes

visual_summary

evidence_refs

source_event_ids

confidence

confidence_score

ML-ready placeholders

candidate_features

positive_example_refs

negative_example_refs

ambiguous_example_refs

labeling_guidance

11. Decide how to construct rule_text

Implement:

def choose_canonical_rule_text(candidate: RuleCandidate) -> str:
    ...
Rule selection logic

Use this priority:

best rule_statement

if none, best definition

if none, promote a strong condition only as last resort

Best event selection criteria

Prefer:

explicit rule/definition language

highest confidence

clearer concept/subconcept

shorter and more canonical wording

Important

Do not concatenate multiple unrelated primary events into one long sentence.

Choose one canonical sentence.

12. Construct conditions, invalidations, exceptions, and comparisons

Implement helpers:

def collect_condition_texts(candidate: RuleCandidate) -> list[str]:
    ...

def collect_invalidation_texts(candidate: RuleCandidate) -> list[str]:
    ...

def collect_exception_texts(candidate: RuleCandidate) -> list[str]:
    ...

def collect_comparison_texts(candidate: RuleCandidate) -> list[str]:
    ...

def collect_algorithm_notes(candidate: RuleCandidate) -> list[str]:
    ...
Rules

dedupe normalized text

keep short statements

preserve order when reasonable

do not copy the canonical rule_text back into conditions unless it is genuinely distinct

13. Generate visual_summary

Implement:

def build_candidate_visual_summary(candidate: RuleCandidate) -> str | None:
    ...
Logic

Use linked evidence refs to produce a compact summary.

If there is one strong evidence ref:

reuse or lightly adapt its compact_visual_summary

If there are several:

choose the best representative or merge into one short line

Important

max 1–2 lines

do not narrate frame-by-frame

do not stuff all evidence summaries together

14. Map evidence roles into ML/example fields

Implement:

def distribute_example_refs(candidate: RuleCandidate) -> dict[str, list[str]]:
    ...
Mapping

Based on linked EvidenceRef.example_role:

positive_example → positive_example_refs

counterexample / negative_example → negative_example_refs

ambiguous_example → ambiguous_example_refs

This is very useful for later ML labeling.

15. Add candidate confidence scoring

Implement:

def score_rule_candidate_confidence(candidate: RuleCandidate) -> tuple[str, float]:
    ...
Increase confidence when

there is a clear primary rule statement

concept and subconcept are present

multiple supporting events agree

evidence is linked

invalidation/conditions align cleanly

Lower confidence when

no clear primary statement exists

concept is missing

candidate had to be inferred mostly from examples

evidence is weak or contradictory

split heuristics were borderline

Output

confidence: low / medium / high

confidence_score: float in [0,1]

16. Generate deterministic rule ids

Implement:

def make_rule_id(
    lesson_id: str,
    concept: str | None,
    subconcept: str | None,
    candidate_index: int,
) -> str:
    ...
Example format
rule_<lesson_slug>_<concept_or_unknown>_<subconcept_or_general>_<index>

Keep it deterministic and stable across identical input.

17. Build final collection

Implement:

def build_rule_cards(
    knowledge_collection: KnowledgeEventCollection,
    evidence_index: EvidenceIndex,
) -> tuple[RuleCardCollection, list[dict]]:
    ...

The function should:

group events into candidates

attach evidence

merge duplicates inside candidates

split over-broad candidates

convert candidates to RuleCard

produce debug rows

return:

RuleCardCollection

debug rows

18. Save outputs

Implement:

def save_rule_cards(collection: RuleCardCollection, output_path: Path) -> None:
    ...

def save_rule_debug(debug_rows: list[dict], output_path: Path) -> None:
    ...
Output paths

Use Task 1 path contracts:

output_intermediate/<lesson>.rule_cards.json

output_intermediate/<lesson>.rule_debug.json

19. Integrate into pipeline.component2.main

Insert Task 5 after evidence linking and before any future markdown-from-rule-card rendering.

Conceptual flow
if feature_flags.enable_knowledge_events:
    knowledge_collection = ...

if feature_flags.enable_evidence_linking:
    evidence_index = ...

if feature_flags.enable_rule_cards:
    rule_cards, rule_debug = build_rule_cards(
        knowledge_collection=knowledge_collection,
        evidence_index=evidence_index,
    )
    save_rule_cards(...)
    save_rule_debug(...)

# legacy markdown flow still remains unchanged
Feature flag

Add:

enable_rule_cards

Safe default:

False

When disabled:

no behavior change

Debug output requirements

Write per-candidate debug rows like:

{
  "candidate_id": "rcand_lesson2_4",
  "concept": "level",
  "subconcept": "level_rating",
  "source_event_ids": [
    "ke_lesson2_4_rule_statement_0",
    "ke_lesson2_4_condition_0",
    "ke_lesson2_5_invalidation_0"
  ],
  "linked_evidence_ids": [
    "evid_lesson2_3_0"
  ],
  "canonical_rule_text": "A level becomes stronger when price reacts to it multiple times.",
  "conditions": [
    "Reactions should occur near the same price zone."
  ],
  "invalidation": [
    "A single isolated touch is not enough."
  ],
  "split_applied": false,
  "confidence_score": 0.88
}

Also include grouping-score details where useful.

This file is for QA only.

Suggested internal helper functions

Implement at least these helpers:

def normalize_text_for_match(text: str) -> str: ...
def simple_text_similarity(a: str, b: str) -> float: ...
def group_events_into_rule_candidates(...): ...
def score_event_candidate_match(...): ...
def is_role_compatible(...): ...
def attach_evidence_to_candidates(...): ...
def merge_duplicate_primary_events(...): ...
def split_overbroad_candidate(...): ...
def choose_canonical_rule_text(...): ...
def build_candidate_visual_summary(...): ...
def distribute_example_refs(...): ...
def score_rule_candidate_confidence(...): ...
def candidate_to_rule_card(...): ...
def build_rule_cards(...): ...

Keep them small and testable.

Tests to implement

Create tests/test_rule_reducer.py.

Required tests
1. Load valid inputs

Ensure valid KnowledgeEventCollection and EvidenceIndex can be loaded.

2. Group compatible events

Given:

same concept

same subconcept

same section/chunk

compatible roles

verify they form one candidate.

3. Do not merge incompatible events

Given:

same broad concept but different subconcepts
or

unrelated rule statements

verify they remain separate candidates.

4. Attach evidence by source event ids

Given evidence whose source_event_ids overlap candidate event ids, verify it links correctly.

5. Split over-broad candidate

Given one candidate with two clearly different primary rules, verify it splits.

6. Choose canonical rule text

Given multiple primary events, verify the clearer/higher-confidence one is chosen.

7. Build final RuleCard

Verify output contains:

rule_text

conditions

invalidation

evidence_refs

source_event_ids

8. Example refs distribution

Verify positive/counterexample/ambiguous evidence ids map to the correct ML-ready fields.

9. Confidence scoring

Verify stronger candidates score above weaker ones.

10. Serialization

Ensure RuleCardCollection serializes correctly.

11. Feature-flag-safe integration

When enable_rule_cards=False, legacy pipeline remains unchanged.

Important implementation rules
Do

keep rule cards atomic

preserve provenance strongly

prefer conservative merging

split when uncertain

keep rule_text canonical and short

keep conditions/invalidation distinct

use evidence as support, not as the primary rule source

Do not

do not create giant topic summaries

do not merge across different subconcepts unless one side is null and match is strong

do not collapse invalidation into conditions

do not duplicate the same text across all fields

do not require an LLM for first-pass normalization

Definition of done

Task 5 is complete when:

pipeline/component2/rule_reducer.py exists

it loads knowledge_events.json and evidence_index.json

it groups compatible KnowledgeEvents into rule candidates

it merges duplicates conservatively

it splits over-broad candidates

it emits valid RuleCardCollection

it writes rule_cards.json

it optionally writes rule_debug.json

legacy markdown flow remains unchanged when feature flag is off

Short copy-paste version
Implement Task 5 only: Rule Normalization and Merge Logic.

Create:
- pipeline/component2/rule_reducer.py
- tests/test_rule_reducer.py

Goal:
After Step 4 evidence linking, normalize KnowledgeEvents into RuleCards and write:
- output_intermediate/<lesson>.rule_cards.json
- optional output_intermediate/<lesson>.rule_debug.json

Inputs:
- output_intermediate/<lesson>.knowledge_events.json
- output_intermediate/<lesson>.evidence_index.json

Requirements:
1. Load validated KnowledgeEventCollection and EvidenceIndex
2. Group compatible KnowledgeEvents into internal RuleCandidate objects
3. Use grouping signals:
   - same concept
   - same subconcept
   - same section/subsection
   - same or nearby chunk
   - compatible event roles
   - text similarity
4. Attach EvidenceRefs to candidates using source_event_ids and concept alignment
5. Merge duplicate primary rule statements conservatively
6. Split over-broad candidates when:
   - multiple distinct primary rules exist
   - conflicting subconcepts exist
   - conditions/invalidation belong to different rules
7. Convert candidates into Task 2 RuleCard objects
8. Populate:
   - rule_text
   - conditions
   - context
   - invalidation
   - exceptions
   - comparisons
   - algorithm_notes
   - visual_summary
   - evidence_refs
   - source_event_ids
   - confidence
   - confidence_score
   - positive_example_refs
   - negative_example_refs
   - ambiguous_example_refs
9. Save RuleCardCollection JSON
10. Integrate behind feature flag:
   - enable_rule_cards
11. Do not break legacy markdown/reducer flow

Do not:
- use an LLM as the required first-pass reducer
- create giant topic summaries
- merge incompatible subconcepts
- lose provenance

If you want, I can do Task 6 next in the same format.