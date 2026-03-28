"""CLI: build lesson_registry.json and run corpus contract validation."""

from __future__ import annotations

import json
from pathlib import Path

import click

from pipeline.contracts.corpus_validator import validate_corpus, validate_registry_v1
from pipeline.contracts.lesson_registry import build_registry_v1, load_registry_v1, save_registry_v1
from pipeline.corpus.lesson_registry import discover_lessons


@click.group("lesson_contract", help="Lesson export contract v1 (Stage 6.1).")
def main() -> None:
    pass


@main.command("registry")
@click.argument(
    "input_root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write lesson_registry.json here (default: <input_root>/lesson_registry.json).",
)
@click.option("--no-validate", is_flag=True, help="Skip per-lesson contract validation.")
@click.option(
    "--lenient",
    is_flag=True,
    help="Lenient validation (warnings do not promote to errors).",
)
def registry_cmd(
    input_root: Path,
    output: Path | None,
    no_validate: bool,
    lenient: bool,
) -> None:
    doc = build_registry_v1(
        input_root,
        validate=not no_validate,
        strict_validation=not lenient,
    )
    out = output or (input_root / "lesson_registry.json")
    save_registry_v1(doc, out)
    click.echo(f"Wrote {out}")


@main.command("validate")
@click.argument(
    "input_root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--report",
    "-r",
    type=click.Path(path_type=Path),
    default=None,
    help="Write JSON report path (default: stdout).",
)
@click.option("--lenient", is_flag=True, help="Lenient mode (warnings only for some checks).")
@click.option(
    "--registry",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional lesson_registry.json to cross-check against disk.",
)
def validate_cmd(
    input_root: Path,
    report: Path | None,
    lenient: bool,
    registry: Path | None,
) -> None:
    lessons = discover_lessons(input_root)
    payload: dict = validate_corpus(lessons, strict=not lenient)
    if registry:
        reg_doc = load_registry_v1(registry)
        payload["registry_check"] = validate_registry_v1(reg_doc, input_root, strict=not lenient)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if report:
        report.write_text(text, encoding="utf-8")
        click.echo(f"Wrote {report}")
    else:
        click.echo(text)


if __name__ == "__main__":
    main()
