"""Validation checks for Stage 6.2 corpus outputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.contracts.lesson_registry import load_registry_v1


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

    for row in rules:
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
        if not row.get("lesson_id"):
            errors.append({"category": "provenance", "message": "Evidence missing lesson_id"})
        for rid in row.get("linked_rule_ids", []):
            if rid not in rule_ids:
                errors.append({"category": "cross_ref", "message": f"Evidence {row.get('global_id')} references missing rule {rid}"})
        for cid in row.get("related_concept_ids", []):
            if cid not in node_ids:
                warnings.append({"category": "cross_ref", "message": f"Evidence {row.get('global_id')} references unknown concept {cid}"})

    # Registry replay checks
    if lesson_registry_path is not None and lesson_registry_path.exists():
        reg = load_registry_v1(lesson_registry_path)
        valid_lessons = {x.lesson_id for x in reg.lessons if x.status == "valid"}
        ingested_lessons = {x.get("lesson_id") for x in rules if x.get("lesson_id")}
        missing = sorted(valid_lessons - ingested_lessons)
        for lesson_id in missing:
            errors.append({"category": "registry_replay", "message": f"Valid registry lesson missing from corpus: {lesson_id}"})

    return CorpusValidationResult(errors=errors, warnings=warnings)


def corpus_output_fingerprints(output_root: Path) -> dict[str, str]:
    """Stable content fingerprints for determinism checks."""
    return {name: _sha256(output_root / name) for name in REQUIRED_CORPUS_OUTPUTS}

