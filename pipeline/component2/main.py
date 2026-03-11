from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import time
from typing import Callable

import click

from pipeline.component2.llm_processor import assemble_video_markdown, process_chunks, write_llm_debug
from pipeline.component2.quant_reducer import synthesize_full_document
from pipeline.component2.parser import parse_and_sync, seconds_to_mmss, write_lesson_chunks
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
    reducer_model: str | None = None,
    target_duration_seconds: float = 120.0,
    max_concurrency: int = 5,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    pipeline_started_at = time.perf_counter()

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

    filtered_events_path = root / "filtered_visual_events.json"
    filtered_debug_path = root / "filtered_visual_events.debug.json"
    chunk_debug_path = output_intermediate_dir / f"{lesson_name}.chunks.json"
    llm_debug_path = output_intermediate_dir / f"{lesson_name}.llm_debug.json"
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

    _emit(
        "Step 3.3/5: Running Pass 1 literal-scribe synthesis "
        f"(chunks={len(chunks)}, concurrency={max(1, max_concurrency)})..."
    )

    def _on_chunk_progress(completed: int, total: int, chunk, chunk_elapsed_seconds: float) -> None:
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
            max_concurrency=max_concurrency,
            progress_callback=_on_chunk_progress,
        )
    )
    _emit(f"Step 3.3/5 complete: synthesized {len(processed_chunks)} intermediate markdown chunks.")

    _emit("Step 3.4/5: Writing intermediate markdown and debug artifacts...")
    intermediate_markdown = assemble_video_markdown(lesson_name, processed_chunks)
    intermediate_markdown_path.write_text(intermediate_markdown, encoding="utf-8")
    write_llm_debug(llm_debug_path, processed_chunks)
    _emit(f"Step 3.4/5 complete: wrote `{intermediate_markdown_path.name}` and debug artifacts.")

    _emit("Step 3.5/5: Running Pass 2 quant reduction for RAG-ready markdown...")
    rag_ready_markdown = synthesize_full_document(
        intermediate_markdown,
        video_id=video_id,
        model=reducer_model,
    )
    rag_ready_markdown_path.write_text(rag_ready_markdown, encoding="utf-8")
    _emit(f"Step 3.5/5 complete: wrote `{rag_ready_markdown_path.name}`.")

    return {
        "filtered_events_path": filtered_events_path,
        "filtered_debug_path": filtered_debug_path,
        "chunk_debug_path": chunk_debug_path,
        "llm_debug_path": llm_debug_path,
        "intermediate_markdown_path": intermediate_markdown_path,
        "rag_ready_markdown_path": rag_ready_markdown_path,
        "markdown_path": rag_ready_markdown_path,
    }


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
    "--reducer-model",
    default=None,
    help="Optional Gemini model override for the final quant-reducer pass.",
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
def main(
    vtt: Path,
    visuals_json: Path,
    output_root: Path | None,
    video_id: str | None,
    model: str | None,
    reducer_model: str | None,
    target_duration_seconds: float,
    max_concurrency: int,
) -> None:
    def _timestamped_echo(message: str) -> None:
        click.echo(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - {message}")

    outputs = run_component2_pipeline(
        vtt_path=vtt,
        visuals_json_path=visuals_json,
        output_root=output_root,
        video_id=video_id,
        model=model,
        reducer_model=reducer_model,
        target_duration_seconds=target_duration_seconds,
        max_concurrency=max_concurrency,
        progress_callback=_timestamped_echo,
    )
    for name, path in outputs.items():
        click.echo(f"{name}: {path}")


if __name__ == "__main__":
    main()
