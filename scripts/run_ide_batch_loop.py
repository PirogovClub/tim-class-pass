"""
Loop: run pipeline -> if exit 10 and last_agent_task is a batch, write a no-change
response for that batch and re-run. Stops when the pipeline exits 0.

Usage (from project root):
  uv run python scripts/run_ide_batch_loop.py --video_id "Lesson 2. Levels part 1"

Use when the remaining frames are known to have no material change (e.g. same slide).
This helper only automates Step 2 batch responses; the current Step 3 runs automatically
and produces markdown outputs.
"""
import argparse
import json
import os
import re
import subprocess
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.chdir(_project_root)


def frame_path_to_key(path: str) -> str:
    """Extract 6-digit frame key from path like .../frame_000171.jpg"""
    m = re.search(r"frame_(\d{6})\.jpg", path.replace("\\", "/"))
    return m.group(1) if m else ""


def frame_key_to_timestamp(key: str) -> str:
    """Frame key (1-based index at 1fps) -> HH:MM:SS. Frame 1 = 00:00:01."""
    n = int(key)
    total_sec = max(0, n - 1)
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_no_change_batch_response(response_file: str, frame_paths: list) -> None:
    """Write a JSON object keyed by frame number with material_change false and timestamps."""
    out = {}
    for path in frame_paths:
        key = frame_path_to_key(path)
        if not key:
            continue
        ts = frame_key_to_timestamp(key)
        out[key] = {"frame_timestamp": ts, "material_change": False}
    with open(response_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Loop pipeline with no-change batch responses until the pipeline completes.")
    parser.add_argument("--video_id", required=True, help="Video ID in data/")
    args = parser.parse_args()
    video_id = args.video_id
    data_dir = os.path.join(_project_root, "data", video_id)
    batches_dir = os.path.join(data_dir, "batches")
    last_task_path = os.path.join(batches_dir, "last_agent_task.json")

    iteration = 0
    while True:
        iteration += 1
        print(f"\n--- Iteration {iteration}: running pipeline ---", flush=True)
        r = subprocess.run(
            [sys.executable, "main.py", "--video_id", video_id],
            cwd=_project_root,
        )
        if r.returncode == 0:
            print("Pipeline completed (exit 0).", flush=True)
            return 0
        if r.returncode != 10:
            print(f"Pipeline failed with exit code {r.returncode}.", flush=True)
            return r.returncode
        if not os.path.exists(last_task_path):
            print("Exit 10 but last_agent_task.json not found.", flush=True)
            return 1
        with open(last_task_path, "r", encoding="utf-8") as f:
            task = json.load(f)
        if task.get("type") != "batch" or "response_file" not in task or "frame_paths" not in task:
            print("Unexpected last_agent_task.json structure.", flush=True)
            return 1
        response_file = task["response_file"]
        if not os.path.isabs(response_file):
            response_file = os.path.join(_project_root, response_file)
        frame_paths = task["frame_paths"]
        print(f"Writing no-change response for {len(frame_paths)} frames -> {response_file}", flush=True)
        write_no_change_batch_response(response_file, frame_paths)


if __name__ == "__main__":
    sys.exit(main())
