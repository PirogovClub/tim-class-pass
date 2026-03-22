from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from helpers import config as pipeline_config
from pipeline.contracts import PipelinePaths
from pipeline.orchestrator import (
    STAGE_KNOWLEDGE_EXTRACT,
    STAGE_MARKDOWN_RENDER,
    STAGE_RUN_STATUS_PENDING,
    STAGE_VISION,
    stable_sha256,
)


def discover_videos(data_root: str | Path, state_store) -> list[dict[str, Any]]:
    root = Path(data_root)
    discovered: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        video_id = child.name
        config_hash = stable_sha256(pipeline_config.get_config_for_video(video_id))
        row = state_store.ensure_video(
            video_id=video_id,
            video_root=child,
            title=video_id,
            config_hash=config_hash,
            status="DISCOVERED",
        )
        discovered.append(row)
    return discovered


def discover_lessons(video_id: str, video_root: str | Path, state_store) -> list[dict[str, Any]]:
    root = Path(video_root)
    lessons: list[dict[str, Any]] = []
    for vtt_path in sorted(root.glob("*.vtt")):
        lesson_name = vtt_path.stem
        lesson_id = f"{video_id}::{lesson_name}"
        lessons.append(
            state_store.ensure_lesson(
                lesson_id=lesson_id,
                video_id=video_id,
                lesson_name=lesson_name,
                lesson_root=root,
                vtt_path=vtt_path,
                status="DISCOVERED",
            )
        )
    return lessons


def _render_enabled(config: dict[str, Any]) -> bool:
    return bool(
        config.get("enable_new_markdown_render")
        or config.get("use_llm_review_render")
        or config.get("use_llm_rag_render")
    )


def plan_stages(state_store, *, force: bool = False) -> dict[str, int]:
    planned_counts = {
        STAGE_VISION: 0,
        STAGE_KNOWLEDGE_EXTRACT: 0,
        STAGE_MARKDOWN_RENDER: 0,
    }
    for lesson in state_store.list_lessons():
        lesson_name = lesson["lesson_name"]
        video_id = lesson["video_id"]
        lesson_root = Path(lesson["lesson_root"])
        paths = PipelinePaths(video_root=lesson_root)
        cfg = pipeline_config.get_config_for_video(video_id)

        required: list[tuple[str, bool]] = [
            (STAGE_VISION, (lesson_root / "dense_analysis.json").exists()),
            (STAGE_KNOWLEDGE_EXTRACT, paths.knowledge_events_path(lesson_name).exists()),
        ]
        if _render_enabled(cfg):
            render_complete = (
                paths.review_markdown_path(lesson_name).exists()
                or paths.rag_ready_export_path(lesson_name).exists()
            )
            required.append((STAGE_MARKDOWN_RENDER, render_complete))

        for stage_name, already_complete in required:
            if already_complete and not force:
                continue
            state_store.create_or_reuse_stage_run(
                lesson_id=lesson["lesson_id"],
                stage_name=stage_name,
                execution_mode="gemini_batch",
                status=STAGE_RUN_STATUS_PENDING,
                force_new_attempt=force and already_complete,
            )
            planned_counts[stage_name] += 1
    return planned_counts
