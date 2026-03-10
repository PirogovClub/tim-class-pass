#!/usr/bin/env python3
"""
Count total duration of all videos in a folder (including subfolders).
Requires ffprobe (from ffmpeg) to be installed and on PATH.
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Common video extensions
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".m2ts", ".ogv",
}

DEFAULT_ROOT = Path(r"H:\trading-education")


def get_duration_seconds(path: Path) -> float | None:
    """Get video duration in seconds using ffprobe. Returns None on error."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count total duration of videos in a folder (recursive)."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Root folder to scan (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only print total (no per-file or summary counts)",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    videos = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    ]

    if not videos:
        print(f"No video files found under {root}")
        return

    total_seconds = 0.0
    failed = 0

    def safe_display(s: str) -> str:
        """Make string safe for console (avoids UnicodeEncodeError on Windows)."""
        enc = sys.stdout.encoding or "utf-8"
        return s.encode(enc, errors="replace").decode(enc)

    for path in sorted(videos):
        duration = get_duration_seconds(path)
        if duration is None:
            failed += 1
            if not args.quiet:
                print(f"  (skip) {safe_display(str(path.relative_to(root)))}", file=sys.stderr)
            continue
        total_seconds += duration
        if not args.quiet:
            m, s = divmod(int(duration), 60)
            h, m = divmod(m, 60)
            print(f"  {h}:{m:02d}:{s:02d}  {safe_display(str(path.relative_to(root)))}")

    if not args.quiet:
        print()
        print(f"Videos: {len(videos) - failed} ok, {failed} skipped")

    total_minutes = int(total_seconds // 60)
    total_hours = total_minutes // 60
    remaining_minutes = total_minutes % 60

    print(f"Total: {total_hours} hours, {remaining_minutes} minutes")
    print(f"       ({total_seconds / 3600:.2f} hours)")


if __name__ == "__main__":
    main()
