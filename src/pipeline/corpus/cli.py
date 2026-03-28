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
    "--corpus-root",
    "--input-root",
    "corpus_root",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Corpus root directory containing lesson data folders (paths in registry are relative to this).",
)
@click.option(
    "--lesson-registry",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Stage 6.1 lesson_registry.json used as authoritative ingestion manifest.",
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
    corpus_root: Path,
    lesson_registry: Path,
    output_root: Path,
    strict: bool,
) -> None:
    """Freeze schema v1 and build corpus-level exports."""
    click.echo(f"Corpus root      : {corpus_root}")
    click.echo(f"Lesson registry  : {lesson_registry}")
    click.echo(f"Output root      : {output_root}")
    click.echo(f"Strict mode      : {strict}")
    click.echo()

    try:
        summary = build_corpus(
            corpus_root,
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
    click.echo(f"  Ingest registry  : {summary.get('ingestion_registry_path', '')}")


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
