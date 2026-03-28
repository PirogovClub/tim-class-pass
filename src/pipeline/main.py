import sys
import os
import logging
from pathlib import Path
import click
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
AGENT_NEEDS_ANALYSIS = 10
IMAGE_AGENT_CHOICES = ["openai", "gemini", "mlx", "setra", "ide"]


@click.command()
@click.option("--url", help="YouTube video URL to download and process")
@click.option("--video_id", help="Process an existing video ID folder in data/")
@click.option(
    "--agent-images",
    type=click.Choice(IMAGE_AGENT_CHOICES),
    default=None,
    help="Agent for frame analysis (Step 2): ide (IDE as AI agent), openai, gemini. Overrides pipeline.yml and env.",
)
@click.option(
    "--agent",
    type=click.Choice(IMAGE_AGENT_CHOICES),
    default=None,
    help="Alias for --agent-images when step-specific flag is not set.",
)
@click.option(
    "--batch-size",
    type=int,
    default=None,
    help="Frames per agent batch (default from pipeline.yml or 10). Overrides config.",
)
@click.option(
    "--workers",
    type=int,
    default=None,
    help="Max workers for frame extraction + structural compare (cap 8). Overrides config.",
)
@click.option(
    "--recapture",
    is_flag=True,
    help="Force re-extraction of frames even if frames_dense/ already exists",
)
@click.option(
    "--recompare",
    is_flag=True,
    help="Force re-run of structural compare even if structural_index.json exists",
)
@click.option(
    "--parallel",
    is_flag=True,
    help="Option B: Step 2 generates all batch task files + manifest, then exit 10; spawn subagents, then re-run with --merge-only",
)
@click.option(
    "--merge-only",
    is_flag=True,
    help="Step 2 only: merge all dense_batch_response_*.json into dense_analysis.json, then continue to markdown synthesis.",
)
@click.option(
    "--stop-after",
    type=int,
    default=None,
    help="Stop after this step (1, 2, or 3). Default: run all steps.",
)
@click.option(
    "--max-batches",
    type=int,
    default=None,
    help="Step 2: stop after this many batches (default: none = run all batches).",
)
def main(
    url,
    video_id,
    agent_images,
    agent,
    batch_size,
    workers,
    recapture,
    recompare,
    parallel,
    merge_only,
    stop_after,
    max_batches,
):
    """Multimodal YouTube Video Transcript Enrichment Pipeline (Dense Mode)."""
    if (url and video_id) or (not url and not video_id):
        raise click.UsageError("Exactly one of --url or --video_id is required.")

    logger.info("=" * 50)

    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        video_id_resolved = video_id

        # ── Step 0: Download (optional) ───────────────────────────────────
        if url:
            from pipeline import downloader
            logger.info("Step 0: Downloading video/transcripts...")
            video_id_resolved = downloader.extract_video_id(url)
            if not video_id_resolved:
                logger.error("Failed to extract video ID.")
                sys.exit(1)
            if not downloader.download_video_and_transcript(url, video_id_resolved):
                logger.error("Download failed.")
                sys.exit(1)

        logger.info(f"Video ID: {video_id_resolved}")

        # Resolve config from project folder (data/<video_id>/pipeline.yml) then CLI overrides
        from helpers import config as pipeline_config
        cfg = pipeline_config.get_config_for_video(video_id_resolved)

        # Log to project folder so all work for this run is in one place
        project_dir = os.path.join(DATA_DIR, video_id_resolved)
        os.makedirs(project_dir, exist_ok=True)
        log_path = os.path.join(project_dir, "pipeline.log")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(file_handler)
        agent_images_resolved = agent_images if agent_images is not None else (agent if agent is not None else (cfg.get("provider_images") or cfg["agent_images"]))
        batch_size_resolved = batch_size if batch_size is not None else cfg["batch_size"]
        video_file = cfg.get("video_file")
        vtt_file = cfg.get("vtt_file")
        capture_fps = float(cfg.get("capture_fps", 1.0))
        llm_queue_diff_threshold = float(cfg.get("llm_queue_diff_threshold", 0.14))
        step2_parallel_chunks = bool(cfg.get("step2_parallel_chunks", False))
        step2_reprocess_boundaries = bool(cfg.get("step2_reprocess_boundaries", True))
        step2_chunk_size = cfg.get("step2_chunk_size")
        step2_chunk_workers = cfg.get("step2_chunk_workers")
        cfg_workers = cfg.get("workers")
        if workers is not None:
            requested_workers = workers
        elif cfg_workers is not None:
            requested_workers = cfg_workers
        else:
            requested_workers = None
        default_workers = min(max((os.cpu_count() or 1) // 2, 1), 8)
        if requested_workers is None:
            max_workers = default_workers
        else:
            try:
                requested_workers = int(requested_workers)
            except (TypeError, ValueError):
                requested_workers = default_workers
            if requested_workers < 1:
                requested_workers = 1
            max_workers = min(requested_workers, 8)

        if agent_images_resolved == "gemini":
            from helpers.clients import gemini_client
            gemini_client.require_gemini_key()
        elif agent_images_resolved == "openai":
            from helpers.clients import openai_client
            openai_client.require_openai_key()
        elif agent_images_resolved == "setra":
            from helpers.clients import setra_client
            setra_client.require_setra_config()

        logger.info("=" * 50)
        logger.info("Transcript Enrichment Pipeline — Dense Mode")
        logger.info(f"Agent (images): {agent_images_resolved} | Batch size: {batch_size_resolved}")
        logger.info(f"Max workers: {max_workers}")
        logger.info(f"Capture FPS: {capture_fps} | LLM queue diff threshold: {llm_queue_diff_threshold}")
        logger.info(
            "Step 2 chunking: "
            f"enabled={step2_parallel_chunks}, chunk_size={step2_chunk_size or batch_size_resolved}, "
            f"chunk_workers={step2_chunk_workers}, reprocess_boundaries={step2_reprocess_boundaries}"
        )
        if video_file or vtt_file:
            logger.info(f"From pipeline.yml: video_file={video_file or 'auto'} | vtt_file={vtt_file or 'auto'}")
        logger.info("=" * 50)

        # ── Step 1: Dense frame capture (skip if already done, unless --recapture) ────
        from pipeline import dense_capturer
        frames_dir = os.path.join(DATA_DIR, video_id_resolved, "frames_dense")
        index_file = os.path.join(DATA_DIR, video_id_resolved, "dense_index.json")
        already_captured = os.path.exists(index_file) and os.path.isdir(frames_dir)

        if recapture or not already_captured:
            if recapture:
                logger.info("Step 1: Re-extracting frames (--recapture flag set)...")
            else:
                logger.info("Step 1: Extracting 1 frame/second (first run)...")
            dense_capturer.extract_dense_frames(
                video_id_resolved,
                video_file_override=video_file,
                max_workers=max_workers,
                capture_fps=capture_fps,
            )
        else:
            import json
            with open(index_file) as f:
                n = len(json.load(f))
            logger.info(f"Step 1: Skipped — {n} frames already extracted. Use --recapture to redo.")

        # ── Step 1.5: Structural compare (SSIM pre-filter) ───────────────
        from pipeline import structural_compare
        logger.info("Step 1.5: Structural compare (SSIM pre-filter)...")
        structural_compare.run_structural_compare(
            video_id_resolved,
            force=bool(recompare or recapture),
            max_workers=max_workers,
            progress_callback=lambda message: logger.info(message),
        )

        # ── Step 1.6: LLM queue selection (diff threshold) ────────────────
        from pipeline import select_llm_frames
        logger.info(f"Step 1.6: Building LLM queue (diff > {llm_queue_diff_threshold:.4f} + previous)...")
        select_llm_frames.build_llm_queue(video_id_resolved, threshold=llm_queue_diff_threshold)

        # ── Step 1.7: Build LLM prompt files ──────────────────────────────
        from pipeline import build_llm_prompts
        logger.info("Step 1.7: Building LLM prompts...")
        build_llm_prompts.build_llm_prompts(video_id_resolved)

        if stop_after == 1:
            logger.info("=" * 50)
            logger.info("Stopped after Step 1 (--stop-after 1).")
            logger.info("=" * 50)
            return

        # ── Step 2: Dense analysis (batched, agent-driven) ────────────────
        logger.info("Step 2: Dense frame analysis (batched)...")
        from pipeline import dense_analyzer
        parallel_batches = parallel or cfg.get("parallel_batches") is True
        dense_analyzer.run_analysis(
            video_id_resolved,
            batch_size_resolved,
            agent=agent_images_resolved,
            parallel_batches=parallel_batches,
            merge_only=merge_only,
            max_batches=max_batches,
            step2_parallel_chunks=step2_parallel_chunks,
            step2_reprocess_boundaries=step2_reprocess_boundaries,
            step2_chunk_size=step2_chunk_size,
            step2_chunk_workers=step2_chunk_workers,
        )

        if stop_after == 2:
            logger.info("=" * 50)
            logger.info("Stopped after Step 2 (--stop-after 2).")
            logger.info("=" * 50)
            return

        # ── Step 3: Component 2 + markdown synthesis ───────────────────────
        logger.info("Step 3: Running Component 2 + markdown synthesis...")
        from pipeline.component2.main import run_component2_pipeline

        video_dir = Path(DATA_DIR) / video_id_resolved
        dense_analysis_path = video_dir / "dense_analysis.json"
        if not dense_analysis_path.is_file():
            raise FileNotFoundError(f"Missing dense analysis file: {dense_analysis_path}")

        if vtt_file:
            vtt_paths = [video_dir / vtt_file]
        else:
            vtt_paths = sorted(video_dir.glob("*.vtt"))
        vtt_paths = [path for path in vtt_paths if path.is_file()]
        if not vtt_paths:
            raise FileNotFoundError(f"No VTT files found under {video_dir}")

        model_component2 = cfg.get("model_component2")
        model_component2_reducer = cfg.get("model_component2_reducer")
        provider_component2 = cfg.get("provider_component2")
        provider_component2_reducer = cfg.get("provider_component2_reducer")
        for required_provider in {provider_component2, provider_component2_reducer}:
            if required_provider == "gemini":
                from helpers.clients import gemini_client

                gemini_client.require_gemini_key()
            elif required_provider == "openai":
                from helpers.clients import openai_client

                openai_client.require_openai_key()
            elif required_provider == "setra":
                from helpers.clients import setra_client

                setra_client.require_setra_config()
        for current_vtt_path in vtt_paths:
            outputs = run_component2_pipeline(
                vtt_path=current_vtt_path,
                visuals_json_path=dense_analysis_path,
                output_root=video_dir,
                video_id=video_id_resolved,
                model=model_component2,
                provider=provider_component2,
                reducer_model=model_component2_reducer,
                reducer_provider=provider_component2_reducer,
                progress_callback=lambda message: logger.info(message),
            )
            logger.info(f"Generated markdown outputs for {current_vtt_path.name}")
            logger.info(f"  • filtered_visual_events.json: {outputs['filtered_events_path']}")
            logger.info(f"  • intermediate markdown: {outputs['intermediate_markdown_path']}")
            logger.info(f"  • rag-ready markdown: {outputs['rag_ready_markdown_path']}")

        logger.info("=" * 50)
        logger.info(f"Pipeline Complete! Check data/{video_id_resolved}/")
        logger.info(f"  • filtered_visual_events.json — Instructional visual events only")
        logger.info(f"  • output_intermediate/*.md — Pass 1 literal-scribe markdown")
        logger.info(f"  • output_rag_ready/*.md — Final RAG-ready lesson markdown")
        logger.info("=" * 50)

    except SystemExit as e:
        if e.code == AGENT_NEEDS_ANALYSIS:
            logger.info("=" * 50)
            logger.info("Pipeline paused — frame analysis batch input required.")
            logger.info("Read the batch prompt file, write the response, then re-run this command.")
            logger.info("=" * 50)
            sys.exit(AGENT_NEEDS_ANALYSIS)
        raise
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
