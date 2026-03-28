"""Click CLI: batch extract audio from videos in a folder."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import click

from helpers.utils.video_audio import extract_audio_from_folder


def _cli_progress(event: Mapping[str, Any]) -> None:
    et = event["event"]
    if et == "batch_start":
        n = int(event["total"])
        if n == 0:
            click.echo("No matching video files found.")
        else:
            pw = int(event.get("parallel_workers", 1))
            if pw > 1:
                click.echo(
                    f"Found {n} video file(s). Extracting with up to {pw} parallel workers…",
                )
            else:
                click.echo(f"Found {n} video file(s). Extracting audio…")
        return
    if et == "file_start":
        click.echo(
            f"[{event['index']}/{event['total']}] {event['source'].name} → encoding…",
        )
        return
    if et == "encode_progress":
        click.echo(
            f"        [{event['index']}/{event['total']}] … {event['message']}",
        )
        return
    if et == "file_end":
        idx, tot = int(event["index"]), int(event["total"])
        if event["ok"]:
            click.echo(f"[{idx}/{tot}] OK   → {event['output'].name}")
        else:
            click.echo(f"[{idx}/{tot}] FAIL — {event['error']}", err=True)


@click.command()
@click.argument(
    "input_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: INPUT_DIR/audio/).",
)
@click.option("--recursive", is_flag=True, help="Recurse into subdirectories.")
@click.option("--overwrite", is_flag=True, help="Overwrite existing audio files.")
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="No per-file progress (summary and errors only).",
)
@click.option(
    "--max-workers",
    type=int,
    default=None,
    help=(
        "Max parallel FFmpeg jobs (default: min(files, cpu_cores/2); use 1 for serial)."
    ),
)
def main(
    input_dir: Path,
    output_dir: Path | None,
    recursive: bool,
    overwrite: bool,
    quiet: bool,
    max_workers: int | None,
) -> None:
    """Extract audio tracks from video files in INPUT_DIR."""
    if max_workers is not None and max_workers < 1:
        raise click.UsageError("--max-workers must be at least 1.")
    reports = extract_audio_from_folder(
        input_dir,
        output_dir,
        recursive=recursive,
        overwrite=overwrite,
        progress_callback=None if quiet else _cli_progress,
        max_workers=max_workers,
    )
    ok_count = sum(1 for r in reports if r.ok)
    fail_count = sum(1 for r in reports if not r.ok)
    click.echo(
        f"Done: {ok_count} extracted, {fail_count} failed out of {len(reports)} videos.",
    )
    if quiet:
        for r in reports:
            if not r.ok:
                click.echo(f"  FAIL: {r.source.name} -- {r.error}", err=True)


if __name__ == "__main__":
    main()
