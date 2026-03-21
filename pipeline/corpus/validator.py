"""Per-lesson and cross-lesson validation for the corpus build.

Produces a validation_report.json with errors and warnings.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pipeline.corpus.adapters import (
    ARTIFACT_SUFFIXES,
    find_artifact,
    load_lesson_concept_graph,
    load_lesson_evidence_index,
    load_lesson_knowledge_events,
    load_lesson_rule_cards,
)
from pipeline.corpus.contracts import LessonRecord
from pipeline.corpus.id_utils import make_global_id, make_global_node_id


class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def add_error(self, lesson_id: str, category: str, message: str) -> None:
        self.errors.append({"lesson_id": lesson_id, "category": category, "message": message})

    def add_warning(self, lesson_id: str, category: str, message: str) -> None:
        self.warnings.append({"lesson_id": lesson_id, "category": category, "message": message})

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def status(self) -> str:
        if self.errors:
            return "invalid"
        if self.warnings:
            return "warning"
        return "valid"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_lesson(lesson: LessonRecord, strict: bool = False) -> ValidationResult:
    """Validate a single lesson's artifacts against the v1 contract."""
    result = ValidationResult()
    lid = lesson.lesson_id

    for artifact_name, suffix in ARTIFACT_SUFFIXES.items():
        if not lesson.available_artifacts.get(artifact_name):
            if artifact_name == "concept_graph":
                result.add_warning(lid, "missing_artifact", f"Optional artifact missing: {artifact_name}")
            else:
                result.add_error(lid, "missing_artifact", f"Required artifact missing: {artifact_name}")
            continue

        artifact_path = Path(lesson.artifact_paths[artifact_name])
        if not artifact_path.exists():
            result.add_error(lid, "file_not_found", f"File not found: {artifact_path}")
            continue

        try:
            raw = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            result.add_error(lid, "json_parse", f"Failed to parse {artifact_name}: {exc}")
            continue

        try:
            if artifact_name == "knowledge_events":
                col = load_lesson_knowledge_events(artifact_path)
                if not col.events:
                    result.add_warning(lid, "empty_artifact", "knowledge_events.json has 0 events")
                for ev in col.events:
                    if not ev.event_id:
                        result.add_error(lid, "missing_id", "KnowledgeEvent with empty event_id")
            elif artifact_name == "rule_cards":
                col = load_lesson_rule_cards(artifact_path)
                if not col.rules:
                    result.add_warning(lid, "empty_artifact", "rule_cards.json has 0 rules")
                for rc in col.rules:
                    if not rc.rule_id:
                        result.add_error(lid, "missing_id", "RuleCard with empty rule_id")
            elif artifact_name == "evidence_index":
                idx = load_lesson_evidence_index(artifact_path)
                if not idx.evidence_refs:
                    result.add_warning(lid, "empty_artifact", "evidence_index.json has 0 evidence refs")
                for ev in idx.evidence_refs:
                    if not ev.evidence_id:
                        result.add_error(lid, "missing_id", "EvidenceRef with empty evidence_id")
            elif artifact_name == "concept_graph":
                cg = load_lesson_concept_graph(artifact_path)
                if not cg.nodes:
                    result.add_warning(lid, "empty_artifact", "concept_graph.json has 0 nodes")
        except ValidationError as exc:
            result.add_error(lid, "schema_validation", f"Schema validation failed for {artifact_name}: {exc}")

    _check_intra_lesson_integrity(lesson, result)

    if strict:
        for w in list(result.warnings):
            result.errors.append(w)
        result.warnings.clear()

    return result


def _check_intra_lesson_integrity(lesson: LessonRecord, result: ValidationResult) -> None:
    """Check referential integrity within a single lesson."""
    lid = lesson.lesson_id

    event_ids: set[str] = set()
    rule_ids: set[str] = set()
    evidence_ids: set[str] = set()

    ke_path = lesson.artifact_paths.get("knowledge_events")
    if ke_path and Path(ke_path).exists():
        try:
            col = load_lesson_knowledge_events(Path(ke_path))
            event_ids = {ev.event_id for ev in col.events}
        except Exception:
            pass

    rc_path = lesson.artifact_paths.get("rule_cards")
    if rc_path and Path(rc_path).exists():
        try:
            col = load_lesson_rule_cards(Path(rc_path))
            rule_ids = {rc.rule_id for rc in col.rules}
        except Exception:
            pass

    ei_path = lesson.artifact_paths.get("evidence_index")
    if ei_path and Path(ei_path).exists():
        try:
            idx = load_lesson_evidence_index(Path(ei_path))
            evidence_ids = {ev.evidence_id for ev in idx.evidence_refs}
        except Exception:
            pass

    if rc_path and Path(rc_path).exists():
        try:
            col = load_lesson_rule_cards(Path(rc_path))
            for rc in col.rules:
                for eid in rc.source_event_ids:
                    if eid and eid not in event_ids:
                        result.add_warning(lid, "integrity", f"Rule {rc.rule_id} references unknown event {eid}")
                for eid in rc.evidence_refs:
                    if eid and eid not in evidence_ids:
                        result.add_warning(lid, "integrity", f"Rule {rc.rule_id} references unknown evidence {eid}")
                if not rc.evidence_refs:
                    result.add_warning(lid, "no_evidence", f"Rule {rc.rule_id} has no evidence_refs")
        except Exception:
            pass

    if ei_path and Path(ei_path).exists():
        try:
            idx = load_lesson_evidence_index(Path(ei_path))
            for ev in idx.evidence_refs:
                for rid in ev.linked_rule_ids:
                    if rid and rid not in rule_ids:
                        result.add_warning(lid, "integrity", f"Evidence {ev.evidence_id} references unknown rule {rid}")
                if not ev.linked_rule_ids:
                    result.add_warning(lid, "no_linked_rules", f"Evidence {ev.evidence_id} has no linked_rule_ids")
        except Exception:
            pass


def validate_cross_lesson(
    lessons: list[LessonRecord],
    global_events: list[dict],
    global_rules: list[dict],
    global_evidence: list[dict],
    global_nodes: list[dict],
    global_relations: list[dict],
) -> ValidationResult:
    """Check cross-lesson constraints: ID collisions, referential integrity."""
    result = ValidationResult()

    lesson_ids = [lr.lesson_id for lr in lessons]
    dupes = [lid for lid, cnt in Counter(lesson_ids).items() if cnt > 1]
    for d in dupes:
        result.add_error(d, "duplicate_lesson", f"Duplicate lesson_id: {d}")

    event_gids: set[str] = set()
    for ev in global_events:
        gid = ev.get("global_id", "")
        if gid in event_gids:
            result.add_error(ev.get("lesson_id", "?"), "duplicate_global_id", f"Duplicate global event ID: {gid}")
        event_gids.add(gid)

    rule_gids: set[str] = set()
    for rc in global_rules:
        gid = rc.get("global_id", "")
        if gid in rule_gids:
            result.add_error(rc.get("lesson_id", "?"), "duplicate_global_id", f"Duplicate global rule ID: {gid}")
        rule_gids.add(gid)

    evidence_gids: set[str] = set()
    for ev in global_evidence:
        gid = ev.get("global_id", "")
        if gid in evidence_gids:
            result.add_error(ev.get("lesson_id", "?"), "duplicate_global_id", f"Duplicate global evidence ID: {gid}")
        evidence_gids.add(gid)

    for rc in global_rules:
        for eid in rc.get("source_event_ids", []):
            if eid not in event_gids:
                result.add_warning(
                    rc.get("lesson_id", "?"), "cross_ref",
                    f"Rule {rc.get('global_id')} references missing global event {eid}",
                )
        for eid in rc.get("evidence_refs", []):
            if eid not in evidence_gids:
                result.add_warning(
                    rc.get("lesson_id", "?"), "cross_ref",
                    f"Rule {rc.get('global_id')} references missing global evidence {eid}",
                )

    for ev in global_evidence:
        for rid in ev.get("linked_rule_ids", []):
            if rid not in rule_gids:
                result.add_warning(
                    ev.get("lesson_id", "?"), "cross_ref",
                    f"Evidence {ev.get('global_id')} references missing global rule {rid}",
                )

    node_gids = {n.get("global_id", "") for n in global_nodes}
    for rel in global_relations:
        src = rel.get("source_id", "")
        dst = rel.get("target_id", "")
        if src not in node_gids:
            result.add_error("corpus", "graph_integrity", f"Relation source {src} not in node set")
        if dst not in node_gids:
            result.add_error("corpus", "graph_integrity", f"Relation target {dst} not in node set")

    return result


def save_validation_report(report: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
