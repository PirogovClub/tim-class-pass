"""Build grounded, structured answer payloads from retrieval results."""

from __future__ import annotations

from typing import Any

from pipeline.rag.query_intents import (
    INTENT_CONCEPT_COMPARISON,
    INTENT_CROSS_LESSON_CONFLICT,
    INTENT_EXAMPLE_LOOKUP,
    INTENT_SUPPORT_POLICY,
)


def build_answer(retrieval_result: dict[str, Any], return_summary: bool = True) -> dict[str, Any]:
    query = retrieval_result.get("query", "")
    normalized_query = retrieval_result.get("normalized_query", query)
    top_hits = retrieval_result.get("top_hits", [])
    expansion = retrieval_result.get("expansion", {})
    detected_unit_bias = retrieval_result.get("detected_unit_bias", "mixed")
    detected_intents: list[str] = list(retrieval_result.get("detected_intents") or [])
    intent_signals: dict[str, Any] = dict(retrieval_result.get("intent_signals") or {})
    intent_set = set(detected_intents)

    grouped: dict[str, list[dict[str, Any]]] = {
        "rule_cards": [],
        "knowledge_events": [],
        "evidence_refs": [],
        "concepts": [],
    }
    for hit in top_hits:
        ut = hit.get("unit_type", "")
        if ut == "rule_card":
            grouped["rule_cards"].append(hit)
        elif ut == "knowledge_event":
            grouped["knowledge_events"].append(hit)
        elif ut == "evidence_ref":
            grouped["evidence_refs"].append(hit)
        elif ut in ("concept_node", "concept_relation"):
            grouped["concepts"].append(hit)

    citation_doc_ids = [hit["doc_id"] for hit in top_hits]
    limitations: list[str] = []
    if not top_hits:
        limitations.append("No grounded retrieval hits were found for this query.")
    if not any(hit.get("timestamps") for hit in top_hits):
        limitations.append("Top hits do not include timestamp evidence.")
    if not any(hit.get("evidence_ids") for hit in top_hits):
        limitations.append("Top hits do not include explicit evidence IDs.")

    evidence_first = (
        INTENT_EXAMPLE_LOOKUP in intent_set
        or (
            INTENT_SUPPORT_POLICY in intent_set
            and intent_signals.get("prefers_visual_evidence")
        )
    )
    concept_first = (
        INTENT_CONCEPT_COMPARISON in intent_set
        or INTENT_CROSS_LESSON_CONFLICT in intent_set
    )

    if evidence_first and top_hits and top_hits[0].get("unit_type") != "evidence_ref":
        limitations.append(
            "Query looks evidence-oriented; top hit is not an evidence_ref — review ranking or corpus coverage."
        )
    if concept_first and top_hits and top_hits[0].get("unit_type") not in (
        "concept_node",
        "concept_relation",
    ):
        limitations.append(
            "Query looks graph/concept-oriented; top hit is not a concept unit — review expansion or ranking."
        )

    answer_text: str | None = None
    if return_summary:
        preferred_hits: list[dict[str, Any]]
        if evidence_first:
            preferred_hits = (
                grouped["evidence_refs"]
                or grouped["knowledge_events"]
                or grouped["rule_cards"]
                or top_hits
            )
        elif concept_first:
            preferred_hits = (
                grouped["concepts"]
                or grouped["rule_cards"]
                or grouped["knowledge_events"]
                or top_hits
            )
        else:
            preferred_hits = grouped["rule_cards"] or grouped["knowledge_events"] or top_hits
        snippets = [hit.get("text_snippet", "") for hit in preferred_hits[:5] if hit.get("text_snippet")]
        if snippets:
            answer_text = "\n".join(snippets)

    return {
        "query": query,
        "query_analysis": {
            "normalized_query": normalized_query,
            "detected_concepts": expansion.get("canonical_concept_ids", []),
            "detected_unit_bias": detected_unit_bias,
            "detected_intents": detected_intents,
            "intent_signals": {
                "prefers_transcript_only": intent_signals.get("prefers_transcript_only", False),
                "prefers_visual_evidence": intent_signals.get("prefers_visual_evidence", False),
                "mentions_timeframe": intent_signals.get("mentions_timeframe", False),
                "mentions_cross_lesson": intent_signals.get("mentions_cross_lesson", False),
                "mentions_stoploss": intent_signals.get("mentions_stoploss", False),
                "prefers_actionable_rules": intent_signals.get("prefers_actionable_rules", False),
                "prefers_explicit_rules": intent_signals.get("prefers_explicit_rules", False),
                "prefers_examples": intent_signals.get("prefers_examples", False),
                "prefers_theory": intent_signals.get("prefers_theory", False),
            },
            "expansion_trace": expansion,
        },
        "top_hits": top_hits,
        "grouped_results": grouped,
        "summary": {
            "answer_text": answer_text,
            "limitations": limitations,
            "citation_doc_ids": citation_doc_ids,
        },
        "facets": retrieval_result.get("facets", {}),
        "hit_count": retrieval_result.get("hit_count", len(top_hits)),
    }
