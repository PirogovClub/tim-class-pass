from __future__ import annotations

from pipeline.explorer.contracts import BrowserSearchFilters, BrowserSearchRequest
from pipeline.explorer.loader import ExplorerRepository
from pipeline.explorer.service import ExplorerService
from pipeline.rag.store import InMemoryDocStore


class _UnusedRetriever:
    def search(self, *args, **kwargs):  # pragma: no cover - defensive helper for repo-driven tests
        raise AssertionError("Retriever should not be called for this test")


def _make_doc(
    doc_id: str,
    unit_type: str,
    concept_id: str,
    *,
    lesson_id: str = "lesson_bulk",
    confidence_score: float = 0.9,
) -> dict[str, object]:
    doc = {
        "doc_id": doc_id,
        "unit_type": unit_type,
        "lesson_id": lesson_id,
        "title": doc_id,
        "canonical_concept_ids": [concept_id],
        "canonical_subconcept_ids": [],
        "source_rule_ids": [],
        "source_event_ids": [],
        "evidence_ids": [],
        "support_basis": "transcript_primary",
        "evidence_requirement": "optional",
        "teaching_mode": "theory",
        "confidence_score": confidence_score,
        "timestamps": [],
    }
    if unit_type == "rule_card":
        doc["rule_text_ru"] = f"{doc_id} rule text"
    elif unit_type == "knowledge_event":
        doc["normalized_text_ru"] = f"{doc_id} event text"
    elif unit_type == "evidence_ref":
        doc["visual_summary"] = f"{doc_id} evidence summary"
    return doc


def _build_repo_with_docs(
    docs: list[dict[str, object]],
    *,
    concept_id: str,
    lesson_id: str = "lesson_bulk",
) -> ExplorerRepository:
    store = InMemoryDocStore()
    for doc in docs:
        store.add(doc)

    concept_suffix = concept_id.split(":", 1)[1] if ":" in concept_id else concept_id
    concept_meta = {
        concept_id: {
            "concept_id": concept_id,
            "name": concept_suffix,
            "type": "concept",
            "aliases": [concept_suffix],
            "source_lessons": [lesson_id],
        },
        concept_suffix: {
            "concept_id": concept_id,
            "name": concept_suffix,
            "type": "concept",
            "aliases": [concept_suffix],
            "source_lessons": [lesson_id],
        },
    }
    alias_registry = {
        concept_id: {"name": concept_suffix, "aliases": [concept_suffix]},
        concept_suffix: {"name": concept_suffix, "aliases": [concept_suffix]},
    }
    lesson_registry = {
        lesson_id: {"lesson_id": lesson_id, "lesson_title": "Lesson Bulk"},
    }
    return ExplorerRepository(
        store=store,
        concept_neighbors={},
        alias_registry=alias_registry,
        lesson_registry=lesson_registry,
        concept_rule_map={},
        rule_family_index={},
        concept_meta=concept_meta,
        corpus_contract_version="test",
    )


def test_repo_doc_lookup_by_id_lesson_and_concept(explorer_repo):
    rule_doc = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    assert rule_doc is not None
    assert rule_doc["unit_type"] == "rule_card"

    lesson_docs = explorer_repo.get_docs_by_lesson("lesson_alpha")
    assert lesson_docs
    assert all(doc["lesson_id"] == "lesson_alpha" for doc in lesson_docs)

    concept_docs = explorer_repo.get_docs_by_concept("node:stop_loss")
    assert concept_docs
    assert any(doc["doc_id"] == "rule:lesson_alpha:rule_stop_loss_1" for doc in concept_docs)


def test_repo_concept_neighbors_return_relation_and_direction(explorer_repo):
    neighbors = explorer_repo.get_concept_neighbors("node:stop_loss")
    assert neighbors == [
        {
            "concept_id": "node:breakout",
            "relation": "depends_on",
            "direction": "outgoing",
            "weight": 1,
        }
    ]


def test_repo_get_evidence_docs_for_rule_returns_linked_evidence(explorer_repo):
    rule_doc = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    evidence_docs = explorer_repo.get_evidence_docs_for_rule(rule_doc)
    assert [doc["doc_id"] for doc in evidence_docs] == ["evidence:lesson_alpha:ev_stop_loss"]


def test_service_browse_mode_sorts_rule_cards_before_events(explorer_service):
    response = explorer_service.search(BrowserSearchRequest(query="", top_k=10))
    unit_types = [card.unit_type for card in response.cards]
    assert unit_types[:3] == ["rule_card", "rule_card", "rule_card"]
    assert "knowledge_event" in unit_types[3:]


def test_service_concept_detail_reports_full_counts_beyond_preview():
    concept_id = "node:mega_concept"
    docs = [
        *[
            _make_doc(
                f"rule:lesson_bulk:rule_{index:02d}",
                "rule_card",
                concept_id,
                confidence_score=1.0 - (index * 0.01),
            )
            for index in range(12)
        ],
        *[
            _make_doc(
                f"event:lesson_bulk:event_{index:02d}",
                "knowledge_event",
                concept_id,
                confidence_score=0.8 - (index * 0.01),
            )
            for index in range(15)
        ],
        *[
            _make_doc(
                f"evidence:lesson_bulk:evidence_{index:02d}",
                "evidence_ref",
                concept_id,
                confidence_score=0.6 - (index * 0.01),
            )
            for index in range(3)
        ],
    ]
    repo = _build_repo_with_docs(docs, concept_id=concept_id)
    service = ExplorerService(repo, _UnusedRetriever())

    detail = service.get_concept_detail(concept_id)

    assert len(detail.top_rules) == 10
    assert len(detail.top_events) == 10
    assert detail.rule_count == 12
    assert detail.event_count == 15
    assert detail.evidence_count == 3


def test_service_facets_use_full_filtered_set_not_first_page_only():
    concept_id = "node:facet_concept"
    docs = [
        *[
            _make_doc(
                f"rule:lesson_bulk:rule_{index:03d}",
                "rule_card",
                concept_id,
                confidence_score=1.0 - (index * 0.001),
            )
            for index in range(120)
        ],
        *[
            _make_doc(
                f"event:lesson_bulk:event_{index:03d}",
                "knowledge_event",
                concept_id,
                confidence_score=0.7 - (index * 0.001),
            )
            for index in range(5)
        ],
        *[
            _make_doc(
                f"evidence:lesson_bulk:evidence_{index:03d}",
                "evidence_ref",
                concept_id,
                confidence_score=0.5 - (index * 0.001),
            )
            for index in range(3)
        ],
    ]
    repo = _build_repo_with_docs(docs, concept_id=concept_id)
    service = ExplorerService(repo, _UnusedRetriever())

    facets = service.get_facets(filters=BrowserSearchFilters(lesson_ids=["lesson_bulk"]))

    assert facets["by_unit_type"]["rule_card"] == 120
    assert facets["by_unit_type"]["knowledge_event"] == 5
    assert facets["by_unit_type"]["evidence_ref"] == 3
    assert sum(facets["by_unit_type"].values()) == 128
