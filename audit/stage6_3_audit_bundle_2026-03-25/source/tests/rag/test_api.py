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
    assert "detected_intents" in payload["query_analysis"]
    assert isinstance(payload["query_analysis"]["detected_intents"], list)
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


def test_rag_item_related_explore_endpoints(rag_config, built_rag_root, patch_fake_sentence_transformer):
    from pipeline.rag.api import app, init_app

    init_app(rag_config)
    client = TestClient(app)
    rid = "rule:lesson_alpha:rule_stop_loss_1"
    item = client.get(f"/rag/item/rule_card/{rid}")
    assert item.status_code == 200
    assert item.json()["unit_type"] == "rule_card"

    rel = client.get(f"/rag/related/rule_card/{rid}")
    assert rel.status_code == 200
    body = rel.json()
    assert body["found"] is True
    assert "related" in body

    explore = client.get("/rag/explore/lesson/lesson_alpha")
    assert explore.status_code == 200
    exp = explore.json()
    assert exp["lesson_id"] == "lesson_alpha"
    assert exp["unit_counts"]["rule_card"] >= 1


def test_rag_search_explain_returns_trace(rag_config, built_rag_root, patch_fake_sentence_transformer):
    from pipeline.rag.api import app, init_app

    init_app(rag_config)
    client = TestClient(app)
    resp = client.post(
        "/rag/search/explain",
        json={
            "query": "stop loss",
            "top_k": 3,
            "unit_types": ["rule_card"],
            "filters": {"lesson_ids": [], "concept_ids": [], "min_confidence_score": None},
            "return_summary": True,
            "require_evidence": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "search_response" in body
    assert "retrieval_trace" in body
    assert body["retrieval_trace"].get("expansion") is not None
    assert "per_hit_scores" in body["retrieval_trace"]


def test_rag_search_require_evidence(rag_config, built_rag_root, patch_fake_sentence_transformer):
    from pipeline.rag.api import app, init_app

    init_app(rag_config)
    client = TestClient(app)
    response = client.post(
        "/rag/search",
        json={
            "query": "stop loss",
            "top_k": 10,
            "unit_types": ["rule_card"],
            "filters": {"lesson_ids": [], "concept_ids": [], "min_confidence_score": None},
            "return_summary": True,
            "require_evidence": True,
        },
    )
    assert response.status_code == 200
    for hit in response.json()["top_hits"]:
        assert hit.get("evidence_ids")
