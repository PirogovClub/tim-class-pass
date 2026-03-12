"""Machine-readable registry of pipeline stages for inspection and orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    description: str
    callable_path: str
    required_inputs: list[str]
    outputs: list[str]
    enabled_by_default: bool = True
    legacy_stage: bool = False


STAGE_REGISTRY: list[StageSpec] = [
    StageSpec(
        stage_id="step0_download",
        description="Download video and transcript",
        callable_path="pipeline.downloader.download_video_and_transcript",
        required_inputs=["url"],
        outputs=["*.mp4", "*.vtt"],
    ),
    StageSpec(
        stage_id="step1_dense_capture",
        description="Dense frame extraction",
        callable_path="pipeline.dense_capturer.extract_dense_frames",
        required_inputs=["video_id"],
        outputs=["frames_dense/", "dense_index.json"],
    ),
    StageSpec(
        stage_id="step1_5_structural_compare",
        description="Structural diff computation",
        callable_path="pipeline.structural_compare.run_structural_compare",
        required_inputs=["video_id"],
        outputs=["structural_index.json"],
    ),
    StageSpec(
        stage_id="step1_6_llm_queue",
        description="Build LLM frame queue",
        callable_path="pipeline.select_llm_frames.build_llm_queue",
        required_inputs=["video_id"],
        outputs=["llm_queue/"],
    ),
    StageSpec(
        stage_id="step1_7_llm_prompts",
        description="Build frame prompts",
        callable_path="pipeline.build_llm_prompts.build_llm_prompts",
        required_inputs=["video_id"],
        outputs=["llm_queue/*_prompt.txt"],
    ),
    StageSpec(
        stage_id="step2_dense_analysis",
        description="Dense multimodal analysis",
        callable_path="pipeline.dense_analyzer.run_analysis",
        required_inputs=["video_id"],
        outputs=["dense_analysis.json", "frames_dense/*.json"],
    ),
    StageSpec(
        stage_id="step3_invalidation_filter",
        description="Filter instructional visuals",
        callable_path="pipeline.invalidation_filter.run_invalidation_filter",
        required_inputs=["dense_analysis.json"],
        outputs=["filtered_visual_events.json", "filtered_visual_events.debug.json"],
        legacy_stage=True,
    ),
    StageSpec(
        stage_id="step3_parse_and_sync",
        description="Parse VTT and build semantic lesson chunks",
        callable_path="pipeline.component2.parser.parse_and_sync",
        required_inputs=["vtt", "filtered_visual_events.json"],
        outputs=["output_intermediate/*.chunks.json"],
        legacy_stage=True,
    ),
    StageSpec(
        stage_id="step3_markdown_llm",
        description="Generate enriched markdown chunks",
        callable_path="pipeline.component2.llm_processor.process_chunks",
        required_inputs=["LessonChunk[]"],
        outputs=["output_intermediate/*.md", "output_intermediate/*.llm_debug.json"],
        legacy_stage=True,
    ),
    StageSpec(
        stage_id="step3_reducer",
        description="Whole-document RAG reducer",
        callable_path="pipeline.component2.quant_reducer.synthesize_full_document",
        required_inputs=["output_intermediate/*.md"],
        outputs=["output_rag_ready/*.md", "output_intermediate/*.reducer_usage.json"],
        legacy_stage=True,
    ),
    StageSpec(
        stage_id="step3_2b_knowledge_events",
        description="Extract atomic knowledge events",
        callable_path="pipeline.component2.knowledge_builder.build_knowledge_events_from_extraction_results",
        required_inputs=["output_intermediate/*.chunks.json"],
        outputs=["output_intermediate/*.knowledge_events.json"],
    ),
    StageSpec(
        stage_id="step4_evidence_linking",
        description="Link compact evidence to knowledge events",
        callable_path="pipeline.component2.evidence_linker.build_evidence_index",
        required_inputs=[
            "output_intermediate/*.knowledge_events.json",
            "output_intermediate/*.chunks.json",
        ],
        outputs=["output_intermediate/*.evidence_index.json"],
    ),
    StageSpec(
        stage_id="step4b_rule_cards",
        description="Normalize knowledge events into rule cards",
        callable_path="pipeline.component2.rule_reducer.build_rule_cards",
        required_inputs=[
            "output_intermediate/*.knowledge_events.json",
            "output_intermediate/*.evidence_index.json",
        ],
        outputs=["output_intermediate/*.rule_cards.json"],
    ),
    StageSpec(
        stage_id="step5_exporters",
        description="Render review and RAG markdown from rule cards",
        callable_path="pipeline.component2.exporters.export_review_markdown",
        required_inputs=[
            "output_intermediate/*.rule_cards.json",
            "output_intermediate/*.evidence_index.json",
        ],
        outputs=[
            "output_review/*.review_markdown.md",
            "output_rag_ready/*.rag_ready.md",
        ],
    ),
]
