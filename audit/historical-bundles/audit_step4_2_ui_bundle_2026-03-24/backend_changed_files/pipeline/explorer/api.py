"""FastAPI router for the Step 4.1 explorer backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from pipeline.explorer.contracts import (
    BrowserSearchFilters,
    BrowserSearchRequest,
    BrowserSearchResponse,
    ConceptDetailResponse,
    ConceptNeighbor,
    EvidenceDetailResponse,
    LessonDetailResponse,
    RuleDetailResponse,
)
from pipeline.explorer.loader import ExplorerRepository
from pipeline.explorer.service import ExplorerService
from pipeline.rag.config import RAGConfig
from pipeline.rag.retriever import HybridRetriever

explorer_router = APIRouter(prefix="/browser", tags=["browser"])

_explorer_service: ExplorerService | None = None
_asset_root: Path | None = None
_dense_index_cache: dict[str, dict[str, str]] = {}


def init_explorer(cfg: RAGConfig, retriever: HybridRetriever | None = None) -> None:
    global _explorer_service, _asset_root, _dense_index_cache
    if retriever is None:
        raise ValueError("Explorer initialization requires a retriever instance")
    repo = ExplorerRepository.from_paths(cfg.rag_root, cfg.corpus_root)
    _explorer_service = ExplorerService(repo, retriever)
    _asset_root = cfg.asset_root
    _dense_index_cache = {}


def _get_explorer() -> ExplorerService:
    if _explorer_service is None:
        raise HTTPException(503, "Explorer system not initialized. Run 'build' first.")
    return _explorer_service


def _get_asset_root() -> Path:
    if _asset_root is None:
        raise HTTPException(503, "Explorer assets are not initialized. Run 'build' first.")
    return _asset_root


def _load_dense_index(lesson_id: str) -> dict[str, str]:
    if lesson_id in _dense_index_cache:
        return _dense_index_cache[lesson_id]

    dense_index_path = _get_asset_root() / lesson_id / "dense_index.json"
    if not dense_index_path.exists():
        raise HTTPException(404, f"No dense frame index found for lesson {lesson_id!r}")

    payload = json.loads(dense_index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HTTPException(500, f"Invalid dense frame index for lesson {lesson_id!r}")

    dense_index = {
        str(frame_key): str(relative_path)
        for frame_key, relative_path in payload.items()
        if isinstance(relative_path, str)
    }
    _dense_index_cache[lesson_id] = dense_index
    return dense_index


def _frame_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return "application/octet-stream"


@explorer_router.get("/health")
def browser_health() -> dict[str, Any]:
    service = _get_explorer()
    return {
        "status": "ok",
        "rag_ready": True,
        "explorer_ready": True,
        "doc_count": service.doc_count,
        "corpus_contract_version": service.corpus_contract_version,
    }


@explorer_router.post("/search", response_model=BrowserSearchResponse)
def browser_search(req: BrowserSearchRequest) -> BrowserSearchResponse:
    return _get_explorer().search(req)


@explorer_router.get("/rule/{doc_id}", response_model=RuleDetailResponse)
def browser_rule(doc_id: str) -> RuleDetailResponse:
    service = _get_explorer()
    try:
        return service.get_rule_detail(doc_id)
    except KeyError:
        raise HTTPException(404, f"Document {doc_id!r} not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@explorer_router.get("/evidence/{doc_id}", response_model=EvidenceDetailResponse)
def browser_evidence(doc_id: str) -> EvidenceDetailResponse:
    service = _get_explorer()
    try:
        return service.get_evidence_detail(doc_id)
    except KeyError:
        raise HTTPException(404, f"Document {doc_id!r} not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@explorer_router.get("/frame/{lesson_id}/{frame_key}")
def browser_frame(lesson_id: str, frame_key: str) -> FileResponse:
    dense_index = _load_dense_index(lesson_id)
    relative_path = dense_index.get(frame_key)
    if not relative_path:
        raise HTTPException(404, f"Frame {frame_key!r} not found for lesson {lesson_id!r}")

    asset_root = _get_asset_root()
    lesson_root = (asset_root / lesson_id).resolve()
    resolved_path = (lesson_root / relative_path).resolve()
    try:
        resolved_path.relative_to(lesson_root)
    except ValueError as exc:
        raise HTTPException(400, "Resolved frame path escapes lesson root") from exc
    if not resolved_path.exists() or not resolved_path.is_file():
        raise HTTPException(404, f"Frame asset {frame_key!r} is missing for lesson {lesson_id!r}")
    return FileResponse(resolved_path, media_type=_frame_media_type(resolved_path))


@explorer_router.get("/concept/{concept_id}", response_model=ConceptDetailResponse)
def browser_concept(concept_id: str) -> ConceptDetailResponse:
    service = _get_explorer()
    try:
        return service.get_concept_detail(concept_id)
    except KeyError:
        raise HTTPException(404, f"Concept {concept_id!r} not found") from None


@explorer_router.get("/concept/{concept_id}/neighbors", response_model=list[ConceptNeighbor])
def browser_neighbors(concept_id: str) -> list[ConceptNeighbor]:
    return _get_explorer().get_neighbors(concept_id)


@explorer_router.get("/lesson/{lesson_id}", response_model=LessonDetailResponse)
def browser_lesson(lesson_id: str) -> LessonDetailResponse:
    service = _get_explorer()
    try:
        return service.get_lesson_detail(lesson_id)
    except KeyError:
        raise HTTPException(404, f"Lesson {lesson_id!r} not found") from None


@explorer_router.get("/facets")
def browser_facets(
    query: str | None = None,
    lesson_ids: list[str] = Query(default_factory=list),
    concept_ids: list[str] = Query(default_factory=list),
    unit_types: list[str] = Query(default_factory=list),
    support_basis: list[str] = Query(default_factory=list),
    evidence_requirement: list[str] = Query(default_factory=list),
    teaching_mode: list[str] = Query(default_factory=list),
    min_confidence_score: float | None = None,
) -> dict[str, dict[str, int]]:
    filters = BrowserSearchFilters(
        lesson_ids=lesson_ids,
        concept_ids=concept_ids,
        unit_types=unit_types,
        support_basis=support_basis,
        evidence_requirement=evidence_requirement,
        teaching_mode=teaching_mode,
        min_confidence_score=min_confidence_score,
    )
    return _get_explorer().get_facets(query=query, filters=filters)
