import os
import sys
import json
import argparse
from dotenv import load_dotenv

load_dotenv()

AGENT_NEEDS_ANALYSIS = 10

def get_batch_prompt(batch_entries: list[tuple[str, str]], video_dir: str, previous_description: str) -> str:
    """
    Returns instructions for the agent to analyze a batch of frames.
    batch_entries: list of (frame_key, frame_path)
    previous_description: the full description of the last analyzed frame
    """
    lines = [
        "You are analyzing video frames from a trading education video.",
        "For each frame listed below, you must:",
        "  1. View the image file using view_file tool",
        "  2. Write a FULL DESCRIPTION of the entire frame (what software is open, what is drawn/displayed, price levels visible, etc.)",
        "  3. Write a DELTA compared to the previous frame's description (what changed, was added, removed, or if it's a scene change).",
        "     - If nothing changed: write 'No change'",
        "     - If minor addition (e.g. new annotation): write 'Added: <what was added>'",
        "     - If completely different scene: write 'Scene change: <brief description of new scene>'",
        "",
        f"Previous frame description: {previous_description or 'None (this is the first frame)'}",
        "",
        "Frames to analyze:",
    ]
    for key, path in batch_entries:
        abs_path = os.path.abspath(path)
        lines.append(f"  Frame {key}: {abs_path}")
    lines += [
        "",
        "Save your response as a JSON object to the response file. Format:",
        '{',
        '  "000001": { "description": "...", "delta": "..." },',
        '  "000002": { "description": "...", "delta": "..." }',
        '}',
        "",
        "NOTE: Per-frame .txt files will be automatically written to frames_dense/ alongside each .jpg.",
    ]
    return "\n".join(lines)

def run_analysis(video_id: str, batch_size: int = 10):
    video_dir = os.path.join("data", video_id)
    index_file = os.path.join(video_dir, "dense_index.json")
    analysis_file = os.path.join(video_dir, "dense_analysis.json")

    if not os.path.exists(index_file):
        print(f"Error: {index_file} not found. Run dense_capturer.py first.")
        sys.exit(1)

    with open(index_file, "r", encoding="utf-8") as f:
        index = json.load(f)

    # Load existing analysis (partial progress)
    if os.path.exists(analysis_file):
        with open(analysis_file, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    else:
        analysis = {}

    all_keys = sorted(index.keys())
    remaining_keys = [k for k in all_keys if k not in analysis]

    if not remaining_keys:
        print("All frames already analyzed.")
        return

    print(f"Total frames: {len(all_keys)} | Already analyzed: {len(analysis)} | Remaining: {len(remaining_keys)}")

    # Get the last analyzed description for delta context
    if analysis:
        last_key = sorted(analysis.keys())[-1]
        previous_description = analysis[last_key].get("description", "")
    else:
        previous_description = ""

    # Process next batch
    batch_keys = remaining_keys[:batch_size]
    batch_entries = [(k, os.path.join(video_dir, index[k])) for k in batch_keys]

    batch_start = batch_keys[0]
    batch_end = batch_keys[-1]
    batch_label = f"{batch_start}-{batch_end}"

    prompt_file = os.path.join(video_dir, f"dense_batch_prompt_{batch_label}.txt")
    response_file = os.path.join(video_dir, f"dense_batch_response_{batch_label}.json")

    # Write the prompt
    prompt_text = get_batch_prompt(batch_entries, video_dir, previous_description)
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt_text)

    print(f"Batch {batch_label}: {len(batch_keys)} frames")

    if not os.path.exists(response_file):
        print(f"ANTIGRAVITY: Batch prompt written to: {prompt_file}")
        print(f"ANTIGRAVITY: Agent must write response to: {response_file}")
        print(f"ANTIGRAVITY: Previous frame description provided for delta context.")
        sys.exit(AGENT_NEEDS_ANALYSIS)

    # Read and merge batch response
    with open(response_file, "r", encoding="utf-8") as f:
        batch_result = json.load(f)

    analysis.update(batch_result)

    # Write per-frame .txt files in frames_dense/ alongside the .jpg
    frames_dir = os.path.join(video_dir, "frames_dense")
    for key, entry in batch_result.items():
        txt_path = os.path.join(frames_dir, f"frame_{key}.txt")
        description = entry.get("description", "")
        delta = entry.get("delta", "")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"[Description]\n{description}\n\n[Delta]\n{delta}\n")

    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    newly_done = len(analysis)
    still_remaining = len(all_keys) - newly_done

    print(f"Merged batch. Written {len(batch_result)} txt files. Total analyzed: {newly_done}/{len(all_keys)}")

    if still_remaining > 0:
        print(f"ANTIGRAVITY: {still_remaining} frames remaining. Re-run to process next batch.")
        sys.exit(AGENT_NEEDS_ANALYSIS)

    print(f"Analysis complete. Saved to {analysis_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze dense frames with full description + delta")
    parser.add_argument("video_id", help="Video ID in data/")
    parser.add_argument("--batch-size", type=int, default=10, help="Frames per agent batch (default: 10)")
    args = parser.parse_args()
    
    run_analysis(args.video_id, args.batch_size)
