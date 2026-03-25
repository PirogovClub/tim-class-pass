I’m narrowing this to Task 1 only: inspect the existing pipeline and preserve backward compatibility while introducing the new structure cleanly. I’ll map what to review, what to freeze, what to wrap, and what to test first so the coding agent can change the code without destabilizing the current flow.

Thought for 15s

Below is a detailed Python implementation plan for Task 1 only: inspect the existing pipeline and preserve backward compatibility while preparing for the structured JSON redesign.

Confidence: High — the current framework docs are clear enough to define a safe first implementation step. The main pipeline currently runs Steps 0 → 1 → 1.5 → 1.6 → 1.7 → 2 → 3 from pipeline/main.py, while the standalone Component 2 / Step 3 flow starts from pipeline.component2.main and currently goes invalidation filter → parser → LLM processor → markdown/reducer outputs. 

FRAMEWORK_MODULES

 

pipeline

Task 1 objective

Task 1 is not to redesign the whole pipeline yet.

Task 1 should do three things:

Inspect and map the current codepath

Freeze the compatibility surface

Create safe extension points for later tasks

The goal from your instruction is explicit: review the orchestration, invalidation filter, parse/sync logic, LLM processor, markdown synthesis, reducer, and export logic, while not breaking dense analysis generation and keeping existing entry points working if possible. 

Response: Visual Decoding Review

What exists now
Main CLI pipeline

The current main CLI is pipeline/main.py. It validates CLI input, loads config, sets up logging, and runs the main stages in order. Step 2 is dense_analyzer.run_analysis(...), and Step 3 is the markdown pipeline afterward. 

FRAMEWORK_MODULES

Standalone Step 3 / Component 2 pipeline

The standalone entry point is:

uv run python -m pipeline.component2.main \
  --vtt "data/<video_id>/<lesson>.vtt" \
  --visuals-json "data/<video_id>/dense_analysis.json" \
  --output-root "data/<video_id>" \
  --video-id "<video_id>"

It currently does:

invalidation filter

parser/sync

LLM processor

writes markdown/debug artifacts

and outputs:

filtered visual events

output_intermediate/*.md

output_intermediate/*.chunks.json

output_intermediate/*.llm_debug.json

output_intermediate/*.reducer_usage.json

output_rag_ready/*.md 

pipeline

 

pipeline

That means Task 1 should wrap and document this flow, not replace it.

Deliverable for Task 1

The correct deliverable for Task 1 is:

A. A pipeline inventory document in code form

A structured inspection layer that knows:

what module runs where

what function is the current entry point

what input/output files are used

what objects are passed between stages

B. Compatibility guards

A small compatibility layer that preserves:

current CLI entry points

current Step 2 dense analysis behavior

current Step 3 markdown outputs

C. Extension hooks

A controlled place where future tasks can insert:

knowledge extraction

evidence linking

rule reduction

exporters

without destabilizing old behavior.

What to implement in Python
1. Create a pipeline/contracts.py

This file defines the current stable interface and future extension points.

Purpose

It becomes the single reference for:

output directories

stage names

artifact names

current/legacy vs new outputs

Example
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

    # Future-safe placeholders
    def knowledge_events_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.knowledge_events.json"

    def evidence_index_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.evidence_index.json"

    def rule_cards_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.rule_cards.json"

    def concept_graph_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.concept_graph.json"
Why this matters

Right now the docs already note a mismatch between README references and actual output folders, and the real code uses output_intermediate/ and output_rag_ready/. 

FRAMEWORK_MODULES


This file removes ambiguity and gives the next tasks a stable base.

2. Create pipeline/stage_registry.py

This file defines a stage map for inspection and later orchestration.

Purpose

Instead of scattering stage knowledge across modules, formalize it.

Example
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    description: str
    callable_path: str
    required_inputs: list[str]
    outputs: list[str]
    enabled_by_default: bool = True
    legacy_stage: bool = False


STAGE_REGISTRY = [
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
        callable_path="pipeline.invalidation_filter",
        required_inputs=["dense_analysis.json"],
        outputs=["filtered_visual_events.json", "filtered_visual_events.debug.json"],
        legacy_stage=True,
    ),
    StageSpec(
        stage_id="step3_parse_and_sync",
        description="Parse VTT and build semantic lesson chunks",
        callable_path="pipeline.component2.parser",
        required_inputs=["vtt", "filtered_visual_events.json"],
        outputs=["output_intermediate/*.chunks.json"],
        legacy_stage=True,
    ),
    StageSpec(
        stage_id="step3_markdown_llm",
        description="Generate enriched markdown chunks",
        callable_path="pipeline.component2.llm_processor",
        required_inputs=["LessonChunk[]"],
        outputs=["output_intermediate/*.md", "output_intermediate/*.llm_debug.json"],
        legacy_stage=True,
    ),
    StageSpec(
        stage_id="step3_reducer",
        description="Whole-document RAG reducer",
        callable_path="pipeline.component2.reducer",
        required_inputs=["output_intermediate/*.md"],
        outputs=["output_rag_ready/*.md", "output_intermediate/*.reducer_usage.json"],
        legacy_stage=True,
    ),
]
Why this matters

It gives you a machine-readable map of the current pipeline as documented in pipeline.md, including the current markdown-centric Step 3 flow. 

pipeline

3. Create pipeline/inspection.py

This is the main Task 1 implementation.

Purpose

Programmatically inspect the current pipeline and produce a report showing:

available modules

resolved function symbols

expected artifacts

whether each artifact exists for a video root

compatibility status

Example interface
from dataclasses import dataclass, asdict
from importlib import import_module
from pathlib import Path
from typing import Optional
import json

from pipeline.contracts import PipelinePaths
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


def resolve_callable(callable_path: str):
    module_name, attr_name = callable_path.rsplit(".", 1)
    module = import_module(module_name)
    return getattr(module, attr_name)


def inspect_stages() -> list[StageInspectionResult]:
    results = []
    for stage in STAGE_REGISTRY:
        notes = []
        import_ok = False
        callable_exists = False
        try:
            obj = resolve_callable(stage.callable_path)
            import_ok = True
            callable_exists = callable(obj)
        except Exception as e:
            notes.append(str(e))
        results.append(StageInspectionResult(
            stage_id=stage.stage_id,
            callable_path=stage.callable_path,
            import_ok=import_ok,
            callable_exists=callable_exists,
            notes=notes,
        ))
    return results


def inspect_artifacts(video_root: Path, lesson_name: Optional[str] = None) -> list[ArtifactInspectionResult]:
    paths = PipelinePaths(video_root=video_root)
    artifacts = [
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
        ArtifactInspectionResult(name, str(path), path.exists())
        for name, path in artifacts
    ]


def build_report(video_root: Path, lesson_name: Optional[str] = None) -> PipelineInspectionReport:
    stage_results = inspect_stages()
    artifact_results = inspect_artifacts(video_root, lesson_name)
    warnings = []
    backward_compatible = True

    for stage in stage_results:
        if not (stage.import_ok and stage.callable_exists):
            warnings.append(f"Stage {stage.stage_id} is not resolvable.")
            if stage.stage_id in {
                "step2_dense_analysis",
                "step3_invalidation_filter",
                "step3_parse_and_sync",
                "step3_markdown_llm",
                "step3_reducer",
            }:
                backward_compatible = False

    return PipelineInspectionReport(
        video_root=str(video_root),
        stage_results=stage_results,
        artifact_results=artifact_results,
        backward_compatible=backward_compatible,
        warnings=warnings,
    )


def write_report(video_root: Path, output_path: Path, lesson_name: Optional[str] = None) -> None:
    report = build_report(video_root, lesson_name)
    output_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
Why this matters

Task 1 needs a real inspection tool, not just reading docs. This lets the coding agent prove what exists before making changes.

4. Add a non-breaking wrapper around pipeline.component2.main

The Step 3 pipeline currently orchestrates invalidation filter → parser → LLM processor → reducer and writes markdown/debug outputs. 

pipeline

Task 1 should not change behavior yet. It should wrap it.

Create pipeline/component2/orchestrator.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pipeline.contracts import PipelinePaths
from pipeline.inspection import build_report


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
    target_duration_seconds: int = 90
    max_concurrency: int = 4
    enable_structured_outputs: bool = False  # future flag


@dataclass
class Component2RunArtifacts:
    inspection_report_path: Path
    filtered_visuals_path: Path
    chunks_path: Optional[Path]
    pass1_markdown_path: Optional[Path]
    rag_ready_markdown_path: Optional[Path]


def prepare_component2_run(config: Component2RunConfig, lesson_name: str) -> Component2RunArtifacts:
    paths = PipelinePaths(video_root=config.output_root)
    inspection_report_path = config.output_root / "pipeline_inspection.json"
    report = build_report(config.output_root, lesson_name=lesson_name)
    inspection_report_path.write_text(
        __import__("json").dumps(__import__("dataclasses").asdict(report), indent=2),
        encoding="utf-8",
    )
    return Component2RunArtifacts(
        inspection_report_path=inspection_report_path,
        filtered_visuals_path=paths.filtered_visuals_path,
        chunks_path=paths.lesson_chunks_path(lesson_name),
        pass1_markdown_path=paths.pass1_markdown_path(lesson_name),
        rag_ready_markdown_path=paths.rag_ready_markdown_path(lesson_name),
    )
Why this matters

It inserts a stable preflight step without changing output behavior.

5. Add feature flags, not branching rewrites

Task 1 should introduce config flags that default to old behavior.

Recommended flags

enable_structured_outputs=False

enable_rule_cards=False

enable_evidence_index=False

enable_concept_graph=False

preserve_legacy_markdown=True

Example
from dataclasses import dataclass


@dataclass
class PipelineFeatureFlags:
    preserve_legacy_markdown: bool = True
    enable_structured_outputs: bool = False
    enable_rule_cards: bool = False
    enable_evidence_index: bool = False
    enable_concept_graph: bool = False

This is the safest possible compatibility move.

Step-by-step coding plan for Task 1
Step 1 — Add path contracts

Create pipeline/contracts.py.

Acceptance criteria

centralizes output paths

matches current real folders:

output_intermediate/

output_rag_ready/ 

FRAMEWORK_MODULES

Step 2 — Add stage registry

Create pipeline/stage_registry.py.

Acceptance criteria

lists current documented stage order

distinguishes legacy Step 3 markdown stages from future ones

contains callable paths for inspection

Step 3 — Add inspection utility

Create pipeline/inspection.py.

Acceptance criteria

can import and verify all current main stage callables

can report missing outputs for a lesson/video root

writes pipeline_inspection.json

Step 4 — Add Component 2 preflight wrapper

Create pipeline/component2/orchestrator.py.

Acceptance criteria

can be called before current Step 3 logic

writes inspection report

does not change old output content

Step 5 — Integrate inspection into pipeline/component2/main.py

Minimal change:

call preflight preparation first

keep current pipeline after that unchanged

Acceptance criteria

existing CLI still works

current markdown outputs still appear exactly where expected

no regression in current Step 3 behavior

Step 6 — Add feature flags

Introduce flags in config or local runtime object.

Acceptance criteria

old behavior remains default

future structured outputs can be added without changing CLI semantics

Step 7 — Add tests

Create tests for Task 1 only.

Suggested test plan for Task 1
Test 1 — stage inspection resolves current core modules

Verify the inspection utility can resolve:

pipeline.main.main

pipeline.dense_analyzer.run_analysis

invalidation filter callable/module

parser callable/module

LLM processor callable/module

This directly supports the instruction to inspect orchestration and preserve dense-analysis behavior. 

Response: Visual Decoding Review

Test 2 — path contract matches current output structure

Given video_root = data/test_video, check:

output_intermediate/

output_rag_ready/

filtered visual paths

Test 3 — preflight report generation

Given a fake lesson name, ensure pipeline_inspection.json is created.

Test 4 — backward compatibility flag defaults

Ensure all new feature flags default to legacy behavior.

Test 5 — no disruption to existing CLI

Smoke test:

invoke component2 main with mocks

verify current downstream calls still occur in same order

Recommended folder additions

Add only these files for Task 1:

pipeline/
  contracts.py
  stage_registry.py
  inspection.py

pipeline/component2/
  orchestrator.py

Do not add knowledge_builder.py, evidence_linker.py, rule_reducer.py, or exporters yet. Those belong to later tasks.

What Task 1 should not do

Task 1 should not:

change dense_analyzer.run_analysis

change invalidation logic

change the parser chunking logic

change markdown prompt semantics

change reducer behavior

introduce new JSON artifacts as required outputs yet

Those come later.

Task 1 is only about safely understanding and wrapping the current system.

Definition of done for Task 1

Task 1 is complete when all of these are true:

There is a programmatic inspection report for the existing pipeline

Current CLI entry points still work

Dense analysis generation remains untouched

The existing Step 3 markdown pipeline still produces:

filtered visuals

chunks json

pass1 markdown

llm debug

reducer usage

rag ready markdown 

pipeline

The codebase now has a clear, documented place to add future structured-output stages without rewriting the old flow

Short instruction block for the coding agent

You can copy this part directly if you want a tighter implementation directive:

Implement Task 1 only.

Goal:
- inspect the current pipeline programmatically
- preserve backward compatibility
- add safe extension points for future structured JSON outputs

Do not redesign behavior yet.

Add:
1. pipeline/contracts.py
2. pipeline/stage_registry.py
3. pipeline/inspection.py
4. pipeline/component2/orchestrator.py

Requirements:
- centralize path conventions for current outputs
- define a machine-readable registry of current stages
- implement an inspection report that verifies stage callables and known artifacts
- integrate a preflight inspection into pipeline.component2.main
- preserve existing CLI and existing Step 2 / Step 3 behavior by default
- add feature flags for future structured outputs, all defaulting to disabled

Do not modify dense analysis logic.
Do not replace the markdown pipeline yet.
Do not change reducer behavior.
Add tests for inspection, path contracts, compatibility defaults, and preflight report generation.

If you want, I can do the same for Task 2 and make it equally concrete in Python terms.