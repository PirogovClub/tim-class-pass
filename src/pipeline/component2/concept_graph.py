"""Task 12: Lightweight lesson-level concept graph from rule cards."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from pipeline.io_utils import atomic_write_json, atomic_write_text
from pipeline.schemas import (
    ConceptGraph,
    ConceptGraphStats,
    ConceptNode,
    ConceptRelation,
    RuleCard,
    RuleCardCollection,
)
from pipeline.component2.canonical_lexicon import lookup_canonical

# ----- Cue words for relation inference -----

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

CONTRAST_NAME_PAIRS = [
    ("false_breakout", "break_confirmation"),
    ("weak_level", "strong_level"),
]

MAX_SECONDARY_NODE_LEN = 120
CO_OCCURRENCE_THRESHOLD = 2


# ----- Normalization -----


def normalize_text(text: str | None) -> str:
    """Collapse whitespace and strip; return empty string for None or blank."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_concept_id(name: str) -> str:
    """Turn a concept/subconcept name into a stable slug (lowercase, alphanumeric + underscore)."""
    text = normalize_text(name).lower()
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9а-яё]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def _derive_canonical_label(name: str) -> str | None:
    """Return a canonical English-like label for a concept name via lexicon lookup.

    Returns None if no canonical label is found (i.e. the name is already English
    or not in the lexicon).
    """
    return lookup_canonical(name.strip())


# ----- Rule-level accessors -----


def get_rule_concept(rule: RuleCard) -> str | None:
    """Return normalized concept text, or None if blank."""
    concept = normalize_text(rule.concept)
    return concept or None


def get_rule_subconcept(rule: RuleCard) -> str | None:
    """Return normalized subconcept text, or None if blank."""
    subconcept = normalize_text(rule.subconcept) if rule.subconcept else ""
    return subconcept or None


def get_rule_source_chunk_indexes(rule: RuleCard) -> list[int]:
    """Return sorted unique chunk indexes from rule metadata."""
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
    """Return normalized source section names from rule metadata."""
    metadata = rule.metadata or {}
    values = metadata.get("source_sections", []) or []
    return [normalize_text(v) for v in values if normalize_text(v)]


def get_rule_source_subsections(rule: RuleCard) -> list[str]:
    """Return normalized source subsection names from rule metadata."""
    metadata = rule.metadata or {}
    values = metadata.get("source_subsections", []) or []
    return [normalize_text(v) for v in values if normalize_text(v)]


def _is_short_reusable_text(text: str) -> bool:
    """True if text is short, non-empty, and likely reusable (not a long prose paragraph)."""
    normalized = normalize_text(text)
    if not normalized or len(normalized) > MAX_SECONDARY_NODE_LEN:
        return False
    if normalized.lower() in ("none", "n/a", "unknown", "not applicable"):
        return False
    return True


def _owning_node_id(rule: RuleCard) -> str:
    """Return the most specific owning node id for secondary nodes: subconcept if present, else concept."""
    subconcept = get_rule_subconcept(rule)
    if subconcept:
        return normalize_concept_id(subconcept)
    return normalize_concept_id(get_rule_concept(rule) or "unknown")


# ----- Node builders -----


def collect_concept_names(rules: list[RuleCard]) -> tuple[dict[str, str], dict[str, str]]:
    """Collect unique (concept_id -> name) and (subconcept_id -> name) from rules."""
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


def _collect_source_rule_ids_for_concept(concept_id: str, rules: list[RuleCard]) -> list[str]:
    """Return sorted rule_ids that reference the given concept_id."""
    result: set[str] = set()
    for rule in rules:
        c = get_rule_concept(rule)
        sc = get_rule_subconcept(rule)
        if c and normalize_concept_id(c) == concept_id:
            result.add(rule.rule_id)
        if sc and normalize_concept_id(sc) == concept_id:
            result.add(rule.rule_id)
    return sorted(result)


def infer_parent_concept_id_for_subconcept(
    subconcept_name: str, rules: list[RuleCard]
) -> str | None:
    """Return the concept_id most often paired with this subconcept in rules."""
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


def dedupe_nodes(nodes: list[ConceptNode]) -> list[ConceptNode]:
    """Merge nodes by concept_id; merge aliases, source_rule_ids, and metadata for duplicates."""
    seen: dict[str, ConceptNode] = {}
    for node in nodes:
        if node.concept_id not in seen:
            seen[node.concept_id] = node
            continue

        existing = seen[node.concept_id]
        merged_aliases = sorted(set(existing.aliases + node.aliases))
        merged_rule_ids = sorted(set(existing.source_rule_ids + node.source_rule_ids))
        merged_metadata = {**existing.metadata, **node.metadata}

        seen[node.concept_id] = ConceptNode(
            concept_id=existing.concept_id,
            name=existing.name or node.name,
            type=existing.type or node.type,
            parent_id=existing.parent_id or node.parent_id,
            aliases=merged_aliases,
            source_rule_ids=merged_rule_ids,
            canonical_label=existing.canonical_label or node.canonical_label,
            metadata=merged_metadata,
        )
    return list(seen.values())


def create_concept_nodes(rules: list[RuleCard]) -> list[ConceptNode]:
    """Build concept and subconcept nodes from rules; infer parent for each subconcept."""
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
                source_rule_ids=_collect_source_rule_ids_for_concept(concept_id, rules),
                canonical_label=_derive_canonical_label(concept_name),
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
                source_rule_ids=_collect_source_rule_ids_for_concept(subconcept_id, rules),
                canonical_label=_derive_canonical_label(subconcept_name),
                metadata={},
            )
        )

    return dedupe_nodes(nodes)


def create_secondary_nodes(rules: list[RuleCard]) -> list[ConceptNode]:
    """Create condition, invalidation, and exception nodes from rule cards.

    Only creates nodes for short, non-empty, reusable text (not long prose).
    """
    nodes: list[ConceptNode] = []
    seen: dict[str, ConceptNode] = {}

    for rule in rules:
        for cond_text in rule.conditions:
            if not _is_short_reusable_text(cond_text):
                continue
            node_id = f"condition:{normalize_concept_id(cond_text)}"
            if node_id not in seen:
                seen[node_id] = ConceptNode(
                    concept_id=node_id,
                    name=normalize_text(cond_text),
                    type="condition",
                    parent_id=_owning_node_id(rule),
                    aliases=[],
                    source_rule_ids=[rule.rule_id],
                    canonical_label=_derive_canonical_label(cond_text),
                    metadata={},
                )
            else:
                existing = seen[node_id]
                seen[node_id] = ConceptNode(
                    concept_id=existing.concept_id,
                    name=existing.name,
                    type=existing.type,
                    parent_id=existing.parent_id,
                    aliases=existing.aliases,
                    source_rule_ids=sorted(set(existing.source_rule_ids + [rule.rule_id])),
                    canonical_label=existing.canonical_label,
                    metadata=existing.metadata,
                )

        for inv_text in rule.invalidation:
            if not _is_short_reusable_text(inv_text):
                continue
            node_id = f"invalidation:{normalize_concept_id(inv_text)}"
            if node_id not in seen:
                seen[node_id] = ConceptNode(
                    concept_id=node_id,
                    name=normalize_text(inv_text),
                    type="invalidation",
                    parent_id=_owning_node_id(rule),
                    aliases=[],
                    source_rule_ids=[rule.rule_id],
                    canonical_label=_derive_canonical_label(inv_text),
                    metadata={},
                )
            else:
                existing = seen[node_id]
                seen[node_id] = ConceptNode(
                    concept_id=existing.concept_id,
                    name=existing.name,
                    type=existing.type,
                    parent_id=existing.parent_id,
                    aliases=existing.aliases,
                    source_rule_ids=sorted(set(existing.source_rule_ids + [rule.rule_id])),
                    canonical_label=existing.canonical_label,
                    metadata=existing.metadata,
                )

        for exc_text in rule.exceptions:
            if not _is_short_reusable_text(exc_text):
                continue
            node_id = f"exception:{normalize_concept_id(exc_text)}"
            if node_id not in seen:
                seen[node_id] = ConceptNode(
                    concept_id=node_id,
                    name=normalize_text(exc_text),
                    type="exception",
                    parent_id=_owning_node_id(rule),
                    aliases=[],
                    source_rule_ids=[rule.rule_id],
                    canonical_label=_derive_canonical_label(exc_text),
                    metadata={},
                )
            else:
                existing = seen[node_id]
                seen[node_id] = ConceptNode(
                    concept_id=existing.concept_id,
                    name=existing.name,
                    type=existing.type,
                    parent_id=existing.parent_id,
                    aliases=existing.aliases,
                    source_rule_ids=sorted(set(existing.source_rule_ids + [rule.rule_id])),
                    canonical_label=existing.canonical_label,
                    metadata=existing.metadata,
                )

    nodes.extend(seen.values())
    return nodes


# ----- Relation helpers -----


def make_relation_id(source_id: str, relation_type: str, target_id: str) -> str:
    """Build a unique relation id from source, type, and target."""
    return f"rel_{source_id}_{relation_type}_{target_id}"


def create_parent_child_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Add has_subconcept relation for each rule that has both concept and subconcept.

    Task 17: single direction only (no mirrored parent_of/child_of).
    """
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
                relation_id=make_relation_id(concept_id, "has_subconcept", subconcept_id),
                source_id=concept_id,
                target_id=subconcept_id,
                relation_type="has_subconcept",
                weight=1,
                source_rule_ids=[rule.rule_id],
                metadata={"reason": "concept-subconcept pair"},
            )
        )

    return dedupe_relations(relations)


def create_sibling_related_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Add related_to (both directions) between subconcepts that share the same concept."""
    concept_to_subconcepts: dict[str, set[str]] = defaultdict(set)

    for rule in rules:
        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)
        if not concept or not subconcept:
            continue
        concept_to_subconcepts[normalize_concept_id(concept)].add(
            normalize_concept_id(subconcept)
        )

    relations: list[ConceptRelation] = []

    for concept_id, subconcept_ids in concept_to_subconcepts.items():
        ordered = sorted(subconcept_ids)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                relations.append(
                    ConceptRelation(
                        relation_id=make_relation_id(left, "related_to", right),
                        source_id=left,
                        target_id=right,
                        relation_type="related_to",
                        weight=1,
                        source_rule_ids=[],
                        metadata={"reason": f"shared parent concept {concept_id}"},
                    )
                )
                relations.append(
                    ConceptRelation(
                        relation_id=make_relation_id(right, "related_to", left),
                        source_id=right,
                        target_id=left,
                        relation_type="related_to",
                        weight=1,
                        source_rule_ids=[],
                        metadata={"reason": f"shared parent concept {concept_id}"},
                    )
                )

    return dedupe_relations(relations)


def create_secondary_edges(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Create has_condition, has_invalidation, has_exception edges from rule cards."""
    relations: list[ConceptRelation] = []

    for rule in rules:
        owner_id = _owning_node_id(rule)

        for cond_text in rule.conditions:
            if not _is_short_reusable_text(cond_text):
                continue
            target_id = f"condition:{normalize_concept_id(cond_text)}"
            relations.append(
                ConceptRelation(
                    relation_id=make_relation_id(owner_id, "has_condition", target_id),
                    source_id=owner_id,
                    target_id=target_id,
                    relation_type="has_condition",
                    weight=1,
                    source_rule_ids=[rule.rule_id],
                    metadata={"reason": "rule condition attachment"},
                )
            )

        for inv_text in rule.invalidation:
            if not _is_short_reusable_text(inv_text):
                continue
            target_id = f"invalidation:{normalize_concept_id(inv_text)}"
            relations.append(
                ConceptRelation(
                    relation_id=make_relation_id(owner_id, "has_invalidation", target_id),
                    source_id=owner_id,
                    target_id=target_id,
                    relation_type="has_invalidation",
                    weight=1,
                    source_rule_ids=[rule.rule_id],
                    metadata={"reason": "rule invalidation attachment"},
                )
            )

        for exc_text in rule.exceptions:
            if not _is_short_reusable_text(exc_text):
                continue
            target_id = f"exception:{normalize_concept_id(exc_text)}"
            relations.append(
                ConceptRelation(
                    relation_id=make_relation_id(owner_id, "has_exception", target_id),
                    source_id=owner_id,
                    target_id=target_id,
                    relation_type="has_exception",
                    weight=1,
                    source_rule_ids=[rule.rule_id],
                    metadata={"reason": "rule exception attachment"},
                )
            )

    return dedupe_relations(relations)


def create_co_occurs_with_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Add co_occurs_with edges between concept/subconcept pairs that appear together in >= CO_OCCURRENCE_THRESHOLD rules."""
    pair_counts: dict[tuple[str, str], list[str]] = defaultdict(list)

    for rule in rules:
        node_ids: set[str] = set()
        concept = get_rule_concept(rule)
        subconcept = get_rule_subconcept(rule)
        if concept:
            node_ids.add(normalize_concept_id(concept))
        if subconcept:
            node_ids.add(normalize_concept_id(subconcept))

        ordered = sorted(node_ids)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                pair_counts[(left, right)].append(rule.rule_id)

    relations: list[ConceptRelation] = []
    for (left, right), rule_ids in sorted(pair_counts.items()):
        if len(rule_ids) < CO_OCCURRENCE_THRESHOLD:
            continue
        relations.append(
            ConceptRelation(
                relation_id=make_relation_id(left, "co_occurs_with", right),
                source_id=left,
                target_id=right,
                relation_type="co_occurs_with",
                weight=len(rule_ids),
                source_rule_ids=sorted(set(rule_ids)),
                metadata={"reason": "co-occurrence in rule cards"},
            )
        )

    return relations


def average_source_chunk_index(rule: RuleCard) -> float | None:
    """Return mean of rule's source chunk indexes, or None if none."""
    indexes = get_rule_source_chunk_indexes(rule)
    if not indexes:
        return None
    return sum(indexes) / len(indexes)


def group_rules_by_concept_family(rules: list[RuleCard]) -> dict[str, list[RuleCard]]:
    """Group rules by normalized concept id (or 'unclassified' if no concept)."""
    families: dict[str, list[RuleCard]] = defaultdict(list)

    for rule in rules:
        concept = get_rule_concept(rule)
        if concept:
            family_id = normalize_concept_id(concept)
        else:
            family_id = "unclassified"
        families[family_id].append(rule)

    return families


def create_precedes_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Add precedes relations from source chunk order within each concept family."""
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
                idx
                for idx in [average_source_chunk_index(rule) for rule in group]
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
                        weight=1,
                        source_rule_ids=[],
                        metadata={"reason": "source chunk order within concept family"},
                    )
                )

    return dedupe_relations(relations)


def has_dependency_cue(text: str) -> bool:
    """True if text contains any DEPENDENCY_CUES phrase."""
    text_norm = normalize_text(text).lower()
    return any(cue in text_norm for cue in DEPENDENCY_CUES)


def create_depends_on_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Add depends_on (subconcept -> concept) when rule text has dependency cues."""
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
            relations.append(
                ConceptRelation(
                    relation_id=make_relation_id(source_id, "depends_on", concept_id),
                    source_id=source_id,
                    target_id=concept_id,
                    relation_type="depends_on",
                    weight=1,
                    source_rule_ids=[rule.rule_id],
                    metadata={"reason": "dependency cue in rule/comparison/context text"},
                )
            )

    return dedupe_relations(relations)


def has_contrast_cue(text: str) -> bool:
    """True if text contains any CONTRAST_CUES phrase."""
    text_norm = normalize_text(text).lower()
    return any(cue in text_norm for cue in CONTRAST_CUES)


def create_contrasts_with_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Add contrasts_with from CONTRAST_NAME_PAIRS and from contrast cues in rule text."""
    relations: list[ConceptRelation] = []
    seen_pairs: set[tuple[str, str]] = set()

    all_ids: set[str] = set()
    for rule in rules:
        for value in [get_rule_concept(rule), get_rule_subconcept(rule)]:
            if value:
                all_ids.add(normalize_concept_id(value))

    for left, right in CONTRAST_NAME_PAIRS:
        if left in all_ids and right in all_ids:
            seen_pairs.add((left, right))
            seen_pairs.add((right, left))

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
                seen_pairs.add((right, left))

    for source_id, target_id in sorted(seen_pairs):
        relations.append(
            ConceptRelation(
                relation_id=make_relation_id(source_id, "contrasts_with", target_id),
                source_id=source_id,
                target_id=target_id,
                relation_type="contrasts_with",
                weight=1,
                source_rule_ids=[],
                metadata={"reason": "name pair or comparison cue"},
            )
        )

    return dedupe_relations(relations)


def looks_supporting_subconcept(subconcept_id: str) -> bool:
    """True if subconcept_id contains rating/confirmation/validation/strength."""
    return any(
        token in subconcept_id
        for token in [
            "rating",
            "confirmation",
            "validation",
            "strength",
        ]
    )


def create_supports_relations(rules: list[RuleCard]) -> list[ConceptRelation]:
    """Add supports (subconcept -> concept) when subconcept name looks support-like."""
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
                    weight=1,
                    source_rule_ids=[rule.rule_id],
                    metadata={"reason": "support-like subconcept naming"},
                )
            )

    return dedupe_relations(relations)


def dedupe_relations(relations: list[ConceptRelation]) -> list[ConceptRelation]:
    """Merge relations by (source_id, relation_type, target_id); combine weight and source_rule_ids."""
    seen: dict[tuple[str, str, str], ConceptRelation] = {}

    for rel in relations:
        key = (rel.source_id, rel.relation_type, rel.target_id)
        if key not in seen:
            seen[key] = rel
            continue

        existing = seen[key]
        merged_rule_ids = sorted(set(existing.source_rule_ids + rel.source_rule_ids))
        merged_weight = existing.weight + rel.weight
        merged_meta = {**existing.metadata}
        if rel.metadata:
            for k, v in rel.metadata.items():
                if k not in merged_meta:
                    merged_meta[k] = v
                elif isinstance(merged_meta.get(k), list) and isinstance(v, list):
                    merged_meta[k] = sorted(set(merged_meta[k] + v))

        seen[key] = ConceptRelation(
            relation_id=existing.relation_id,
            source_id=existing.source_id,
            target_id=existing.target_id,
            relation_type=existing.relation_type,
            weight=merged_weight,
            source_rule_ids=merged_rule_ids,
            metadata=merged_meta,
        )

    return list(seen.values())


ALLOWED_RELATION_TYPES = {
    "has_subconcept",
    "has_condition",
    "has_invalidation",
    "has_exception",
    "co_occurs_with",
}


def _filter_provenance_backed(relations: list[ConceptRelation]) -> list[ConceptRelation]:
    """Keep only relations with non-empty source_rule_ids and allowed types (Task 17)."""
    return [
        r for r in relations
        if r.source_rule_ids and r.relation_type in ALLOWED_RELATION_TYPES
    ]


# ----- Public API -----


def build_concept_graph(
    rule_cards: RuleCardCollection,
) -> tuple[ConceptGraph, list[dict]]:
    """Build a lesson-level concept graph and debug rows from rule cards."""
    rules = rule_cards.rules
    debug_rows: list[dict] = []

    concept_nodes = create_concept_nodes(rules)
    secondary_nodes = create_secondary_nodes(rules)
    all_nodes = dedupe_nodes(concept_nodes + secondary_nodes)

    relations: list[ConceptRelation] = []
    relations.extend(create_parent_child_relations(rules))
    relations.extend(create_sibling_related_relations(rules))
    relations.extend(create_precedes_relations(rules))
    relations.extend(create_depends_on_relations(rules))
    relations.extend(create_contrasts_with_relations(rules))
    relations.extend(create_supports_relations(rules))
    relations.extend(create_secondary_edges(rules))
    relations.extend(create_co_occurs_with_relations(rules))

    relations = dedupe_relations(relations)
    relations = _filter_provenance_backed(relations)

    for rel in relations:
        debug_rows.append(
            {
                "relation_id": rel.relation_id,
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "relation_type": rel.relation_type,
                "weight": rel.weight,
                "source_rule_ids": rel.source_rule_ids,
                "metadata": rel.metadata,
            }
        )

    graph = ConceptGraph(
        lesson_id=rule_cards.lesson_id,
        graph_version="1.0",
        nodes=all_nodes,
        relations=relations,
        stats=ConceptGraphStats(
            node_count=len(all_nodes),
            edge_count=len(relations),
        ),
    )
    return graph, debug_rows


def load_rule_cards(path: Path) -> RuleCardCollection:
    """Load and validate RuleCardCollection from JSON file."""
    return RuleCardCollection.model_validate_json(path.read_text(encoding="utf-8"))


def save_concept_graph(graph: ConceptGraph, output_path: Path) -> None:
    """Write ConceptGraph to JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        output_path, graph.model_dump_json(indent=2), encoding="utf-8"
    )


def save_concept_graph_debug(debug_rows: list[dict], output_path: Path) -> None:
    """Write concept graph relation debug rows to JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_path, debug_rows)
