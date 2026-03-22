from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_and_search_endpoints_work(rag_config, built_rag_root, patch_fake_sentence_transformer):
    from pipeline.rag.api import app, init_app

    init_app(rag_config)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["rag_ready"] is True

    response = client.post(
        "/rag/search",
        json={
            "query": "stop loss",
            "top_k": 3,
            "unit_types": ["rule_card", "knowledge_event", "evidence_ref"],
            "filters": {"lesson_ids": [], "concept_ids": [], "min_confidence_score": None},
            "return_summary": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "query_analysis" in payload
    assert payload["top_hits"]


def test_doc_lesson_concept_endpoints_work(rag_config, built_rag_root, patch_fake_sentence_transformer):
    from pipeline.rag.api import app, init_app

    init_app(rag_config)
    client = TestClient(app)

    doc = client.get("/rag/doc/rule:lesson_alpha:rule_stop_loss_1")
    assert doc.status_code == 200

    lesson = client.get("/rag/lesson/lesson_alpha")
    assert lesson.status_code == 200
    assert lesson.json()["doc_count"] > 0

    concept = client.get("/rag/concept/node:stop_loss")
    assert concept.status_code == 200
    assert concept.json()["doc_count"] > 0
