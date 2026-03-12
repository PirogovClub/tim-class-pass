from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Callable

import click

from helpers.usage_report import write_video_usage_summary
from pipeline.component2.evidence_linker import (
    build_evidence_index,
    load_knowledge_events,
    save_evidence_debug,
    save_evidence_index,
)
from pipeline.component2.knowledge_builder import (
    adapt_chunks,
    build_knowledge_events_from_extraction_results,
    save_knowledge_debug,
    save_knowledge_events,
)
from pipeline.component2.llm_processor import (
    assemble_video_markdown,
    legacy_debug_rows,
    process_chunks,
    process_chunks_knowledge_extract,
    process_rule_cards_markdown_render,
    write_llm_debug,
)
from pipeline.component2.orchestrator import Component2RunConfig, prepare_component2_run
from pipeline.component2.parser import parse_and_sync, seconds_to_mmss, write_lesson_chunks
from pipeline.component2.quant_reducer import synthesize_full_document
from pipeline.component2.rule_reducer import (
    build_rule_cards,
    load_evidence_index,
    load_knowledge_events as load_knowledge_events_collection,
    save_rule_cards,
    save_rule_debug,
)
from pipeline.component2.exporters import (
    export_review_markdown,
    export_rag_markdown,
    load_rule_cards as load_rule_cards_for_export,
    write_export_manifest,
)
from pipeline.contracts import PipelinePaths
from pipeline.schemas import RuleCardCollection
from pipeline.invalidation_filter import (
    build_debug_report,
    filter_visual_events,
    load_dense_analysis,
    write_debug_report,
    write_filtered_events,
)


def _default_output_root(vtt_path: Path) -> Path:
    return vtt_path.parent


def _derive_lesson_name(vtt_path: Path) -> str:
    return vtt_path.stem


def _format_elapsed(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def run_component2_pipeline(
    *,
    vtt_path: Path | str,
    visuals_json_path: Path | str,
    output_root: Path | str | None = None,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    reducer_model: str | None = None,
    reducer_provider: str | None = None,
    target_duration_seconds: float = 120.0,
    max_concurrency: int = 5,
    enable_knowledge_events: bool = False,
    enable_evidence_linking: bool = False,
    enable_rule_cards: bool = False,
    preserve_legacy_markdown: bool = True,
    enable_new_markdown_render: bool = False,
    enable_exporters: bool = False,
    use_llm_review_render: bool = False,
    use_llm_rag_render: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    pipeline_started_at = time.perf_counter()
    knowledge_collection = None
    evidence_index = None
    rule_cards = None

    def _emit(message: str) -> None:
        if progress_callback is not None:
            elapsed = _format_elapsed(time.perf_counter() - pipeline_started_at)
            progress_callback(f"[+{elapsed}] {message}")

    vtt = Path(vtt_path)
    visuals_json = Path(visuals_json_path)
    lesson_name = _derive_lesson_name(vtt)
    root = Path(output_root) if output_root is not None else _default_output_root(vtt)
    output_intermediate_dir = root / "output_intermediate"
    output_rag_ready_dir = root / "output_rag_ready"
    output_intermediate_dir.mkdir(parents=True, exist_ok=True)
    output_rag_ready_dir.mkdir(parents=True, exist_ok=True)
    step4_ran = False
    step5_ran = False

    # Preflight: write pipeline inspection report (Task 1)
    _preflight_config = Component2RunConfig(
        vtt_path=vtt,
        visuals_json_path=visuals_json,
        output_root=root,
        video_id=video_id,
        model=model,
        provider=provider,
        reducer_model=reducer_model,
        reducer_provider=reducer_provider,
        target_duration_seconds=target_duration_seconds,
        max_concurrency=max_concurrency,
    )
    prepare_component2_run(_preflight_config, lesson_name)

    filtered_events_path = root / "filtered_visual_events.json"
    filtered_debug_path = root / "filtered_visual_events.debug.json"
    chunk_debug_path = output_intermediate_dir / f"{lesson_name}.chunks.json"
    llm_debug_path = output_intermediate_dir / f"{lesson_name}.llm_debug.json"
    reducer_usage_path = output_intermediate_dir / f"{lesson_name}.reducer_usage.json"
    intermediate_markdown_path = output_intermediate_dir / f"{lesson_name}.md"
    rag_ready_markdown_path = output_rag_ready_dir / f"{lesson_name}.md"

    _emit(f"Step 3.1/5: Filtering instructional visual events from `{visuals_json.name}`...")
    raw_analysis = load_dense_analysis(visuals_json)
    events = filter_visual_events(raw_analysis)
    filter_report = build_debug_report(raw_analysis, events)
    write_filtered_events(filtered_events_path, events)
    write_debug_report(filtered_debug_path, filter_report)
    _emit(
        "Step 3.1/5 complete: "
        f"kept {filter_report['kept_events']} events, rejected {filter_report['rejected_frames']}, "
        f"input frames {filter_report['input_frames']}."
    )

    _emit(f"Step 3.2/5: Synchronizing transcript `{vtt.name}` with filtered events...")
    chunks = parse_and_sync(
        vtt_path=vtt,
        filtered_events_path=filtered_events_path,
        target_duration_seconds=target_duration_seconds,
    )
    write_lesson_chunks(chunk_debug_path, chunks)
    total_transcript_lines = sum(len(chunk.transcript_lines) for chunk in chunks)
    total_chunk_events = sum(len(chunk.visual_events) for chunk in chunks)
    _emit(
        "Step 3.2/5 complete: "
        f"created {len(chunks)} chunks from {total_transcript_lines} transcript lines and "
        f"{total_chunk_events} synchronized visual events."
    )

    if enable_knowledge_events:
        _emit("Step 3.2b: Extracting structured knowledge events...")
        paths = PipelinePaths(video_root=root)
        raw_chunks = [c.model_dump() for c in chunks]
        adapted = adapt_chunks(raw_chunks, lesson_id=lesson_name, lesson_title=None)

        def _on_extraction_progress(
            completed: int, total: int, chunk, chunk_elapsed_seconds: float
        ) -> None:
            _emit(
                f"  Chunk {completed}/{total} complete "
                f"[{seconds_to_mmss(chunk.start_time_seconds)}-{seconds_to_mmss(chunk.end_time_seconds)}], "
                f"chunk_time={chunk_elapsed_seconds:.1f}s."
            )

        results = asyncio.run(
            process_chunks_knowledge_extract(
                adapted,
                video_id=video_id,
                model=model,
                provider=provider,
                max_concurrency=max_concurrency,
                progress_callback=_on_extraction_progress,
            )
        )
        extraction_results = [r[1] for r in results]
        knowledge_collection, debug_rows = build_knowledge_events_from_extraction_results(
            adapted, extraction_results, lesson_name, None
        )
        for i, row in enumerate(debug_rows):
            if i < len(results):
                row["request_usage"] = results[i][2]
        save_knowledge_events(knowledge_collection, paths.knowledge_events_path(lesson_name))
        assert knowledge_collection is not None
        save_knowledge_debug(debug_rows, paths.knowledge_debug_path(lesson_name))
        _emit(
            f"Step 3.2b complete: wrote {len(knowledge_collection.events)} events to "
            f"{paths.knowledge_events_path(lesson_name).name}, debug to {paths.knowledge_debug_path(lesson_name).name}."
        )

    if enable_evidence_linking:
        paths = PipelinePaths(video_root=root)
        knowledge_events_for_evidence = None
        if enable_knowledge_events:
            knowledge_events_for_evidence = knowledge_collection.events
        else:
            ke_path = paths.knowledge_events_path(lesson_name)
            if ke_path.exists():
                knowledge_events_for_evidence = load_knowledge_events(ke_path)
            else:
                _emit(
                    f"Step 4 skipped: enable_evidence_linking is True but {ke_path.name} not found. "
                    "Run with --enable-knowledge-events first or ensure the file exists."
                )
        if knowledge_events_for_evidence is not None:
            _emit("Step 4: Linking visual evidence to knowledge events...")
            raw_chunks = [c.model_dump() for c in chunks]
            evidence_index, evidence_debug = build_evidence_index(
                lesson_id=lesson_name,
                knowledge_events=knowledge_events_for_evidence,
                chunks=raw_chunks,
                dense_analysis=raw_analysis,
            )
            save_evidence_index(evidence_index, paths.evidence_index_path(lesson_name))
            save_evidence_debug(evidence_debug, paths.evidence_debug_path(lesson_name))
            step4_ran = True
            assert evidence_index is not None
            _emit(
                f"Step 4 complete: wrote {len(evidence_index.evidence_refs)} evidence refs to "
                f"{paths.evidence_index_path(lesson_name).name}, debug to {paths.evidence_debug_path(lesson_name).name}."
            )

    if enable_rule_cards:
        paths = PipelinePaths(video_root=root)
        ke_path = paths.knowledge_events_path(lesson_name)
        ei_path = paths.evidence_index_path(lesson_name)
        if knowledge_collection is None and ke_path.exists():
            knowledge_collection = load_knowledge_events_collection(ke_path)
        if evidence_index is None and ei_path.exists():
            evidence_index = load_evidence_index(ei_path)
        if knowledge_collection is not None and evidence_index is not None:
            _emit("Step 4b: Building rule cards from knowledge events and evidence...")
            rule_cards, rule_debug = build_rule_cards(
                knowledge_collection=knowledge_collection,
                evidence_index=evidence_index,
            )
            save_rule_cards(rule_cards, paths.rule_cards_path(lesson_name))
            save_rule_debug(rule_debug, paths.rule_debug_path(lesson_name))
            step5_ran = True
            _emit(
                f"Step 4b complete: wrote {len(rule_cards.rules)} rule cards to "
                f"{paths.rule_cards_path(lesson_name).name}, debug to {paths.rule_debug_path(lesson_name).name}."
            )
        else:
            if knowledge_collection is None:
                _emit(
                    f"Step 4b skipped: enable_rule_cards is True but {ke_path.name} not found. "
                    "Run with --enable-knowledge-events first or ensure the file exists."
                )
            if evidence_index is None:
                _emit(
                    f"Step 4b skipped: enable_rule_cards requires {ei_path.name}. "
                    "Run with --enable-evidence-linking first or ensure the file exists."
                )

    # Task 7 exporter stage: derive review_markdown.md and rag_ready.md from structured JSON only
    exporter_ran = False
    if enable_exporters:
        paths = PipelinePaths(video_root=root)
        rc_path = paths.rule_cards_path(lesson_name)
        ei_path = paths.evidence_index_path(lesson_name)
        ke_path = paths.knowledge_events_path(lesson_name)
        if not rc_path.exists():
            _emit(
                f"Exporters skipped: {rc_path.name} not found. "
                "Run with --enable-rule-cards first or ensure the file exists."
            )
        elif not ei_path.exists():
            _emit(
                f"Exporters skipped: {ei_path.name} not found. "
                "Run with --enable-evidence-linking first or ensure the file exists."
            )
        else:
            _emit("Step (exporters): Generating review and RAG markdown from rule cards and evidence...")
            review_path = paths.review_markdown_path(lesson_name)
            rag_path = paths.rag_ready_export_path(lesson_name)
            review_debug_path = paths.review_render_debug_path(lesson_name) if use_llm_review_render else None
            rag_debug_path = paths.rag_render_debug_path(lesson_name) if use_llm_rag_render else None
            lesson_title = None
            if rule_cards is not None:
                lesson_title = getattr(rule_cards, "lesson_id", None)  # use from index below
            if evidence_index is not None:
                lesson_title = getattr(evidence_index, "lesson_title", None) or lesson_title
            _, review_usage = export_review_markdown(
                lesson_id=lesson_name,
                lesson_title=lesson_title,
                rule_cards_path=rc_path,
                evidence_index_path=ei_path,
                knowledge_events_path=ke_path if ke_path.exists() else None,
                output_path=review_path,
                use_llm=use_llm_review_render,
                video_id=video_id,
                model=model,
                provider=provider,
                review_render_debug_path=review_debug_path,
            )
            _, rag_usage = export_rag_markdown(
                lesson_id=lesson_name,
                lesson_title=lesson_title,
                rule_cards_path=rc_path,
                evidence_index_path=ei_path,
                knowledge_events_path=ke_path if ke_path.exists() else None,
                output_path=rag_path,
                use_llm=use_llm_rag_render,
                video_id=video_id,
                model=model,
                provider=provider,
                rag_render_debug_path=rag_debug_path,
            )
            # Optional export manifest
            rc_coll = rule_cards if rule_cards is not None else load_rule_cards_for_export(rc_path)
            ei_coll = evidence_index if evidence_index is not None else load_evidence_index(ei_path)
            manifest_path = paths.output_review_dir / f"{lesson_name}.export_manifest.json"
            write_export_manifest(
                {
                    "lesson_id": lesson_name,
                    "review_markdown_path": str(review_path),
                    "rag_markdown_path": str(rag_path),
                    "used_llm_review_render": use_llm_review_render,
                    "used_llm_rag_render": use_llm_rag_render,
                    "rule_count": len(rc_coll.rules),
                    "evidence_count": len(ei_coll.evidence_refs),
                },
                manifest_path,
            )
            exporter_ran = True
            _emit(
                f"Step (exporters) complete: wrote `{review_path.name}`, `{rag_path.name}`, and manifest."
            )

    # New markdown render path (after 4b): requires rule_cards + evidence_index
    render_ran = False
    if enable_new_markdown_render:
        paths = PipelinePaths(video_root=root)
        rc_path = paths.rule_cards_path(lesson_name)
        ei_path = paths.evidence_index_path(lesson_name)
        if rule_cards is None and rc_path.exists():
            rule_cards = RuleCardCollection.model_validate_json(
                rc_path.read_text(encoding="utf-8")
            )
        if evidence_index is None and ei_path.exists():
            evidence_index = load_evidence_index(ei_path)
        if rule_cards is not None and evidence_index is not None:
            _emit("Step (render): Generating review markdown from rule cards and evidence...")
            render_result, render_usage = process_rule_cards_markdown_render(
                lesson_id=lesson_name,
                lesson_title=None,
                rule_cards=rule_cards.rules,
                evidence_refs=evidence_index.evidence_refs,
                render_mode="review",
                video_id=video_id,
                model=model,
                provider=provider,
            )
            review_md_path = output_intermediate_dir / f"{lesson_name}.review.md"
            review_md_path.write_text(render_result.markdown, encoding="utf-8")
            render_debug_path = output_intermediate_dir / f"{lesson_name}.render_debug.json"
            render_debug_row = {
                "num_rule_cards": len(rule_cards.rules),
                "num_evidence_refs": len(evidence_index.evidence_refs),
                "render_mode": "review",
                "markdown_preview": (render_result.markdown[:500] + "...")
                if len(render_result.markdown) > 500
                else render_result.markdown,
                "request_usage": render_usage,
            }
            write_llm_debug(render_debug_path, [render_debug_row])
            render_ran = True
            _emit(
                f"Step (render) complete: wrote `{review_md_path.name}` and `{render_debug_path.name}`."
            )
        else:
            if rule_cards is None:
                _emit(
                    "Render skipped: rule_cards not available. Run with --enable-rule-cards first or ensure rule_cards.json exists."
                )
            if evidence_index is None:
                _emit(
                    "Render skipped: evidence_index not available. Run with --enable-evidence-linking first or ensure evidence_index.json exists."
                )

    if preserve_legacy_markdown:
        _emit(
            "Step 3.3/5: Running Pass 1 literal-scribe synthesis "
            f"(chunks={len(chunks)}, concurrency={max(1, max_concurrency)})..."
        )

        def _on_chunk_progress(
            completed: int, total: int, chunk, chunk_elapsed_seconds: float
        ) -> None:
            _emit(
                f"  Chunk {completed}/{total} complete "
                f"[{seconds_to_mmss(chunk.start_time_seconds)}-{seconds_to_mmss(chunk.end_time_seconds)}], "
                f"{len(chunk.visual_events)} visual events, "
                f"chunk_time={chunk_elapsed_seconds:.1f}s."
            )

        processed_chunks = asyncio.run(
            process_chunks(
                chunks,
                video_id=video_id,
                model=model,
                provider=provider,
                max_concurrency=max_concurrency,
                progress_callback=_on_chunk_progress,
            )
        )
        _emit(
            f"Step 3.3/5 complete: synthesized {len(processed_chunks)} intermediate markdown chunks."
        )

        _emit("Step 3.4/5: Writing intermediate markdown and debug artifacts...")
        intermediate_markdown = assemble_video_markdown(lesson_name, processed_chunks)
        intermediate_markdown_path.write_text(intermediate_markdown, encoding="utf-8")
        write_llm_debug(llm_debug_path, legacy_debug_rows(processed_chunks))
        _emit(
            f"Step 3.4/5 complete: wrote `{intermediate_markdown_path.name}` and debug artifacts."
        )

        _emit("Step 3.5/5: Running Pass 2 quant reduction for RAG-ready markdown...")
        reducer_result = synthesize_full_document(
            intermediate_markdown,
            video_id=video_id,
            model=reducer_model,
            provider=reducer_provider,
        )
        if isinstance(reducer_result, tuple):
            rag_ready_markdown, reducer_usage = reducer_result
        else:
            rag_ready_markdown, reducer_usage = reducer_result, []
        rag_ready_markdown_path.write_text(rag_ready_markdown, encoding="utf-8")
        reducer_usage_path.write_text(
            json.dumps(reducer_usage, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        write_video_usage_summary(root)
        _emit(f"Step 3.5/5 complete: wrote `{rag_ready_markdown_path.name}`.")

    result: dict[str, Path] = {
        "filtered_events_path": filtered_events_path,
        "filtered_debug_path": filtered_debug_path,
        "chunk_debug_path": chunk_debug_path,
    }
    if preserve_legacy_markdown:
        result["llm_debug_path"] = llm_debug_path
        result["reducer_usage_path"] = reducer_usage_path
        result["intermediate_markdown_path"] = intermediate_markdown_path
        result["rag_ready_markdown_path"] = rag_ready_markdown_path
        result["markdown_path"] = rag_ready_markdown_path
    if enable_knowledge_events:
        paths = PipelinePaths(video_root=root)
        result["knowledge_events_path"] = paths.knowledge_events_path(lesson_name)
        result["knowledge_debug_path"] = paths.knowledge_debug_path(lesson_name)
    if step4_ran:
        paths = PipelinePaths(video_root=root)
        result["evidence_index_path"] = paths.evidence_index_path(lesson_name)
        result["evidence_debug_path"] = paths.evidence_debug_path(lesson_name)
    if step5_ran:
        paths = PipelinePaths(video_root=root)
        result["rule_cards_path"] = paths.rule_cards_path(lesson_name)
        result["rule_debug_path"] = paths.rule_debug_path(lesson_name)
    if render_ran:
        result["review_markdown_path"] = output_intermediate_dir / f"{lesson_name}.review.md"
        result["render_debug_path"] = output_intermediate_dir / f"{lesson_name}.render_debug.json"
    if exporter_ran:
        paths = PipelinePaths(video_root=root)
        result["review_markdown_export_path"] = paths.review_markdown_path(lesson_name)
        result["rag_ready_export_path"] = paths.rag_ready_export_path(lesson_name)
        result["export_manifest_path"] = paths.output_review_dir / f"{lesson_name}.export_manifest.json"
    return result


@click.command(help="Run the standalone Component 2 + Step 3 markdown synthesis pipeline.")
@click.option(
    "--vtt",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the raw VTT transcript.",
)
@click.option(
    "--visuals-json",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the dense frame-analysis JSON that will be invalidation-filtered.",
)
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output folder. Defaults to the VTT parent directory.",
)
@click.option(
    "--video-id",
    default=None,
    help="Optional video id used for config/model lookup.",
)
@click.option(
    "--model",
    default=None,
    help="Optional Gemini model override for markdown synthesis.",
)
@click.option(
    "--provider",
    default=None,
    type=click.Choice(["openai", "gemini", "mlx", "setra"]),
    help="Optional provider override for markdown synthesis.",
)
@click.option(
    "--reducer-model",
    default=None,
    help="Optional Gemini model override for the final quant-reducer pass.",
)
@click.option(
    "--reducer-provider",
    default=None,
    type=click.Choice(["openai", "gemini", "setra"]),
    help="Optional provider override for the final quant-reducer pass.",
)
@click.option(
    "--target-duration-seconds",
    type=float,
    default=120.0,
    show_default=True,
    help="Target chunk duration before semantic cut extension.",
)
@click.option(
    "--max-concurrency",
    type=int,
    default=5,
    show_default=True,
    help="Maximum number of concurrent Gemini chunk requests.",
)
@click.option(
    "--enable-knowledge-events",
    is_flag=True,
    default=False,
    help="Run structured knowledge extraction and write knowledge_events.json + knowledge_debug.json.",
)
@click.option(
    "--enable-evidence-linking",
    is_flag=True,
    default=False,
    help="Link visual evidence to knowledge events and write evidence_index.json + evidence_debug.json.",
)
@click.option(
    "--enable-rule-cards",
    is_flag=True,
    default=False,
    help="Build rule cards from knowledge events and evidence; write rule_cards.json and rule_debug.json.",
)
@click.option(
    "--no-preserve-legacy-markdown",
    "no_preserve_legacy_markdown",
    is_flag=True,
    default=False,
    help="Skip legacy chunk markdown synthesis and quant reducer (Steps 3.3–3.5).",
)
@click.option(
    "--enable-new-markdown-render",
    is_flag=True,
    default=False,
    help="Generate review markdown from rule cards and evidence (requires rule_cards + evidence_index).",
)
@click.option(
    "--enable-exporters",
    is_flag=True,
    default=False,
    help="Task 7: Export review_markdown.md and rag_ready.md from rule_cards + evidence_index (no raw chunks).",
)
@click.option(
    "--use-llm-review-render",
    is_flag=True,
    default=False,
    help="Use LLM for review markdown when --enable-exporters (default: deterministic).",
)
@click.option(
    "--use-llm-rag-render",
    is_flag=True,
    default=False,
    help="Use LLM for RAG markdown when --enable-exporters (default: deterministic).",
)
def main(
    vtt: Path,
    visuals_json: Path,
    output_root: Path | None,
    video_id: str | None,
    model: str | None,
    provider: str | None,
    reducer_model: str | None,
    reducer_provider: str | None,
    target_duration_seconds: float,
    max_concurrency: int,
    enable_knowledge_events: bool,
    enable_evidence_linking: bool,
    enable_rule_cards: bool,
    no_preserve_legacy_markdown: bool,
    enable_new_markdown_render: bool,
    enable_exporters: bool,
    use_llm_review_render: bool,
    use_llm_rag_render: bool,
) -> None:
    def _timestamped_echo(message: str) -> None:
        click.echo(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - {message}")

    outputs = run_component2_pipeline(
        vtt_path=vtt,
        visuals_json_path=visuals_json,
        output_root=output_root,
        video_id=video_id,
        model=model,
        provider=provider,
        reducer_model=reducer_model,
        reducer_provider=reducer_provider,
        target_duration_seconds=target_duration_seconds,
        max_concurrency=max_concurrency,
        enable_knowledge_events=enable_knowledge_events,
        enable_evidence_linking=enable_evidence_linking,
        enable_rule_cards=enable_rule_cards,
        preserve_legacy_markdown=not no_preserve_legacy_markdown,
        enable_new_markdown_render=enable_new_markdown_render,
        enable_exporters=enable_exporters,
        use_llm_review_render=use_llm_review_render,
        use_llm_rag_render=use_llm_rag_render,
        progress_callback=_timestamped_echo,
    )
    for name, path in outputs.items():
        click.echo(f"{name}: {path}")


if __name__ == "__main__":
    main()
