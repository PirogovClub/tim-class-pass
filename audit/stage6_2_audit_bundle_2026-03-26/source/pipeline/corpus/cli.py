"""Click CLI for corpus build + validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from pipeline.corpus.corpus_builder import build_corpus
from pipeline.corpus.corpus_validation import validate_corpus_outputs


@click.group()
def cli() -> None:
    """Stage 6.2 corpus operations."""
    pass


@cli.command("build")
@click.option(
    "--input-root",
    required=False,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Root directory containing lesson data folders (fallback discovery mode).",
)
@click.option(
    "--lesson-registry",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to Stage 6.1 lesson_registry.json (authoritative ingestion mode).",
)
@click.option(
    "--output-root",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for corpus output files.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors.",
)
def build_cmd(
    input_root: Path | None,
    lesson_registry: Path | None,
    output_root: Path,
    strict: bool,
) -> None:
    """Freeze schema v1 and build corpus-level exports."""
    click.echo(f"Input root : {input_root}")
    click.echo(f"Output root: {output_root}")
    click.echo(f"Strict mode: {strict}")
    click.echo()

    if input_root is None and lesson_registry is None:
        click.echo("ERROR: provide --lesson-registry or --input-root", err=True)
        sys.exit(2)
    resolved_input = input_root or lesson_registry.parent

    try:
        summary = build_corpus(
            resolved_input,
            output_root,
            strict=strict,
            lesson_registry_path=lesson_registry,
        )
    except RuntimeError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    click.echo("Corpus build complete.")
    click.echo(f"  Lessons          : {summary['lessons']}")
    click.echo(f"  Knowledge events : {summary['events']}")
    click.echo(f"  Rule cards       : {summary['rules']}")
    click.echo(f"  Evidence refs    : {summary['evidence']}")
    click.echo(f"  Concept nodes    : {summary['concept_nodes']}")
    click.echo(f"  Concept relations: {summary['concept_relations']}")
    click.echo(f"  Validation       : {summary['validation_status']}")
    click.echo(f"  Skipped registry : {len(summary.get('skipped_registry_lessons', []))}")
    click.echo(f"  Output           : {summary['output_root']}")


@cli.command("validate")
@click.option(
    "--output-root",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing corpus outputs to validate.",
)
@click.option(
    "--lesson-registry",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional Stage 6.1 lesson_registry.json for replay checks.",
)
@click.option(
    "--report",
    required=False,
    type=click.Path(path_type=Path),
    default=None,
    help="Optional path to write corpus_validation_report.json.",
)
def validate_cmd(output_root: Path, lesson_registry: Path | None, report: Path | None) -> None:
    result = validate_corpus_outputs(output_root, lesson_registry_path=lesson_registry)
    payload = result.to_dict()
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if report is not None:
        report.write_text(text, encoding="utf-8")
        click.echo(f"Wrote {report}")
    else:
        click.echo(text)
    if result.errors:
        sys.exit(1)


if __name__ == "__main__":
    cli()
