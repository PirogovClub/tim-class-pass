"""Path contracts and feature flags for the pipeline.

Single source of truth for output directories and artifact paths.
Matches current output_intermediate/ and output_rag_ready/ usage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PipelinePaths:
    video_root: Path
    vtt_path: Optional[Path] = None
    visuals_json_path: Optional[Path] = None

    @property
    def filtered_visuals_path(self) -> Path:
        return self.video_root / "filtered_visual_events.json"

    @property
    def filtered_visuals_debug_path(self) -> Path:
        return self.video_root / "filtered_visual_events.debug.json"

    @property
    def output_intermediate_dir(self) -> Path:
        return self.video_root / "output_intermediate"

    @property
    def output_rag_ready_dir(self) -> Path:
        return self.video_root / "output_rag_ready"

    @property
    def output_review_dir(self) -> Path:
        return self.video_root / "output_review"

    def lesson_chunks_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.chunks.json"

    def pass1_markdown_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.md"

    def llm_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.llm_debug.json"

    def reducer_usage_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.reducer_usage.json"

    def rag_ready_markdown_path(self, lesson_name: str) -> Path:
        return self.output_rag_ready_dir / f"{lesson_name}.md"

    # Task 7 exporter outputs (distinct from legacy .md)
    def review_markdown_path(self, lesson_name: str) -> Path:
        return self.output_review_dir / f"{lesson_name}.review_markdown.md"

    def rag_ready_export_path(self, lesson_name: str) -> Path:
        return self.output_rag_ready_dir / f"{lesson_name}.rag_ready.md"

    def review_render_debug_path(self, lesson_name: str) -> Path:
        return self.output_review_dir / f"{lesson_name}.review_render_debug.json"

    def rag_render_debug_path(self, lesson_name: str) -> Path:
        return self.output_rag_ready_dir / f"{lesson_name}.rag_render_debug.json"

    # Future-safe placeholders for structured outputs (Task 2+)
    def knowledge_events_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.knowledge_events.json"

    def knowledge_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.knowledge_debug.json"

    def evidence_index_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.evidence_index.json"

    def evidence_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.evidence_debug.json"

    def rule_cards_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.rule_cards.json"

    def rule_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.rule_debug.json"

    def concept_graph_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.concept_graph.json"

    def export_manifest_path(self, lesson_name: str) -> Path:
        return self.output_review_dir / f"{lesson_name}.export_manifest.json"

    def inspection_report_path(self) -> Path:
        return self.video_root / "pipeline_inspection.json"

    def ensure_output_dirs(self) -> None:
        """Create output_intermediate, output_review, output_rag_ready if needed."""
        self.output_intermediate_dir.mkdir(parents=True, exist_ok=True)
        self.output_review_dir.mkdir(parents=True, exist_ok=True)
        self.output_rag_ready_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class PipelineFeatureFlags:
    """Feature flags for future structured outputs. All default to legacy behavior."""

    preserve_legacy_markdown: bool = True
    enable_structured_outputs: bool = False
    enable_knowledge_events: bool = False
    enable_rule_cards: bool = False
    enable_evidence_index: bool = False
    enable_concept_graph: bool = False
    enable_new_markdown_render: bool = False
    enable_exporters: bool = False
    use_llm_review_render: bool = False
    use_llm_rag_render: bool = False
