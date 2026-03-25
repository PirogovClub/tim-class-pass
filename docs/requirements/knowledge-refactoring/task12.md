Yes — here is the **full description for Task 12**.

I’m assuming Task 12 in this sequence is:

**Task 12 — Add Lightweight Concept Graph Generation**

**Confidence: High**

---

# Task 12 — Add Lightweight Concept Graph Generation

## Goal

Add a lightweight **concept graph layer** that captures relationships between concepts, subconcepts, and rule groups extracted from each lesson.

This task must ensure that the pipeline can represent not only isolated rules, but also how ideas connect, for example:

* `level` → `level_recognition`
* `level_recognition` → `level_rating`
* `level_rating` → `break_confirmation`
* `break_confirmation` ↔ `false_breakout`

The graph should support:

* better retrieval
* lesson synthesis
* future cross-lesson merging
* algorithm planning
* QA of concept structure

This task must stay **lightweight and deterministic**.
It is not a full knowledge graph system.

---

# Why this task exists

By Task 5, the pipeline already produces:

* `knowledge_events.json`
* `evidence_index.json`
* `rule_cards.json`

Those artifacts are enough to retrieve individual rules, but they do not yet represent:

* concept hierarchy
* dependency order
* contrasts between related ideas
* transitions from one setup to another
* relationships between rule families

For example, a trading lesson may teach:

* what a level is
* how to rate a level
* how a breakout is confirmed
* how a false breakout differs from a confirmed breakout

Without a concept graph, those relationships stay implicit.

Task 12 makes them explicit in a compact, useful structure.

---

# Deliverables

Create:

* `pipeline/component2/concept_graph.py`
* `tests/test_concept_graph.py`

Update:

* `rule_reducer.py`
* optionally `knowledge_builder.py`
* `exporters.py`
* `main.py`
* `contracts.py` if needed

Use Task 2 schemas:

* `ConceptNode`
* `ConceptRelation`
* `ConceptGraph`
* `RuleCardCollection`

---

# Scope

Task 12 should generate a **lesson-level concept graph**.

It does **not** need to solve:

* global graph merging across all lessons
* ontology management
* graph database integration
* advanced semantic graph inference

Those can come later.

For now, the graph should be:

* per lesson
* compact
* deterministic
* driven mostly by existing structured artifacts

---

# Core design principles

## 1. Build from structured artifacts, not raw transcript

The concept graph should be generated primarily from:

* `rule_cards.json`
* optionally `knowledge_events.json`

Do not rebuild graph structure from raw chunk transcript.

## 2. Be conservative

Only create edges when there is a clear signal.

Better to miss a weak relationship than invent a false one.

## 3. Keep the graph lightweight

This is not a full semantic web.

Use:

* nodes
* typed relations
* minimal metadata

## 4. Deterministic first

Use explicit heuristics, not an LLM, for initial graph generation.

## 5. Use the graph to support later work

The graph should help later with:

* cross-lesson synthesis
* rule navigation
* algorithm design
* RAG expansion and reranking

---

# What the graph should represent

## Nodes

At minimum, the graph should represent:

* top-level concepts
* subconcepts
* optional rule-group nodes when helpful

It does **not** need a node for every single rule card unless that becomes useful later.

## Relations

At minimum, support these relation types:

* `parent_of`
* `child_of`
* `related_to`
* `depends_on`
* `contrasts_with`
* `precedes`
* `supports`

These relation types already fit the schema direction we established earlier.

---

# Inputs

## Required

* `output_intermediate/<lesson>.rule_cards.json`

## Optional

* `output_intermediate/<lesson>.knowledge_events.json`

Rule cards should be the primary input, because they are already normalized and merged.

---

# Outputs

Write:

* `output_intermediate/<lesson>.concept_graph.json`

Optional:

* `output_intermediate/<lesson>.concept_graph_debug.json`

---

# Functional requirements

## 1. Create `pipeline/component2/concept_graph.py`

This module is responsible for:

* loading rule cards
* identifying concept and subconcept nodes
* generating typed relations
* building a `ConceptGraph`
* writing output JSON
* optionally producing debug information

---

## 2. Build graph from `RuleCardCollection`

The graph should primarily use:

* `rule.concept`
* `rule.subconcept`
* optional rule metadata like:

  * source sections
  * source chunk indexes
  * comparisons
  * conditions
  * invalidations

### Important

Do **not** require raw transcript access.

---

## 3. Create concept nodes

At minimum, create nodes for:

### A. Concept nodes

Each unique non-empty `rule.concept`

Example:

* `level`
* `break_confirmation`
* `false_breakout`

### B. Subconcept nodes

Each unique non-empty `rule.subconcept`

Example:

* `level_recognition`
* `level_rating`
* `trend_break_level`

### Node rules

* dedupe by normalized id
* preserve readable `name`
* assign `type` such as:

  * `concept`
  * `subconcept`
  * optionally `rule_group`

### Parent rules

If a rule has:

* `concept = "level"`
* `subconcept = "level_rating"`

then:

* create node `level`
* create node `level_rating`
* add relation `level parent_of level_rating`
* optionally also `level_rating child_of level`

---

## 4. Generate graph relations heuristically

This is the heart of Task 12.

Implement heuristics for the following relation types.

### A. `parent_of` / `child_of`

Create when:

* a rule has both concept and subconcept

Example:

* `level` parent_of `level_rating`

### B. `related_to`

Create when:

* two subconcepts share the same concept
* or two concepts frequently co-occur in the same lesson sections
* or two rule groups are clearly adjacent and non-hierarchical

Example:

* `level_recognition related_to level_rating`

### C. `depends_on`

Create when:

* one concept appears to require understanding another first
* e.g. rating a level depends on first recognizing the level

Example:

* `level_rating depends_on level_recognition`

### D. `precedes`

Create when:

* source chunk indexes or source order imply a teaching sequence

Example:

* `level_recognition precedes level_rating`

### E. `contrasts_with`

Create when:

* rule comparisons or concept names indicate opposition or distinction

Examples:

* `false_breakout contrasts_with break_confirmation`
* `weak_level contrasts_with strong_level`

### F. `supports`

Create when:

* a concept clearly functions as supporting logic for another concept

Example:

* `level_rating supports break_confirmation`

### Important

Use conservative heuristics.
Do not create all possible edges.

---

## 5. Use source order as a weak signal, not the only signal

Source chunk order can help with:

* `precedes`
* `depends_on`

But should not create relationships by itself unless the concepts are plausibly connected.

For example:

* two unrelated ideas mentioned sequentially should not automatically get an edge

---

## 6. Use comparisons and wording as relation hints

Task 12 should inspect fields like:

* `rule.comparisons`
* `rule.rule_text`
* `rule.subconcept`
* `rule.concept`

for hints such as:

* “vs”
* “difference between”
* “unlike”
* “in contrast”
* “depends on”
* “requires”
* “before”
* “after”

These can help infer:

* `contrasts_with`
* `depends_on`
* `precedes`

This should stay heuristic and lightweight.

---

## 7. Keep graph metadata compact

Each node and relation may include small metadata, such as:

### Node metadata

* source rule ids count
* lesson id

### Relation metadata

* source rule ids
* heuristic reason
* source chunk indexes

But do **not** dump full rule cards into the graph.

---

## 8. Add relation confidence if useful, but keep it simple

This is optional for Task 12.

If included, relation metadata may have:

* `score`
* `reason`

Example:

```json
{
  "score": 0.82,
  "reason": "shared concept + ordered chunk sequence"
}
```

This is optional but helpful.

---

## 9. Integrate into `main.py`

Add concept-graph generation after Task 5 rule cards.

### Conceptual flow

```text
knowledge events
→ evidence linking
→ rule cards
→ concept graph
→ exporters
```

### Feature flag

Add:

* `enable_concept_graph`

Safe default:

* `False`

When enabled:

* write `output_intermediate/<lesson>.concept_graph.json`

### Important

Exporters should not depend on the graph initially.
Graph generation is additive.

---

## 10. Update `contracts.py`

Ensure there is a path helper for:

* `output_intermediate/<lesson>.concept_graph.json`

If already present, verify naming and usage are consistent.

Optional:

* `concept_graph_debug_path(...)`

---

## 11. Optionally surface graph hints in review markdown

This is optional, not required.

For example, review markdown could later include a compact section like:

```markdown
## Concept relationships
- level -> level_recognition
- level_recognition -> level_rating
- false_breakout contrasts_with break_confirmation
```

But Task 12 does not need to do this unless it is easy.

The primary output is still the JSON graph.

---

# Suggested internal workflow

## Step 1

Load `RuleCardCollection`

## Step 2

Create normalized node ids from:

* concept
* subconcept

## Step 3

Create nodes

## Step 4

Infer parent-child edges from concept/subconcept

## Step 5

Infer additional relation types from:

* shared concept
* ordering
* comparisons
* wording hints

## Step 6

Dedupe nodes and relations

## Step 7

Write `ConceptGraph`

---

# Suggested public functions

In `concept_graph.py`, expose at least:

```python id="16"}
def load_rule_cards(path: Path) -> RuleCardCollection:
    ...

def build_concept_graph(
    rule_cards: RuleCardCollection,
) -> tuple[ConceptGraph, list[dict]]:
    ...

def save_concept_graph(graph: ConceptGraph, output_path: Path) -> None:
    ...

def save_concept_graph_debug(debug_rows: list[dict], output_path: Path) -> None:
    ...
```

Optional helpers:

```python id="17"}
def normalize_concept_id(name: str) -> str:
    ...

def create_concept_nodes(rules: list[RuleCard]) -> list[ConceptNode]:
    ...

def create_concept_relations(rules: list[RuleCard], nodes: list[ConceptNode]) -> list[ConceptRelation]:
    ...
```

---

# Suggested heuristics for relations

## Parent-child

If a rule has both concept and subconcept:

* create `concept parent_of subconcept`
* optionally also `subconcept child_of concept`

## Related-to

If two subconcepts:

* share same concept
* are different
* and appear in the same lesson

create `related_to`

## Precedes

If:

* average source chunk index of A < average source chunk index of B
* and A/B are related by same concept family

create `precedes`

## Depends-on

If:

* names or comparisons suggest dependency
* or ordering + same family strongly indicate staged learning

Example:

* `level_rating depends_on level_recognition`

## Contrasts-with

If:

* comparisons mention contrast
* names suggest opposition:

  * false vs confirmed
  * weak vs strong
  * support vs resistance may also be related but not necessarily contrast

---

# Tests to implement

Create `tests/test_concept_graph.py`.

## Required tests

### 1. Create concept and subconcept nodes

Given rule cards with:

* `concept="level"`
* `subconcept="level_rating"`

verify both nodes are created.

### 2. Parent-child edge

Verify:

* `level parent_of level_rating`

### 3. Related-to edge for sibling subconcepts

Given:

* `level_recognition`
* `level_rating`

verify they can be connected as related siblings.

### 4. Precedes edge from source order

Given chunk-index ordering that clearly implies sequence, verify `precedes` is created.

### 5. Contrasts-with edge

Given rules/cards about:

* `false_breakout`
* `break_confirmation`

verify a contrast relation can be inferred when wording supports it.

### 6. Dedupe nodes and relations

Ensure repeated rule cards do not create duplicate nodes/edges.

### 7. Graph serialization

Ensure `ConceptGraph` serializes cleanly.

### 8. Feature-flag-safe integration

When `enable_concept_graph=False`, pipeline behavior remains unchanged.

---

# Important implementation rules

## Do

* keep graph generation deterministic
* use `RuleCardCollection` as the primary source
* keep node and relation metadata compact
* create only conservative edges
* preserve stable ids

## Do not

* do not build graph from raw transcript replay
* do not create a node for every sentence
* do not invent many weak edges
* do not make exporters depend on the graph yet
* do not over-engineer into a full ontology system

---

# Definition of done

Task 12 is complete when:

1. `pipeline/component2/concept_graph.py` exists
2. it loads `rule_cards.json`
3. it creates concept and subconcept nodes
4. it creates basic typed relations
5. it writes `concept_graph.json`
6. graph generation is deterministic and lightweight
7. `main.py` can run it behind a feature flag
8. tests cover nodes, relations, dedupe, and serialization

---

# Copy-paste instruction for the coding agent

```text id="18"}
Implement Task 12 only: Add Lightweight Concept Graph Generation.

Create:
- pipeline/component2/concept_graph.py
- tests/test_concept_graph.py

Update:
- main.py
- contracts.py if needed

Goal:
Generate a lightweight lesson-level concept graph from normalized rule cards.

Required input:
- output_intermediate/<lesson>.rule_cards.json

Required output:
- output_intermediate/<lesson>.concept_graph.json
- optional debug json

Requirements:
1. Load RuleCardCollection
2. Create nodes for unique concepts and subconcepts
3. Create parent/child relations when a rule has both concept and subconcept
4. Add conservative heuristic relations:
   - related_to
   - depends_on
   - precedes
   - contrasts_with
   - supports
5. Use source rule metadata, ordering, and comparisons as hints
6. Keep graph deterministic and lightweight
7. Dedupe nodes and relations
8. Write ConceptGraph JSON
9. Integrate behind feature flag:
   - enable_concept_graph

Do not:
- build graph from raw transcript replay
- create a node for every sentence
- invent weak or speculative edges
- turn this into a full ontology/graph-database system
```

Yes — below is a **detailed implementation addendum for Task 12**, with concrete function behavior and usable code skeletons.

**Confidence: High**

The main goal is to keep Task 12:

* deterministic
* lightweight
* rule-card-driven
* easy to test
* easy to extend later across lessons

---

# `pipeline/component2/concept_graph.py`

## 1. Imports and small constants

```python
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
import re

from pipeline.schemas import (
    RuleCard,
    RuleCardCollection,
    ConceptNode,
    ConceptRelation,
    ConceptGraph,
)
```

I would also define a small set of cue words for relation inference:

```python
CONTRAST_CUES = [
    "vs",
    "versus",
    "in contrast",
    "unlike",
    "difference between",
    "false breakout",
    "confirmed breakout",
]

DEPENDENCY_CUES = [
    "depends on",
    "requires",
    "based on",
    "after recognizing",
    "after identifying",
]

SUPPORT_CUES = [
    "supports",
    "strengthens",
    "confirms",
    "helps validate",
]

PRECEDENCE_CUES = [
    "before",
    "after",
    "first",
    "then",
    "next",
]
```

---

## 2. Normalization helpers

These should be used everywhere instead of ad hoc string handling.

```python
def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_concept_id(name: str) -> str:
    text = normalize_text(name).lower()
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9а-яё]+", "_", text, flags=re.IGNORECASE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"
```

### Behavior

* `"Level Rating"` → `"level_rating"`
* `"False Breakout"` → `"false_breakout"`
* `"Уровень, ложный пробой"` → normalized slug form
* empty → `"unknown"`

---

## 3. Rule-level helper accessors

The graph builder should not rely on raw metadata structure everywhere.

```python
def get_rule_concept(rule: RuleCard) -> str | None:
    concept = normalize_text(rule.concept)
    return concept or None


def get_rule_subconcept(rule: RuleCard) -> str | None:
    subconcept = normalize_text(rule.subconcept)
    return subconcept or None


def get_rule_source_chunk_indexes(rule: RuleCard) -> list[int]:
    metadata = rule.metadata or {}
    indexes = metadata.get("source_chunk_indexes", []) or []
    out: list[int] = []
    for item in indexes:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def get_rule_source_sections(rule: RuleCard) -> list[str]:
    metadata = rule.metadata or {}
    values = metadata.get("source_sections", []) or []
    return [normalize_text(v) for v in values if normalize_text(v)]


def get_rule_source_subsections(rule: RuleCard) -> list[str]:
    metadata = rule.metadata or {}
    values = metadata.get("source_subsections", []) or []
    return [normalize_text(v) for v in values if normalize_text(v)]
```

---

## 4. Node builders

You do **not** want a node per rule by default.
You want nodes for:

* unique concepts
* unique subconcepts

### Internal aggregation model

```python
def collect_concept_names(rules: list[RuleCard]) -> tuple[dict[str, str], dict[str, str]]:
    concept_map: dict[str, str] = {}
    subconcept_map: dict[str, str] = {}

    for rule in rules:
        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)

        if concept:
            concept_id = normalize_concept_id(concept)
            concept_map.setdefault(concept_id, concept)

        if subconcept:
            subconcept_id = normalize_concept_id(subconcept)
            subconcept_map.setdefault(subconcept_id, subconcept)

    return concept_map, subconcept_map
```

### Node creation

```python
def create_concept_nodes(rules: list[RuleCard]) -> list[ConceptNode]:
    concept_map, subconcept_map = collect_concept_names(rules)
    nodes: list[ConceptNode] = []

    for concept_id, concept_name in sorted(concept_map.items()):
        nodes.append(
            ConceptNode(
                concept_id=concept_id,
                name=concept_name,
                type="concept",
                parent_id=None,
                aliases=[],
                metadata={},
            )
        )

    for subconcept_id, subconcept_name in sorted(subconcept_map.items()):
        parent_id = infer_parent_concept_id_for_subconcept(subconcept_name, rules)
        nodes.append(
            ConceptNode(
                concept_id=subconcept_id,
                name=subconcept_name,
                type="subconcept",
                parent_id=parent_id,
                aliases=[],
                metadata={},
            )
        )

    return dedupe_nodes(nodes)
```

---

## 5. Parent inference for subconcepts

A subconcept should usually attach to the concept most often paired with it in rule cards.

```python
def infer_parent_concept_id_for_subconcept(subconcept_name: str, rules: list[RuleCard]) -> str | None:
    target = normalize_text(subconcept_name)
    counts: dict[str, int] = defaultdict(int)

    for rule in rules:
        if get_rule_subconcept(rule) != target:
            continue
        concept = get_rule_concept(rule)
        if not concept:
            continue
        counts[normalize_concept_id(concept)] += 1

    if not counts:
        return None

    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
```

### Example

If:

* 4 rules have `concept="level", subconcept="level_rating"`
* 1 rule has `concept="break_confirmation", subconcept="level_rating"`

then parent is `level`.

---

## 6. Node dedupe

```python
def dedupe_nodes(nodes: list[ConceptNode]) -> list[ConceptNode]:
    seen: dict[str, ConceptNode] = {}
    for node in nodes:
        if node.concept_id not in seen:
            seen[node.concept_id] = node
            continue

        existing = seen[node.concept_id]
        merged_aliases = sorted(set(existing.aliases + node.aliases))
        merged_metadata = {**existing.metadata, **node.metadata}

        seen[node.concept_id] = ConceptNode(
            concept_id=existing.concept_id,
            name=existing.name or node.name,
            type=existing.type or node.type,
            parent_id=existing.parent_id or node.parent_id,
            aliases=merged_aliases,
            metadata=merged_metadata,
        )
    return list(seen.values())
```

---

# Relation generation

## 7. Base relation helper

```python
def make_relation_id(source_id: str, relation_type: str, target_id: str) -> str:
    return f"rel_{source_id}_{relation_type}_{target_id}"
```

---

## 8. Parent/child relations

These are the safest relations and should always be created when both concept and subconcept exist.

```python
def create_parent_child_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    relations: list[ConceptRelation] = []

    for rule in rules:
        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)

        if not concept or not subconcept:
            continue

        concept_id = normalize_concept_id(concept)
        subconcept_id = normalize_concept_id(subconcept)

        relations.append(
            ConceptRelation(
                relation_id=make_relation_id(concept_id, "parent_of", subconcept_id),
                source_id=concept_id,
                target_id=subconcept_id,
                relation_type="parent_of",
                metadata={"source_rule_ids": [rule.rule_id]},
            )
        )
        relations.append(
            ConceptRelation(
                relation_id=make_relation_id(subconcept_id, "child_of", concept_id),
                source_id=subconcept_id,
                target_id=concept_id,
                relation_type="child_of",
                metadata={"source_rule_ids": [rule.rule_id]},
            )
        )

    return dedupe_relations(relations)
```

---

## 9. Sibling `related_to` relations

If two subconcepts share the same parent concept, they are often useful sibling relations.

```python
def create_sibling_related_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    concept_to_subconcepts: dict[str, set[str]] = defaultdict(set)

    for rule in rules:
        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)
        if not concept or not subconcept:
            continue
        concept_to_subconcepts[normalize_concept_id(concept)].add(normalize_concept_id(subconcept))

    relations: list[ConceptRelation] = []

    for concept_id, subconcept_ids in concept_to_subconcepts.items():
        ordered = sorted(subconcept_ids)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                relations.append(
                    ConceptRelation(
                        relation_id=make_relation_id(left, "related_to", right),
                        source_id=left,
                        target_id=right,
                        relation_type="related_to",
                        metadata={"reason": f"shared parent concept {concept_id}"},
                    )
                )
                relations.append(
                    ConceptRelation(
                        relation_id=make_relation_id(right, "related_to", left),
                        source_id=right,
                        target_id=left,
                        relation_type="related_to",
                        metadata={"reason": f"shared parent concept {concept_id}"},
                    )
                )

    return dedupe_relations(relations)
```

### Why both directions?

Because `related_to` is symmetric in meaning, but your schema is directed.
Storing both directions makes traversal easier later.

---

## 10. Source-order helpers

These help infer `precedes` and sometimes `depends_on`.

```python
def average_source_chunk_index(rule: RuleCard) -> float | None:
    indexes = get_rule_source_chunk_indexes(rule)
    if not indexes:
        return None
    return sum(indexes) / len(indexes)


def group_rules_by_concept_family(rules: list[RuleCard]) -> dict[str, list[RuleCard]]:
    families: dict[str, list[RuleCard]] = defaultdict(list)

    for rule in rules:
        concept = get_rule_concept(rule)
        if concept:
            family_id = normalize_concept_id(concept)
        else:
            family_id = "unclassified"
        families[family_id].append(rule)

    return families
```

---

## 11. `precedes` relations

Use source order conservatively.

```python
def create_precedes_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    relations: list[ConceptRelation] = []
    families = group_rules_by_concept_family(rules)

    for _, family_rules in families.items():
        by_subconcept: dict[str, list[RuleCard]] = defaultdict(list)

        for rule in family_rules:
            subconcept = get_rule_subconcept(rule)
            if not subconcept:
                continue
            by_subconcept[normalize_concept_id(subconcept)].append(rule)

        ordered = []
        for subconcept_id, group in by_subconcept.items():
            avg_idx = [
                idx for idx in [average_source_chunk_index(rule) for rule in group]
                if idx is not None
            ]
            if not avg_idx:
                continue
            ordered.append((subconcept_id, sum(avg_idx) / len(avg_idx)))

        ordered.sort(key=lambda x: (x[1], x[0]))

        for i in range(len(ordered) - 1):
            left_id, left_pos = ordered[i]
            right_id, right_pos = ordered[i + 1]

            if right_pos > left_pos:
                relations.append(
                    ConceptRelation(
                        relation_id=make_relation_id(left_id, "precedes", right_id),
                        source_id=left_id,
                        target_id=right_id,
                        relation_type="precedes",
                        metadata={"reason": "source chunk order within concept family"},
                    )
                )

    return dedupe_relations(relations)
```

### Important

This only compares subconcepts within the same concept family.
That keeps it conservative.

---

## 12. `depends_on` relations

I would make these stricter than `precedes`.

### Helper for dependency hints

```python
def has_dependency_cue(text: str) -> bool:
    text_norm = normalize_text(text).lower()
    return any(cue in text_norm for cue in DEPENDENCY_CUES)
```

### Inference

```python
def create_depends_on_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    relations: list[ConceptRelation] = []

    for rule in rules:
        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)
        if not concept or not subconcept:
            continue

        source_id = normalize_concept_id(subconcept)
        concept_id = normalize_concept_id(concept)

        texts = [rule.rule_text] + (rule.comparisons or []) + (rule.context or [])
        combined = " ".join(normalize_text(t) for t in texts if normalize_text(t))

        if has_dependency_cue(combined):
            # simplest conservative assumption: subconcept depends on parent concept
            relations.append(
                ConceptRelation(
                    relation_id=make_relation_id(source_id, "depends_on", concept_id),
                    source_id=source_id,
                    target_id=concept_id,
                    relation_type="depends_on",
                    metadata={"reason": "dependency cue in rule/comparison/context text"},
                )
            )

    return dedupe_relations(relations)
```

### Later improvement

You could later infer dependencies between sibling subconcepts, but for V1 I would keep it parent-focused unless there is a strong cue.

---

## 13. `contrasts_with` relations

This is important for things like:

* `false_breakout`
* `break_confirmation`

### Helper

```python
def has_contrast_cue(text: str) -> bool:
    text_norm = normalize_text(text).lower()
    return any(cue in text_norm for cue in CONTRAST_CUES)
```

### Exact-name heuristic

I would also explicitly encode a few safe lexical pairs:

```python
CONTRAST_NAME_PAIRS = [
    ("false_breakout", "break_confirmation"),
    ("weak_level", "strong_level"),
]
```

### Inference

```python
def create_contrasts_with_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    relations: list[ConceptRelation] = []
    seen_pairs: set[tuple[str, str]] = set()

    # 1. lexical/name-based contrast
    all_ids = set()
    for rule in rules:
        for value in [get_rule_concept(rule), get_rule_subconcept(rule)]:
            if value:
                all_ids.add(normalize_concept_id(value))

    for left, right in CONTRAST_NAME_PAIRS:
        if left in all_ids and right in all_ids:
            seen_pairs.add((left, right))
            seen_pairs.add((right, left))

    # 2. comparison-text-based contrast
    for rule in rules:
        texts = [rule.rule_text] + (rule.comparisons or [])
        combined = " ".join(normalize_text(t) for t in texts if normalize_text(t))
        if not has_contrast_cue(combined):
            continue

        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)
        if concept and subconcept:
            left = normalize_concept_id(subconcept)
            right = normalize_concept_id(concept)
            if left != right:
                seen_pairs.add((left, right))

    for source_id, target_id in sorted(seen_pairs):
        relations.append(
            ConceptRelation(
                relation_id=make_relation_id(source_id, "contrasts_with", target_id),
                source_id=source_id,
                target_id=target_id,
                relation_type="contrasts_with",
                metadata={"reason": "name pair or comparison cue"},
            )
        )

    return dedupe_relations(relations)
```

### Note

This is still conservative and probably under-generates — which is good for V1.

---

## 14. `supports` relations

This one should be even more conservative.

The safest version:

* if a rule’s subconcept looks like a rating/confirmation/validation concept, it may support its parent concept or related decision concept.

### Helper

```python
def looks_supporting_subconcept(subconcept_id: str) -> bool:
    return any(token in subconcept_id for token in [
        "rating",
        "confirmation",
        "validation",
        "strength",
    ])
```

### Inference

```python
def create_supports_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    relations: list[ConceptRelation] = []

    for rule in rules:
        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)
        if not concept or not subconcept:
            continue

        concept_id = normalize_concept_id(concept)
        subconcept_id = normalize_concept_id(subconcept)

        if looks_supporting_subconcept(subconcept_id) and subconcept_id != concept_id:
            relations.append(
                ConceptRelation(
                    relation_id=make_relation_id(subconcept_id, "supports", concept_id),
                    source_id=subconcept_id,
                    target_id=concept_id,
                    relation_type="supports",
                    metadata={"reason": "support-like subconcept naming"},
                )
            )

    return dedupe_relations(relations)
```

---

## 15. Relation dedupe

```python
def dedupe_relations(relations: list[ConceptRelation]) -> list[ConceptRelation]:
    seen: dict[tuple[str, str, str], ConceptRelation] = {}

    for rel in relations:
        key = (rel.source_id, rel.relation_type, rel.target_id)
        if key not in seen:
            seen[key] = rel
            continue

        existing = seen[key]
        merged_meta = {**existing.metadata}
        if rel.metadata:
            for k, v in rel.metadata.items():
                if k not in merged_meta:
                    merged_meta[k] = v
                elif isinstance(merged_meta[k], list) and isinstance(v, list):
                    merged_meta[k] = sorted(set(merged_meta[k] + v))

        seen[key] = ConceptRelation(
            relation_id=existing.relation_id,
            source_id=existing.source_id,
            target_id=existing.target_id,
            relation_type=existing.relation_type,
            metadata=merged_meta,
        )

    return list(seen.values())
```

---

## 16. Full graph builder

```python
def build_concept_graph(
    rule_cards: RuleCardCollection,
) -> tuple[ConceptGraph, list[dict]]:
    rules = rule_cards.rules
    debug_rows: list[dict] = []

    nodes = create_concept_nodes(rules)

    relations: list[ConceptRelation] = []
    relations.extend(create_parent_child_relations(rules))
    relations.extend(create_sibling_related_relations(rules))
    relations.extend(create_precedes_relations(rules))
    relations.extend(create_depends_on_relations(rules))
    relations.extend(create_contrasts_with_relations(rules))
    relations.extend(create_supports_relations(rules))

    relations = dedupe_relations(relations)

    for rel in relations:
        debug_rows.append(
            {
                "relation_id": rel.relation_id,
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "relation_type": rel.relation_type,
                "metadata": rel.metadata,
            }
        )

    graph = ConceptGraph(
        lesson_id=rule_cards.lesson_id,
        nodes=nodes,
        relations=relations,
    )
    return graph, debug_rows
```

---

## 17. Save helpers

```python
def load_rule_cards(path: Path) -> RuleCardCollection:
    return RuleCardCollection.model_validate_json(path.read_text(encoding="utf-8"))


def save_concept_graph(graph: ConceptGraph, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(graph.model_dump_json(indent=2), encoding="utf-8")


def save_concept_graph_debug(debug_rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    output_path.write_text(json.dumps(debug_rows, indent=2), encoding="utf-8")
```

If Task 9’s `atomic_write_json(...)` exists, use that instead.

---

# Integration into `main.py`

## Exact conceptual integration

After rule cards are written:

```python
if feature_flags.enable_concept_graph:
    if require_artifact(
        paths.rule_cards_path(lesson_name),
        "step12_concept_graph",
        "Generate rule_cards.json first",
    ):
        rule_cards = load_rule_cards(paths.rule_cards_path(lesson_name))
        concept_graph, concept_graph_debug = build_concept_graph(rule_cards)
        save_concept_graph(concept_graph, paths.concept_graph_path(lesson_name))
        # optional:
        # save_concept_graph_debug(concept_graph_debug, paths.output_intermediate_dir / f"{lesson_name}.concept_graph_debug.json")
```

---

# Tests

## `tests/test_concept_graph.py`

### Test 1 — node creation

```python
def test_create_concept_and_subconcept_nodes():
    rules = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            RuleCard(
                rule_id="r1",
                lesson_id="lesson1",
                concept="level",
                subconcept="level_rating",
                rule_text="A level becomes stronger when price reacts to it multiple times.",
            )
        ],
    )

    graph, _ = build_concept_graph(rules)

    node_ids = {node.concept_id for node in graph.nodes}
    assert "level" in node_ids
    assert "level_rating" in node_ids
```

### Test 2 — parent-child relation

```python
def test_parent_child_relation():
    rules = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            RuleCard(
                rule_id="r1",
                lesson_id="lesson1",
                concept="level",
                subconcept="level_rating",
                rule_text="A level becomes stronger when price reacts to it multiple times.",
            )
        ],
    )

    graph, _ = build_concept_graph(rules)

    rels = {(r.source_id, r.relation_type, r.target_id) for r in graph.relations}
    assert ("level", "parent_of", "level_rating") in rels
    assert ("level_rating", "child_of", "level") in rels
```

### Test 3 — sibling related relation

```python
def test_sibling_related_relation():
    rules = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", subconcept="level_recognition", rule_text="Recognize the level."),
            RuleCard(rule_id="r2", lesson_id="lesson1", concept="level", subconcept="level_rating", rule_text="Rate the level."),
        ],
    )

    graph, _ = build_concept_graph(rules)
    rels = {(r.source_id, r.relation_type, r.target_id) for r in graph.relations}

    assert ("level_recognition", "related_to", "level_rating") in rels
    assert ("level_rating", "related_to", "level_recognition") in rels
```

### Test 4 — precedes relation

```python
def test_precedes_relation_from_source_order():
    r1 = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        subconcept="level_recognition",
        rule_text="Recognize the level first.",
        metadata={"source_chunk_indexes": [1]},
    )
    r2 = RuleCard(
        rule_id="r2",
        lesson_id="lesson1",
        concept="level",
        subconcept="level_rating",
        rule_text="Then rate the level.",
        metadata={"source_chunk_indexes": [5]},
    )

    graph, _ = build_concept_graph(RuleCardCollection(lesson_id="lesson1", rules=[r1, r2]))
    rels = {(r.source_id, r.relation_type, r.target_id) for r in graph.relations}

    assert ("level_recognition", "precedes", "level_rating") in rels
```

### Test 5 — contrasts_with relation

```python
def test_contrasts_with_relation():
    rules = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            RuleCard(
                rule_id="r1",
                lesson_id="lesson1",
                concept="break_confirmation",
                subconcept="break_confirmation",
                rule_text="A confirmed breakout holds beyond the level.",
                comparisons=["In contrast to a false breakout, price holds above the level."],
            ),
            RuleCard(
                rule_id="r2",
                lesson_id="lesson1",
                concept="false_breakout",
                subconcept="false_breakout",
                rule_text="A false breakout fails to hold beyond the level.",
            ),
        ],
    )

    graph, _ = build_concept_graph(rules)
    rels = {(r.source_id, r.relation_type, r.target_id) for r in graph.relations}

    assert ("false_breakout", "contrasts_with", "break_confirmation") in rels or \
           ("break_confirmation", "contrasts_with", "false_breakout") in rels
```

### Test 6 — dedupe

```python
def test_relation_dedupe():
    rules = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            RuleCard(rule_id="r1", lesson_id="lesson1", concept="level", subconcept="level_rating", rule_text="A"),
            RuleCard(rule_id="r2", lesson_id="lesson1", concept="level", subconcept="level_rating", rule_text="B"),
        ],
    )

    graph, _ = build_concept_graph(rules)
    parent_edges = [r for r in graph.relations if r.relation_type == "parent_of"]
    assert len(parent_edges) == 1
```

---

# One more thing I would explicitly add

I would add this sentence to Task 12:

```text
Graph generation must be conservative and deterministic: source-order alone is not enough to infer a relationship unless the connected nodes also belong to the same concept family or there is an explicit wording/comparison cue.
```

That protects the graph from becoming noisy.

---

# My recommendation

Yes — for Task 12, I would definitely include this level of detail.

The main risk in Task 12 is not building nodes — that part is easy.
The real risk is generating too many weak edges.

These implementations keep the graph:

* useful
* compact
* stable
* explainable


