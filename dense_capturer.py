import os
import sys
import json
import shutil
import argparse
import subprocess

def extract_dense_frames(video_id: str, video_file_override: str | None = None):
    """
    Extract 1 fps frames. video_file_override: optional filename (e.g. from pipeline.yml)
    relative to data/<video_id>/. If None, use first .mp4 in folder.
    """
    video_dir = os.path.join("data", video_id)
    frames_dir = os.path.join(video_dir, "frames_dense")
    index_file = os.path.join(video_dir, "dense_index.json")

    # Always start clean
    if os.path.exists(frames_dir):
        print(f"Cleaning {frames_dir}...")
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir)

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

    # Use ffmpeg to extract 1 fps
    output_pattern = os.path.join(frames_dir, "frame_%06d.jpg")
    cmd = [
        "ffmpeg", "-i", video_file,
        "-vf", "fps=1,scale=1280:-1",
        "-qscale:v", "2",
        "-y",
        output_pattern
    ]
    
    # Run with stderr not captured so FFmpeg progress (frame= ... fps= ...) is visible
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=None, text=True)
    if result.returncode != 0:
        # Re-run with capture to get error message
        result_err = subprocess.run(cmd, capture_output=True, text=True)
        print(f"FFmpeg error:\n{result_err.stderr or result_err.stdout or 'unknown'}")
        cmd_uv = ["uv", "run", "ffmpeg"] + cmd[1:]
        result2 = subprocess.run(cmd_uv, stdout=subprocess.DEVNULL, stderr=None, text=True)
        if result2.returncode != 0:
            result2_err = subprocess.run(cmd_uv, capture_output=True, text=True)
            print(f"FFmpeg (uv) error:\n{result2_err.stderr or result2_err.stdout or 'unknown'}")
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
    args = parser.parse_args()
    
    n = extract_dense_frames(args.video_id)
    print(f"Done: {n} frames extracted.")
