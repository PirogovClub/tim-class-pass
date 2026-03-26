"""CLI for Stage 5.6 reviewed corpus export (`python -m pipeline.adjudication.export_cli`)."""

from __future__ import annotations

import json
from pathlib import Path

import click

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import QualityTier
from pipeline.adjudication.export_service import run_export
from pipeline.adjudication.export_validation import validate_export_dir
from pipeline.adjudication.repository import AdjudicationRepository


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Reviewed corpus export (Gold/Silver JSONL, manifest, eval subsets, validation)."""


@main.command("export")
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Path to adjudication SQLite database.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Directory to write JSONL + export_manifest.json.",
)
@click.option(
    "--tiers",
    type=click.Choice(["gold", "silver", "both"], case_sensitive=False),
    default="both",
    show_default=True,
    help="Which tier bundles to emit.",
)
@click.option(
    "--eval-subsets/--no-eval-subsets",
    default=True,
    show_default=True,
    help="Emit eval_*.jsonl derived from gold rows (gold tier only).",
)
@click.option(
    "--no-corpus-filter",
    is_flag=True,
    default=False,
    help="Export all materialized rows (do not restrict to a corpus index file).",
)
@click.option(
    "--corpus-json",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Optional JSON with rule_card_ids, evidence_link_ids, concept_link_ids, related_rule_relation_ids lists.",
)
def export_cmd(
    db_path: Path,
    output_dir: Path,
    tiers: str,
    eval_subsets: bool,
    no_corpus_filter: bool,
    corpus_json: Path | None,
) -> None:
    """Run read-only export into output-dir."""
    if not db_path.is_file():
        raise click.ClickException(f"Database not found: {db_path}")
    initialize_adjudication_storage(db_path)
    repo = AdjudicationRepository(db_path)

    tier_set: set[QualityTier]
    if tiers == "gold":
        tier_set = {QualityTier.GOLD}
    elif tiers == "silver":
        tier_set = {QualityTier.SILVER}
    else:
        tier_set = {QualityTier.GOLD, QualityTier.SILVER}

    corpus_index = None
    if not no_corpus_filter:
        if corpus_json is None:
            raise click.ClickException(
                "Either pass --corpus-json with inventory lists or use --no-corpus-filter."
            )
        raw = json.loads(corpus_json.read_text(encoding="utf-8"))
        from pipeline.adjudication.corpus_inventory import CorpusTargetIndex

        corpus_index = CorpusTargetIndex(
            rule_card_ids=frozenset(raw.get("rule_card_ids") or []),
            evidence_link_ids=frozenset(raw.get("evidence_link_ids") or []),
            concept_link_ids=frozenset(raw.get("concept_link_ids") or []),
            related_rule_relation_ids=frozenset(raw.get("related_rule_relation_ids") or []),
        )

    run_export(
        repo,
        output_dir,
        tiers=tier_set,
        corpus_index=corpus_index,
        explorer=None,
        write_eval_subsets=eval_subsets and QualityTier.GOLD in tier_set,
    )
    click.echo(f"Export written to {output_dir.resolve()}")


@main.command("validate")
@click.option(
    "--export-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    required=True,
    help="Directory containing export_manifest.json and JSONL files.",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Optional adjudication SQLite DB to verify rule/evidence rows and duplicate/family references.",
)
@click.option(
    "--strict-provenance",
    is_flag=True,
    default=False,
    help="Require non-empty lesson_id on exported rule_card rows (gold and silver).",
)
def validate_cmd(export_dir: Path, db_path: Path | None, strict_provenance: bool) -> None:
    """Validate an existing export directory (tiers, counts, uniqueness, cross-file refs, optional DB)."""
    res = validate_export_dir(export_dir, db_path=db_path, strict_provenance=strict_provenance)
    for w in res.warnings:
        click.echo(f"WARNING: {w}", err=True)
    if res.errors:
        for e in res.errors:
            click.echo(f"ERROR: {e}", err=True)
        raise click.ClickException("Validation failed.")
    click.echo("Validation OK.")


if __name__ == "__main__":
    main()
