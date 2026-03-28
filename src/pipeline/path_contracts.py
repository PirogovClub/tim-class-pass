"""Filesystem path layout and feature flags for the pipeline.

Single source of truth for output directories and artifact paths.
Matches current output_intermediate/ and output_rag_ready/ usage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class ValidationPolicy:
    """Phase 1: policy for validity gates. Defaults enforce strict final artifacts."""

    allow_unlinked_evidence_pre_reduction: bool = True
    reject_placeholder_rule_text: bool = True
    require_rule_source_event_ids: bool = True
    require_event_normalized_text: bool = True


STRICT_FINAL_EXPORT_POLICY = ValidationPolicy(
    allow_unlinked_evidence_pre_reduction=True,
    reject_placeholder_rule_text=True,
    require_rule_source_event_ids=True,
    require_event_normalized_text=True,
)

RELAXED_PRE_REDUCTION_POLICY = ValidationPolicy(
    allow_unlinked_evidence_pre_reduction=True,
    reject_placeholder_rule_text=False,
    require_rule_source_event_ids=False,
    require_event_normalized_text=True,
)


@dataclass(frozen=True)
class PipelinePaths:
    video_root: Path
    vtt_path: Optional[Path] = None
    visuals_json_path: Optional[Path] = None

    @property
    def filtered_visuals_path(self) -> Path:
        """Path to filtered visual events JSON after invalidation filter."""
        return self.video_root / "filtered_visual_events.json"

    @property
    def filtered_visuals_debug_path(self) -> Path:
        """Path to filtered visual events debug JSON."""
        return self.video_root / "filtered_visual_events.debug.json"

    @property
    def output_intermediate_dir(self) -> Path:
        """Directory for intermediate pipeline artifacts (chunks, knowledge, evidence, rules)."""
        return self.video_root / "output_intermediate"

    @property
    def output_rag_ready_dir(self) -> Path:
        """Directory for RAG-ready markdown and export outputs."""
        return self.video_root / "output_rag_ready"

    @property
    def output_review_dir(self) -> Path:
        """Directory for review markdown and export manifests."""
        return self.video_root / "output_review"

    def batch_root_dir(self) -> Path:
        """Root directory for batch orchestration artifacts."""
        return self.output_intermediate_dir / "batch"

    def batch_spool_dir(self, stage_name: str) -> Path:
        """Directory for lesson-local spool fragments for one stage."""
        return self.batch_root_dir() / stage_name / "spool"

    def batch_spool_requests_path(self, stage_name: str, fragment_name: str) -> Path:
        """Path to a lesson-local spool JSONL fragment."""
        return self.batch_spool_dir(stage_name) / f"{fragment_name}.jsonl"

    def batch_spool_manifest_path(self, stage_name: str, fragment_name: str) -> Path:
        """Path to a lesson-local spool manifest JSON."""
        return self.batch_spool_dir(stage_name) / f"{fragment_name}.manifest.json"

    def batch_results_dir(self, stage_name: str) -> Path:
        """Directory for downloaded Gemini batch result JSONL files."""
        return self.batch_root_dir() / stage_name / "results"

    def batch_result_download_path(self, stage_name: str, batch_job_name: str) -> Path:
        """Path for downloaded raw batch result JSONL."""
        return self.batch_results_dir(stage_name) / f"{batch_job_name}.jsonl"

    def batch_materialization_debug_path(self, stage_name: str) -> Path:
        """Path for batch materialization debug manifest."""
        return self.batch_root_dir() / stage_name / "materialization_debug.json"

    def lesson_chunks_path(self, lesson_name: str) -> Path:
        """Path to lesson chunks JSON (synced transcript + visual events)."""
        return self.output_intermediate_dir / f"{lesson_name}.chunks.json"

    def pass1_markdown_path(self, lesson_name: str) -> Path:
        """Path to pass-1 intermediate markdown."""
        return self.output_intermediate_dir / f"{lesson_name}.md"

    def llm_debug_path(self, lesson_name: str) -> Path:
        """Path to LLM chunk processing debug JSON."""
        return self.output_intermediate_dir / f"{lesson_name}.llm_debug.json"

    def reducer_usage_path(self, lesson_name: str) -> Path:
        """Path to quant reducer usage JSON."""
        return self.output_intermediate_dir / f"{lesson_name}.reducer_usage.json"

    def rag_ready_markdown_path(self, lesson_name: str) -> Path:
        """Path to legacy RAG-ready markdown (post reducer)."""
        return self.output_rag_ready_dir / f"{lesson_name}.md"

    # Task 7 exporter outputs (distinct from legacy .md)
    def review_markdown_path(self, lesson_name: str) -> Path:
        """Path to exporter-generated review markdown."""
        return self.output_review_dir / f"{lesson_name}.review_markdown.md"

    def rag_ready_export_path(self, lesson_name: str) -> Path:
        """Path to exporter-generated RAG-ready markdown."""
        return self.output_rag_ready_dir / f"{lesson_name}.rag_ready.md"

    def review_render_debug_path(self, lesson_name: str) -> Path:
        """Path to review render debug JSON (when using LLM render)."""
        return self.output_review_dir / f"{lesson_name}.review_render_debug.json"

    def rag_render_debug_path(self, lesson_name: str) -> Path:
        """Path to RAG render debug JSON (when using LLM render)."""
        return self.output_rag_ready_dir / f"{lesson_name}.rag_render_debug.json"

    # Future-safe placeholders for structured outputs (Task 2+)
    def knowledge_events_path(self, lesson_name: str) -> Path:
        """Path to extracted knowledge events JSON."""
        return self.output_intermediate_dir / f"{lesson_name}.knowledge_events.json"

    def knowledge_debug_path(self, lesson_name: str) -> Path:
        """Path to knowledge extraction debug JSON."""
        return self.output_intermediate_dir / f"{lesson_name}.knowledge_debug.json"

    def evidence_index_path(self, lesson_name: str) -> Path:
        """Path to evidence index JSON (linked visual evidence)."""
        return self.output_intermediate_dir / f"{lesson_name}.evidence_index.json"

    def evidence_debug_path(self, lesson_name: str) -> Path:
        """Path to evidence linking debug JSON."""
        return self.output_intermediate_dir / f"{lesson_name}.evidence_debug.json"

    def rule_cards_path(self, lesson_name: str) -> Path:
        """Path to rule cards JSON (normalized rules from knowledge + evidence)."""
        return self.output_intermediate_dir / f"{lesson_name}.rule_cards.json"

    def rule_debug_path(self, lesson_name: str) -> Path:
        """Path to rule reducer debug JSON."""
        return self.output_intermediate_dir / f"{lesson_name}.rule_debug.json"

    def concept_graph_path(self, lesson_name: str) -> Path:
        """Path to lesson-level concept graph JSON (Task 12)."""
        return self.output_intermediate_dir / f"{lesson_name}.concept_graph.json"

    def concept_graph_debug_path(self, lesson_name: str) -> Path:
        """Path to concept graph relation debug JSON."""
        return self.output_intermediate_dir / f"{lesson_name}.concept_graph_debug.json"

    def ml_manifest_path(self, lesson_name: str) -> Path:
        """Path to lesson-level ML manifest (Task 13)."""
        return self.output_intermediate_dir / f"{lesson_name}.ml_manifest.json"

    def labeling_manifest_path(self, lesson_name: str) -> Path:
        """Path to lesson-level labeling manifest (Task 13)."""
        return self.output_intermediate_dir / f"{lesson_name}.labeling_manifest.json"

    def export_manifest_path(self, lesson_name: str) -> Path:
        """Path to exporter artifact manifest JSON for a lesson."""
        return self.output_review_dir / f"{lesson_name}.export_manifest.json"

    def inspection_report_path(self) -> Path:
        """Path to pipeline inspection report JSON (preflight)."""
        return self.video_root / "pipeline_inspection.json"

    def ensure_output_dirs(self) -> None:
        """Create output_intermediate, output_review, output_rag_ready if needed."""
        self.output_intermediate_dir.mkdir(parents=True, exist_ok=True)
        self.output_review_dir.mkdir(parents=True, exist_ok=True)
        self.output_rag_ready_dir.mkdir(parents=True, exist_ok=True)

    def ensure_batch_dirs(self, *stage_names: str) -> None:
        """Create batch spool/results directories for the given stages."""
        stages: Iterable[str] = stage_names or (
            "vision",
            "knowledge_extract",
            "markdown_render",
        )
        self.ensure_output_dirs()
        self.batch_root_dir().mkdir(parents=True, exist_ok=True)
        for stage_name in stages:
            self.batch_spool_dir(stage_name).mkdir(parents=True, exist_ok=True)
            self.batch_results_dir(stage_name).mkdir(parents=True, exist_ok=True)


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
    enable_ml_prep: bool = False  # Task 13: enrich rule cards for ML and write manifests
    use_llm_review_render: bool = False
    use_llm_rag_render: bool = False
