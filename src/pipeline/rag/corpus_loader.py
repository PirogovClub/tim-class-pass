"""Load Step 2 corpus exports and transform them into retrieval documents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.rag.contracts import CorpusInputManifest, RAGBuildResult
from pipeline.rag.config import RAGConfig
from pipeline.rag.retrieval_docs import (
    ConceptNodeDoc,
    ConceptRelationDoc,
    EvidenceRefDoc,
    KnowledgeEventDoc,
    RuleCardDoc,
)
from pipeline.rag.metadata_sqlite import write_retrieval_metadata_sqlite
from pipeline.rag.store import InMemoryDocStore


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    if not isinstance(rows, list):
        raise ValueError(f"Expected JSONL list from {path}")
    return rows


def _write_jsonl(path: Path, docs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")


def write_build_metadata(path: Path, build_result: RAGBuildResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_result.model_dump_json(indent=2), encoding="utf-8")


def _append_unique_str(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _append_unique_timestamp(items: list[dict[str, Any]], value: dict[str, Any]) -> None:
    if not value:
        return
    if value not in items:
        items.append(value)


def _enrich_doc_links(
    store: InMemoryDocStore,
    alias_registry: dict[str, Any],
    overlap_report: list[dict[str, Any]],
) -> None:
    related_terms_by_concept: dict[str, list[str]] = {}
    for row in overlap_report:
        concept_id = row.get("concept_id")
        name = row.get("name")
        if concept_id and name:
            related_terms_by_concept.setdefault(concept_id, []).append(name)

    event_map = {doc["doc_id"]: doc for doc in store.get_by_unit("knowledge_event")}
    evidence_map = {doc["doc_id"]: doc for doc in store.get_by_unit("evidence_ref")}

    for doc in store.get_all():
        alias_terms = list(doc.get("alias_terms") or [])
        keywords = list(doc.get("keywords") or [])

        for concept_id in doc.get("canonical_concept_ids") or []:
            alias_info = alias_registry.get(concept_id, {})
            for term in alias_info.get("aliases") or []:
                _append_unique_str(alias_terms, term)
                _append_unique_str(keywords, term)
            if alias_info.get("name"):
                _append_unique_str(alias_terms, alias_info["name"])
                _append_unique_str(keywords, alias_info["name"])
            for related in related_terms_by_concept.get(concept_id, []):
                _append_unique_str(keywords, related)

        if doc.get("unit_type") == "rule_card":
            for event_id in doc.get("source_event_ids") or []:
                event_doc = event_map.get(event_id)
                if not event_doc:
                    continue
                for ts in event_doc.get("timestamps") or []:
                    _append_unique_timestamp(doc["timestamps"], ts)
                for evidence_id in event_doc.get("evidence_ids") or []:
                    _append_unique_str(doc["evidence_ids"], evidence_id)

        if doc.get("unit_type") in {"rule_card", "knowledge_event"}:
            for evidence_id in doc.get("evidence_ids") or []:
                evidence_doc = evidence_map.get(evidence_id)
                if not evidence_doc:
                    continue
                for ts in evidence_doc.get("timestamps") or []:
                    _append_unique_timestamp(doc["timestamps"], ts)

        doc["alias_terms"] = alias_terms
        doc["keywords"] = keywords


def load_corpus_and_build_docs(cfg: RAGConfig) -> InMemoryDocStore:
    """Load all Step 2 corpus exports, transform to retrieval docs."""
    manifest = CorpusInputManifest.from_root(cfg.corpus_root)
    store = InMemoryDocStore()

    frequencies = _read_json(manifest.path("concept_frequencies.json"))
    alias_registry = _read_json(manifest.path("concept_alias_registry.json"))
    overlap_report = _read_json(manifest.path("concept_overlap_report.json"))
    _read_json(manifest.path("schema_versions.json"))
    _read_json(manifest.path("lesson_registry.json"))
    _jsonl_rows(manifest.path("corpus_lessons.jsonl"))
    _read_json(manifest.path("rule_family_index.json"))
    _read_json(manifest.path("concept_rule_map.json"))
    _read_json(manifest.path("corpus_metadata.json"))

    rules = _jsonl_rows(manifest.path("corpus_rule_cards.jsonl"))
    for raw in rules:
        store.add(RuleCardDoc.from_corpus(raw))

    events = _jsonl_rows(manifest.path("corpus_knowledge_events.jsonl"))
    for raw in events:
        store.add(KnowledgeEventDoc.from_corpus(raw))

    evidence = _jsonl_rows(manifest.path("corpus_evidence_index.jsonl"))
    for raw in evidence:
        store.add(EvidenceRefDoc.from_corpus(raw))

    graph = _read_json(manifest.path("corpus_concept_graph.json"))
    node_name_map: dict[str, str] = {}
    for node in graph.get("nodes", []):
        node_name_map[node.get("global_id", "")] = node.get("name", "")
        store.add(ConceptNodeDoc.from_corpus(node, frequencies))

    for rel in graph.get("relations", []):
        store.add(ConceptRelationDoc.from_corpus(rel, node_name_map))

    _enrich_doc_links(store, alias_registry, overlap_report if isinstance(overlap_report, list) else [])
    return store


def build_and_persist(cfg: RAGConfig) -> dict[str, Any]:
    """Build retrieval docs from corpus and persist to output_rag/."""
    store = load_corpus_and_build_docs(cfg)
    cfg.rag_root.mkdir(parents=True, exist_ok=True)

    store.save(cfg.rag_root / "retrieval_docs_all.jsonl")

    output_map = {
        "rule_card": cfg.rag_root / "retrieval_docs_rule_cards.jsonl",
        "knowledge_event": cfg.rag_root / "retrieval_docs_knowledge_events.jsonl",
        "evidence_ref": cfg.rag_root / "retrieval_docs_evidence_refs.jsonl",
        "concept_node": cfg.rag_root / "retrieval_docs_concept_nodes.jsonl",
        "concept_relation": cfg.rag_root / "retrieval_docs_concept_relations.jsonl",
    }
    for unit_type, path in output_map.items():
        _write_jsonl(path, store.get_by_unit(unit_type))  # type: ignore[arg-type]

    concept_docs = store.get_by_unit("concept_node") + store.get_by_unit("concept_relation")
    _write_jsonl(cfg.rag_root / "retrieval_docs_concepts.jsonl", concept_docs)

    corpus_meta: dict[str, Any] = {}
    meta_path = cfg.corpus_root / "corpus_metadata.json"
    if meta_path.exists():
        corpus_meta = _read_json(meta_path)

    schema_versions_blob: dict[str, Any] = {}
    sv_path = cfg.corpus_root / "schema_versions.json"
    if sv_path.exists():
        raw_sv = _read_json(sv_path)
        if isinstance(raw_sv, dict):
            schema_versions_blob = raw_sv

    build_result = RAGBuildResult(
        corpus_contract_version=corpus_meta.get("corpus_contract_version", "unknown"),
        source_corpus_root=cfg.corpus_root,
        retrieval_doc_counts={ut: len(store.get_by_unit(ut)) for ut in store.unit_types()},  # type: ignore[arg-type]
        total_retrieval_docs=store.doc_count,
        build_timestamp=datetime.now(timezone.utc),
    )
    write_build_metadata(cfg.rag_root / "rag_build_metadata.json", build_result)

    write_retrieval_metadata_sqlite(
        store,
        cfg.rag_root / "rag_metadata.sqlite",
        corpus_contract_version=str(corpus_meta.get("corpus_contract_version", "unknown")),
        schema_versions_blob=schema_versions_blob,
        embedding_model_version=cfg.embedding_model,
    )

    return build_result.model_dump(mode="json")
