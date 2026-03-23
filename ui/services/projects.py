from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from pipeline.contracts import PipelinePaths
from pipeline.orchestrator.models import slugify_lesson_name, stable_sha256
from ui.models import ArtifactSnapshot, ProjectRecord
from ui.settings import UISettings
from ui.storage import UIStateStore


VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm")
TRANSCRIPT_EXTENSIONS = (".vtt",)


def _row_to_project(row: dict) -> ProjectRecord:
    return ProjectRecord(
        project_id=str(row["project_id"]),
        slug=str(row["slug"]),
        title=str(row["title"]),
        lesson_name=str(row["lesson_name"]),
        project_root=Path(str(row["project_root"])),
        source_video_path=None if not row.get("source_video_path") else Path(str(row["source_video_path"])),
        transcript_path=None if not row.get("transcript_path") else Path(str(row["transcript_path"])),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def resolve_path(settings: UISettings, raw_path: str | None) -> Path | None:
    value = str(raw_path or "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = settings.project_root / path
    return path.resolve()


def _pick_matching_file(root: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def detect_transcript(project_root: Path, requested: Path | None, title: str) -> Path | None:
    if requested is not None:
        return requested
    preferred = _pick_matching_file(project_root, [f"{title}.vtt", f"{project_root.name}.vtt"])
    if preferred is not None:
        return preferred
    transcripts = sorted(project_root.glob("*.vtt"))
    return transcripts[0] if transcripts else None


def detect_video(project_root: Path, requested: Path | None) -> Path | None:
    if requested is not None:
        return requested
    for ext in VIDEO_EXTENSIONS:
        matches = sorted(project_root.glob(f"*{ext}"))
        if matches:
            return matches[0]
    return None


def inspect_artifacts(
    project_root: Path,
    lesson_name: str,
    transcript_path: Path | None,
    video_path: Path | None,
) -> ArtifactSnapshot:
    paths = PipelinePaths(video_root=project_root)
    return ArtifactSnapshot(
        transcript_exists=bool(transcript_path and transcript_path.exists()),
        video_exists=bool(video_path and video_path.exists()),
        filtered_visuals_exists=paths.filtered_visuals_path.exists(),
        dense_analysis_exists=(project_root / "dense_analysis.json").exists(),
        knowledge_events_exists=paths.knowledge_events_path(lesson_name).exists(),
        rule_cards_exists=paths.rule_cards_path(lesson_name).exists(),
        evidence_index_exists=paths.evidence_index_path(lesson_name).exists(),
        concept_graph_exists=paths.concept_graph_path(lesson_name).exists(),
        review_markdown_exists=paths.review_markdown_path(lesson_name).exists(),
        rag_ready_exists=(
            paths.rag_ready_export_path(lesson_name).exists()
            or paths.rag_ready_markdown_path(lesson_name).exists()
        ),
        export_manifest_exists=paths.export_manifest_path(lesson_name).exists(),
    )


def inspect_run_prerequisites(project: ProjectRecord) -> dict[str, bool]:
    artifacts = inspect_artifacts(
        project.project_root,
        project.lesson_name,
        project.transcript_path,
        project.source_video_path,
    )
    return {
        "has_transcript": artifacts.transcript_exists,
        "has_video": artifacts.video_exists,
        "has_dense_analysis": artifacts.dense_analysis_exists,
        "has_queue_manifest": (project.project_root / "llm_queue" / "manifest.json").exists(),
        "has_dense_index": (project.project_root / "dense_index.json").exists(),
        "corpus_ready": artifacts.corpus_ready,
        "exports_ready": artifacts.exports_ready,
    }


def derive_effective_status(artifacts: ArtifactSnapshot, latest_run) -> str:
    if latest_run is not None:
        if latest_run.status == "WAITING_REMOTE":
            return "waiting_for_remote"
        if latest_run.status in {"QUEUED", "RUNNING", "CANCEL_REQUESTED"}:
            if latest_run.run_kind == "CORPUS":
                return "ready_for_corpus" if artifacts.corpus_ready else "missing_inputs"
            if "batch" in latest_run.run_mode:
                return "running_batch"
            return "running_sync"
        if latest_run.status in {"FAILED", "INTERRUPTED"}:
            return "failed"
        if latest_run.status == "CANCELLED":
            return "ready_to_run" if artifacts.transcript_exists else "missing_inputs"
        if latest_run.status == "SUCCEEDED" and artifacts.corpus_ready and artifacts.exports_ready:
            return "complete"

    if not artifacts.transcript_exists:
        return "missing_inputs"
    if artifacts.corpus_ready and artifacts.exports_ready:
        return "complete"
    if artifacts.corpus_ready:
        return "ready_for_corpus"
    if artifacts.dense_analysis_exists and not artifacts.knowledge_events_exists:
        return "ready_for_knowledge_extract"
    if artifacts.transcript_exists:
        return "ready_to_run"
    return "new"


def derive_next_action(artifacts: ArtifactSnapshot, latest_run, effective_status: str) -> str:
    if effective_status == "missing_inputs":
        return "Add transcript"
    if effective_status == "waiting_for_remote":
        return "Reconcile remote batch"
    if effective_status == "failed":
        return "Inspect logs and retry"
    if effective_status == "running_batch":
        return "Monitor batch progress"
    if effective_status == "running_sync":
        return "Monitor sync run"
    if effective_status == "ready_for_corpus":
        return "Build corpus"
    if effective_status == "complete":
        return "Review outputs"
    if artifacts.dense_analysis_exists and not artifacts.knowledge_events_exists:
        return "Run knowledge extract"
    if artifacts.transcript_exists and not artifacts.dense_analysis_exists:
        return "Run sync or batch vision"
    if artifacts.transcript_exists and artifacts.knowledge_events_exists and not artifacts.exports_ready:
        return "Run post-process"
    return "Inspect project"


def make_project_id(project_root: Path, title: str) -> str:
    slug = slugify_lesson_name(title or project_root.name)
    digest = stable_sha256(str(project_root.resolve()))[:8]
    return f"{slug}-{digest}"


def sanitize_filename(name: str, fallback_stem: str, allowed_extensions: tuple[str, ...]) -> str:
    raw_name = Path(str(name or "").strip()).name
    suffix = Path(raw_name).suffix.lower()
    if suffix not in allowed_extensions:
        raise ValueError(f"Unsupported file extension for {raw_name or fallback_stem}.")
    safe_stem = str(fallback_stem or "upload").strip().replace("/", "_").replace("\\", "_")
    safe_stem = safe_stem or "upload"
    return f"{safe_stem}{suffix}"


def ensure_within_directory(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError("Resolved file path escapes the project directory.")
    return candidate_resolved


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}__{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _copy_stream_to_path(
    source: BinaryIO,
    destination: Path,
    *,
    max_bytes: int,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(destination, "wb") as target:
        while True:
            chunk = source.read(64 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise ValueError(f"Upload exceeds maximum allowed size of {max_bytes} bytes.")
            target.write(chunk)
    return destination


def save_uploaded_file(
    upload: UploadFile,
    *,
    destination_root: Path,
    preferred_stem: str,
    allowed_extensions: tuple[str, ...],
    max_bytes: int,
) -> Path:
    if not upload.filename:
        raise ValueError("Uploaded file is missing a filename.")
    destination_name = sanitize_filename(upload.filename, preferred_stem, allowed_extensions)
    destination = ensure_within_directory(destination_root, unique_destination(destination_root / destination_name))
    upload.file.seek(0)
    return _copy_stream_to_path(upload.file, destination, max_bytes=max_bytes)


def copy_path_into_project(
    source_path: Path,
    *,
    destination_root: Path,
    preferred_stem: str,
    allowed_extensions: tuple[str, ...],
    max_bytes: int,
) -> Path:
    if not source_path.exists() or not source_path.is_file():
        raise ValueError(f"Source path does not exist: {source_path}")
    if source_path.stat().st_size > max_bytes:
        raise ValueError(f"Source file exceeds maximum allowed size of {max_bytes} bytes.")
    destination_name = sanitize_filename(source_path.name, preferred_stem, allowed_extensions)
    destination = ensure_within_directory(destination_root, unique_destination(destination_root / destination_name))
    if source_path.resolve() == destination.resolve():
        return source_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    return destination.resolve()


def import_project(
    store: UIStateStore,
    settings: UISettings,
    *,
    title: str,
    project_root_raw: str | None,
    source_video_raw: str | None,
    transcript_raw: str | None,
    source_video_upload: UploadFile | None = None,
    transcript_upload: UploadFile | None = None,
) -> ProjectRecord:
    normalized_title = str(title or "").strip()
    if not normalized_title and not str(project_root_raw or "").strip():
        raise ValueError("Provide a project title or project root.")

    project_root = resolve_path(settings, project_root_raw)
    if project_root is None:
        project_root = (settings.data_root / normalized_title).resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    preferred_stem = normalized_title or project_root.name

    source_video_path = None
    manual_video_path = resolve_path(settings, source_video_raw)
    if source_video_upload is not None and source_video_upload.filename:
        source_video_path = save_uploaded_file(
            source_video_upload,
            destination_root=project_root,
            preferred_stem=preferred_stem,
            allowed_extensions=VIDEO_EXTENSIONS,
            max_bytes=settings.upload_max_video_bytes,
        )
    elif manual_video_path is not None:
        source_video_path = copy_path_into_project(
            manual_video_path,
            destination_root=project_root,
            preferred_stem=preferred_stem,
            allowed_extensions=VIDEO_EXTENSIONS,
            max_bytes=settings.upload_max_video_bytes,
        )

    transcript_path = None
    manual_transcript_path = resolve_path(settings, transcript_raw)
    if transcript_upload is not None and transcript_upload.filename:
        transcript_path = save_uploaded_file(
            transcript_upload,
            destination_root=project_root,
            preferred_stem=preferred_stem,
            allowed_extensions=TRANSCRIPT_EXTENSIONS,
            max_bytes=settings.upload_max_transcript_bytes,
        )
    elif manual_transcript_path is not None:
        transcript_path = copy_path_into_project(
            manual_transcript_path,
            destination_root=project_root,
            preferred_stem=preferred_stem,
            allowed_extensions=TRANSCRIPT_EXTENSIONS,
            max_bytes=settings.upload_max_transcript_bytes,
        )

    source_video_path = detect_video(project_root, source_video_path)
    transcript_path = detect_transcript(project_root, transcript_path, preferred_stem)
    lesson_name = transcript_path.stem if transcript_path is not None else (normalized_title or project_root.name)
    final_title = normalized_title or lesson_name
    artifacts = inspect_artifacts(project_root, lesson_name, transcript_path, source_video_path)
    effective_status = derive_effective_status(artifacts, latest_run=None)
    row = store.upsert_project(
        project_id=make_project_id(project_root, final_title),
        slug=slugify_lesson_name(final_title),
        title=final_title,
        lesson_name=lesson_name,
        project_root=project_root,
        source_video_path=source_video_path,
        transcript_path=transcript_path,
        status=effective_status,
    )
    return _row_to_project(row)


def refresh_project_record(store: UIStateStore, project_id: str):
    row = store.get_project(project_id)
    if row is None:
        raise KeyError(project_id)
    project = _row_to_project(row)
    artifacts = inspect_artifacts(
        project.project_root,
        project.lesson_name,
        project.transcript_path,
        project.source_video_path,
    )
    effective_status = derive_effective_status(artifacts, None)
    updated = store.upsert_project(
        project_id=project.project_id,
        slug=project.slug,
        title=project.title,
        lesson_name=project.lesson_name,
        project_root=project.project_root,
        source_video_path=project.source_video_path,
        transcript_path=project.transcript_path,
        status=effective_status,
    )
    return _row_to_project(updated)

