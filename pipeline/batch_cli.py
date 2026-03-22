from __future__ import annotations

import json
import time
from pathlib import Path

import click

from helpers import config as pipeline_config
from pipeline.component2.exporters import load_evidence_index, load_rule_cards
from pipeline.component2.knowledge_builder import adapt_chunks, load_chunks_json
from pipeline.component2.llm_processor import (
    emit_batch_spool_for_knowledge_extract,
    emit_batch_spool_for_markdown_render,
    materialize_batch_results_for_knowledge_extract,
    materialize_batch_results_for_markdown_render,
)
from pipeline.component2.parser import parse_and_sync, write_lesson_chunks
from pipeline.contracts import PipelinePaths
from pipeline.dense_analyzer import (
    emit_batch_spool_for_analysis,
    materialize_batch_results_for_analysis,
)
from pipeline.invalidation_filter import (
    build_debug_report,
    filter_visual_events,
    load_dense_analysis,
    write_debug_report,
    write_filtered_events,
)
from pipeline.orchestrator import STAGE_KNOWLEDGE_EXTRACT, STAGE_MARKDOWN_RENDER, STAGE_VISION, StateStore
from pipeline.orchestrator.batch_assembler import assemble_batch_files
from pipeline.orchestrator.discovery import discover_lessons, discover_videos, plan_stages
from pipeline.orchestrator.run_manager import (
    download_completed_batches,
    poll_active_batches,
    retry_failed_requests,
    submit_ready_batches,
)
from pipeline.orchestrator.status_service import format_status_tables

STAGE_CHOICES = [STAGE_VISION, STAGE_KNOWLEDGE_EXTRACT, STAGE_MARKDOWN_RENDER]


def _store(db_path: str | Path) -> StateStore:
    return StateStore(db_path)


def _discover_all(data_root: str | Path, store: StateStore) -> tuple[int, int]:
    videos = discover_videos(data_root, store)
    lesson_count = 0
    for video in videos:
        lesson_count += len(discover_lessons(video["video_id"], video["video_root"], store))
    return (len(videos), lesson_count)


def _lesson_context(lesson: dict) -> dict:
    return {
        "lesson_id": lesson["lesson_id"],
        "lesson_name": lesson["lesson_name"],
        "video_id": lesson["video_id"],
    }


def _load_queue_manifest(video_root: Path) -> tuple[list[str], Path]:
    manifest_path = video_root / "llm_queue" / "manifest.json"
    if not manifest_path.exists():
        raise click.ClickException(
            f"Missing {manifest_path}. Build the queue first with the existing Step 1.6 flow."
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("items") or {}
    return (sorted(items.keys()), video_root / "llm_queue")


def _ensure_filtered_visuals(video_root: Path, paths: PipelinePaths) -> None:
    if paths.filtered_visuals_path.exists():
        return
    dense_analysis_path = video_root / "dense_analysis.json"
    if not dense_analysis_path.exists():
        raise click.ClickException(
            f"Missing {dense_analysis_path}. Vision batch output must exist before chunk planning."
        )
    raw_analysis = load_dense_analysis(dense_analysis_path)
    events = filter_visual_events(raw_analysis)
    report = build_debug_report(raw_analysis, events)
    write_filtered_events(paths.filtered_visuals_path, events)
    write_debug_report(paths.filtered_visuals_debug_path, report)


def _ensure_lesson_chunks(lesson: dict, paths: PipelinePaths, cfg: dict) -> list[dict]:
    lesson_name = lesson["lesson_name"]
    chunks_path = paths.lesson_chunks_path(lesson_name)
    if not chunks_path.exists():
        _ensure_filtered_visuals(Path(lesson["lesson_root"]), paths)
        chunks = parse_and_sync(
            vtt_path=Path(lesson["vtt_path"]),
            filtered_events_path=paths.filtered_visuals_path,
            target_duration_seconds=float(cfg.get("target_duration_seconds", 120.0)),
        )
        write_lesson_chunks(chunks_path, chunks)
    return load_chunks_json(chunks_path)


def run_discover(*, data_root: str | Path, db_path: str | Path) -> tuple[int, int]:
    store = _store(db_path)
    return _discover_all(data_root, store)


def run_plan(*, db_path: str | Path, force: bool = False) -> dict[str, int]:
    store = _store(db_path)
    return plan_stages(store, force=force)


def run_spool(
    *,
    stage: str,
    db_path: str | Path,
    limit_videos: int | None = None,
) -> int:
    store = _store(db_path)
    lessons = store.list_lessons()
    if limit_videos is not None:
        allowed_video_ids = sorted({lesson["video_id"] for lesson in lessons})[: max(0, limit_videos)]
        lessons = [lesson for lesson in lessons if lesson["video_id"] in allowed_video_ids]
    pending_runs = store.list_stage_runs(stage_name=stage, status="PENDING", execution_mode="gemini_batch")
    pending_lesson_ids = {row["lesson_id"] for row in pending_runs}
    if pending_lesson_ids:
        lessons = [lesson for lesson in lessons if lesson["lesson_id"] in pending_lesson_ids]

    spooled = 0
    for lesson in lessons:
        video_root = Path(lesson["lesson_root"])
        cfg = pipeline_config.get_config_for_video(lesson["video_id"])
        paths = PipelinePaths(video_root=video_root)
        if stage == STAGE_VISION:
            queue_keys, frames_dir = _load_queue_manifest(video_root)
            emit_batch_spool_for_analysis(
                video_root=video_root,
                lesson_context=_lesson_context(lesson),
                queue_keys=queue_keys,
                frames_dir=frames_dir,
                config=cfg,
                state_store=store,
            )
            spooled += 1
        elif stage == STAGE_KNOWLEDGE_EXTRACT:
            raw_chunks = _ensure_lesson_chunks(lesson, paths, cfg)
            adapted = adapt_chunks(raw_chunks, lesson_id=lesson["lesson_name"], lesson_title=None)
            emit_batch_spool_for_knowledge_extract(
                chunks=adapted,
                lesson_id=lesson["lesson_id"],
                video_id=lesson["video_id"],
                paths=paths,
                state_store=store,
            )
            spooled += 1
        elif stage == STAGE_MARKDOWN_RENDER:
            rule_cards_path = paths.rule_cards_path(lesson["lesson_name"])
            evidence_index_path = paths.evidence_index_path(lesson["lesson_name"])
            if not rule_cards_path.exists() or not evidence_index_path.exists():
                continue
            rule_cards = load_rule_cards(rule_cards_path)
            evidence_index = load_evidence_index(evidence_index_path)
            emit_batch_spool_for_markdown_render(
                lesson_id=lesson["lesson_id"],
                rule_cards=rule_cards.rules,
                evidence_refs=evidence_index.evidence_refs,
                paths=paths,
                state_store=store,
                render_mode="review",
                video_id=lesson["video_id"],
            )
            spooled += 1
    return spooled


def run_assemble(*, stage: str, db_path: str | Path) -> list[Path]:
    store = _store(db_path)
    return assemble_batch_files(store, stage_name=stage)


def run_submit(*, stage: str | None, db_path: str | Path, max_batches: int) -> list[str]:
    store = _store(db_path)
    return submit_ready_batches(store, stage_name=stage, max_batches=max_batches)


def run_poll(*, db_path: str | Path) -> dict[str, str]:
    store = _store(db_path)
    return poll_active_batches(store)


def run_download(*, db_path: str | Path) -> list[Path]:
    store = _store(db_path)
    return download_completed_batches(store)


def run_materialize(*, stage: str, db_path: str | Path) -> int:
    store = _store(db_path)
    lessons_by_id = {lesson["lesson_id"]: lesson for lesson in store.list_lessons()}
    jobs = [
        job for job in store.list_batch_jobs(stage_name=stage)
        if Path(job["local_request_file"]).with_name(f"{job['batch_job_name']}.results.jsonl").exists()
    ]
    materialized = 0
    for job in jobs:
        result_path = Path(job["local_request_file"]).with_name(f"{job['batch_job_name']}.results.jsonl")
        request_rows = store.list_batch_requests(batch_job_name=job["batch_job_name"])
        lesson_ids = sorted({row["lesson_id"] for row in request_rows})
        for lesson_id in lesson_ids:
            lesson = lessons_by_id.get(lesson_id)
            if lesson is None:
                continue
            video_root = Path(lesson["lesson_root"])
            paths = PipelinePaths(video_root=video_root)
            if stage == STAGE_VISION:
                materialize_batch_results_for_analysis(
                    result_path,
                    video_root=video_root,
                    lesson_context=_lesson_context(lesson),
                    frames_dir=video_root / "frames_dense",
                    state_store=store,
                )
            elif stage == STAGE_KNOWLEDGE_EXTRACT:
                raw_chunks = load_chunks_json(paths.lesson_chunks_path(lesson["lesson_name"]))
                adapted = adapt_chunks(raw_chunks, lesson_id=lesson["lesson_name"], lesson_title=None)
                materialize_batch_results_for_knowledge_extract(
                    result_path,
                    adapted,
                    lesson["lesson_id"],
                    paths,
                    store,
                )
            elif stage == STAGE_MARKDOWN_RENDER:
                materialize_batch_results_for_markdown_render(
                    result_path,
                    lesson["lesson_id"],
                    paths,
                    store,
                )
            materialized += 1
    return materialized


def run_resume(*, data_root: str | Path, db_path: str | Path) -> dict[str, int]:
    run_discover(data_root=data_root, db_path=db_path)
    run_plan(db_path=db_path, force=False)
    summary = {"spooled": 0, "assembled": 0, "submitted": 0, "downloaded": 0, "materialized": 0}
    for stage in STAGE_CHOICES:
        summary["spooled"] += run_spool(stage=stage, db_path=db_path)
        summary["assembled"] += len(run_assemble(stage=stage, db_path=db_path))
        summary["submitted"] += len(run_submit(stage=stage, db_path=db_path, max_batches=3))
    run_poll(db_path=db_path)
    summary["downloaded"] = len(run_download(db_path=db_path))
    for stage in STAGE_CHOICES:
        summary["materialized"] += run_materialize(stage=stage, db_path=db_path)
    return summary


@click.group(help="Manage Gemini Batch orchestration for existing lessons.")
@click.option(
    "--db-path",
    default="var/pipeline_state.db",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="SQLite state store path.",
)
@click.pass_context
def main(ctx: click.Context, db_path: Path) -> None:
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path


@main.command()
@click.option("--data-root", default="data", show_default=True, type=click.Path(file_okay=False, path_type=Path))
@click.pass_context
def discover(ctx: click.Context, data_root: Path) -> None:
    video_count, lesson_count = run_discover(data_root=data_root, db_path=ctx.obj["db_path"])
    click.echo(f"Discovered videos={video_count} lessons={lesson_count}")


@main.command()
@click.option("--force", is_flag=True, help="Create new stage runs even if outputs already exist.")
@click.pass_context
def plan(ctx: click.Context, force: bool) -> None:
    planned = run_plan(db_path=ctx.obj["db_path"], force=force)
    click.echo(json.dumps(planned, indent=2))


@main.command()
@click.option("--stage", required=True, type=click.Choice(STAGE_CHOICES))
@click.option("--limit-videos", type=int, default=None, help="Limit processing to the first N discovered videos.")
@click.pass_context
def spool(ctx: click.Context, stage: str, limit_videos: int | None) -> None:
    count = run_spool(stage=stage, db_path=ctx.obj["db_path"], limit_videos=limit_videos)
    click.echo(f"Spooled {count} lesson fragment(s) for stage={stage}")


@main.command()
@click.option("--stage", required=True, type=click.Choice(STAGE_CHOICES))
@click.pass_context
def assemble(ctx: click.Context, stage: str) -> None:
    paths = run_assemble(stage=stage, db_path=ctx.obj["db_path"])
    click.echo(f"Assembled {len(paths)} batch file(s) for stage={stage}")


@main.command()
@click.option("--stage", type=click.Choice(STAGE_CHOICES), default=None, help="Limit submission to one stage.")
@click.option("--max-batches", type=int, default=3, show_default=True)
@click.pass_context
def submit(ctx: click.Context, stage: str | None, max_batches: int) -> None:
    batch_names = run_submit(stage=stage, db_path=ctx.obj["db_path"], max_batches=max_batches)
    click.echo(f"Submitted {len(batch_names)} batch job(s)")


@main.command()
@click.pass_context
def poll(ctx: click.Context) -> None:
    statuses = run_poll(db_path=ctx.obj["db_path"])
    click.echo(json.dumps(statuses, indent=2))


@main.command()
@click.pass_context
def download(ctx: click.Context) -> None:
    paths = run_download(db_path=ctx.obj["db_path"])
    click.echo(f"Downloaded {len(paths)} result file(s)")


@main.command()
@click.option("--stage", required=True, type=click.Choice(STAGE_CHOICES))
@click.pass_context
def materialize(ctx: click.Context, stage: str) -> None:
    count = run_materialize(stage=stage, db_path=ctx.obj["db_path"])
    click.echo(f"Materialized {count} lesson output(s) for stage={stage}")


@main.command()
@click.option("--data-root", default="data", show_default=True, type=click.Path(file_okay=False, path_type=Path))
@click.pass_context
def resume(ctx: click.Context, data_root: Path) -> None:
    summary = run_resume(data_root=data_root, db_path=ctx.obj["db_path"])
    click.echo(json.dumps(summary, indent=2))


@main.command()
@click.option("--watch", type=int, default=None, help="Refresh every N seconds until interrupted.")
@click.pass_context
def status(ctx: click.Context, watch: int | None) -> None:
    store = _store(ctx.obj["db_path"])
    while True:
        click.echo(format_status_tables(store))
        if watch is None:
            return
        time.sleep(max(1, watch))
        click.echo("")


@main.command("retry-failed")
@click.option("--stage", required=True, type=click.Choice(STAGE_CHOICES))
@click.pass_context
def retry_failed_command(ctx: click.Context, stage: str) -> None:
    recreated = retry_failed_requests(_store(ctx.obj["db_path"]), stage)
    click.echo(f"Recreated {recreated} retry request(s) for stage={stage}")


if __name__ == "__main__":
    main()
