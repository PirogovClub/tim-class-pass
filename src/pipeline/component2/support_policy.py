"""Transcript-first classification policy for knowledge events and rules.

Pure functions that classify teaching mode, evidence requirement, support basis,
and support levels based on event type, scores, and context. These implement the
ground truth policy: transcript is primary, visuals are supporting evidence.
"""

from __future__ import annotations

from typing import Any

# ── Default policy table keyed by event_type ─────────────────────────────

DEFAULT_EVENT_POLICY: dict[str, dict[str, str]] = {
    "definition":     {"teaching_mode": "theory",  "evidence_requirement": "none"},
    "comparison":     {"teaching_mode": "theory",  "evidence_requirement": "none"},
    "warning":        {"teaching_mode": "theory",  "evidence_requirement": "optional"},
    "process_step":   {"teaching_mode": "theory",  "evidence_requirement": "optional"},
    "algorithm_hint": {"teaching_mode": "theory",  "evidence_requirement": "optional"},
    "rule_statement": {"teaching_mode": "mixed",   "evidence_requirement": "optional"},
    "condition":      {"teaching_mode": "theory",  "evidence_requirement": "optional"},
    "invalidation":   {"teaching_mode": "theory",  "evidence_requirement": "optional"},
    "exception":      {"teaching_mode": "theory",  "evidence_requirement": "optional"},
    "example":        {"teaching_mode": "example", "evidence_requirement": "required"},
    "observation":    {"teaching_mode": "theory",  "evidence_requirement": "optional"},
}

_EXAMPLE_LANGUAGE = frozenset({
    "показ", "смотр", "видим", "график", "chart", "setup", "пример",
    "демонстрац", "failure", "breakout", "пробой", "свеч",
})


def classify_teaching_mode(
    event_type: str,
    raw_text: str,
    linked_visual_count: int = 0,
    visual_example_type: str | None = None,
) -> str:
    """Classify how the concept is taught: theory, example, or mixed."""
    default = DEFAULT_EVENT_POLICY.get(event_type, {}).get("teaching_mode", "theory")

    if event_type in ("definition", "comparison"):
        return "theory"

    if event_type == "example":
        return "example"

    lower = (raw_text or "").lower()
    has_example_lang = any(kw in lower for kw in _EXAMPLE_LANGUAGE)

    if has_example_lang and linked_visual_count > 0:
        if event_type == "rule_statement":
            return "mixed"
        return "example"

    if visual_example_type and visual_example_type not in ("illustration", "unknown"):
        if event_type == "rule_statement":
            return "mixed"

    return default


def classify_evidence_requirement(
    event_type: str,
    teaching_mode: str,
    concept: str | None = None,
    subconcept: str | None = None,
) -> str:
    """Determine whether visual evidence is required, optional, or unnecessary."""
    default = DEFAULT_EVENT_POLICY.get(event_type, {}).get("evidence_requirement", "optional")

    if teaching_mode == "example":
        return "required"

    if event_type in ("definition", "comparison"):
        return "none"

    return default


def classify_support_basis(
    transcript_support_score: float,
    visual_support_score: float,
    teaching_mode: str,
) -> str:
    """Determine the primary grounding source for a rule or event."""
    if transcript_support_score >= 0.60 and visual_support_score < 0.35:
        return "transcript_primary"
    if transcript_support_score >= 0.60 and visual_support_score >= 0.35:
        return "transcript_plus_visual"
    if (
        transcript_support_score < 0.45
        and visual_support_score >= 0.60
        and teaching_mode in ("example", "mixed")
    ):
        return "visual_primary"
    return "inferred"


def classify_transcript_support_level(score: float) -> str:
    """Bucket a transcript support score into weak/moderate/strong."""
    if score >= 0.75:
        return "strong"
    if score >= 0.45:
        return "moderate"
    return "weak"


def classify_visual_support_level(
    score: float,
    example_role: str | None = None,
) -> str:
    """Classify the strength of visual support for a rule or event."""
    if score <= 0.0 and not example_role:
        return "none"
    if example_role == "illustration":
        return "illustration"
    if example_role == "ambiguous_example":
        return "ambiguous"
    if example_role in ("counterexample", "negative_example"):
        return "counterexample"
    if score >= 0.75:
        return "strong_example"
    if score > 0.0:
        return "supporting_example"
    return "none"


def should_require_visual_evidence(rule_or_event: Any) -> bool:
    """Return True only when the entity actually needs linked visual evidence."""
    tm = getattr(rule_or_event, "teaching_mode", None)
    er = getattr(rule_or_event, "evidence_requirement", None)
    return tm == "example" or er == "required"
