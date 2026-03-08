import argparse
import sys
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
AGENT_NEEDS_ANALYSIS = 10
AGENT_CHOICES = ["openai", "gemini", "ide"]


def main():
    parser = argparse.ArgumentParser(description="Multimodal YouTube Video Transcript Enrichment Pipeline (Dense Mode)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="YouTube video URL to download and process")
    group.add_argument("--video_id", help="Process an existing video ID folder in data/")

    parser.add_argument(
        "--agent-images",
        default=None,
        choices=AGENT_CHOICES,
        help="Agent for frame analysis (Step 2): ide (IDE as AI agent), openai, gemini. Overrides pipeline.yml and env.",
    )
    parser.add_argument(
        "--agent-dedup",
        default=None,
        choices=AGENT_CHOICES,
        help="Agent for deduplication (Step 3): ide, openai, gemini. Overrides pipeline.yml and env.",
    )
    parser.add_argument(
        "--agent",
        default=None,
        choices=AGENT_CHOICES,
        help="Set both agent-images and agent-dedup (used when step-specific flags not set).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Frames per agent batch (default from pipeline.yml or 10). Overrides config.",
    )
    parser.add_argument(
        "--recapture",
        action="store_true",
        help="Force re-extraction of frames even if frames_dense/ already exists"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Option B: Step 2 generates all batch task files + manifest, then exit 10; spawn subagents, then re-run with --merge-only",
    )
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Step 2 only: merge all dense_batch_response_*.json into dense_analysis.json, then run Step 3 (use after parallel subagents finished)",
    )

    args = parser.parse_args()

    # video_id not known yet if --url; we'll resolve config after Step 0
    video_id_before_download = args.video_id
    logger.info("=" * 50)

    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        video_id = args.video_id

        # ── Step 0: Download (optional) ───────────────────────────────────
        if args.url:
            import downloader
            logger.info("Step 0: Downloading video/transcripts...")
            video_id = downloader.extract_video_id(args.url)
            if not video_id:
                logger.error("Failed to extract video ID.")
                sys.exit(1)
            if not downloader.download_video_and_transcript(args.url, video_id):
                logger.error("Download failed.")
                sys.exit(1)

        logger.info(f"Video ID: {video_id}")

        # Resolve config: pipeline.yml (default + video) then CLI overrides
        import config as pipeline_config
        cfg = pipeline_config.get_config_for_video(video_id)
        agent_images = args.agent_images if args.agent_images is not None else (args.agent if args.agent is not None else cfg["agent_images"])
        agent_dedup = args.agent_dedup if args.agent_dedup is not None else (args.agent if args.agent is not None else cfg["agent_dedup"])
        batch_size = args.batch_size if args.batch_size is not None else cfg["batch_size"]
        video_file = cfg.get("video_file")
        vtt_file = cfg.get("vtt_file")

        if agent_images == "gemini" or agent_dedup == "gemini":
            import gemini_client
            gemini_client.require_gemini_key()

        logger.info("=" * 50)
        logger.info("Transcript Enrichment Pipeline — Dense Mode")
        logger.info(f"Agent (images): {agent_images} | Agent (dedup): {agent_dedup} | Batch size: {batch_size}")
        if video_file or vtt_file:
            logger.info(f"From pipeline.yml: video_file={video_file or 'auto'} | vtt_file={vtt_file or 'auto'}")
        logger.info("=" * 50)

        # ── Step 1: Dense frame capture (skip if already done, unless --recapture) ────
        import dense_capturer
        frames_dir = os.path.join(DATA_DIR, video_id, "frames_dense")
        index_file = os.path.join(DATA_DIR, video_id, "dense_index.json")
        already_captured = os.path.exists(index_file) and os.path.isdir(frames_dir)
        
        if args.recapture or not already_captured:
            if args.recapture:
                logger.info("Step 1: Re-extracting frames (--recapture flag set)...")
            else:
                logger.info("Step 1: Extracting 1 frame/second (first run)...")
            dense_capturer.extract_dense_frames(video_id, video_file_override=video_file)
        else:
            import json
            with open(index_file) as f:
                n = len(json.load(f))
            logger.info(f"Step 1: Skipped — {n} frames already extracted. Use --recapture to redo.")

        # ── Step 2: Dense analysis (batched, agent-driven) ────────────────
        logger.info("Step 2: Dense frame analysis (batched)...")
        import dense_analyzer
        parallel_batches = args.parallel or cfg.get("parallel_batches") is True
        dense_analyzer.run_analysis(
            video_id,
            batch_size,
            agent=agent_images,
            parallel_batches=parallel_batches,
            merge_only=args.merge_only,
        )

        # ── Step 3: Deduplication + polish (agent-driven) ─────────────────
        logger.info("Step 3: Deduplicating and producing final outputs...")
        import deduplicator
        deduplicator.run_deduplicator(video_id, agent=agent_dedup, vtt_file_override=vtt_file)

        logger.info("=" * 50)
        logger.info(f"Pipeline Complete! Check data/{video_id}/")
        logger.info(f"  • *_enriched.vtt  — Timed VTT with visual descriptions")
        logger.info(f"  • video_commentary.md — Full non-timed visual screenplay")
        logger.info("=" * 50)

    except SystemExit as e:
        if e.code == AGENT_NEEDS_ANALYSIS:
            logger.info("=" * 50)
            logger.info("Pipeline paused — agent analysis required.")
            logger.info("Read the batch prompt file, write the response, then re-run this command.")
            logger.info("=" * 50)
            sys.exit(AGENT_NEEDS_ANALYSIS)
        raise
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
