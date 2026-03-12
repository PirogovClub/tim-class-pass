Task 2 is:

Define the canonical internal schema

This is the first real foundation for the redesign. If Task 2 is done well, all later tasks become much easier.

Confidence: High — this is the right next step because without stable schemas, Task 3–7 will drift and produce inconsistent artifacts.

Task 2 objective

Create the canonical internal data model for the pipeline.

This model must support:

dense first-pass extraction

structured knowledge extraction

evidence preservation

rule normalization

markdown export later

RAG later

ML labeling later

The schema must be:

explicit

versioned

testable

serializable to JSON

easy to evolve without breaking old outputs

Main design choice

Use Pydantic models for the canonical schema.

Why:

strong validation

easy JSON serialization

default values and optional fields are clear

future schema evolution is easier

better than loose dicts

safer than raw dataclasses for a pipeline like this

Use:

BaseModel

Field

Literal

Optional

list[...]

dict[...]

If the codebase already strongly prefers dataclasses, you can wrap them later, but for Task 2 I recommend Pydantic as the source of truth.

What to create

Create a new file:

pipeline/schemas.py

This file will contain all canonical models.

Also create:

tests/test_schemas.py
Schema philosophy

The models should represent four levels of knowledge maturity:

Level 1 — raw normalized units

Things extracted from transcript/visuals before interpretation.

Example:

KnowledgeEvent

EvidenceRef

Level 2 — structured rule objects

Things already normalized into retrievable knowledge.

Example:

RuleCard

Level 3 — graph / relationships

Things that connect rules and concepts across the lesson.

Example:

ConceptNode

ConceptRelation

ConceptGraph

Level 4 — container artifacts

Things written to disk as lesson outputs.

Example:

LessonKnowledgeBundle

Step-by-step implementation plan
Step 1 — create common enums / literals

Define reusable literal types first.

Suggested types
from typing import Literal

EventType = Literal[
    "definition",
    "rule_statement",
    "condition",
    "invalidation",
    "exception",
    "comparison",
    "example",
    "warning",
    "process_step",
    "algorithm_hint",
    "observation",
]

VisualType = Literal[
    "annotated_chart",
    "plain_chart",
    "hand_drawing",
    "diagram",
    "text_slide",
    "mixed_visual",
    "unknown",
]

ExampleRole = Literal[
    "positive_example",
    "negative_example",
    "counterexample",
    "ambiguous_example",
    "illustration",
    "unknown",
]

ConfidenceLabel = Literal[
    "low",
    "medium",
    "high",
]

ConceptRelationType = Literal[
    "parent_of",
    "child_of",
    "related_to",
    "depends_on",
    "contrasts_with",
    "precedes",
    "supports",
]
Why this matters

This prevents inconsistent string values like:

"rule"

"rule statement"

"rule_statement"

You want one vocabulary.

Step 2 — add base mixins for shared fields

Many objects need common provenance fields.

Create a small reusable base.

Example
from pydantic import BaseModel, Field
from typing import Optional, List


class ProvenanceMixin(BaseModel):
    lesson_id: str = Field(..., description="Unique lesson identifier")
    lesson_title: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    source_event_ids: List[str] = Field(default_factory=list)
Optional timestamp mixin
class TimeRangeMixin(BaseModel):
    timestamp_start: Optional[str] = Field(None, description="MM:SS or HH:MM:SS")
    timestamp_end: Optional[str] = None
Why this matters

It keeps schemas consistent and avoids duplicated fields with slightly different names.

Step 3 — define EvidenceRef

This is critical because your visuals should become linked evidence, not verbose primary content.

Required behavior

It must preserve:

timestamps

frame ids

screenshot paths

visual type

example role

linked rules later

compact visual summary only

Suggested model
from pydantic import BaseModel, Field
from typing import List, Optional


class EvidenceRef(ProvenanceMixin, TimeRangeMixin):
    evidence_id: str = Field(..., description="Unique evidence identifier")
    frame_ids: List[str] = Field(default_factory=list)
    screenshot_paths: List[str] = Field(default_factory=list)
    visual_type: VisualType = "unknown"
    example_role: ExampleRole = "unknown"
    compact_visual_summary: Optional[str] = Field(
        None,
        description="Short evidence summary, not frame-by-frame narration"
    )
    linked_rule_ids: List[str] = Field(default_factory=list)
    raw_visual_event_ids: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
Validation rules to add

compact_visual_summary should be short

no None lists

frame ids and screenshot paths default to empty lists

Step 4 — define KnowledgeEvent

This is the atomic extracted unit.

Required behavior

A KnowledgeEvent should represent one extracted statement like:

a definition

a rule

an invalidation

a condition

a comparison

a process step

It is not yet the final rule card.

Suggested model
class KnowledgeEvent(ProvenanceMixin, TimeRangeMixin):
    event_id: str = Field(..., description="Unique knowledge event identifier")
    event_type: EventType
    raw_text: str = Field(..., description="Raw extracted text")
    normalized_text: str = Field(..., description="Normalized clean text")
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ambiguity_notes: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
Important rule

KnowledgeEvent is atomic.

Do not allow it to become a multi-paragraph blob.

Add validation

raw_text must not be empty

normalized_text must not be empty

if confidence_score exists, it must be within [0,1]

Step 5 — define RuleCard

This is the primary retrievable knowledge object.

Required behavior

A RuleCard should represent one normalized rule that can later drive:

RAG retrieval

algorithm design

ML labeling

Suggested model
class RuleCard(ProvenanceMixin):
    rule_id: str = Field(..., description="Unique rule identifier")
    concept: str = Field(..., description="Top-level concept, e.g. level")
    subconcept: Optional[str] = Field(None, description="Subconcept, e.g. level_rating")
    title: Optional[str] = None
    rule_text: str = Field(..., description="Canonical statement of the rule")
    conditions: List[str] = Field(default_factory=list)
    context: List[str] = Field(default_factory=list)
    invalidation: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    comparisons: List[str] = Field(default_factory=list)
    algorithm_notes: List[str] = Field(default_factory=list)
    visual_summary: Optional[str] = Field(
        None,
        description="Compact visual evidence summary if useful"
    )
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    # ML-readiness
    candidate_features: List[str] = Field(default_factory=list)
    positive_example_refs: List[str] = Field(default_factory=list)
    negative_example_refs: List[str] = Field(default_factory=list)
    ambiguous_example_refs: List[str] = Field(default_factory=list)
    labeling_guidance: Optional[str] = None

    metadata: dict = Field(default_factory=dict)
Important rule

RuleCard must stay canonical and compact.

It is not a lesson summary.

Validation ideas

concept required

rule_text required

rule_text should not be huge

all list fields default to empty lists

no nested dict soup for primary rule meaning

Step 6 — define concept graph models

These models are lighter, but still important.

ConceptNode
class ConceptNode(BaseModel):
    concept_id: str
    name: str
    type: str = Field(..., description="concept, subconcept, pattern, rule_group")
    parent_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
ConceptRelation
class ConceptRelation(BaseModel):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: ConceptRelationType
    metadata: dict = Field(default_factory=dict)
ConceptGraph
class ConceptGraph(BaseModel):
    lesson_id: str
    nodes: List[ConceptNode] = Field(default_factory=list)
    relations: List[ConceptRelation] = Field(default_factory=list)
Why this matters

You will later want to connect:

level

level_recognition

level_rating

break_confirmation

false_breakout

without flattening everything into one tag list.

Step 7 — define lesson-level output containers

Instead of writing disconnected JSON blobs with unclear top-level structure, define container models.

KnowledgeEventCollection
class KnowledgeEventCollection(BaseModel):
    schema_version: str = "1.0"
    lesson_id: str
    events: List[KnowledgeEvent] = Field(default_factory=list)
EvidenceIndex
class EvidenceIndex(BaseModel):
    schema_version: str = "1.0"
    lesson_id: str
    evidence: List[EvidenceRef] = Field(default_factory=list)
RuleCardCollection
class RuleCardCollection(BaseModel):
    schema_version: str = "1.0"
    lesson_id: str
    rules: List[RuleCard] = Field(default_factory=list)
LessonKnowledgeBundle
class LessonKnowledgeBundle(BaseModel):
    schema_version: str = "1.0"
    lesson_id: str
    lesson_title: Optional[str] = None
    knowledge_events: List[KnowledgeEvent] = Field(default_factory=list)
    evidence_index: List[EvidenceRef] = Field(default_factory=list)
    rule_cards: List[RuleCard] = Field(default_factory=list)
    concept_graph: Optional[ConceptGraph] = None
    metadata: dict = Field(default_factory=dict)
Why this matters

It gives consistent output shape and allows versioning later.

Step 8 — add helper methods for JSON persistence

Add lightweight helpers in the same file or a nearby utility file.

Example
from pathlib import Path
import json


class JsonIOModel(BaseModel):
    def to_pretty_json(self) -> str:
        return self.model_dump_json(indent=2)

    def save_json(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

You can also make your models inherit from a common base:

class SchemaBase(BaseModel):
    model_config = {
        "extra": "forbid",
        "populate_by_name": True,
    }

    def save_json(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
Critical rule

Use:

extra = "forbid"

This is very important.

It prevents random undefined fields from silently creeping into the pipeline.

Recommended final structure of pipeline/schemas.py

Order the file like this:

1. imports
2. Literal type aliases
3. base schema class
4. mixins
5. EvidenceRef
6. KnowledgeEvent
7. RuleCard
8. ConceptNode / ConceptRelation / ConceptGraph
9. collection/container classes

That will keep the file readable.

Validation rules to implement

These are important for Task 2.

Rule 1 — forbid unknown fields

All models should reject undeclared fields.

Rule 2 — normalize empty lists

Never allow None where a list should exist.

Rule 3 — require canonical ids

Each main object must require its id:

event_id

rule_id

evidence_id

concept_id

Rule 4 — confidence score bounds

If present, confidence score must be in [0.0, 1.0]

Rule 5 — rule text required for RuleCard

No empty rule cards.

Rule 6 — compact visual summary stays compact

You do not need strict token counting yet, but add a validator warning or cap if needed later.

Suggested code skeleton

Below is a strong starting skeleton for the coding agent.

from __future__ import annotations

from typing import Literal, Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, field_validator


EventType = Literal[
    "definition",
    "rule_statement",
    "condition",
    "invalidation",
    "exception",
    "comparison",
    "example",
    "warning",
    "process_step",
    "algorithm_hint",
    "observation",
]

VisualType = Literal[
    "annotated_chart",
    "plain_chart",
    "hand_drawing",
    "diagram",
    "text_slide",
    "mixed_visual",
    "unknown",
]

ExampleRole = Literal[
    "positive_example",
    "negative_example",
    "counterexample",
    "ambiguous_example",
    "illustration",
    "unknown",
]

ConfidenceLabel = Literal["low", "medium", "high"]

ConceptRelationType = Literal[
    "parent_of",
    "child_of",
    "related_to",
    "depends_on",
    "contrasts_with",
    "precedes",
    "supports",
]


class SchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def save_json(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")


class ProvenanceMixin(SchemaBase):
    lesson_id: str
    lesson_title: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    source_event_ids: List[str] = Field(default_factory=list)


class TimeRangeMixin(SchemaBase):
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None


class EvidenceRef(ProvenanceMixin, TimeRangeMixin):
    evidence_id: str
    frame_ids: List[str] = Field(default_factory=list)
    screenshot_paths: List[str] = Field(default_factory=list)
    visual_type: VisualType = "unknown"
    example_role: ExampleRole = "unknown"
    compact_visual_summary: Optional[str] = None
    linked_rule_ids: List[str] = Field(default_factory=list)
    raw_visual_event_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeEvent(ProvenanceMixin, TimeRangeMixin):
    event_id: str
    event_type: EventType
    raw_text: str
    normalized_text: str
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ambiguity_notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_text", "normalized_text")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Text fields must not be blank")
        return v.strip()


class RuleCard(ProvenanceMixin):
    rule_id: str
    concept: str
    subconcept: Optional[str] = None
    title: Optional[str] = None
    rule_text: str
    conditions: List[str] = Field(default_factory=list)
    context: List[str] = Field(default_factory=list)
    invalidation: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    comparisons: List[str] = Field(default_factory=list)
    algorithm_notes: List[str] = Field(default_factory=list)
    visual_summary: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    candidate_features: List[str] = Field(default_factory=list)
    positive_example_refs: List[str] = Field(default_factory=list)
    negative_example_refs: List[str] = Field(default_factory=list)
    ambiguous_example_refs: List[str] = Field(default_factory=list)
    labeling_guidance: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("concept", "rule_text")
    @classmethod
    def required_text_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Required text fields must not be blank")
        return v.strip()


class ConceptNode(SchemaBase):
    concept_id: str
    name: str
    type: str
    parent_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptRelation(SchemaBase):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: ConceptRelationType
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptGraph(SchemaBase):
    lesson_id: str
    nodes: List[ConceptNode] = Field(default_factory=list)
    relations: List[ConceptRelation] = Field(default_factory=list)


class KnowledgeEventCollection(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    events: List[KnowledgeEvent] = Field(default_factory=list)


class EvidenceIndex(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    evidence: List[EvidenceRef] = Field(default_factory=list)


class RuleCardCollection(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    rules: List[RuleCard] = Field(default_factory=list)


class LessonKnowledgeBundle(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    lesson_title: Optional[str] = None
    knowledge_events: List[KnowledgeEvent] = Field(default_factory=list)
    evidence_index: List[EvidenceRef] = Field(default_factory=list)
    rule_cards: List[RuleCard] = Field(default_factory=list)
    concept_graph: Optional[ConceptGraph] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
Tests to implement for Task 2

Create tests/test_schemas.py.

Test 1 — valid KnowledgeEvent

Construct a valid instance and ensure serialization works.

Test 2 — blank text rejected

Blank raw_text or normalized_text should fail.

Test 3 — valid RuleCard

Construct a minimal valid rule card.

Test 4 — rule card requires concept and rule text

Blank values should fail.

Test 5 — confidence score bounds

1.2 and -0.1 should fail.

Test 6 — unknown field rejected

Passing an extra random field should fail.

Test 7 — valid EvidenceRef

Ensure empty lists serialize correctly.

Test 8 — bundle serialization

Construct a small LessonKnowledgeBundle with:

one event

one evidence ref

one rule card

and ensure JSON dump works.

Acceptance criteria for Task 2

Task 2 is done when:

pipeline/schemas.py exists

All core models are defined:

EvidenceRef

KnowledgeEvent

RuleCard

ConceptNode

ConceptRelation

ConceptGraph

container models

Models validate correctly

Unknown fields are rejected

JSON serialization works

Tests cover happy path and failure path

No existing pipeline behavior is changed yet

Short copy-paste instruction for the coding agent
Implement Task 2 only: define the canonical internal schema.

Create:
- pipeline/schemas.py
- tests/test_schemas.py

Use Pydantic models as the canonical schema layer.

Define:
1. Literal/enums for:
   - EventType
   - VisualType
   - ExampleRole
   - ConfidenceLabel
   - ConceptRelationType

2. Base/mixins:
   - SchemaBase with extra="forbid"
   - ProvenanceMixin
   - TimeRangeMixin

3. Core models:
   - EvidenceRef
   - KnowledgeEvent
   - RuleCard
   - ConceptNode
   - ConceptRelation
   - ConceptGraph

4. Collection/container models:
   - KnowledgeEventCollection
   - EvidenceIndex
   - RuleCardCollection
   - LessonKnowledgeBundle

Requirements:
- all list fields must default to empty lists
- ids must be explicit
- confidence_score must be bounded 0..1 if present
- required text fields must reject blank values
- models must support JSON serialization
- unknown fields must be rejected

Do not change the current pipeline behavior yet.
Do not add extraction logic yet.
Only define the schema foundation and tests.

If you want, I can now do Task 3 in the same level of detail.