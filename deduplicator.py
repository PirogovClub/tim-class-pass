import os
import sys
import json
import glob
import argparse
import pendulum

AGENT_NEEDS_ANALYSIS = 10

def group_scenes(analysis: dict) -> list[dict]:
    """
    Groups consecutive frames into scenes based on delta.
    Returns a list of scene dicts: {start_key, end_key, frames, scene_type, deltas}
    """
    scenes = []
    current_scene = None

    for key in sorted(analysis.keys()):
        entry = analysis[key]
        delta = entry.get("delta", "No change").strip()
        is_change = not (delta.lower() == "no change")

        if current_scene is None:
            current_scene = {
                "start_key": key,
                "end_key": key,
                "frames": [key],
                "deltas": [delta],
                "first_description": entry.get("description", "")
            }
        elif is_change:
            # Close current scene and start new one
            scenes.append(current_scene)
            current_scene = {
                "start_key": key,
                "end_key": key,
                "frames": [key],
                "deltas": [delta],
                "first_description": entry.get("description", "")
            }
        else:
            current_scene["end_key"] = key
            current_scene["frames"].append(key)
            current_scene["deltas"].append(delta)

    if current_scene:
        scenes.append(current_scene)

    return scenes

def key_to_timestamp(key: str) -> str:
    """Convert frame key (zero-padded seconds) to HH:MM:SS"""
    seconds = int(key)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def is_time_in_block(target_ts: str, start_ts: str, end_ts: str) -> bool:
    try:
        def to_s(ts):
            parts = ts.replace(",", ".").split(":")
            h, m, s = parts[0], parts[1], parts[2].split(".")[0]
            return int(h) * 3600 + int(m) * 60 + int(s)
        return to_s(start_ts) <= to_s(target_ts) <= to_s(end_ts)
    except Exception:
        return False

def stitch_vtt(vtt_file: str, scene_map: dict[str, str]) -> str:
    """Insert [Visual: ...] blocks into VTT at the right timestamps. Returns enriched content."""
    with open(vtt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    result = []
    inserted_scenes = set()

    for i, line in enumerate(lines):
        result.append(line)
        if "-->" in line:
            parts = line.split("-->")
            start_ts = parts[0].strip().split(".")[0]
            end_ts = parts[1].strip().split(".")[0]

            for ts, description in scene_map.items():
                if ts not in inserted_scenes and is_time_in_block(ts, start_ts, end_ts):
                    result.append(f"\n[Visual: {description}]\n")
                    inserted_scenes.add(ts)
                    break

    return "".join(result)

def run_deduplicator(video_id: str):
    video_dir = os.path.join("data", video_id)
    analysis_file = os.path.join(video_dir, "dense_analysis.json")
    prompt_file = os.path.join(video_dir, "dedup_prompt.txt")
    response_file = os.path.join(video_dir, "dedup_response.json")

    if not os.path.exists(analysis_file):
        print(f"Error: {analysis_file} not found. Run dense_analyzer first.")
        sys.exit(1)

    with open(analysis_file, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    scenes = group_scenes(analysis)
    print(f"Found {len(scenes)} scenes from {len(analysis)} frames.")

    # Write prompt for agent
    prompt_lines = [
        "You are producing a polished visual description of a video.",
        "Below are the video's scenes grouped by visual change.",
        "For each scene, you will be given:",
        "  - The start timestamp (HH:MM:SS)",
        "  - The full description of the first frame of the scene",
        "  - All the deltas (what changed second by second within the scene)",
        "",
        "Your tasks:",
        "1. Write a single polished paragraph describing what is visually happening in each scene.",
        "   Merge all deltas into a natural narrative. Do not list deltas mechanically.",
        "2. For scenes with 'No change' deltas (static scenes), a single sentence suffices.",
        "3. For 'Scene change' scenes, note clearly what the new scene contains.",
        "",
        "Format your response as JSON:",
        '{ "HH:MM:SS": "polished description paragraph", ... }',
        "",
        "=== SCENES ===",
    ]

    for scene in scenes:
        ts = key_to_timestamp(scene["start_key"])
        end_ts = key_to_timestamp(scene["end_key"])
        meaningful_deltas = [d for d in scene["deltas"] if d.lower() not in ("no change", "scene start")]
        prompt_lines += [
            f"\n[{ts} --> {end_ts}]",
            f"First frame description: {scene['first_description']}",
            f"Deltas within scene ({len(meaningful_deltas)} changes):"
        ]
        for d in meaningful_deltas[:20]:  # cap to avoid huge prompts
            prompt_lines.append(f"  - {d}")
        if len(meaningful_deltas) > 20:
            prompt_lines.append(f"  ... and {len(meaningful_deltas) - 20} more changes")

    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write("\n".join(prompt_lines))

    if not os.path.exists(response_file):
        print(f"ANTIGRAVITY: Dedup prompt written to: {prompt_file}")
        print(f"ANTIGRAVITY: Agent must write polished scene descriptions to: {response_file}")
        sys.exit(AGENT_NEEDS_ANALYSIS)

    with open(response_file, "r", encoding="utf-8") as f:
        scene_map = json.load(f)  # { "HH:MM:SS": "description", ... }

    print(f"Loaded {len(scene_map)} polished scene descriptions.")

    # Find original VTT
    vtt_files = glob.glob(os.path.join(video_dir, "*.vtt"))
    vtt_files = [v for v in vtt_files if "_enriched" not in v and "_final" not in v]

    for vtt_file in vtt_files:
        enriched_content = stitch_vtt(vtt_file, scene_map)
        name = os.path.splitext(os.path.basename(vtt_file))[0]
        enriched_path = os.path.join(video_dir, f"{name}_enriched.vtt")
        with open(enriched_path, "w", encoding="utf-8") as f:
            f.write(enriched_content)
        print(f"Enriched VTT saved: {enriched_path}")

    # Write video_commentary.md
    commentary_path = os.path.join(video_dir, "video_commentary.md")
    commentary_lines = [f"# Video Commentary: {video_id}\n"]
    commentary_lines.append("A non-timed visual description of every scene in the video. "
                             "Reading this document gives full understanding of what is shown on screen.\n")
    for i, scene in enumerate(scenes):
        ts = key_to_timestamp(scene["start_key"])
        end_ts = key_to_timestamp(scene["end_key"])
        description = scene_map.get(ts, scene["first_description"])
        duration_s = int(scene["end_key"]) - int(scene["start_key"]) + 1
        commentary_lines.append(f"## [{ts}] Scene {i+1} ({duration_s}s)")
        commentary_lines.append(f"{description}\n")

    with open(commentary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(commentary_lines))
    print(f"Video commentary saved: {commentary_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deduplicate and polish dense analysis into final outputs")
    parser.add_argument("video_id", help="Video ID in data/")
    args = parser.parse_args()
    run_deduplicator(args.video_id)
