from __future__ import annotations

import json
import time
from pathlib import Path

from pipeline.path_contracts import PipelinePaths
from ui.services import import_project
from ui.settings import UISettings
from ui.storage import UIStateStore


def write_text(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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
    batch_ready: bool = False,
) -> Path:
    project_root = settings.data_root / name
    project_root.mkdir(parents=True, exist_ok=True)
    paths = PipelinePaths(video_root=project_root)
    if transcript:
        write_text(project_root / f"{name}.vtt", "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n")
    if video:
        write_text(project_root / f"{name}.mp4", "fake-video")
    if filtered_visuals:
        write_text(paths.filtered_visuals_path, "{}")
    if dense_analysis:
        write_json(project_root / "dense_analysis.json", {"000001": {"material_change": True}})
    if corpus_ready:
        write_json(
            paths.knowledge_events_path(name),
            {
                "schema_version": "1.0",
                "lesson_id": name,
                "events": [
                    {
                        "event_id": "ke_0",
                        "event_type": "rule_statement",
                        "raw_text": "Правило уровня",
                        "normalized_text": "правило уровня",
                        "concept": "уровень",
                        "subconcept": "рейтинг уровня",
                        "lesson_id": name,
                        "source_language": "ru",
                        "metadata": {"chunk_index": 0},
                    }
                ],
            },
        )
        write_json(
            paths.rule_cards_path(name),
            {
                "schema_version": "1.0",
                "lesson_id": name,
                "rules": [
                    {
                        "rule_id": "rule_0",
                        "concept": "уровень",
                        "subconcept": "рейтинг уровня",
                        "rule_text": "Правило уровня",
                        "lesson_id": name,
                        "source_event_ids": ["ke_0"],
                        "evidence_refs": ["ev_0"],
                        "source_language": "ru",
                    }
                ],
            },
        )
        write_json(
            paths.evidence_index_path(name),
            {
                "schema_version": "1.0",
                "lesson_id": name,
                "evidence_refs": [
                    {
                        "evidence_id": "ev_0",
                        "lesson_id": name,
                        "frame_ids": ["frame_0"],
                        "linked_rule_ids": ["rule_0"],
                        "source_event_ids": ["ke_0"],
                        "source_language": "ru",
                    }
                ],
            },
        )
        write_json(
            paths.concept_graph_path(name),
            {
                "lesson_id": name,
                "graph_version": "1.0",
                "nodes": [
                    {
                        "concept_id": "c_level",
                        "name": "уровень",
                        "type": "concept",
                        "aliases": ["уровень"],
                        "source_rule_ids": ["rule_0"],
                    }
                ],
                "relations": [],
                "stats": {"node_count": 1, "edge_count": 0},
            },
        )
    if exports_ready:
        write_text(paths.review_markdown_path(name), "# Review\n")
        write_text(paths.rag_ready_export_path(name), "# Rag\n")
        write_json(paths.export_manifest_path(name), {})
    if batch_ready:
        write_json(project_root / "dense_index.json", {"000001": {"timestamp": "00:00:01"}})
        queue_dir = project_root / "llm_queue"
        queue_dir.mkdir(parents=True, exist_ok=True)
        write_text(queue_dir / "frame_000001.jpg", "jpg")
        write_json(
            queue_dir / "manifest.json",
            {"items": {"000001": {"source": "frame_000001.jpg"}}},
        )
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


def create_external_source(tmp_root: Path, filename: str, content: str = "x") -> Path:
    path = tmp_root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def wait_for_run_status(store: UIStateStore, run_id: str, expected: set[str], *, timeout_seconds: float = 15.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        row = store.get_run(run_id)
        if row is not None and str(row["status"]) in expected:
            return row
        time.sleep(0.2)
    row = store.get_run(run_id)
    raise AssertionError(f"Run {run_id} did not reach {expected}. Last row: {row}")

