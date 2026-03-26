"""Component 2 preflight: inspection report and run preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pipeline.path_contracts import PipelinePaths
from pipeline.inspection import build_report, write_report


@dataclass
class Component2RunConfig:
    vtt_path: Path
    visuals_json_path: Path
    output_root: Path
    video_id: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    reducer_model: Optional[str] = None
    reducer_provider: Optional[str] = None
    target_duration_seconds: float = 120.0
    max_concurrency: int = 5
    enable_structured_outputs: bool = False


@dataclass
class Component2RunArtifacts:
    inspection_report_path: Path
    filtered_visuals_path: Path
    chunks_path: Optional[Path]
    pass1_markdown_path: Optional[Path]
    rag_ready_markdown_path: Optional[Path]


def prepare_component2_run(
    config: Component2RunConfig,
    lesson_name: str,
) -> Component2RunArtifacts:
    """Run preflight inspection, write pipeline_inspection.json, return artifact paths."""
    config.output_root.mkdir(parents=True, exist_ok=True)
    paths = PipelinePaths(video_root=config.output_root)
    inspection_report_path = paths.inspection_report_path()
    write_report(config.output_root, inspection_report_path, lesson_name=lesson_name)

    return Component2RunArtifacts(
        inspection_report_path=inspection_report_path,
        filtered_visuals_path=paths.filtered_visuals_path,
        chunks_path=paths.lesson_chunks_path(lesson_name),
        pass1_markdown_path=paths.pass1_markdown_path(lesson_name),
        rag_ready_markdown_path=paths.rag_ready_markdown_path(lesson_name),
    )
