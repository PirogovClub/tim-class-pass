"""Constants for the frozen lesson export contract (v1)."""

from __future__ import annotations

# Primary artifacts (required for every processed lesson under v1).
REQUIRED_ARTIFACT_FILENAMES: tuple[str, ...] = (
    "knowledge_events.json",
    "rule_cards.json",
    "evidence_index.json",
    "concept_graph.json",
)

OPTIONAL_MARKDOWN_ARTIFACTS: tuple[str, ...] = (
    "review_markdown.md",
    "rag_ready.md",
)

ARTIFACT_KEY_BY_FILENAME: dict[str, str] = {
    "knowledge_events.json": "knowledge_events",
    "rule_cards.json": "rule_cards",
    "evidence_index.json": "evidence_index",
    "concept_graph.json": "concept_graph",
    "review_markdown.md": "review_markdown",
    "rag_ready.md": "rag_ready",
}
