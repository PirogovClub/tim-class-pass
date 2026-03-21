"""Click CLI for corpus build."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from pipeline.corpus.corpus_builder import build_corpus


@click.command("build")
@click.option(
    "--input-root",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Root directory containing lesson data folders.",
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
def main(input_root: Path, output_root: Path, strict: bool) -> None:
    """Freeze schema v1 and build corpus-level exports."""
    click.echo(f"Input root : {input_root}")
    click.echo(f"Output root: {output_root}")
    click.echo(f"Strict mode: {strict}")
    click.echo()

    try:
        summary = build_corpus(input_root, output_root, strict=strict)
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
    click.echo(f"  Output           : {summary['output_root']}")


if __name__ == "__main__":
    main()
