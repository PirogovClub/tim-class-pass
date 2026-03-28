"""Authoritative reviewable target IDs from the explorer / retrieval corpus (Stage 5.2+).

Queues and write validation left-join adjudication state to this inventory so never-reviewed
corpus items still appear as unresolved, and arbitrary IDs cannot be adjudicated.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.adjudication.enums import ReviewTargetType


@dataclass(frozen=True, slots=True)
class CorpusTargetIndex:
    """Frozen sets of valid target_id strings per ReviewTargetType (corpus-backed)."""

    rule_card_ids: frozenset[str]
    evidence_link_ids: frozenset[str]
    concept_link_ids: frozenset[str]
    related_rule_relation_ids: frozenset[str]

    @classmethod
    def empty(cls) -> CorpusTargetIndex:
        return cls(frozenset(), frozenset(), frozenset(), frozenset())

    def contains(self, target_type: ReviewTargetType, target_id: str) -> bool:
        if target_type == ReviewTargetType.RULE_CARD:
            return target_id in self.rule_card_ids
        if target_type == ReviewTargetType.EVIDENCE_LINK:
            return target_id in self.evidence_link_ids
        if target_type == ReviewTargetType.CONCEPT_LINK:
            return target_id in self.concept_link_ids
        if target_type == ReviewTargetType.RELATED_RULE_RELATION:
            return target_id in self.related_rule_relation_ids
        return False

    @classmethod
    def from_explorer_repository(cls, repo: object) -> CorpusTargetIndex:
        """Build from ``ExplorerRepository`` (``pipeline.explorer.loader``)."""
        # Late import: explorer depends on rag store, not adjudication.
        from pipeline.explorer.loader import ExplorerRepository

        if not isinstance(repo, ExplorerRepository):
            raise TypeError("repo must be an ExplorerRepository")

        rules: set[str] = set()
        evidence: set[str] = set()
        concept_links: set[str] = set()
        related_rules: set[str] = set()

        for doc in repo.get_all_docs():
            doc_id = str(doc.get("doc_id") or "").strip()
            if not doc_id:
                continue
            ut = str(doc.get("unit_type") or "")
            if ut == "rule_card":
                rules.add(doc_id)
            elif ut == "evidence_ref":
                evidence.add(doc_id)
            elif ut == "concept_relation":
                cids = [str(c) for c in (doc.get("canonical_concept_ids") or [])]
                has_rule = any(c.startswith("rule:") for c in cids)
                if has_rule or doc_id.startswith("rel:rule:"):
                    related_rules.add(doc_id)
                else:
                    concept_links.add(doc_id)

        return cls(
            frozenset(rules),
            frozenset(evidence),
            frozenset(concept_links),
            frozenset(related_rules),
        )
