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


def main():
    parser = argparse.ArgumentParser(description="Multimodal YouTube Video Transcript Enrichment Pipeline (Dense Mode)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="YouTube video URL to download and process")
    group.add_argument("--video_id", help="Process an existing video ID folder in data/")

    parser.add_argument(
        "--provider",
        default=os.getenv("LLM_PROVIDER", "antigravity"),
        choices=["openai", "gemini", "antigravity"],
        help="LLM provider (default: antigravity)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of frames per agent analysis batch (default: 10)"
    )
    parser.add_argument(
        "--recapture",
        action="store_true",
        help="Force re-extraction of frames even if frames_dense/ already exists"
    )

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Transcript Enrichment Pipeline — Dense Mode")
    logger.info(f"Provider: {args.provider} | Batch size: {args.batch_size}")
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
            dense_capturer.extract_dense_frames(video_id)
        else:
            import json
            with open(index_file) as f:
                n = len(json.load(f))
            logger.info(f"Step 1: Skipped — {n} frames already extracted. Use --recapture to redo.")

        # ── Step 2: Dense analysis (batched, agent-driven) ────────────────
        logger.info("Step 2: Dense frame analysis (batched)...")
        import dense_analyzer
        # Loop until all batches are done — each iteration may sys.exit(10)
        # so repeated runs of main.py progress through batches
        dense_analyzer.run_analysis(video_id, args.batch_size)

        # ── Step 3: Deduplication + polish (agent-driven) ─────────────────
        logger.info("Step 3: Deduplicating and producing final outputs...")
        import deduplicator
        deduplicator.run_deduplicator(video_id)

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
