"""Task 13: ML-readiness layer — candidate features, example buckets, labeling guidance, manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.io_utils import atomic_write_json
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    RuleCard,
    RuleCardCollection,
    validate_rule_card_for_export,
)


# ----- Feature vocabulary (concept/subconcept → candidate feature names) -----

FEATURE_HINTS_BY_CONCEPT: dict[str, list[str]] = {
    "level": [
        "price_zone_width",
        "touch_count",
        "extrema_cluster_count",
    ],
    "level_recognition": [
        "touch_count",
        "extrema_cluster_count",
        "reaction_spacing",
    ],
    "level_rating": [
        "reaction_count",
        "reaction_magnitude",
        "price_zone_width",
        "higher_timeframe_alignment",
    ],
    "break_confirmation": [
        "time_beyond_level",
        "close_beyond_level_count",
        "distance_beyond_level",
        "retest_success_flag",
    ],
    "false_breakout": [
        "max_distance_beyond_level",
        "time_beyond_level",
        "reversal_speed",
        "return_through_level_flag",
        "failed_acceptance_flag",
    ],
    "trend_break_level": [
        "trendline_touch_count",
        "post_break_hold_time",
        "retest_behavior",
    ],
}

FEATURE_CUES: dict[str, list[str]] = {
    "reaction": ["reaction_count", "reaction_magnitude"],
    "multiple reactions": ["reaction_count"],
    "touch": ["touch_count"],
    "zone": ["price_zone_width"],
    "cluster": ["extrema_cluster_count"],
    "hold above": ["time_beyond_level", "close_beyond_level_count"],
    "hold below": ["time_beyond_level", "close_beyond_level_count"],
    "retest": ["retest_success_flag", "retest_behavior"],
    "fails to hold": ["failed_acceptance_flag", "reversal_speed"],
    "returns below": ["return_through_level_flag"],
    "returns through": ["return_through_level_flag"],
    "distance beyond": ["distance_beyond_level", "max_distance_beyond_level"],
}


# ----- Text helpers -----


def normalize_text(text: str | None) -> str:
    """Collapse whitespace and strip; return empty string for None or blank."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def dedupe_preserve_order(items: list[str]) -> list[str]:
    """Return unique non-blank strings in original order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = normalize_text(item)
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_feature_name(name: str) -> str:
    """Normalize to lowercase snake_case identifier for feature names."""
    text = normalize_text(name).lower()
    text = text.replace("/", "_")
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def get_rule_family_key(rule: RuleCard) -> str | None:
    """Prefer subconcept, then concept, for ML feature lookup."""
    if normalize_text(rule.subconcept):
        return normalize_feature_name(rule.subconcept or "")
    if normalize_text(rule.concept):
        return normalize_feature_name(rule.concept)
    return None


def pick_top_items(items: list[str], limit: int = 2) -> list[str]:
    """Return up to limit deduplicated non-blank items for use in guidance templates."""
    cleaned = [normalize_text(x) for x in items if normalize_text(x)]
    cleaned = dedupe_preserve_order(cleaned)
    return cleaned[:limit]


def sentence_join(items: list[str]) -> str:
    """Join items into a single sentence with commas and final 'and'."""
    items = [normalize_text(x) for x in items if normalize_text(x)]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


# ----- Candidate feature inference -----


def infer_candidate_features(rule: RuleCard) -> list[str]:
    """Derive candidate algorithmic feature names from rule concept, subconcept, and text."""
    if validate_rule_card_for_export(rule):
        return []
    features: list[str] = []

    family_key = get_rule_family_key(rule)
    concept_key = (
        normalize_feature_name(rule.concept) if normalize_text(rule.concept) else None
    )
    subconcept_key = (
        normalize_feature_name(rule.subconcept)
        if normalize_text(rule.subconcept)
        else None
    )

    for key in [subconcept_key, concept_key, family_key]:
        if key and key in FEATURE_HINTS_BY_CONCEPT:
            features.extend(FEATURE_HINTS_BY_CONCEPT[key])

    all_text_parts = [
        rule.rule_text,
        *(rule.conditions or []),
        *(rule.invalidation or []),
        *(rule.exceptions or []),
        *(rule.comparisons or []),
        *(rule.algorithm_notes or []),
        rule.visual_summary or "",
    ]
    combined = " ".join(
        normalize_text(x).lower() for x in all_text_parts if normalize_text(x)
    )

    for cue, hinted_features in FEATURE_CUES.items():
        if cue in combined:
            features.extend(hinted_features)

    features = [normalize_feature_name(f) for f in features]
    return dedupe_preserve_order(features)


# ----- Evidence lookup -----


def build_evidence_lookup(evidence_index: EvidenceIndex) -> dict[str, EvidenceRef]:
    """Build evidence_id -> EvidenceRef from index (uses evidence_refs)."""
    return {
        evidence.evidence_id: evidence
        for evidence in evidence_index.evidence_refs
    }


def get_linked_evidence_for_rule(
    rule: RuleCard,
    evidence_lookup: dict[str, EvidenceRef],
) -> list[EvidenceRef]:
    """Resolve rule.evidence_refs to list of EvidenceRef."""
    evidence_refs = rule.evidence_refs or []
    return [evidence_lookup[eid] for eid in evidence_refs if eid in evidence_lookup]


# ----- ML eligibility gate (06-phase1: generic visuals and counterexample require explicit negative) -----

GENERIC_EVIDENCE_MARKERS = {
    "intro",
    "introduction slide",
    "intro slide",
    "title",
    "logo",
    "instructor",
    "speaker",
    "overlay",
    "hand drawing",
    "diagram",
    "sketch",
    "concept explanation",
    "abstract diagram",
}


def _norm_text(text: str | None) -> str:
    """Strip and lower for marker checks; avoid clash with normalize_text in this module."""
    return (text or "").strip().lower()


def _contains_any(text: str, phrases: set[str]) -> bool:
    return any(p in text for p in phrases)


def is_generic_evidence(ref: EvidenceRef) -> bool:
    summary = _norm_text(getattr(ref, "compact_visual_summary", ""))
    return _contains_any(summary, GENERIC_EVIDENCE_MARKERS)


def has_explicit_negative_evidence(ref: EvidenceRef) -> bool:
    summary = _norm_text(getattr(ref, "compact_visual_summary", ""))
    return any(
        phrase in summary
        for phrase in (
            "failed breakout",
            "false breakout",
            "did not hold",
            "invalid",
            "rejected",
            "rejection",
            "trap",
            "mistake",
            "pierced and returned",
            "broke and reversed",
        )
    )


def is_evidence_ml_eligible(ref: EvidenceRef, rule: RuleCard) -> bool:
    """True iff this evidence ref should be used for ML (06-phase1: no generic visuals; counterexample requires explicit negative)."""
    if not (getattr(ref, "linked_rule_ids", []) or []):
        return False
    if not (getattr(ref, "source_event_ids", []) or []):
        return False
    if getattr(rule, "rule_id", None) not in (getattr(ref, "linked_rule_ids", []) or []):
        return False

    role = getattr(ref, "example_role", None)
    if role not in {"positive_example", "counterexample"}:
        return False

    if is_generic_evidence(ref):
        return False

    if role == "counterexample" and not has_explicit_negative_evidence(ref):
        return False

    return True


def should_emit_labeling_task(ref: EvidenceRef, rule: RuleCard) -> bool:
    """True iff we should emit a labeling task for this ref (06-phase1: counterexample requires explicit negative)."""
    if not is_evidence_ml_eligible(ref, rule):
        return False

    if ref.example_role == "counterexample":
        return has_explicit_negative_evidence(ref)

    if ref.example_role == "positive_example":
        return True

    return False


# ----- Example-role distribution (conservative: illustration not in positive) -----


def distribute_example_refs_for_ml(
    rule: RuleCard,
    evidence_refs: list[EvidenceRef],
) -> dict[str, list[str]]:
    """Map evidence roles into ML buckets (06-phase1). Only positive_example and counterexample; illustration/ambiguous not in buckets."""
    positive: list[str] = []
    negative: list[str] = []
    ambiguous: list[str] = []

    for evidence in evidence_refs:
        if not is_evidence_ml_eligible(evidence, rule):
            continue

        if evidence.example_role == "positive_example":
            positive.append(evidence.evidence_id)
        elif evidence.example_role == "counterexample":
            negative.append(evidence.evidence_id)

    return {
        "positive_example_refs": dedupe_preserve_order(positive),
        "negative_example_refs": dedupe_preserve_order(negative),
        "ambiguous_example_refs": dedupe_preserve_order(ambiguous),
    }


# ----- Labeling guidance -----


def build_labeling_guidance(rule: RuleCard) -> str | None:
    """Generate compact deterministic labeling instruction from conditions + invalidation + rule_text."""
    errors = validate_rule_card_for_export(rule)
    if errors:
        return None
    rule_text = normalize_text(rule.rule_text)
    conditions = pick_top_items(rule.conditions or [], limit=2)
    invalidation = pick_top_items(rule.invalidation or [], limit=1)

    if conditions and invalidation:
        return (
            f"Label positive only when {sentence_join(conditions)}. "
            f"Do not label positive when {sentence_join(invalidation)}."
        )

    if conditions:
        return f"Label positive only when {sentence_join(conditions)}."

    if invalidation and rule_text:
        return (
            f"Label positive only when the setup clearly matches this rule: {rule_text}. "
            f"Do not label positive when {sentence_join(invalidation)}."
        )

    if rule_text:
        return (
            f"Label positive only when the setup clearly matches this rule: {rule_text}"
        )

    return None


# ----- Rule enrichment -----


def enrich_rule_card_for_ml(
    rule: RuleCard,
    evidence_refs: list[EvidenceRef],
) -> RuleCard:
    """Enrich a single rule with candidate_features, example buckets, and labeling_guidance. Preserves provenance."""
    errors = validate_rule_card_for_export(rule)
    if errors:
        return rule.model_copy(update={
            "candidate_features": [],
            "positive_example_refs": [],
            "negative_example_refs": [],
            "ambiguous_example_refs": [],
            "labeling_guidance": None,
        })

    feature_list = infer_candidate_features(rule)
    example_buckets = distribute_example_refs_for_ml(rule, evidence_refs)
    labeling_guidance = build_labeling_guidance(rule)

    return rule.model_copy(update={
        "candidate_features": feature_list,
        "positive_example_refs": example_buckets["positive_example_refs"],
        "negative_example_refs": example_buckets["negative_example_refs"],
        "ambiguous_example_refs": example_buckets["ambiguous_example_refs"],
        "labeling_guidance": labeling_guidance,
    })


def enrich_rule_card_collection_for_ml(
    rules: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> RuleCardCollection:
    """Enrich all rules in the collection for ML; return new collection."""
    evidence_lookup = build_evidence_lookup(evidence_index)
    enriched_rules: list[RuleCard] = []

    for rule in rules.rules:
        linked_evidence = get_linked_evidence_for_rule(rule, evidence_lookup)
        enriched_rules.append(enrich_rule_card_for_ml(rule, linked_evidence))

    return RuleCardCollection(
        schema_version=rules.schema_version,
        lesson_id=rules.lesson_id,
        rules=enriched_rules,
    )


# ----- ML manifest -----


def build_ml_manifest(
    lesson_id: str,
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build lesson-level ML manifest (rules + examples) and optional debug rows."""
    evidence_lookup = build_evidence_lookup(evidence_index)

    rules_payload: list[dict[str, Any]] = []
    examples_payload: list[dict[str, Any]] = []
    debug_rows: list[dict[str, Any]] = []

    used_evidence_ids: set[str] = set()

    for rule in rule_cards.rules:
        if validate_rule_card_for_export(rule):
            debug_rows.append({
                "rule_id": rule.rule_id,
                "skipped_from_manifest": True,
                "reason": validate_rule_card_for_export(rule),
            })
            continue
        linked_evidence = get_linked_evidence_for_rule(rule, evidence_lookup)
        used_evidence_ids.update(e.evidence_id for e in linked_evidence)

        rules_payload.append({
            "rule_id": rule.rule_id,
            "concept": rule.concept,
            "subconcept": rule.subconcept,
            "confidence": rule.confidence,
            "confidence_score": rule.confidence_score,
            "candidate_features": rule.candidate_features or [],
            "labeling_guidance": rule.labeling_guidance,
            "positive_example_refs": rule.positive_example_refs or [],
            "negative_example_refs": rule.negative_example_refs or [],
            "ambiguous_example_refs": rule.ambiguous_example_refs or [],
            "source_event_ids": rule.source_event_ids or [],
        })

        debug_rows.append({
            "rule_id": rule.rule_id,
            "linked_evidence_count": len(linked_evidence),
            "positive_count": len(rule.positive_example_refs or []),
            "negative_count": len(rule.negative_example_refs or []),
            "ambiguous_count": len(rule.ambiguous_example_refs or []),
        })

    for evidence_id in sorted(used_evidence_ids):
        evidence = evidence_lookup[evidence_id]
        examples_payload.append({
            "evidence_id": evidence.evidence_id,
            "example_role": evidence.example_role,
            "frame_ids": evidence.frame_ids or [],
            "screenshot_paths": evidence.screenshot_paths or [],
            "timestamp_start": evidence.timestamp_start,
            "timestamp_end": evidence.timestamp_end,
            "source_event_ids": evidence.source_event_ids or [],
        })

    manifest: dict[str, Any] = {
        "lesson_id": lesson_id,
        "rules": rules_payload,
        "examples": examples_payload,
    }
    return manifest, debug_rows


def build_labeling_manifest(
    lesson_id: str,
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> dict[str, Any]:
    """Build manifest of labeling tasks (one per rule+evidence in ML buckets)."""
    evidence_lookup = build_evidence_lookup(evidence_index)

    tasks: list[dict[str, Any]] = []

    for rule in rule_cards.rules:
        if validate_rule_card_for_export(rule):
            continue
        for evidence_id in (
            (rule.positive_example_refs or [])
            + (rule.negative_example_refs or [])
            + (rule.ambiguous_example_refs or [])
        ):
            if evidence_id not in evidence_lookup:
                continue
            evidence = evidence_lookup[evidence_id]
            if not should_emit_labeling_task(evidence, rule):
                continue
            tasks.append({
                "rule_id": rule.rule_id,
                "concept": rule.concept,
                "subconcept": rule.subconcept,
                "expected_role": evidence.example_role,
                "labeling_guidance": rule.labeling_guidance,
                "evidence_id": evidence.evidence_id,
                "frame_ids": evidence.frame_ids or [],
                "screenshot_paths": evidence.screenshot_paths or [],
            })

    return {
        "lesson_id": lesson_id,
        "tasks": tasks,
    }


def compute_ml_readiness_coverage(
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> dict[str, int]:
    """Report how many rules/evidence have ML-ready fields (for QA)."""
    rules = rule_cards.rules
    evidence_list = evidence_index.evidence_refs

    return {
        "rules_total": len(rules),
        "rules_with_candidate_features": sum(
            1 for r in rules if (r.candidate_features or [])
        ),
        "rules_with_labeling_guidance": sum(
            1 for r in rules if normalize_text(r.labeling_guidance)
        ),
        "rules_with_positive_examples": sum(
            1 for r in rules if (r.positive_example_refs or [])
        ),
        "rules_with_negative_examples": sum(
            1 for r in rules if (r.negative_example_refs or [])
        ),
        "rules_with_ambiguous_examples": sum(
            1 for r in rules if (r.ambiguous_example_refs or [])
        ),
        "evidence_total": len(evidence_list),
        "evidence_with_screenshots": sum(
            1 for e in evidence_list if (e.screenshot_paths or [])
        ),
        "evidence_with_frame_ids": sum(
            1 for e in evidence_list if (e.frame_ids or [])
        ),
    }


def save_ml_manifest(payload: dict[str, Any], output_path: Path) -> None:
    """Write ML manifest JSON atomically."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_path, payload, encoding="utf-8")
