from __future__ import annotations

import asyncio
from pathlib import Path

import click

from pipeline.component2.llm_processor import assemble_video_markdown, process_chunks, write_llm_debug
from pipeline.component2.parser import parse_and_sync, write_lesson_chunks
from pipeline.invalidation_filter import run_invalidation_filter


def _default_output_root(vtt_path: Path) -> Path:
    return vtt_path.parent


def _derive_lesson_name(vtt_path: Path) -> str:
    return vtt_path.stem


def run_component2_pipeline(
    *,
    vtt_path: Path | str,
    visuals_json_path: Path | str,
    output_root: Path | str | None = None,
    video_id: str | None = None,
    model: str | None = None,
    target_duration_seconds: float = 120.0,
    max_concurrency: int = 5,
) -> dict[str, Path]:
    vtt = Path(vtt_path)
    visuals_json = Path(visuals_json_path)
    lesson_name = _derive_lesson_name(vtt)
    root = Path(output_root) if output_root is not None else _default_output_root(vtt)
    output_markdown_dir = root / "output_markdown"
    output_markdown_dir.mkdir(parents=True, exist_ok=True)

    filtered_events_path = root / "filtered_visual_events.json"
    filtered_debug_path = root / "filtered_visual_events.debug.json"
    chunk_debug_path = output_markdown_dir / f"{lesson_name}.chunks.json"
    llm_debug_path = output_markdown_dir / f"{lesson_name}.llm_debug.json"
    markdown_path = output_markdown_dir / f"{lesson_name}.md"

    run_invalidation_filter(
        input_path=visuals_json,
        output_path=filtered_events_path,
        debug_path=filtered_debug_path,
    )
    chunks = parse_and_sync(
        vtt_path=vtt,
        filtered_events_path=filtered_events_path,
        target_duration_seconds=target_duration_seconds,
    )
    write_lesson_chunks(chunk_debug_path, chunks)
    processed_chunks = asyncio.run(
        process_chunks(
            chunks,
            video_id=video_id,
            model=model,
            max_concurrency=max_concurrency,
        )
    )
    markdown = assemble_video_markdown(lesson_name, processed_chunks)
    markdown_path.write_text(markdown, encoding="utf-8")
    write_llm_debug(llm_debug_path, processed_chunks)

    return {
        "filtered_events_path": filtered_events_path,
        "filtered_debug_path": filtered_debug_path,
        "chunk_debug_path": chunk_debug_path,
        "llm_debug_path": llm_debug_path,
        "markdown_path": markdown_path,
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
    target_duration_seconds: float,
    max_concurrency: int,
) -> None:
    outputs = run_component2_pipeline(
        vtt_path=vtt,
        visuals_json_path=visuals_json,
        output_root=output_root,
        video_id=video_id,
        model=model,
        target_duration_seconds=target_duration_seconds,
        max_concurrency=max_concurrency,
    )
    for name, path in outputs.items():
        click.echo(f"{name}: {path}")


if __name__ == "__main__":
    main()
