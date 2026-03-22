from __future__ import annotations

from pathlib import Path

from pipeline.contracts import PipelinePaths
from ui.services import import_project
from ui.settings import UISettings
from ui.storage import UIStateStore


def write_text(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold_project_files(
    settings: UISettings,
    name: str,
    *,
    transcript: bool = True,
    video: bool = False,
    filtered_visuals: bool = False,
    dense_analysis: bool = False,
    corpus_ready: bool = False,
    exports_ready: bool = False,
) -> Path:
    project_root = settings.data_root / name
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PipelinePaths(video_root=project_root)
    if transcript:
        write_text(project_root / f"{name}.vtt", "WEBVTT\n\n00:00.000 --> 00:01.000\nHello\n")
    if video:
        write_text(project_root / f"{name}.mp4", "fake-video")
    if filtered_visuals:
        write_text(paths.filtered_visuals_path, "{}")
    if dense_analysis:
        write_text(project_root / "dense_analysis.json", "{}")
    if corpus_ready:
        write_text(paths.knowledge_events_path(name), "{}")
        write_text(paths.rule_cards_path(name), "{}")
        write_text(paths.evidence_index_path(name), "{}")
        write_text(paths.concept_graph_path(name), "{}")
    if exports_ready:
        write_text(paths.review_markdown_path(name), "# Review\n")
        write_text(paths.rag_ready_export_path(name), "# Rag\n")
        write_text(paths.export_manifest_path(name), "{}")
    return project_root


def register_project(store: UIStateStore, settings: UISettings, name: str) -> dict:
    project = import_project(
        store,
        settings,
        title=name,
        project_root_raw=str(settings.data_root / name),
        source_video_raw="",
        transcript_raw="",
    )
    return {
        "project_id": project.project_id,
        "title": project.title,
        "project_root": project.project_root,
    }

