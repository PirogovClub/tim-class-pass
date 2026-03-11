from __future__ import annotations

from pathlib import Path

import click

from helpers.usage_report import build_video_usage_summary, write_video_usage_summary


@click.command(help="Build or inspect AI usage summary for a processed video run.")
@click.option("--video-id", required=True, help="Video directory under data/.")
@click.option(
    "--output",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional output path for the JSON summary. Defaults to data/<video_id>/ai_usage_summary.json.",
)
@click.option("--print-summary", "print_summary", is_flag=True, help="Print the summary totals to stdout.")
def main(video_id: str, output: Path | None, print_summary: bool) -> None:
    video_dir = Path("data") / video_id
    destination = write_video_usage_summary(video_dir, output_path=output)
    if print_summary:
        summary = build_video_usage_summary(video_dir)
        click.echo(f"Summary written to: {destination}")
        click.echo(f"Requests: {summary['totals']['request_count']}")
        click.echo(f"Prompt tokens: {summary['totals']['prompt_tokens']}")
        click.echo(f"Output tokens: {summary['totals']['output_tokens']}")
        click.echo(f"Total tokens: {summary['totals']['total_tokens']}")
        return
    click.echo(str(destination))


if __name__ == "__main__":
    main()
