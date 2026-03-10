import os
import sys
import json
import re
import glob
import argparse
import pendulum

AGENT_NEEDS_ANALYSIS = 10


def _normalize_agent(agent: str) -> str:
    if agent == "antigravity":
        return "ide"
    return agent


def _parse_json_from_response(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def _dedup_openai(prompt_text: str, video_id: str | None = None) -> dict:
    from helpers.clients import openai_client
    text = openai_client.chat_completion(
        [{"role": "user", "content": prompt_text + "\n\nReturn only a JSON object. Keys are HH:MM:SS timestamps, values are polished description strings."}],
        step="dedup",
        video_id=video_id,
        max_tokens=4000,
    )
    return _parse_json_from_response(text or "{}")


def _dedup_gemini(prompt_text: str, video_id: str | None = None) -> dict:
    from helpers.clients import gemini_client
    from google.genai import types
    model = gemini_client.get_model_for_step("dedup", video_id)
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_text + "\n\nReturn only a JSON object. Keys are HH:MM:SS timestamps, values are polished description strings.")],
        )
    ]
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
    )
    if os.getenv("GEMINI_STREAMING"):
        text = gemini_client.generate_with_retry_stream(model=model, contents=contents, config=config).strip()
    else:
        response = gemini_client.generate_with_retry(model=model, contents=contents, config=config)
        text = (response.text or "{}").strip()
    if not text:
        return {}
    return _parse_json_from_response(text)

def group_scenes(analysis: dict) -> list[dict]:
    """
    Groups consecutive frames into scenes based on lesson_relevant and scene_boundary.
    material_change is used only as a backward-compatible fallback when lesson_relevant
    is missing (e.g. old Gemini batch files).
    Returns a list of scene dicts: {start_key, end_key, frames, scene_type, change_summaries,
    first_entry, first_relevant_entry}

    first_entry: the first frame in the scene (may be minimal/skipped).
    first_relevant_entry: the first lesson_relevant frame in the scene; falls back to first_entry.
    Downstream consumers should prefer first_relevant_entry for rich summarization.
    """
    scenes = []
    current_scene = None

    for key in sorted(analysis.keys()):
        entry = analysis[key]
        lesson_relevant = entry.get("lesson_relevant")
        if lesson_relevant is None:
            lesson_relevant = entry.get("material_change", True)
        scene_boundary = entry.get("scene_boundary")
        if scene_boundary is None:
            scene_boundary = bool(lesson_relevant and entry.get("material_change", True))

        if current_scene is None:
            current_scene = {
                "start_key": key,
                "end_key": key,
                "frames": [key],
                "change_summaries": [entry.get("change_summary", [])],
                "first_entry": entry,
                "first_relevant_entry": entry if lesson_relevant else None,
            }
        elif scene_boundary:
            # Finalize previous scene: fill first_relevant_entry fallback
            if current_scene["first_relevant_entry"] is None:
                current_scene["first_relevant_entry"] = current_scene["first_entry"]
            scenes.append(current_scene)
            current_scene = {
                "start_key": key,
                "end_key": key,
                "frames": [key],
                "change_summaries": [entry.get("change_summary", [])],
                "first_entry": entry,
                "first_relevant_entry": entry if lesson_relevant else None,
            }
        else:
            current_scene["end_key"] = key
            current_scene["frames"].append(key)
            current_scene["change_summaries"].append(entry.get("change_summary", []))
            # Track first relevant entry within the scene
            if current_scene["first_relevant_entry"] is None and lesson_relevant:
                current_scene["first_relevant_entry"] = entry

    if current_scene:
        if current_scene["first_relevant_entry"] is None:
            current_scene["first_relevant_entry"] = current_scene["first_entry"]
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

def run_deduplicator(video_id: str, agent: str = "ide", vtt_file_override: str | None = None):
    """
    vtt_file_override: optional filename (e.g. from pipeline.yml) relative to data/<video_id>/.
    If None, process all non-enriched .vtt in the folder.
    """
    agent = _normalize_agent(agent)
    video_dir = os.path.join("data", video_id)
    analysis_file = os.path.join(video_dir, "dense_analysis.json")
    batches_dir = os.path.join(video_dir, "batches")
    os.makedirs(batches_dir, exist_ok=True)
    prompt_file = os.path.join(batches_dir, "dedup_prompt.txt")
    response_file = os.path.join(batches_dir, "dedup_response.json")

    if not os.path.exists(analysis_file):
        print(f"Error: {analysis_file} not found. Run dense_analyzer first.")
        sys.exit(1)

    with open(analysis_file, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    scenes = group_scenes(analysis)
    print(f"Found {len(scenes)} scenes from {len(analysis)} frames.")

    # Build a text summary from the structured first_entry
    def summarize_entry(entry: dict) -> str:
        """Build a human-readable summary from a structured frame entry."""
        parts = []
        if entry.get("explanation_summary"):
            parts.append(f"Summary: {entry['explanation_summary']}")
        vis_type = entry.get("visual_representation_type")
        if vis_type:
            parts.append(f"Type: {vis_type}")
        state = entry.get("current_state", {})
        if state.get("symbol"):
            parts.append(f"Symbol: {state['symbol']}")
        if state.get("timeframe"):
            parts.append(f"TF: {state['timeframe']}")
        if state.get("platform"):
            parts.append(f"Platform: {state['platform']}")
        facts = state.get("visual_facts", [])
        if facts:
            parts.append(f"Facts: {'; '.join(facts)}")
        interp = state.get("trading_relevant_interpretation", [])
        if interp:
            parts.append(f"Interpretation: {'; '.join(interp)}")
        extracted_facts = entry.get("extracted_facts") or {}
        extracted_state = extracted_facts.get("current_state", {}) if isinstance(extracted_facts, dict) else {}
        extracted_visual_facts = extracted_state.get("visual_facts", [])
        if extracted_visual_facts and not facts:
            parts.append(f"Facts: {'; '.join(extracted_visual_facts)}")
        # Fallback for legacy format
        if not parts:
            desc = entry.get("description", "")
            if desc:
                parts.append(desc)
        return " | ".join(parts) if parts else "(no structured data)"

    # Write prompt for agent
    prompt_lines = [
        "You are producing a polished visual description of a video.",
        "Below are the video's scenes grouped by visual change.",
        "For each scene, you will be given:",
        "  - The start timestamp (HH:MM:SS)",
        "  - A structured summary of the first frame of the scene",
        "  - All the change summaries within the scene",
        "",
        "Your tasks:",
        "1. Write a single polished paragraph describing what is visually happening in each scene.",
        "   Merge all changes into a natural narrative. Do not list changes mechanically.",
        "2. For scenes with no changes (static scenes), a single sentence suffices.",
        "3. For scene-change scenes, note clearly what the new scene contains.",
        "",
        "Format your response as JSON:",
        '{ "HH:MM:SS": "polished description paragraph", ... }',
        "",
        "=== SCENES ===",
    ]

    for scene in scenes:
        ts = key_to_timestamp(scene["start_key"])
        end_ts = key_to_timestamp(scene["end_key"])
        # Prefer first_relevant_entry for rich summarization; fall back to first_entry for legacy data
        anchor_entry = scene.get("first_relevant_entry") or scene["first_entry"]
        first_summary = summarize_entry(anchor_entry)
        # Flatten change_summaries (list of lists) into meaningful items
        all_changes = []
        for cs_list in scene["change_summaries"]:
            if isinstance(cs_list, list):
                all_changes.extend(cs_list)
            elif isinstance(cs_list, str) and cs_list:
                all_changes.append(cs_list)
        meaningful_changes = [c for c in all_changes if c]
        prompt_lines += [
            f"\n[{ts} --> {end_ts}]",
            f"First frame: {first_summary}",
            f"Changes within scene ({len(meaningful_changes)}):"
        ]
        for c in meaningful_changes[:20]:  # cap to avoid huge prompts
            prompt_lines.append(f"  - {c}")
        if len(meaningful_changes) > 20:
            prompt_lines.append(f"  ... and {len(meaningful_changes) - 20} more changes")

    prompt_text = "\n".join(prompt_lines)
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt_text)

    if not os.path.exists(response_file):
        if agent == "ide":
            # State file for orchestrator/subagent: prompt and response paths, prompt_content
            state_file = os.path.join(batches_dir, "last_agent_task.json")
            state = {
                "prompt_file": os.path.abspath(prompt_file),
                "response_file": os.path.abspath(response_file),
                "type": "dedup",
                "prompt_content": prompt_text,
            }
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            print(f"IDE: Dedup prompt written to: {prompt_file}")
            print(f"IDE: Agent must write polished scene descriptions to: {response_file}")
            print(f"IDE: State written to: {state_file}")
            sys.exit(AGENT_NEEDS_ANALYSIS)
        # OpenAI or Gemini: call text API and write response
        try:
            if agent == "openai":
                scene_map = _dedup_openai(prompt_text, video_id=video_id)
            else:
                scene_map = _dedup_gemini(prompt_text, video_id)
            with open(response_file, "w", encoding="utf-8") as f:
                json.dump(scene_map, f, indent=2, ensure_ascii=False)
            print(f"API: Wrote dedup response to {response_file}")
        except Exception as e:
            print(f"Error calling dedup API: {e}")
            raise

    with open(response_file, "r", encoding="utf-8") as f:
        scene_map = json.load(f)  # { "HH:MM:SS": "description", ... }

    print(f"Loaded {len(scene_map)} polished scene descriptions.")

    # Resolve VTT file(s): pipeline.yml override (single file) or all non-enriched .vtt
    if vtt_file_override:
        single = os.path.join(video_dir, vtt_file_override)
        if not os.path.isfile(single):
            print(f"Error: vtt_file from config not found: {single}")
            sys.exit(1)
        vtt_files = [single]
    else:
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
        first_summary = summarize_entry(scene["first_entry"])
        description = scene_map.get(ts, first_summary)
        duration_s = int(scene["end_key"]) - int(scene["start_key"]) + 1
        commentary_lines.append(f"## [{ts}] Scene {i+1} ({duration_s}s)")
        commentary_lines.append(f"{description}\n")

    with open(commentary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(commentary_lines))
    print(f"Video commentary saved: {commentary_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deduplicate and polish dense analysis into final outputs")
    parser.add_argument("video_id", help="Video ID in data/")
    parser.add_argument("--vtt-file", default=None, help="VTT filename in data/<video_id>/ (from pipeline.yml)")
    parser.add_argument(
        "--agent",
        default=os.getenv("AGENT_DEDUP", os.getenv("AGENT", "ide")),
        choices=["openai", "gemini", "ide", "antigravity"],
        help="Agent: ide (IDE as AI agent), openai, gemini (default: ide)",
    )
    args = parser.parse_args()
    run_deduplicator(args.video_id, agent=args.agent, vtt_file_override=args.vtt_file)
