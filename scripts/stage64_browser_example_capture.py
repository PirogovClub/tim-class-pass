"""Discover real browser API example ids from the live RAG corpus (no hardcoded lesson_alpha ids)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def _flatten_cards(body: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = list(body.get("cards") or [])
    groups = body.get("groups") or {}
    if isinstance(groups, dict):
        for g in groups.values():
            if isinstance(g, list):
                out.extend(g)
    return out


def _first_type(cards: list[dict[str, Any]], unit_type: str) -> dict[str, Any] | None:
    for c in cards:
        if c.get("unit_type") == unit_type:
            return c
    return None


def _search_payload(query: str, top_k: int = 25) -> dict[str, Any]:
    return {
        "query": query,
        "top_k": top_k,
        "filters": {
            "lesson_ids": [],
            "concept_ids": [],
            "unit_types": [],
            "support_basis": [],
            "evidence_requirement": [],
            "teaching_mode": [],
            "min_confidence_score": None,
        },
        "return_groups": True,
    }


def _is_http_error_json(data: Any) -> bool:
    return isinstance(data, dict) and "detail" in data and isinstance(data.get("detail"), str)


def _default_queries() -> list[str]:
    raw = os.environ.get(
        "STAGE64_EXAMPLE_SEARCH_QUERIES",
        "stop,торговля,урок,price,level,risk,trading,lesson",
    )
    return [q.strip() for q in raw.split(",") if q.strip()]


def capture_browser_examples(client: TestClient, examples: Path) -> dict[str, Any]:
    """Write example_browser_*.json under ``examples``; return manifest metadata."""
    meta: dict[str, Any] = {
        "live_api_captured": True,
        "discovery_method": "search_then_rule_chain",
        "queries_tried": [],
        "discovered_ids": {},
    }

    search_body: dict[str, Any] | None = None
    flat: list[dict[str, Any]] = []
    rule_id: str | None = None
    winning_query: str | None = None

    for q in _default_queries():
        r = client.post("/browser/search", json=_search_payload(q))
        meta["queries_tried"].append({"query": q, "status": r.status_code})
        if r.status_code != 200:
            continue
        body = r.json()
        if _is_http_error_json(body):
            continue
        cards = _flatten_cards(body)
        hit = _first_type(cards, "rule_card")
        if not hit or not hit.get("doc_id"):
            continue
        rid = str(hit["doc_id"])
        rr = client.get(f"/browser/rule/{rid}")
        if rr.status_code != 200:
            continue
        rule_j = rr.json()
        if _is_http_error_json(rule_j):
            continue
        if not rule_j.get("lesson_id"):
            continue

        search_body = body
        flat = cards
        rule_id = rid
        winning_query = q
        break

    if not search_body or not rule_id:
        raise RuntimeError(
            "Could not discover a rule_card with a valid rule detail from /browser/search; "
            f"tried queries: {meta['queries_tried']!r}",
        )

    rule_resp = client.get(f"/browser/rule/{rule_id}")
    assert rule_resp.status_code == 200
    rule_j = rule_resp.json()
    if _is_http_error_json(rule_j):
        raise RuntimeError(f"Rule detail invalid: {rule_j!r}")

    lesson_id = str(rule_j["lesson_id"])
    evidence_refs = list(rule_j.get("evidence_refs") or [])
    source_events = list(rule_j.get("source_events") or [])
    canon = list(rule_j.get("canonical_concept_ids") or [])

    evidence_id: str | None = None
    if evidence_refs and evidence_refs[0].get("doc_id"):
        evidence_id = str(evidence_refs[0]["doc_id"])
    if not evidence_id:
        ev = _first_type(flat, "evidence_ref")
        if ev and ev.get("doc_id"):
            evidence_id = str(ev["doc_id"])

    event_id: str | None = None
    if source_events and source_events[0].get("doc_id"):
        event_id = str(source_events[0]["doc_id"])
    if not event_id:
        ke = _first_type(flat, "knowledge_event")
        if ke and ke.get("doc_id"):
            event_id = str(ke["doc_id"])

    concept_id: str | None = canon[0] if canon else None
    if not concept_id:
        cn = _first_type(flat, "concept_node")
        if cn and cn.get("doc_id"):
            concept_id = str(cn["doc_id"])

    if not evidence_id:
        raise RuntimeError("Could not resolve evidence doc_id from rule or search hits.")
    if not event_id:
        raise RuntimeError("Could not resolve knowledge_event doc_id from rule or search hits.")
    if not concept_id:
        raise RuntimeError("Could not resolve concept id from rule or search hits.")

    def _save_json(filename: str, data: Any) -> None:
        (examples / filename).write_text(json.dumps(data, indent=2), encoding="utf-8")

    _save_json("example_browser_search.json", search_body)
    _save_json("example_browser_rule.json", rule_j)

    ev_r = client.get(f"/browser/evidence/{evidence_id}")
    if ev_r.status_code != 200 or _is_http_error_json(ev_r.json()):
        raise RuntimeError(f"Evidence detail failed for {evidence_id!r}: {ev_r.status_code} {ev_r.text[:500]}")
    _save_json("example_browser_evidence.json", ev_r.json())

    evn_r = client.get(f"/browser/event/{event_id}")
    if evn_r.status_code != 200 or _is_http_error_json(evn_r.json()):
        raise RuntimeError(f"Event detail failed for {event_id!r}: {evn_r.status_code} {evn_r.text[:500]}")
    _save_json("example_browser_event.json", evn_r.json())

    # Concept id may contain ':' — URL path segment is fine for TestClient
    con_r = client.get(f"/browser/concept/{concept_id}")
    if con_r.status_code != 200 or _is_http_error_json(con_r.json()):
        raise RuntimeError(f"Concept detail failed for {concept_id!r}: {con_r.status_code} {con_r.text[:500]}")
    _save_json("example_browser_concept.json", con_r.json())

    les_r = client.get(f"/browser/lesson/{lesson_id}")
    if les_r.status_code != 200 or _is_http_error_json(les_r.json()):
        raise RuntimeError(f"Lesson detail failed for {lesson_id!r}: {les_r.status_code} {les_r.text[:500]}")
    _save_json("example_browser_lesson.json", les_r.json())

    cmp_r = client.post(
        "/browser/compare/units",
        json={"items": [{"unit_type": "rule_card", "doc_id": rule_id}, {"unit_type": "knowledge_event", "doc_id": event_id}]},
    )
    if cmp_r.status_code != 200 or _is_http_error_json(cmp_r.json()):
        raise RuntimeError(f"Compare units failed: {cmp_r.status_code} {cmp_r.text[:500]}")
    _save_json("example_browser_compare_units.json", cmp_r.json())

    meta["discovered_ids"] = {
        "search_query_winning": winning_query,
        "rule_doc_id": rule_id,
        "evidence_doc_id": evidence_id,
        "event_doc_id": event_id,
        "concept_id": concept_id,
        "lesson_id": lesson_id,
    }
    return meta
