"""In-memory document store backed by JSONL persistence.

All retrieval docs are loaded into RAM at startup for maximum query speed
(32 GB available; ~1.4 GB projected at 250-lesson scale).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.rag.config import UnitType
from pipeline.rag.retrieval_docs import RetrievalDocBase


class DocStore:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self._by_unit: dict[str, list[str]] = {}
        self._by_lesson: dict[str, list[str]] = {}
        self._by_concept: dict[str, list[str]] = {}

    @property
    def doc_count(self) -> int:
        return len(self._docs)

    def add(self, doc: RetrievalDocBase) -> None:
        d = doc.model_dump()
        did = d["doc_id"]
        self._docs[did] = d
        self._by_unit.setdefault(d["unit_type"], []).append(did)
        self._by_lesson.setdefault(d["lesson_id"], []).append(did)
        for cid in d.get("canonical_concept_ids") or []:
            self._by_concept.setdefault(cid, []).append(did)

    def get(self, doc_id: str) -> dict[str, Any] | None:
        return self._docs.get(doc_id)

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._docs.values())

    def get_by_ids(self, doc_ids: list[str]) -> list[dict[str, Any]]:
        return [self._docs[did] for did in doc_ids if did in self._docs]

    def get_by_unit(self, unit_type: UnitType) -> list[dict[str, Any]]:
        return [self._docs[did] for did in self._by_unit.get(unit_type, []) if did in self._docs]

    def get_by_lesson(self, lesson_id: str) -> list[dict[str, Any]]:
        return [self._docs[did] for did in self._by_lesson.get(lesson_id, []) if did in self._docs]

    def get_by_concept(self, concept_id: str) -> list[dict[str, Any]]:
        return [self._docs[did] for did in self._by_concept.get(concept_id, []) if did in self._docs]

    def all_doc_ids(self) -> list[str]:
        return list(self._docs.keys())

    def unit_types(self) -> list[str]:
        return sorted(self._by_unit.keys())

    def lesson_ids(self) -> list[str]:
        return sorted(self._by_lesson.keys())

    def concept_ids(self) -> list[str]:
        return sorted(self._by_concept.keys())

    def filter_ids(
        self,
        unit_types: list[str] | None = None,
        lesson_ids: list[str] | None = None,
        concept_ids: list[str] | None = None,
        min_confidence: float | None = None,
    ) -> set[str]:
        candidates = set(self._docs.keys())
        if unit_types:
            allowed: set[str] = set()
            for ut in unit_types:
                allowed.update(self._by_unit.get(ut, []))
            candidates &= allowed
        if lesson_ids:
            allowed = set()
            for lid in lesson_ids:
                allowed.update(self._by_lesson.get(lid, []))
            candidates &= allowed
        if concept_ids:
            allowed = set()
            for cid in concept_ids:
                allowed.update(self._by_concept.get(cid, []))
            candidates &= allowed
        if min_confidence is not None:
            candidates = {
                did for did in candidates
                if (self._docs[did].get("confidence_score") or 0) >= min_confidence
            }
        return candidates

    def facets(self, doc_ids: set[str] | None = None) -> dict[str, dict[str, int]]:
        target = doc_ids if doc_ids is not None else set(self._docs.keys())
        by_unit: dict[str, int] = {}
        by_lesson: dict[str, int] = {}
        by_concept: dict[str, int] = {}
        for did in target:
            doc = self._docs.get(did)
            if not doc:
                continue
            ut = doc["unit_type"]
            by_unit[ut] = by_unit.get(ut, 0) + 1
            lid = doc["lesson_id"]
            by_lesson[lid] = by_lesson.get(lid, 0) + 1
            for cid in doc.get("canonical_concept_ids") or []:
                by_concept[cid] = by_concept.get(cid, 0) + 1
        return {
            "by_unit_type": by_unit,
            "by_lesson": by_lesson,
            "by_concept": by_concept,
        }

    # ── Persistence ──────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for doc in self._docs.values():
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Path) -> DocStore:
        store = cls()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                did = raw["doc_id"]
                store._docs[did] = raw
                store._by_unit.setdefault(raw["unit_type"], []).append(did)
                store._by_lesson.setdefault(raw["lesson_id"], []).append(did)
                for cid in raw.get("canonical_concept_ids") or []:
                    store._by_concept.setdefault(cid, []).append(did)
        return store
