"""Read-only repository layer for the Step 4.1 explorer backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.rag.store import InMemoryDocStore


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _concept_suffix(value: str) -> str:
    raw = value.strip()
    if ":" in raw:
        return raw.split(":", 1)[1]
    return raw


def _concept_keys(value: str) -> set[str]:
    raw = value.strip().lower()
    if not raw:
        return set()
    suffix = _concept_suffix(raw)
    return {raw, suffix}


def _sort_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        docs,
        key=lambda doc: (
            -(doc.get("confidence_score") or 0.0),
            str(doc.get("lesson_id") or ""),
            str(doc.get("doc_id") or ""),
        ),
    )


class ExplorerRepository:
    def __init__(
        self,
        *,
        store: InMemoryDocStore,
        concept_neighbors: dict[str, list[dict[str, Any]]],
        alias_registry: dict[str, dict[str, Any]],
        lesson_registry: dict[str, dict[str, Any]],
        concept_rule_map: dict[str, list[str]],
        rule_family_index: dict[str, list[str]],
        concept_meta: dict[str, dict[str, Any]],
        corpus_contract_version: str,
    ) -> None:
        self._store = store
        self._concept_neighbors = concept_neighbors
        self._alias_registry = alias_registry
        self._lesson_registry = lesson_registry
        self._concept_rule_map = concept_rule_map
        self._rule_family_index = rule_family_index
        self._concept_meta = concept_meta
        self.corpus_contract_version = corpus_contract_version

        self._docs_by_concept_key: dict[str, set[str]] = {}
        self._docs_by_rule_source: dict[str, set[str]] = {}
        self._docs_by_event_source: dict[str, set[str]] = {}
        self._rule_family_by_rule: dict[str, set[str]] = {}
        self._rule_to_family_names: dict[str, set[str]] = {}
        self._rule_ids_by_family: dict[str, set[str]] = {}

        for family_name, family_rule_ids in rule_family_index.items():
            family_set = set(family_rule_ids)
            self._rule_ids_by_family[str(family_name)] = family_set
            for rule_id in family_set:
                self._rule_family_by_rule.setdefault(rule_id, set()).update(family_set - {rule_id})
                self._rule_to_family_names.setdefault(rule_id, set()).add(str(family_name))

        for doc in store.get_all():
            doc_id = str(doc.get("doc_id") or "")
            for concept_id in (doc.get("canonical_concept_ids") or []) + (doc.get("canonical_subconcept_ids") or []):
                for key in _concept_keys(str(concept_id)):
                    self._docs_by_concept_key.setdefault(key, set()).add(doc_id)
            for rule_id in doc.get("source_rule_ids") or []:
                self._docs_by_rule_source.setdefault(str(rule_id), set()).add(doc_id)
            for event_id in doc.get("source_event_ids") or []:
                self._docs_by_event_source.setdefault(str(event_id), set()).add(doc_id)

    @property
    def doc_count(self) -> int:
        return self._store.doc_count

    @classmethod
    def from_paths(cls, rag_root: Path, corpus_root: Path) -> "ExplorerRepository":
        store = InMemoryDocStore.load(rag_root / "retrieval_docs_all.jsonl")

        corpus_metadata = _load_json(corpus_root / "corpus_metadata.json")
        lesson_rows = _load_json(corpus_root / "lesson_registry.json")
        alias_registry_raw = _load_json(corpus_root / "concept_alias_registry.json")
        concept_rule_map_raw = _load_json(corpus_root / "concept_rule_map.json")
        rule_family_index = _load_json(corpus_root / "rule_family_index.json")
        concept_graph = _load_json(corpus_root / "corpus_concept_graph.json")

        lesson_registry: dict[str, dict[str, Any]] = {}
        for row in lesson_rows:
            if not isinstance(row, dict):
                continue
            lesson_id = str(row.get("lesson_id") or "")
            lesson_slug = str(row.get("lesson_slug") or "")
            if lesson_id:
                lesson_registry[lesson_id] = row
            if lesson_slug:
                lesson_registry[lesson_slug] = row

        alias_registry: dict[str, dict[str, Any]] = {}
        for concept_id, payload in alias_registry_raw.items():
            concept_id = str(concept_id)
            for key in _concept_keys(concept_id):
                alias_registry[key] = payload

        concept_rule_map: dict[str, list[str]] = {}
        for concept_id, rule_ids in concept_rule_map_raw.items():
            normalized_ids = [str(rule_id) for rule_id in rule_ids]
            for key in _concept_keys(str(concept_id)):
                concept_rule_map[key] = normalized_ids

        concept_meta: dict[str, dict[str, Any]] = {}
        concept_neighbors: dict[str, list[dict[str, Any]]] = {}
        for node in concept_graph.get("nodes") or []:
            node_id = str(node.get("global_id") or "")
            if not node_id:
                continue
            meta = {
                "concept_id": node_id,
                "name": node.get("name") or node_id,
                "type": node.get("type") or "",
                "aliases": list(node.get("aliases") or []),
                "source_lessons": list(node.get("source_lessons") or []),
            }
            for key in _concept_keys(node_id):
                concept_meta[key] = meta

        for relation in concept_graph.get("relations") or []:
            source_id = str(relation.get("source_id") or "")
            target_id = str(relation.get("target_id") or "")
            relation_type = str(relation.get("relation_type") or "")
            weight = relation.get("weight")
            if source_id:
                neighbor = {
                    "concept_id": target_id,
                    "relation": relation_type,
                    "direction": "outgoing",
                    "weight": weight,
                }
                for key in _concept_keys(source_id):
                    concept_neighbors.setdefault(key, []).append(neighbor)
            if target_id:
                neighbor = {
                    "concept_id": source_id,
                    "relation": relation_type,
                    "direction": "incoming",
                    "weight": weight,
                }
                for key in _concept_keys(target_id):
                    concept_neighbors.setdefault(key, []).append(neighbor)

        return cls(
            store=store,
            concept_neighbors=concept_neighbors,
            alias_registry=alias_registry,
            lesson_registry=lesson_registry,
            concept_rule_map=concept_rule_map,
            rule_family_index=rule_family_index,
            concept_meta=concept_meta,
            corpus_contract_version=str(corpus_metadata.get("corpus_contract_version") or "unknown"),
        )

    def get_all_docs(self) -> list[dict[str, Any]]:
        return _sort_docs(self._store.get_all())

    def get_doc(self, doc_id: str) -> dict[str, Any] | None:
        return self._store.get(doc_id)

    def get_docs_by_ids(self, doc_ids: list[str]) -> list[dict[str, Any]]:
        docs = [doc for doc in self._store.get_by_ids(doc_ids) if doc is not None]
        return _sort_docs(docs)

    def get_docs_by_lesson(self, lesson_id: str) -> list[dict[str, Any]]:
        return _sort_docs(self._store.get_by_lesson(lesson_id))

    def get_docs_by_concept(self, concept_id: str) -> list[dict[str, Any]]:
        collected_ids: set[str] = set()
        for key in _concept_keys(concept_id):
            collected_ids.update(self._docs_by_concept_key.get(key, set()))
            rule_ids = self._concept_rule_map.get(key, [])
            collected_ids.update(rule_ids)
            for rule_id in rule_ids:
                collected_ids.update(self._docs_by_rule_source.get(rule_id, set()))
        docs = [doc for doc in self._store.get_by_ids(sorted(collected_ids)) if doc is not None]
        return _sort_docs(docs)

    def get_concept_aliases(self, concept_id: str) -> list[str]:
        for key in _concept_keys(concept_id):
            payload = self._alias_registry.get(key)
            if payload:
                aliases = [str(alias) for alias in payload.get("aliases") or []]
                name = str(payload.get("name") or "")
                return [value for value in [name, *aliases] if value]
        return []

    def get_concept_meta(self, concept_id: str) -> dict[str, Any] | None:
        for key in _concept_keys(concept_id):
            payload = self._concept_meta.get(key)
            if payload:
                return payload
        return None

    def get_concept_neighbors(self, concept_id: str) -> list[dict[str, Any]]:
        neighbors: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for key in _concept_keys(concept_id):
            for neighbor in self._concept_neighbors.get(key, []):
                dedupe_key = (
                    str(neighbor.get("concept_id") or ""),
                    str(neighbor.get("relation") or ""),
                    str(neighbor.get("direction") or ""),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                neighbors.append(dict(neighbor))
        return sorted(
            neighbors,
            key=lambda item: (
                str(item.get("direction") or ""),
                str(item.get("relation") or ""),
                str(item.get("concept_id") or ""),
            ),
        )

    def get_related_rule_docs(self, doc: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        related_ids: set[str] = set()
        doc_id = str(doc.get("doc_id") or "")
        related_ids.update(str(rule_id) for rule_id in doc.get("source_rule_ids") or [])
        if doc.get("unit_type") == "rule_card" and doc_id:
            related_ids.add(doc_id)
            related_ids.update(self._rule_family_by_rule.get(doc_id, set()))
        for concept_id in (doc.get("canonical_concept_ids") or []) + (doc.get("canonical_subconcept_ids") or []):
            for key in _concept_keys(str(concept_id)):
                related_ids.update(self._concept_rule_map.get(key, []))
        related_ids.discard(doc_id)
        docs = [
            candidate
            for candidate in self._store.get_by_ids(sorted(related_ids))
            if candidate.get("unit_type") == "rule_card"
        ]
        return _sort_docs(docs)[:limit]

    def get_rules_in_family(self, rule_id: str) -> list[dict[str, Any]]:
        docs = [
            candidate
            for candidate in self._store.get_by_ids(sorted(self._rule_family_by_rule.get(rule_id, set())))
            if candidate.get("unit_type") == "rule_card"
        ]
        return _sort_docs(docs)

    def get_rules_for_concept(self, concept_id: str) -> list[dict[str, Any]]:
        return [
            doc
            for doc in self.get_docs_by_concept(concept_id)
            if doc.get("unit_type") == "rule_card"
        ]

    def get_lessons_for_concept(self, concept_id: str) -> list[str]:
        lesson_ids = {
            str(doc.get("lesson_id") or "")
            for doc in self.get_rules_for_concept(concept_id)
            if doc.get("lesson_id")
        }
        meta = self.get_concept_meta(concept_id) or {}
        lesson_ids.update(str(lesson_id) for lesson_id in meta.get("source_lessons") or [] if lesson_id)
        return sorted(lesson_ids)

    def get_rule_family_names(self, rule_id: str) -> list[str]:
        return sorted(self._rule_to_family_names.get(rule_id, set()))

    def get_concept_overlap_between_lessons(self, lesson_ids: list[str]) -> dict[str, list[str]]:
        concept_to_lessons: dict[str, set[str]] = {}
        lesson_set = {str(lesson_id) for lesson_id in lesson_ids}
        concept_ids = {
            str(meta.get("concept_id") or "")
            for meta in self._concept_meta.values()
            if str(meta.get("concept_id") or "").startswith("node:")
        }
        concept_ids.update(
            key
            for key in self._concept_rule_map.keys()
            if str(key).startswith("node:")
        )
        for concept_id in concept_ids:
            concept_lessons = {
                str(doc.get("lesson_id") or "")
                for doc in self.get_rules_for_concept(concept_id)
                if doc.get("lesson_id") in lesson_set
            }
            if concept_lessons:
                concept_to_lessons[concept_id] = concept_lessons
        return {
            concept_id: sorted(overlap_lessons)
            for concept_id, overlap_lessons in sorted(concept_to_lessons.items())
            if len(overlap_lessons) > 1
        }

    def get_rule_overlap_between_lessons(self, lesson_ids: list[str]) -> dict[str, list[str]]:
        overlap: dict[str, set[str]] = {}
        lesson_set = {str(lesson_id) for lesson_id in lesson_ids}
        for family_name, rule_ids in self._rule_ids_by_family.items():
            family_lessons = {
                str(doc.get("lesson_id") or "")
                for doc in self._store.get_by_ids(sorted(rule_ids))
                if doc.get("unit_type") == "rule_card" and doc.get("lesson_id") in lesson_set
            }
            if len(family_lessons) > 1:
                overlap[family_name] = family_lessons
        return {family_name: sorted(family_lessons) for family_name, family_lessons in sorted(overlap.items())}

    def get_related_rule_docs_grouped(self, doc_id: str) -> dict[str, list[dict[str, Any]]]:
        doc = self.get_doc(doc_id)
        if doc is None:
            raise KeyError(doc_id)
        if doc.get("unit_type") != "rule_card":
            raise ValueError("Document is not a rule_card")

        grouped_ids: dict[str, set[str]] = {
            "same_concept": set(),
            "same_family": set(),
            "same_lesson": set(),
            "linked_by_evidence": set(),
            "cross_lesson_overlap": set(),
        }

        source_lesson_id = str(doc.get("lesson_id") or "")

        for lesson_doc in self.get_docs_by_lesson(source_lesson_id):
            lesson_doc_id = str(lesson_doc.get("doc_id") or "")
            if lesson_doc.get("unit_type") == "rule_card" and lesson_doc_id and lesson_doc_id != doc_id:
                grouped_ids["same_lesson"].add(lesson_doc_id)

        for related_doc in self.get_related_rule_docs(doc, limit=max(self.doc_count, 10)):
            related_doc_id = str(related_doc.get("doc_id") or "")
            if not related_doc_id:
                continue
            if related_doc.get("lesson_id") != source_lesson_id:
                grouped_ids["cross_lesson_overlap"].add(related_doc_id)

        for family_doc in self.get_rules_in_family(doc_id):
            grouped_ids["same_family"].add(str(family_doc.get("doc_id") or ""))

        source_concepts = {
            key
            for concept_id in (doc.get("canonical_concept_ids") or []) + (doc.get("canonical_subconcept_ids") or [])
            for key in _concept_keys(str(concept_id))
        }
        for concept_doc in self.get_related_rule_docs(doc, limit=max(self.doc_count, 10)):
            concept_doc_id = str(concept_doc.get("doc_id") or "")
            concept_keys = {
                key
                for concept_id in (concept_doc.get("canonical_concept_ids") or []) + (concept_doc.get("canonical_subconcept_ids") or [])
                for key in _concept_keys(str(concept_id))
            }
            if source_concepts & concept_keys:
                grouped_ids["same_concept"].add(concept_doc_id)

        for evidence_doc in self.get_evidence_docs_for_rule(doc):
            for rule_id in (evidence_doc.get("source_rule_ids") or []) + (evidence_doc.get("linked_rule_ids") or []):
                if str(rule_id) != doc_id:
                    grouped_ids["linked_by_evidence"].add(str(rule_id))

        cleaned_groups: dict[str, list[dict[str, Any]]] = {}
        for reason, ids in grouped_ids.items():
            ids.discard(doc_id)
            docs = [
                candidate
                for candidate in self._store.get_by_ids(sorted(ids))
                if candidate.get("unit_type") == "rule_card"
            ]
            if docs:
                cleaned_groups[reason] = _sort_docs(docs)
        return cleaned_groups

    def get_related_event_docs(self, doc: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        related_ids: set[str] = set()
        doc_id = str(doc.get("doc_id") or "")
        related_ids.update(str(event_id) for event_id in doc.get("source_event_ids") or [])
        for concept_id in (doc.get("canonical_concept_ids") or []) + (doc.get("canonical_subconcept_ids") or []):
            for key in _concept_keys(str(concept_id)):
                related_ids.update(self._docs_by_concept_key.get(key, set()))
        related_ids.discard(doc_id)
        docs = [
            candidate
            for candidate in self._store.get_by_ids(sorted(related_ids))
            if candidate.get("unit_type") == "knowledge_event"
        ]
        return _sort_docs(docs)[:limit]

    def get_evidence_docs_for_rule(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        related_ids: set[str] = set(str(evidence_id) for evidence_id in doc.get("evidence_ids") or [])
        doc_id = str(doc.get("doc_id") or "")
        if doc_id:
            related_ids.update(self._docs_by_rule_source.get(doc_id, set()))
        docs = [
            candidate
            for candidate in self._store.get_by_ids(sorted(related_ids))
            if candidate.get("unit_type") == "evidence_ref"
        ]
        return _sort_docs(docs)

    def get_source_event_docs_for_rule(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        docs = self._store.get_by_ids([str(event_id) for event_id in doc.get("source_event_ids") or []])
        return _sort_docs([candidate for candidate in docs if candidate.get("unit_type") == "knowledge_event"])

    def get_source_rule_docs_for_evidence(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        docs = self._store.get_by_ids([str(rule_id) for rule_id in doc.get("source_rule_ids") or []])
        return _sort_docs([candidate for candidate in docs if candidate.get("unit_type") == "rule_card"])

    def get_source_event_docs_for_evidence(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        docs = self._store.get_by_ids([str(event_id) for event_id in doc.get("source_event_ids") or []])
        return _sort_docs([candidate for candidate in docs if candidate.get("unit_type") == "knowledge_event"])

    def get_evidence_docs_for_event(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        docs = self._store.get_by_ids([str(eid) for eid in doc.get("evidence_refs") or []])
        return _sort_docs([c for c in docs if c.get("unit_type") == "evidence_ref"])

    def get_linked_rule_docs_for_event(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        rule_ids: set[str] = set()
        for ev in self.get_evidence_docs_for_event(doc):
            rule_ids.update(str(rid) for rid in ev.get("source_rule_ids") or [])
            rule_ids.update(str(rid) for rid in ev.get("linked_rule_ids") or [])
        docs = self._store.get_by_ids(sorted(rule_ids))
        return _sort_docs([c for c in docs if c.get("unit_type") == "rule_card"])

    def get_linked_event_docs_for_event(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        docs = self._store.get_by_ids([str(eid) for eid in doc.get("source_event_ids") or []])
        return _sort_docs([c for c in docs if c.get("unit_type") == "knowledge_event"])

    def get_lesson_meta(self, lesson_id: str) -> dict[str, Any] | None:
        return self._lesson_registry.get(lesson_id)
