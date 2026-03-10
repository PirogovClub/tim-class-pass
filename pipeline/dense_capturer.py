import os
import sys
import json
import shutil
import argparse
import subprocess
import math
from concurrent.futures import ThreadPoolExecutor, as_completed


SEGMENT_SECONDS_TARGET = 60


def _run_ffmpeg_cmd(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=None, text=True)
    if result.returncode == 0:
        return True
    result_err = subprocess.run(cmd, capture_output=True, text=True)
    print(f"FFmpeg error:\n{result_err.stderr or result_err.stdout or 'unknown'}")
    cmd_uv = ["uv", "run", "ffmpeg"] + cmd[1:]
    result2 = subprocess.run(cmd_uv, stdout=subprocess.DEVNULL, stderr=None, text=True)
    if result2.returncode == 0:
        return True
    result2_err = subprocess.run(cmd_uv, capture_output=True, text=True)
    print(f"FFmpeg (uv) error:\n{result2_err.stderr or result2_err.stdout or 'unknown'}")
    return False


def _probe_duration_seconds(video_file: str) -> float | None:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_file,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _extract_segment(
    video_file: str,
    start_seconds: float,
    duration_seconds: float,
    output_dir: str,
    label: str,
) -> bool:
    os.makedirs(output_dir, exist_ok=True)
    output_pattern = os.path.join(output_dir, "frame_%06d.jpg")
    cmd = [
        "ffmpeg",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        video_file,
        "-t",
        f"{duration_seconds:.3f}",
        "-vf",
        "fps=1,scale=1280:-1",
        "-qscale:v",
        "2",
        "-y",
        output_pattern,
    ]
    ok = _run_ffmpeg_cmd(cmd)
    if not ok:
        print(f"FFmpeg failed for segment {label}")
    return ok

def extract_dense_frames(
    video_id: str,
    video_file_override: str | None = None,
    max_workers: int | None = None,
):
    """
    Extract 1 fps frames. video_file_override: optional filename (e.g. from pipeline.yml)
    relative to data/<video_id>/. If None, use first .mp4 in folder.
    """
    video_dir = os.path.join("data", video_id)
    frames_dir = os.path.join(video_dir, "frames_dense")
    index_file = os.path.join(video_dir, "dense_index.json")
    max_workers = int(max_workers) if max_workers is not None else 1
    if max_workers < 1:
        max_workers = 1
    if max_workers > 8:
        max_workers = 8

    # Always start clean
    if os.path.exists(frames_dir):
        print(f"Cleaning {frames_dir}...")
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir)
    for name in os.listdir(video_dir):
        if name.startswith("frames_dense_seg_"):
            seg_path = os.path.join(video_dir, name)
            if os.path.isdir(seg_path):
                shutil.rmtree(seg_path)

    if os.path.exists(index_file):
        os.remove(index_file)

    # Resolve video file: pipeline.yml override or first .mp4
    video_file = None
    if video_file_override:
        candidate = os.path.join(video_dir, video_file_override)
        if os.path.isfile(candidate):
            video_file = candidate
        else:
            print(f"Error: video_file from config not found: {candidate}")
            sys.exit(1)
    if not video_file:
        for f in os.listdir(video_dir):
            if f.endswith(".mp4") and not f.startswith("."):
                video_file = os.path.join(video_dir, f)
                break

    if not video_file:
        print(f"Error: No .mp4 found in {video_dir}")
        sys.exit(1)

    # Safe for Windows console (cp1252)
    try:
        print(f"Extracting 1 frame/second from {video_file}...")
    except UnicodeEncodeError:
        print(f"Extracting 1 frame/second from {video_id}...")

    duration = _probe_duration_seconds(video_file)
    should_segment = duration is not None and duration > SEGMENT_SECONDS_TARGET and max_workers > 1

    if should_segment:
        total_seconds = float(duration)
        segment_count = min(max_workers, int(math.ceil(total_seconds / SEGMENT_SECONDS_TARGET)))
        segment_seconds = float(math.ceil(total_seconds / segment_count))
        segments: list[tuple[float, float, str]] = []
        for i in range(segment_count):
            start = segment_seconds * i
            remaining = total_seconds - start
            if remaining <= 0:
                break
            seg_duration = min(segment_seconds, remaining)
            label = f"{i + 1}/{segment_count}"
            segments.append((start, seg_duration, label))

        print(f"Extracting 1fps in {len(segments)} segments with {max_workers} workers...")
        futures = []
        with ThreadPoolExecutor(max_workers=min(max_workers, len(segments))) as executor:
            for i, (start, seg_duration, label) in enumerate(segments):
                seg_dir = os.path.join(video_dir, f"frames_dense_seg_{i:03d}")
                futures.append(
                    executor.submit(
                        _extract_segment,
                        video_file,
                        start,
                        seg_duration,
                        seg_dir,
                        label,
                    )
                )
            failed = False
            for future in as_completed(futures):
                if not future.result():
                    failed = True
        if failed:
            sys.exit(1)

        # Merge segments into frames_dense/ with global numbering.
        global_index = 1
        segment_dirs = sorted(
            d for d in os.listdir(video_dir) if d.startswith("frames_dense_seg_")
        )
        for seg_dir in segment_dirs:
            seg_path = os.path.join(video_dir, seg_dir)
            frame_files = sorted(
                f for f in os.listdir(seg_path) if f.endswith(".jpg")
            )
            for frame_file in frame_files:
                src = os.path.join(seg_path, frame_file)
                dst_name = f"frame_{global_index:06d}.jpg"
                dst = os.path.join(frames_dir, dst_name)
                os.replace(src, dst)
                global_index += 1
            shutil.rmtree(seg_path)
    else:
        # Use ffmpeg to extract 1 fps
        output_pattern = os.path.join(frames_dir, "frame_%06d.jpg")
        cmd = [
            "ffmpeg", "-i", video_file,
            "-vf", "fps=1,scale=1280:-1",
            "-qscale:v", "2",
            "-y",
            output_pattern
        ]
        ok = _run_ffmpeg_cmd(cmd)
        if not ok:
            sys.exit(1)

    # Build the index
    frames = sorted(f for f in os.listdir(frames_dir) if f.endswith(".jpg"))
    index = {}
    for frame_file in frames:
        # frame_000001.jpg -> key "000001"
        key = frame_file.replace("frame_", "").replace(".jpg", "")
        index[key] = os.path.join("frames_dense", frame_file)

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"Extracted {len(index)} frames. Index saved to {index_file}")
    return len(index)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract 1fps frames from a video")
    parser.add_argument("video_id", help="Video ID in data/")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Max workers for segment extraction (cap 8 recommended).",
    )
    args = parser.parse_args()
    
    n = extract_dense_frames(args.video_id, max_workers=args.workers)
    print(f"Done: {n} frames extracted.")
