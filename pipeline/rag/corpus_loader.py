"""Load Step 2 corpus exports and transform into retrieval documents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.rag.config import RAGConfig
from pipeline.rag.retrieval_docs import (
    ConceptNodeDoc,
    ConceptRelationDoc,
    EvidenceRefDoc,
    KnowledgeEventDoc,
    RetrievalDocBase,
    RuleCardDoc,
)
from pipeline.rag.store import DocStore


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


def _validate_corpus(root: Path) -> None:
    required = [
        "corpus_knowledge_events.jsonl",
        "corpus_rule_cards.jsonl",
        "corpus_evidence_index.jsonl",
        "corpus_concept_graph.json",
        "concept_alias_registry.json",
        "concept_rule_map.json",
        "corpus_metadata.json",
    ]
    for name in required:
        if not (root / name).exists():
            raise FileNotFoundError(f"Missing required corpus file: {root / name}")


def load_corpus_and_build_docs(cfg: RAGConfig) -> DocStore:
    """Load all Step 2 corpus exports, transform to retrieval docs."""
    _validate_corpus(cfg.corpus_root)
    store = DocStore()

    frequencies = _read_json(cfg.corpus_root / "concept_frequencies.json") if (cfg.corpus_root / "concept_frequencies.json").exists() else {}

    rules = _read_jsonl(cfg.corpus_root / "corpus_rule_cards.jsonl")
    for raw in rules:
        store.add(RuleCardDoc.from_corpus(raw))

    events = _read_jsonl(cfg.corpus_root / "corpus_knowledge_events.jsonl")
    for raw in events:
        store.add(KnowledgeEventDoc.from_corpus(raw))

    evidence = _read_jsonl(cfg.corpus_root / "corpus_evidence_index.jsonl")
    for raw in evidence:
        store.add(EvidenceRefDoc.from_corpus(raw))

    graph = _read_json(cfg.corpus_root / "corpus_concept_graph.json")
    node_name_map: dict[str, str] = {}
    for node in graph.get("nodes", []):
        node_name_map[node.get("global_id", "")] = node.get("name", "")
        store.add(ConceptNodeDoc.from_corpus(node, frequencies))

    for rel in graph.get("relations", []):
        store.add(ConceptRelationDoc.from_corpus(rel, node_name_map))

    return store


def build_and_persist(cfg: RAGConfig) -> dict[str, Any]:
    """Build retrieval docs from corpus and persist to output_rag/."""
    store = load_corpus_and_build_docs(cfg)
    cfg.rag_root.mkdir(parents=True, exist_ok=True)

    store.save(cfg.rag_root / "retrieval_docs_all.jsonl")

    for ut in store.unit_types():
        docs = store.get_by_unit(ut)  # type: ignore[arg-type]
        out_path = cfg.rag_root / f"retrieval_docs_{ut}s.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    corpus_meta = {}
    meta_path = cfg.corpus_root / "corpus_metadata.json"
    if meta_path.exists():
        corpus_meta = _read_json(meta_path)

    build_meta = {
        "corpus_contract_version": corpus_meta.get("corpus_contract_version", "unknown"),
        "source_corpus_root": str(cfg.corpus_root),
        "retrieval_doc_counts": {ut: len(store.get_by_unit(ut)) for ut in store.unit_types()},  # type: ignore[arg-type]
        "total_retrieval_docs": store.doc_count,
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (cfg.rag_root / "rag_build_metadata.json").write_text(
        json.dumps(build_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return build_meta
