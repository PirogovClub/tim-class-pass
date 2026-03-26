"""Validation checks for Stage 6.2 corpus outputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline.contracts.lesson_registry import load_registry_v1
from pipeline.contracts.registry_models import LessonRegistryEntryV1


def _registry_entry_ingested(entry: LessonRegistryEntryV1) -> bool:
    """Match corpus_builder._lessons_from_registry inclusion predicate."""
    return entry.status == "valid" and entry.validation_status != "failed"


def _parse_iso_timestamp(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


REQUIRED_CORPUS_OUTPUTS = (
    "corpus_rule_cards.jsonl",
    "corpus_knowledge_events.jsonl",
    "corpus_evidence_index.jsonl",
    "corpus_concept_graph.json",
)


@dataclass
class CorpusValidationResult:
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]

    @property
    def status(self) -> str:
        if self.errors:
            return "failed"
        if self.warnings:
            return "warning"
        return "passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_corpus_outputs(
    output_root: Path,
    *,
    lesson_registry_path: Path | None = None,
) -> CorpusValidationResult:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for name in REQUIRED_CORPUS_OUTPUTS:
        p = output_root / name
        if not p.exists():
            errors.append({"category": "missing_output", "message": f"Missing required output: {name}"})

    if errors:
        return CorpusValidationResult(errors=errors, warnings=warnings)

    rules = _read_jsonl(output_root / "corpus_rule_cards.jsonl")
    events = _read_jsonl(output_root / "corpus_knowledge_events.jsonl")
    evidence = _read_jsonl(output_root / "corpus_evidence_index.jsonl")
    graph = json.loads((output_root / "corpus_concept_graph.json").read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])

    event_ids = {x.get("global_id") for x in events}
    rule_ids = {x.get("global_id") for x in rules}
    evidence_ids = {x.get("global_id") for x in evidence}
    node_ids = {x.get("global_id") for x in nodes}

    def _check_unique(items: list[dict[str, Any]], key: str, kind: str) -> None:
        seen: set[str] = set()
        for row in items:
            gid = row.get(key)
            if not gid:
                errors.append({"category": "missing_id", "message": f"{kind} row missing {key}"})
                continue
            if gid in seen:
                errors.append({"category": "duplicate_id", "message": f"Duplicate {kind} id: {gid}"})
            seen.add(gid)

    _check_unique(events, "global_id", "event")
    _check_unique(rules, "global_id", "rule")
    _check_unique(evidence, "global_id", "evidence")
    _check_unique(nodes, "global_id", "node")

    meta_path = output_root / "corpus_metadata.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        gen_at = meta.get("generated_at")
        if not _parse_iso_timestamp(str(gen_at) if gen_at is not None else ""):
            errors.append({
                "category": "timestamp",
                "message": "corpus_metadata.generated_at missing or not ISO-8601",
            })

    for row in events:
        if row.get("corpus_event_id") and row["corpus_event_id"] != row.get("global_id"):
            errors.append({
                "category": "id_policy",
                "message": f"corpus_event_id must equal global_id for {row.get('global_id')}",
            })
        if "source_event_id" not in row:
            errors.append({"category": "provenance", "message": f"Event {row.get('global_id')} missing source_event_id"})
        if not row.get("source_knowledge_events_json"):
            errors.append({
                "category": "provenance",
                "message": f"Event {row.get('global_id')} missing source_knowledge_events_json",
            })

    for row in rules:
        if row.get("corpus_rule_id") and row["corpus_rule_id"] != row.get("global_id"):
            errors.append({
                "category": "id_policy",
                "message": f"corpus_rule_id must equal global_id for {row.get('global_id')}",
            })
        if row.get("source_rule_id") is None:
            errors.append({"category": "provenance", "message": f"Rule {row.get('global_id')} missing source_rule_id"})
        if not row.get("source_rule_cards_json"):
            errors.append({
                "category": "provenance",
                "message": f"Rule {row.get('global_id')} missing source_rule_cards_json",
            })
        if not row.get("lesson_id"):
            errors.append({"category": "provenance", "message": "Rule missing lesson_id"})
        if "source_event_ids" not in row or "evidence_refs" not in row:
            errors.append({"category": "provenance", "message": f"Rule {row.get('global_id')} missing provenance fields"})
        for eid in row.get("source_event_ids", []):
            if eid not in event_ids:
                errors.append({"category": "cross_ref", "message": f"Rule {row.get('global_id')} references missing event {eid}"})
        for rid in row.get("evidence_refs", []):
            if rid not in evidence_ids:
                errors.append({"category": "cross_ref", "message": f"Rule {row.get('global_id')} references missing evidence {rid}"})

    for row in evidence:
        if row.get("corpus_evidence_id") and row["corpus_evidence_id"] != row.get("global_id"):
            errors.append({
                "category": "id_policy",
                "message": f"corpus_evidence_id must equal global_id for {row.get('global_id')}",
            })
        if "source_evidence_id" not in row:
            errors.append({"category": "provenance", "message": f"Evidence {row.get('global_id')} missing source_evidence_id"})
        if not row.get("source_evidence_index_json"):
            errors.append({
                "category": "provenance",
                "message": f"Evidence {row.get('global_id')} missing source_evidence_index_json",
            })
        if not row.get("lesson_id"):
            errors.append({"category": "provenance", "message": "Evidence missing lesson_id"})
        for rid in row.get("linked_rule_ids", []):
            if rid not in rule_ids:
                errors.append({"category": "cross_ref", "message": f"Evidence {row.get('global_id')} references missing rule {rid}"})
        for cid in row.get("related_concept_ids", []):
            if cid not in node_ids:
                warnings.append({"category": "cross_ref", "message": f"Evidence {row.get('global_id')} references unknown concept {cid}"})

    for node in nodes:
        if not node.get("source_concept_graph_json"):
            errors.append({
                "category": "provenance",
                "message": f"Concept node {node.get('global_id')} missing source_concept_graph_json",
            })
    for rel in graph.get("relations", []):
        if not rel.get("source_concept_graph_json"):
            errors.append({
                "category": "provenance",
                "message": f"Concept relation {rel.get('relation_id')} missing source_concept_graph_json",
            })

    # Registry replay + record count roll-up (ingested lessons only)
    if lesson_registry_path is not None and lesson_registry_path.exists():
        reg = load_registry_v1(lesson_registry_path)
        ingestible = [x for x in reg.lessons if _registry_entry_ingested(x)]
        expected_lesson_ids = {x.lesson_id for x in ingestible}
        ingested_lessons: set[str] = set()
        for row in rules:
            lid = row.get("lesson_id")
            if lid:
                ingested_lessons.add(lid)
        for row in events:
            lid = row.get("lesson_id")
            if lid:
                ingested_lessons.add(lid)
        for row in evidence:
            lid = row.get("lesson_id")
            if lid:
                ingested_lessons.add(lid)
        missing = sorted(expected_lesson_ids - ingested_lessons)
        for lesson_id in missing:
            errors.append({
                "category": "registry_replay",
                "message": f"Ingestible registry lesson missing from corpus rows: {lesson_id}",
            })

        exp_events = sum(x.record_counts.get("knowledge_events", 0) for x in ingestible)
        exp_rules = sum(x.record_counts.get("rule_cards", 0) for x in ingestible)
        exp_evidence = sum(x.record_counts.get("evidence_index", 0) for x in ingestible)
        if exp_events != len(events):
            errors.append({
                "category": "registry_counts",
                "message": (
                    f"Knowledge event count mismatch: registry roll-up {exp_events} vs corpus {len(events)}"
                ),
            })
        if exp_rules != len(rules):
            errors.append({
                "category": "registry_counts",
                "message": f"Rule count mismatch: registry roll-up {exp_rules} vs corpus {len(rules)}",
            })
        if exp_evidence != len(evidence):
            errors.append({
                "category": "registry_counts",
                "message": (
                    f"Evidence count mismatch: registry roll-up {exp_evidence} vs corpus {len(evidence)}"
                ),
            })

    return CorpusValidationResult(errors=errors, warnings=warnings)


def corpus_output_fingerprints(output_root: Path) -> dict[str, str]:
    """Stable content fingerprints for determinism checks."""
    return {name: _sha256(output_root / name) for name in REQUIRED_CORPUS_OUTPUTS}

