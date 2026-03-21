"""Discover processed lessons and build a lesson registry with artifact counts and hashes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.corpus.adapters import ARTIFACT_SUFFIXES, find_artifact
from pipeline.corpus.contracts import SCHEMA_VERSIONS, LessonRecord
from pipeline.corpus.id_utils import slugify_lesson_id


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_entities(path: Path, list_key: str) -> int:
    """Count entities in a JSON file by looking at len(data[list_key])."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get(list_key)
        if isinstance(items, list):
            return len(items)
        return 0
    except Exception:
        return 0


_LIST_KEYS = {
    "knowledge_events": "events",
    "rule_cards": "rules",
    "evidence_index": "evidence_refs",
    "concept_graph": "nodes",
}


def discover_lessons(input_root: Path) -> list[LessonRecord]:
    """Scan input_root for directories containing output_intermediate/ with artifacts."""
    records: list[LessonRecord] = []
    now = datetime.now(timezone.utc).isoformat()

    for lesson_dir in sorted(input_root.iterdir()):
        if not lesson_dir.is_dir():
            continue
        intermediate = lesson_dir / "output_intermediate"
        if not intermediate.is_dir():
            continue

        lesson_id = lesson_dir.name
        lesson_slug = slugify_lesson_id(lesson_id)

        available: dict[str, bool] = {}
        paths: dict[str, str] = {}
        counts: dict[str, int] = {}
        hashes: dict[str, str] = {}
        warnings: list[str] = []

        has_any_artifact = False

        for artifact_name, suffix in ARTIFACT_SUFFIXES.items():
            artifact_path = find_artifact(intermediate, suffix)
            if artifact_path and artifact_path.exists():
                available[artifact_name] = True
                paths[artifact_name] = str(artifact_path)
                hashes[artifact_name] = _sha256_file(artifact_path)
                list_key = _LIST_KEYS.get(artifact_name, "")
                if list_key:
                    counts[artifact_name] = _count_entities(artifact_path, list_key)
                has_any_artifact = True
            else:
                available[artifact_name] = False
                if artifact_name != "concept_graph":
                    warnings.append(f"Missing required artifact: {artifact_name}")

        if not has_any_artifact:
            continue

        status = "valid"
        if any("Missing required" in w for w in warnings):
            status = "warning"

        records.append(LessonRecord(
            lesson_id=lesson_id,
            lesson_slug=lesson_slug,
            lesson_title=lesson_id,
            source_language="ru",
            available_artifacts=available,
            artifact_paths=paths,
            artifact_counts=counts,
            schema_versions=dict(SCHEMA_VERSIONS),
            build_timestamp=now,
            content_hashes=hashes,
            status=status,
            warnings=warnings,
        ))

    records.sort(key=lambda r: r.lesson_id)
    return records


def build_registry(lessons: list[LessonRecord]) -> list[dict]:
    """Convert lesson records to serializable dicts for lesson_registry.json."""
    return [lr.model_dump() for lr in lessons]


def save_registry(registry: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
