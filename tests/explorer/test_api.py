from __future__ import annotations


def _filters() -> dict[str, object]:
    return {
        "lesson_ids": [],
        "concept_ids": [],
        "unit_types": [],
        "support_basis": [],
        "evidence_requirement": [],
        "teaching_mode": [],
        "min_confidence_score": None,
    }


def _search_payload(query: str, top_k: int = 5) -> dict[str, object]:
    return {
        "query": query,
        "top_k": top_k,
        "filters": _filters(),
        "return_groups": True,
    }


def _rule_compare_payload(rule_ids: list[str]) -> dict[str, object]:
    return {
        "rule_ids": rule_ids,
        "include_related_context": True,
    }


def _lesson_compare_payload(lesson_ids: list[str]) -> dict[str, object]:
    return {"lesson_ids": lesson_ids}


def test_browser_health_and_search_endpoints_work(explorer_client):
    health = explorer_client.get("/browser/health")
    assert health.status_code == 200
    assert health.json()["explorer_ready"] is True

    response = explorer_client.post("/browser/search", json=_search_payload("stop loss"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["cards"]
    assert payload["hit_count"] >= 1


def test_browser_detail_endpoints_and_facets_work(explorer_client):
    rule_response = explorer_client.get("/browser/rule/rule:lesson_alpha:rule_stop_loss_1")
    assert rule_response.status_code == 200
    assert rule_response.json()["rule_text_ru"] == "Технический стоп прячется за откат."
    assert rule_response.json()["frame_ids"] == ["000011"]

    evidence_response = explorer_client.get("/browser/evidence/evidence:lesson_alpha:ev_stop_loss")
    assert evidence_response.status_code == 200
    assert evidence_response.json()["source_rules"][0]["doc_id"] == "rule:lesson_alpha:rule_stop_loss_1"
    assert evidence_response.json()["frame_ids"] == ["000011"]

    concept_response = explorer_client.get("/browser/concept/node:stop_loss")
    assert concept_response.status_code == 200
    concept_payload = concept_response.json()
    assert concept_payload["concept_id"] == "node:stop_loss"
    assert concept_payload["rule_count"] == 1
    assert concept_payload["event_count"] == 1
    assert concept_payload["evidence_count"] == 1

    neighbors_response = explorer_client.get("/browser/concept/node:stop_loss/neighbors")
    assert neighbors_response.status_code == 200
    assert neighbors_response.json() == [
        {
            "concept_id": "node:breakout",
            "relation": "depends_on",
            "direction": "outgoing",
            "weight": 1.0,
        }
    ]

    lesson_response = explorer_client.get("/browser/lesson/lesson_alpha")
    assert lesson_response.status_code == 200
    lesson_payload = lesson_response.json()
    assert lesson_payload["rule_count"] == 2
    assert lesson_payload["event_count"] == 2
    assert lesson_payload["evidence_count"] == 2

    facets_response = explorer_client.get("/browser/facets")
    assert facets_response.status_code == 200
    facets_payload = facets_response.json()
    assert facets_payload["by_unit_type"]["rule_card"] == 3
    assert facets_payload["by_unit_type"]["knowledge_event"] == 3
    assert facets_payload["by_unit_type"]["evidence_ref"] == 3


def test_browser_compare_and_traversal_endpoints_work(
    explorer_client,
    sample_compare_rule_ids,
    sample_compare_lesson_ids,
):
    compare_rules = explorer_client.post("/browser/compare/rules", json=_rule_compare_payload(sample_compare_rule_ids))
    assert compare_rules.status_code == 200
    compare_rules_payload = compare_rules.json()
    assert [item["doc_id"] for item in compare_rules_payload["rules"]] == sample_compare_rule_ids
    assert compare_rules_payload["summary"]["possible_relationships"]

    compare_lessons = explorer_client.post(
        "/browser/compare/lessons",
        json=_lesson_compare_payload(sample_compare_lesson_ids),
    )
    assert compare_lessons.status_code == 200
    compare_lessons_payload = compare_lessons.json()
    assert [item["lesson_id"] for item in compare_lessons_payload["lessons"]] == sample_compare_lesson_ids
    assert "node:breakout" in compare_lessons_payload["shared_concepts"]

    related_rules = explorer_client.get("/browser/rule/rule:lesson_alpha:rule_accumulation_1/related")
    assert related_rules.status_code == 200
    related_payload = related_rules.json()
    assert related_payload["source_doc_id"] == "rule:lesson_alpha:rule_accumulation_1"
    assert "same_lesson" in related_payload["groups"]

    concept_rules = explorer_client.get("/browser/concept/node:breakout/rules")
    assert concept_rules.status_code == 200
    concept_rules_payload = concept_rules.json()
    assert concept_rules_payload["concept_id"] == "node:breakout"
    assert concept_rules_payload["total"] == 2

    concept_lessons = explorer_client.get("/browser/concept/node:breakout/lessons")
    assert concept_lessons.status_code == 200
    concept_lessons_payload = concept_lessons.json()
    assert concept_lessons_payload["concept_id"] == "node:breakout"
    assert concept_lessons_payload["lessons"] == sample_compare_lesson_ids


def test_browser_frame_endpoint_serves_dense_frame_asset(explorer_client):
    response = explorer_client.get("/browser/frame/lesson_alpha/000011")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content == b"fake-jpeg-bytes"


def test_browser_detail_error_and_validation_paths_work(explorer_client):
    wrong_type = explorer_client.get("/browser/rule/evidence:lesson_alpha:ev_stop_loss")
    assert wrong_type.status_code == 400

    unknown_rule = explorer_client.get("/browser/rule/rule:missing")
    assert unknown_rule.status_code == 404

    unknown_evidence = explorer_client.get("/browser/evidence/evidence:missing")
    assert unknown_evidence.status_code == 404

    unknown_concept = explorer_client.get("/browser/concept/node:missing")
    assert unknown_concept.status_code == 404

    unknown_lesson = explorer_client.get("/browser/lesson/lesson_missing")
    assert unknown_lesson.status_code == 404

    bad_search = explorer_client.post(
        "/browser/search",
        json={
            "query": "bad request",
            "top_k": "oops",
            "filters": _filters(),
            "return_groups": True,
        },
    )
    assert bad_search.status_code == 422

    bad_compare_rules = explorer_client.post(
        "/browser/compare/rules",
        json=_rule_compare_payload(["rule:lesson_alpha:rule_stop_loss_1"]),
    )
    assert bad_compare_rules.status_code == 400

    unknown_compare_rule = explorer_client.post(
        "/browser/compare/rules",
        json=_rule_compare_payload(["rule:lesson_alpha:rule_stop_loss_1", "rule:missing"]),
    )
    assert unknown_compare_rule.status_code == 404

    bad_compare_lessons = explorer_client.post(
        "/browser/compare/lessons",
        json=_lesson_compare_payload(["lesson_alpha"]),
    )
    assert bad_compare_lessons.status_code == 400

    unknown_related_rules = explorer_client.get("/browser/rule/rule:missing/related")
    assert unknown_related_rules.status_code == 404


def test_browser_stoploss_query_keeps_evidence_first(real_browser_client):
    response = real_browser_client.post("/browser/search", json=_search_payload("Пример постановки стоп-лосса"))
    assert response.status_code == 200
    assert response.json()["cards"][0]["unit_type"] == "evidence_ref"


def test_browser_timeframe_query_keeps_rule_first(real_browser_client):
    response = real_browser_client.post("/browser/search", json=_search_payload("Правила торговли на разных таймфреймах"))
    assert response.status_code == 200
    assert response.json()["cards"][0]["unit_type"] == "rule_card"


def test_browser_daily_level_query_keeps_knowledge_event_first(real_browser_client):
    response = real_browser_client.post("/browser/search", json=_search_payload("Как определить дневной уровень?"))
    assert response.status_code == 200
    assert response.json()["cards"][0]["unit_type"] == "knowledge_event"


def test_browser_visual_support_query_keeps_evidence_first(real_browser_client):
    response = real_browser_client.post(
        "/browser/search",
        json=_search_payload("Какие примеры требуют визуальных доказательств?"),
    )
    assert response.status_code == 200
    first_card = response.json()["cards"][0]
    assert first_card["unit_type"] == "evidence_ref"
    assert first_card["evidence_requirement"] == "required"


def test_browser_transcript_support_query_keeps_transcript_primary_first(real_browser_client):
    response = real_browser_client.post(
        "/browser/search",
        json=_search_payload("Какие правила подтверждаются только по transcript?"),
    )
    assert response.status_code == 200
    first_card = response.json()["cards"][0]
    assert first_card["unit_type"] in {"knowledge_event", "rule_card"}
    assert first_card["support_basis"] == "transcript_primary"
