"""Build lesson_registry.json (contract v1 manifest) for processed lessons."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.contracts.corpus_validator import validate_lesson_record_v1
from pipeline.contracts.registry_models import (
    LessonArtifacts,
    LessonRegistryEntryV1,
    LessonRegistryFileV1,
)
from pipeline.contracts.versioning import load_schema_versions
from pipeline.corpus.lesson_registry import discover_lessons
from pipeline.path_contracts import PipelinePaths


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(p: Path, root: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def _optional_markdown_paths(
    lesson_dir: Path,
    lesson_id: str,
    corpus_root: Path,
) -> tuple[str | None, str | None]:
    paths = PipelinePaths(video_root=lesson_dir)
    review = paths.review_markdown_path(lesson_id)
    rag = paths.rag_ready_export_path(lesson_id)
    review_s = _rel(review, corpus_root) if review.exists() else None
    rag_s = _rel(rag, corpus_root) if rag.exists() else None
    return review_s, rag_s


def build_registry_v1(
    input_root: Path,
    *,
    validate: bool = True,
    strict_validation: bool = True,
    selected_project_roots: list[Path] | None = None,
) -> LessonRegistryFileV1:
    """Discover lessons under input_root and produce a v1 registry document."""
    input_root = input_root.resolve()
    frozen = load_schema_versions()
    now = datetime.now(timezone.utc).isoformat()
    lessons_out: list[LessonRegistryEntryV1] = []

    records = discover_lessons(input_root, selected_project_roots=selected_project_roots)
    for lr in records:
        lesson_dir = input_root / lr.lesson_id
        review_rel, rag_rel = _optional_markdown_paths(lesson_dir, lr.lesson_id, input_root)

        artifact_paths = lr.artifact_paths
        ke = artifact_paths.get("knowledge_events", "")
        rc = artifact_paths.get("rule_cards", "")
        ei = artifact_paths.get("evidence_index", "")
        cg = artifact_paths.get("concept_graph", "")

        hashes: dict[str, str] = {}
        counts: dict[str, int] = {}
        for key, path_str in (
            ("knowledge_events", ke),
            ("rule_cards", rc),
            ("evidence_index", ei),
            ("concept_graph", cg),
        ):
            if path_str and Path(path_str).exists():
                hashes[key] = _sha256_file(Path(path_str))
        counts["knowledge_events"] = lr.artifact_counts.get("knowledge_events", 0)
        counts["rule_cards"] = lr.artifact_counts.get("rule_cards", 0)
        counts["evidence_index"] = lr.artifact_counts.get("evidence_index", 0)
        counts["concept_graph"] = lr.artifact_counts.get("concept_graph", 0)

        validation_errors: list[str] = []
        validation_status: str = "not_run"
        validated_at: str | None = None

        if validate:
            vo = validate_lesson_record_v1(lr, strict=strict_validation)
            validated_at = now
            validation_errors = [e["message"] for e in vo.errors] + [w["message"] for w in vo.warnings]
            validation_status = "passed" if vo.passed else "failed"

        all_four = all(lr.available_artifacts.get(k) for k in ("knowledge_events", "rule_cards", "evidence_index", "concept_graph"))
        status: str = "valid" if all_four and validation_status == "passed" else "invalid"
        if not all_four:
            status = "invalid"

        entry = LessonRegistryEntryV1(
            lesson_id=lr.lesson_id,
            lesson_name=lr.lesson_title,
            lesson_slug=lr.lesson_slug,
            status=status,
            source_artifact_version=None,
            lesson_contract_version=frozen["lesson_contract_version"],
            knowledge_schema_version=frozen["knowledge_schema_version"],
            rule_schema_version=frozen["rule_schema_version"],
            evidence_schema_version=frozen["evidence_schema_version"],
            concept_graph_version=frozen["concept_graph_version"],
            registry_version=frozen["registry_version"],
            artifacts=LessonArtifacts(
                knowledge_events_path=_rel(Path(ke), input_root) if ke else "",
                rule_cards_path=_rel(Path(rc), input_root) if rc else "",
                evidence_index_path=_rel(Path(ei), input_root) if ei else "",
                concept_graph_path=_rel(Path(cg), input_root) if cg else "",
                review_markdown_path=review_rel,
                rag_ready_path=rag_rel,
            ),
            artifact_hashes=hashes,
            record_counts=counts,
            validated_at=validated_at,
            validation_status=validation_status,  # type: ignore[arg-type]
            validation_errors=validation_errors,
        )
        lessons_out.append(entry)

    lessons_out.sort(key=lambda e: e.lesson_id)
    return LessonRegistryFileV1(
        registry_version=frozen["registry_version"],
        lesson_contract_version=frozen["lesson_contract_version"],
        generated_at=now,
        lessons=lessons_out,
    )


def save_registry_v1(doc: LessonRegistryFileV1, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump(mode="json")
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_registry_v1(path: Path) -> LessonRegistryFileV1:
    data = json.loads(path.read_text(encoding="utf-8"))
    return LessonRegistryFileV1.model_validate(data)
