"""Corpus-level validation for frozen lesson contract v1 (Stage 6.1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pipeline.contracts.contract_models import REQUIRED_ARTIFACT_FILENAMES
from pipeline.contracts.registry_models import LessonRegistryEntryV1, LessonRegistryFileV1
from pipeline.contracts.versioning import load_schema_versions, validate_version_map
from pipeline.corpus.adapters import (
    load_lesson_concept_graph,
    load_lesson_evidence_index,
    load_lesson_knowledge_events,
    load_lesson_rule_cards,
)
from pipeline.corpus.contracts import LessonRecord, RuleCardCollection


def _timestamp_nonempty(value: str | None) -> bool:
    return bool(value and str(value).strip())


def _check_timestamps_contract_v1(
    o: ContractValidationOutcome,
    ke_col: Any,
    rc_col: Any,
    ei: Any,
) -> None:
    """§6.1 / §10.2: time range required where lesson content is tied to rules or visual evidence."""
    events_by_id = {e.event_id: e for e in ke_col.events}
    cited_event_ids: set[str] = set()
    for rc in rc_col.rules:
        for eid in rc.source_event_ids or []:
            if eid:
                cited_event_ids.add(eid)
    for eid in cited_event_ids:
        ev = events_by_id.get(eid)
        if ev is None:
            continue
        if not _timestamp_nonempty(ev.timestamp_start) or not _timestamp_nonempty(ev.timestamp_end):
            o.add_error(
                "timestamp",
                f"KnowledgeEvent {eid} is cited by rule_cards.source_event_ids and must have "
                "non-empty timestamp_start and timestamp_end",
            )

    for ref in ei.evidence_refs:
        tied = bool(ref.frame_ids or ref.screenshot_paths or ref.linked_rule_ids)
        if not tied:
            continue
        if not _timestamp_nonempty(ref.timestamp_start) or not _timestamp_nonempty(ref.timestamp_end):
            o.add_error(
                "timestamp",
                f"Evidence {ref.evidence_id} has frames, screenshots, or linked_rule_ids and must have "
                "non-empty timestamp_start and timestamp_end",
            )


def lesson_record_from_registry_entry(
    entry: LessonRegistryEntryV1,
    corpus_root: Path,
) -> LessonRecord | None:
    """Rebuild a LessonRecord from a registry row so live validation can be replayed."""
    art = entry.artifacts
    rels = (
        art.knowledge_events_path,
        art.rule_cards_path,
        art.evidence_index_path,
        art.concept_graph_path,
    )
    if not all(rels):
        return None
    paths_abs = {
        "knowledge_events": (corpus_root / art.knowledge_events_path).resolve(),
        "rule_cards": (corpus_root / art.rule_cards_path).resolve(),
        "evidence_index": (corpus_root / art.evidence_index_path).resolve(),
        "concept_graph": (corpus_root / art.concept_graph_path).resolve(),
    }
    if not all(p.is_file() for p in paths_abs.values()):
        return None
    return LessonRecord(
        lesson_id=entry.lesson_id,
        lesson_slug=entry.lesson_slug or entry.lesson_id,
        lesson_title=entry.lesson_name,
        available_artifacts={k: True for k in paths_abs},
        artifact_paths={k: str(v) for k, v in paths_abs.items()},
        artifact_counts=dict(entry.record_counts),
        schema_versions={
            "knowledge_schema_version": entry.knowledge_schema_version,
            "rule_schema_version": entry.rule_schema_version,
            "evidence_schema_version": entry.evidence_schema_version,
            "concept_graph_version": entry.concept_graph_version,
        },
        build_timestamp="",
        content_hashes=dict(entry.artifact_hashes),
        status="valid",
        warnings=[],
    )


@dataclass
class ContractValidationOutcome:
    lesson_id: str
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, category: str, message: str) -> None:
        self.errors.append({"lesson_id": self.lesson_id, "category": category, "message": message})

    def add_warning(self, category: str, message: str) -> None:
        self.warnings.append({"lesson_id": self.lesson_id, "category": category, "message": message})

    def to_dict(self) -> dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "status": "passed" if self.passed else "failed",
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _merge_strict(outcome: ContractValidationOutcome, strict: bool) -> None:
    if strict:
        for w in list(outcome.warnings):
            outcome.errors.append(w)
        outcome.warnings.clear()


def validate_lesson_record_v1(lesson: LessonRecord, *, strict: bool = True) -> ContractValidationOutcome:
    """Validate one discovered lesson against contract v1 (all four JSON artifacts required)."""
    lid = lesson.lesson_id
    o = ContractValidationOutcome(lesson_id=lid)
    frozen = load_schema_versions()

    for key in ("knowledge_schema_version", "rule_schema_version", "evidence_schema_version", "concept_graph_version"):
        if lesson.schema_versions.get(key) != frozen.get(key):
            o.add_warning(
                "version_stamp",
                f"Lesson record schema_versions[{key}]={lesson.schema_versions.get(key)!r} "
                f"differs from frozen {frozen.get(key)!r}",
            )

    required_keys = ("knowledge_events", "rule_cards", "evidence_index", "concept_graph")
    for ak in required_keys:
        if not lesson.available_artifacts.get(ak):
            o.add_error("missing_artifact", f"Required artifact missing: {ak}")
            continue
        p = lesson.artifact_paths.get(ak)
        if not p or not Path(p).exists():
            o.add_error("file_not_found", f"Artifact path missing on disk: {ak}")
            continue

    if o.errors:
        _merge_strict(o, strict)
        return o

    ke_path = Path(lesson.artifact_paths["knowledge_events"])
    rc_path = Path(lesson.artifact_paths["rule_cards"])
    ei_path = Path(lesson.artifact_paths["evidence_index"])
    cg_path = Path(lesson.artifact_paths["concept_graph"])

    try:
        ke_col = load_lesson_knowledge_events(ke_path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        o.add_error("schema_validation", f"knowledge_events: {exc}")
        _merge_strict(o, strict)
        return o

    try:
        rc_raw = json.loads(rc_path.read_text(encoding="utf-8"))
        rules_raw = rc_raw.get("rules")
        if isinstance(rules_raw, list):
            for idx, rule in enumerate(rules_raw):
                if not isinstance(rule, dict):
                    continue
                rid = rule.get("rule_id", f"index_{idx}")
                if "lesson_id" not in rule:
                    o.add_error("provenance", f"Rule {rid}: missing required key lesson_id")
                if "source_event_ids" not in rule:
                    o.add_error("provenance", f"Rule {rid}: missing required key source_event_ids (use [])")
                if "evidence_refs" not in rule:
                    o.add_error("provenance", f"Rule {rid}: missing required key evidence_refs (use [])")
        rc_col = RuleCardCollection.model_validate(rc_raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        o.add_error("schema_validation", f"rule_cards: {exc}")
        _merge_strict(o, strict)
        return o

    try:
        ei = load_lesson_evidence_index(ei_path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        o.add_error("schema_validation", f"evidence_index: {exc}")
        _merge_strict(o, strict)
        return o

    try:
        cg = load_lesson_concept_graph(cg_path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        o.add_error("schema_validation", f"concept_graph: {exc}")
        _merge_strict(o, strict)
        return o

    event_ids = {e.event_id for e in ke_col.events}
    rule_ids = {r.rule_id for r in rc_col.rules}
    evidence_ids = {e.evidence_id for e in ei.evidence_refs}
    concept_ids = {n.concept_id for n in cg.nodes}

    if not ke_col.events:
        o.add_warning("empty_artifact", "knowledge_events has 0 events")
    if not rc_col.rules:
        o.add_warning("empty_artifact", "rule_cards has 0 rules")
    if not ei.evidence_refs:
        o.add_warning("empty_artifact", "evidence_index has 0 evidence_refs")
    if not cg.nodes:
        o.add_warning("empty_artifact", "concept_graph has 0 nodes")

    _check_timestamps_contract_v1(o, ke_col, rc_col, ei)

    for rc in rc_col.rules:
        if not rc.rule_id:
            o.add_error("provenance", "RuleCard with empty rule_id")
        if not rc.lesson_id:
            o.add_error("provenance", f"Rule {rc.rule_id} missing lesson_id")
        if not isinstance(rc.source_event_ids, list):
            o.add_error("provenance", f"Rule {rc.rule_id} source_event_ids must be a list")
            continue
        if not isinstance(rc.evidence_refs, list):
            o.add_error("provenance", f"Rule {rc.rule_id} evidence_refs must be a list")
            continue
        for eid in rc.evidence_refs:
            if eid and eid not in evidence_ids:
                o.add_warning("integrity", f"Rule {rc.rule_id} references unknown evidence_id {eid}")
        for eid in rc.source_event_ids or []:
            if eid and eid not in event_ids:
                o.add_warning("integrity", f"Rule {rc.rule_id} references unknown event_id {eid}")

    for ev in ei.evidence_refs:
        if ev.summary_language == "en" and (ev.summary_ru or "").strip():
            o.add_error(
                "summary_ru",
                f"Evidence {ev.evidence_id}: summary_language=en but summary_ru is non-empty",
            )
        for rid in ev.linked_rule_ids or []:
            if rid and rid not in rule_ids:
                o.add_warning("integrity", f"Evidence {ev.evidence_id} references unknown rule_id {rid}")
        for cid in ev.related_concept_ids or []:
            if cid and cid not in concept_ids:
                o.add_warning("integrity", f"Evidence {ev.evidence_id} references unknown concept_id {cid}")

    _merge_strict(o, strict)
    return o


def validate_corpus(
    lessons: list[LessonRecord],
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Validate all lessons; return a JSON-serializable report."""
    outcomes = [validate_lesson_record_v1(lr, strict=strict) for lr in lessons]
    error_n = sum(1 for x in outcomes if not x.passed)
    return {
        "contract": "lesson_contract_v1",
        "strict": strict,
        "lesson_count": len(lessons),
        "passed_count": len(lessons) - error_n,
        "failed_count": error_n,
        "overall_status": "passed" if error_n == 0 else "failed",
        "lessons": [x.to_dict() for x in outcomes],
    }


def validate_registry_v1(
    doc: LessonRegistryFileV1,
    corpus_root: Path,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Check registry vs disk: paths, hashes, counts, version fields, and live validation replay (§10.4)."""
    issues: list[dict[str, Any]] = []
    frozen = load_schema_versions()
    corpus_root = corpus_root.resolve()

    top_versions = {
        "lesson_contract_version": doc.lesson_contract_version,
        "registry_version": doc.registry_version,
    }
    for k, v in top_versions.items():
        if frozen.get(k) != v:
            issues.append(
                {
                    "category": "registry_version",
                    "message": f"Root field {k}={v!r} expected {frozen.get(k)!r}",
                }
            )

    for entry in doc.lessons:
        lid = entry.lesson_id
        vers = {
            "knowledge_schema_version": entry.knowledge_schema_version,
            "rule_schema_version": entry.rule_schema_version,
            "evidence_schema_version": entry.evidence_schema_version,
            "concept_graph_version": entry.concept_graph_version,
        }
        for msg in validate_version_map(vers, strict=strict):
            issues.append({"lesson_id": lid, "category": "version", "message": msg})

        for label, rel in (
            ("knowledge_events", entry.artifacts.knowledge_events_path),
            ("rule_cards", entry.artifacts.rule_cards_path),
            ("evidence_index", entry.artifacts.evidence_index_path),
            ("concept_graph", entry.artifacts.concept_graph_path),
        ):
            path = (corpus_root / rel).resolve()
            if not path.is_file():
                issues.append({"lesson_id": lid, "category": "path", "message": f"{label} not found: {path}"})
                continue
            h = entry.artifact_hashes.get(label)
            if h:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != h:
                    issues.append(
                        {
                            "lesson_id": lid,
                            "category": "hash_mismatch",
                            "message": f"{label} hash mismatch for {path}",
                        }
                    )

        def _check_count(
            label: str,
            path_rel: str,
            actual: int,
        ) -> None:
            stored = entry.record_counts.get(label)
            if stored is not None and stored != actual:
                issues.append(
                    {
                        "lesson_id": lid,
                        "category": "count_mismatch",
                        "message": f"record_counts.{label}={stored} but file has {actual} ({path_rel})",
                    }
                )

        base = corpus_root
        try:
            ke = load_lesson_knowledge_events(base / entry.artifacts.knowledge_events_path)
            _check_count("knowledge_events", entry.artifacts.knowledge_events_path, len(ke.events))
        except Exception as exc:
            issues.append({"lesson_id": lid, "category": "parse", "message": f"knowledge_events: {exc}"})

        try:
            rc = load_lesson_rule_cards(base / entry.artifacts.rule_cards_path)
            _check_count("rule_cards", entry.artifacts.rule_cards_path, len(rc.rules))
        except Exception as exc:
            issues.append({"lesson_id": lid, "category": "parse", "message": f"rule_cards: {exc}"})

        try:
            ei = load_lesson_evidence_index(base / entry.artifacts.evidence_index_path)
            _check_count("evidence_index", entry.artifacts.evidence_index_path, len(ei.evidence_refs))
        except Exception as exc:
            issues.append({"lesson_id": lid, "category": "parse", "message": f"evidence_index: {exc}"})

        try:
            cg = load_lesson_concept_graph(base / entry.artifacts.concept_graph_path)
            _check_count("concept_graph", entry.artifacts.concept_graph_path, len(cg.nodes))
        except Exception as exc:
            issues.append({"lesson_id": lid, "category": "parse", "message": f"concept_graph: {exc}"})

        lr = lesson_record_from_registry_entry(entry, corpus_root)
        if lr is not None and entry.validation_status in ("passed", "failed"):
            live = validate_lesson_record_v1(lr, strict=strict)
            actual = "passed" if live.passed else "failed"
            if actual != entry.validation_status:
                issues.append(
                    {
                        "lesson_id": lid,
                        "category": "validation_status_mismatch",
                        "message": (
                            f"registry validation_status={entry.validation_status!r} but "
                            f"live contract validation is {actual!r}"
                        ),
                    }
                )

    status = "passed" if not issues else "failed"
    if not strict and issues:
        status = "warning"
    return {"registry_validation_status": status, "issues": issues, "strict": strict}


def validate_intermediate_dir(
    intermediate_dir: Path,
    lesson_id: str,
    *,
    strict: bool = True,
) -> ContractValidationOutcome:
    """Validate artifacts in a single output_intermediate directory (tests / ad-hoc)."""
    from pipeline.corpus.adapters import ARTIFACT_SUFFIXES, find_artifact

    intermediate_dir = intermediate_dir.resolve()
    paths: dict[str, str] = {}
    available: dict[str, bool] = {}
    for name, suffix in ARTIFACT_SUFFIXES.items():
        found = find_artifact(intermediate_dir, suffix)
        available[name] = found is not None and found.exists()
        if found and found.exists():
            paths[name] = str(found)

    lr = LessonRecord(
        lesson_id=lesson_id,
        lesson_slug=lesson_id,
        lesson_title=lesson_id,
        available_artifacts=available,
        artifact_paths=paths,
        artifact_counts={},
        schema_versions=dict(load_schema_versions()),
        build_timestamp="",
        content_hashes={},
        status="valid",
        warnings=[],
    )
    return validate_lesson_record_v1(lr, strict=strict)


def required_artifact_logical_names() -> tuple[str, ...]:
    return REQUIRED_ARTIFACT_FILENAMES
