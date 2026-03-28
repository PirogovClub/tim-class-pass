"""Programmatic inspection of the pipeline: stages and artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path
from typing import Optional

from pipeline.path_contracts import PipelinePaths
from pipeline.io_utils import atomic_write_json
from pipeline.stage_registry import STAGE_REGISTRY


@dataclass
class StageInspectionResult:
    stage_id: str
    callable_path: str
    import_ok: bool
    callable_exists: bool
    notes: list[str]


@dataclass
class ArtifactInspectionResult:
    artifact_name: str
    path: str
    exists: bool


@dataclass
class PipelineInspectionReport:
    video_root: str
    stage_results: list[StageInspectionResult]
    artifact_results: list[ArtifactInspectionResult]
    backward_compatible: bool
    warnings: list[str]


CORE_STAGE_IDS = frozenset({
    "step2_dense_analysis",
    "step3_invalidation_filter",
    "step3_parse_and_sync",
    "step3_markdown_llm",
    "step3_reducer",
})


def resolve_callable(callable_path: str):
    """Resolve a dotted path to a callable (e.g. 'pipeline.main.main')."""
    module_name, attr_name = callable_path.rsplit(".", 1)
    module = import_module(module_name)
    return getattr(module, attr_name)


def inspect_stages() -> list[StageInspectionResult]:
    """Verify each stage in the registry can be imported and is callable."""
    results: list[StageInspectionResult] = []
    for stage in STAGE_REGISTRY:
        notes: list[str] = []
        import_ok = False
        callable_exists = False
        try:
            obj = resolve_callable(stage.callable_path)
            import_ok = True
            callable_exists = callable(obj)
        except Exception as e:
            notes.append(str(e))
        results.append(
            StageInspectionResult(
                stage_id=stage.stage_id,
                callable_path=stage.callable_path,
                import_ok=import_ok,
                callable_exists=callable_exists,
                notes=notes,
            )
        )
    return results


def inspect_artifacts(
    video_root: Path,
    lesson_name: Optional[str] = None,
) -> list[ArtifactInspectionResult]:
    """Check presence of known artifacts under video_root (and optionally for a lesson)."""
    paths = PipelinePaths(video_root=video_root)
    artifacts: list[tuple[str, Path]] = [
        ("filtered_visual_events", paths.filtered_visuals_path),
        ("filtered_visual_events_debug", paths.filtered_visuals_debug_path),
    ]
    if lesson_name:
        artifacts.extend([
            ("lesson_chunks", paths.lesson_chunks_path(lesson_name)),
            ("pass1_markdown", paths.pass1_markdown_path(lesson_name)),
            ("llm_debug", paths.llm_debug_path(lesson_name)),
            ("reducer_usage", paths.reducer_usage_path(lesson_name)),
            ("rag_ready_markdown", paths.rag_ready_markdown_path(lesson_name)),
        ])
    return [
        ArtifactInspectionResult(
            artifact_name=name,
            path=str(p),
            exists=p.exists(),
        )
        for name, p in artifacts
    ]


def build_report(
    video_root: Path,
    lesson_name: Optional[str] = None,
) -> PipelineInspectionReport:
    """Build a full inspection report for the given video root and optional lesson."""
    stage_results = inspect_stages()
    artifact_results = inspect_artifacts(video_root, lesson_name)
    warnings: list[str] = []
    backward_compatible = True

    for stage in stage_results:
        if not (stage.import_ok and stage.callable_exists):
            warnings.append(f"Stage {stage.stage_id} is not resolvable.")
            if stage.stage_id in CORE_STAGE_IDS:
                backward_compatible = False

    return PipelineInspectionReport(
        video_root=str(video_root),
        stage_results=stage_results,
        artifact_results=artifact_results,
        backward_compatible=backward_compatible,
        warnings=warnings,
    )


def write_report(
    video_root: Path,
    output_path: Path,
    lesson_name: Optional[str] = None,
) -> None:
    """Write the inspection report as JSON to output_path."""
    report = build_report(video_root, lesson_name)
    # Serialize dataclasses to dicts for JSON
    out = {
        "video_root": report.video_root,
        "stage_results": [
            asdict(s) for s in report.stage_results
        ],
        "artifact_results": [
            asdict(a) for a in report.artifact_results
        ],
        "backward_compatible": report.backward_compatible,
        "warnings": report.warnings,
    }
    atomic_write_json(output_path, out)
