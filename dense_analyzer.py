import os
import sys
import json
import re
import argparse
import base64
from dotenv import load_dotenv

load_dotenv()

AGENT_NEEDS_ANALYSIS = 10


def _normalize_agent(agent: str) -> str:
    """Accept 'antigravity' as alias for 'ide'."""
    if agent == "antigravity":
        return "ide"
    return agent


def _parse_json_from_response(text: str) -> dict:
    """Extract JSON from API response, handling markdown code blocks."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _single_frame_prompt(frame_key: str, frame_path: str, previous_state: str) -> str:
    """Build prompt text for analyzing one frame (for API call)."""
    return (
        f"{PRODUCTION_PROMPT}\n\n"
        f"Previous frame state: {previous_state or 'None (this is the first frame)'}\n\n"
        f"Analyze this single frame. Frame key: {frame_key}. Image path: {os.path.abspath(frame_path)}\n\n"
        "Return only valid JSON, no markdown or explanation."
    )


def _analyze_frame_openai(frame_path: str, prompt_text: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    base64_image = _encode_image(frame_path)
    response = client.chat.completions.create(
        model=os.getenv("MODEL_NAME", os.getenv("MODEL_IMAGES", "gpt-4o")),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        ],
        max_tokens=2000,
    )
    text = response.choices[0].message.content or ""
    return _parse_json_from_response(text)


def _analyze_frame_gemini(frame_path: str, prompt_text: str) -> dict:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    with open(frame_path, "rb") as f:
        image_bytes = f.read()
    response = client.models.generate_content(
        model=os.getenv("MODEL_NAME", os.getenv("MODEL_IMAGES", "gemini-1.5-pro")),
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(prompt_text),
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                ],
            )
        ],
    )
    text = (response.text or "").strip()
    return _parse_json_from_response(text)

PRODUCTION_PROMPT = """You are analyzing sequential screenshots from a trading education video for building a structured trading knowledge base.

Important:
The screen may show any of the following:
- live trading charts
- static chart screenshots
- abstract bar diagrams
- candlestick sketches
- hand-drawn pattern illustrations
- whiteboard explanations
- text slides
- mixed visuals

Do NOT assume every frame is a real market chart.

Your task:
1. Determine whether the current screenshot is materially different from the previous screenshot.
2. Identify the visual representation type.
3. Identify whether the frame is a real market example or an abstract teaching example.
4. Choose the correct extraction mode: market_specific, structural_only, or conceptual_only.
5. If there is a material change, extract the current trading-relevant visual state in structured JSON.
6. Separate direct visual facts from low-inference interpretation.
7. Do not invent exact numeric values, symbols, dates, or timeframes if they are abstract, unreadable, or unclear.
8. Copy visible labels exactly when readable.
9. Be concise, conservative, and factual.

Definition of material change:
A frame is materially changed if any of the following occur:
- symbol changed
- timeframe changed
- chart or visual example changed
- zoom level changed meaningfully
- chart or diagram panned to a different relevant area
- a new level, annotation, label, drawing, arrow, or highlighted area appeared or disappeared
- the instructor switched to another concept or example
- a previously unreadable label became readable
- emphasis moved to a different important region
- the visual context changed enough to affect trading interpretation

Do NOT mark material change for:
- tiny cursor movement with no new significance
- negligible rendering differences
- repeated static frames with no meaningful new information

If there is no material change, return:
{ "frame_timestamp": "<timestamp>", "material_change": false }

If there is a material change, return the full structured JSON with these fields:
frame_timestamp, material_change (true), change_summary (array of strings),
visual_representation_type, example_type, extraction_mode, screen_type,
educational_event_type (array), current_state (with symbol, timeframe, platform,
chart_type, visible_date_range, visible_price_range, chart_layout, drawn_objects,
visible_annotations, cursor_or_highlight, visual_facts, structural_pattern_visible,
trading_relevant_interpretation, readability), extracted_entities (setup_names,
level_values, risk_reward_values, atr_values, entry_values, stop_values,
target_values, pattern_terms), notes.

See skills/trading_visual_extraction/SKILL.md for the complete schema and field guidance.

Rules:
- Separate direct visual facts from interpretation.
- If the visual is abstract, do not force exact prices, dates, symbols, or timeframes.
- If the visual is hand-drawn, focus on structure, arrows, levels, and labels.
- If the visual is a real chart, capture exact values when clearly readable.
- If text is unclear, say null or mark confidence low.
- If only approximate reading is possible, explicitly say approx.
- Keep wording concise and structured.
- Return JSON only.
"""


def get_batch_prompt(batch_entries: list[tuple[str, str]], video_dir: str, previous_state: str) -> str:
    """
    Returns the production prompt for the agent to analyze a batch of frames
    using the structured trading visual extraction schema.
    batch_entries: list of (frame_key, frame_path)
    previous_state: JSON string of the last analyzed frame's structured output
    """
    lines = [
        PRODUCTION_PROMPT,
        "",
        f"Previous frame state: {previous_state or 'None (this is the first frame)'}",
        "",
        "Frames to analyze:",
    ]
    for key, path in batch_entries:
        abs_path = os.path.abspath(path)
        lines.append(f"  Frame {key}: {abs_path}")
    lines += [
        "",
        "Save your response as a JSON object to the response file.",
        "Keys are the frame numbers (e.g. \"000001\").",
        "Values are the structured extraction JSON for each frame.",
        "",
        "Example:",
        '{',
        '  "000001": { "frame_timestamp": "00:00:01", "material_change": true, "change_summary": [...], ... },',
        '  "000002": { "frame_timestamp": "00:00:02", "material_change": false }',
        '}',
        "",
        "NOTE: Per-frame .json files will be automatically written to frames_dense/ alongside each .jpg.",
    ]
    return "\n".join(lines)

def run_analysis(video_id: str, batch_size: int = 10, agent: str = "ide"):
    agent = _normalize_agent(agent)
    video_dir = os.path.join("data", video_id)
    index_file = os.path.join(video_dir, "dense_index.json")
    analysis_file = os.path.join(video_dir, "dense_analysis.json")
    batches_dir = os.path.join(video_dir, "batches")
    os.makedirs(batches_dir, exist_ok=True)

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

    # Get the last analyzed frame's structured state for context
    if analysis:
        last_key = sorted(analysis.keys())[-1]
        previous_state = json.dumps(analysis[last_key], ensure_ascii=False)
    else:
        previous_state = ""

    # Process next batch
    batch_keys = remaining_keys[:batch_size]
    batch_entries = [(k, os.path.join(video_dir, index[k])) for k in batch_keys]

    batch_start = batch_keys[0]
    batch_end = batch_keys[-1]
    batch_label = f"{batch_start}-{batch_end}"

    prompt_file = os.path.join(batches_dir, f"dense_batch_prompt_{batch_label}.txt")
    response_file = os.path.join(batches_dir, f"dense_batch_response_{batch_label}.json")

    # Write the prompt (for ide and for reproducibility)
    prompt_text = get_batch_prompt(batch_entries, video_dir, previous_state)
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt_text)

    print(f"Batch {batch_label}: {len(batch_keys)} frames (agent: {agent})")

    if not os.path.exists(response_file):
        if agent == "ide":
            print(f"IDE: Batch prompt written to: {prompt_file}")
            print(f"IDE: Agent must write response to: {response_file}")
            print(f"IDE: Previous frame description provided for delta context.")
            sys.exit(AGENT_NEEDS_ANALYSIS)
        # OpenAI or Gemini: call vision API per frame and write response file
        batch_result = {}
        prev_state = previous_state
        for key, path in batch_entries:
            if not os.path.exists(path):
                print(f"Warning: Frame {path} not found, skipping.")
                continue
            prompt = _single_frame_prompt(key, path, prev_state)
            try:
                if agent == "openai":
                    entry = _analyze_frame_openai(path, prompt)
                else:
                    entry = _analyze_frame_gemini(path, prompt)
                batch_result[key] = entry
                prev_state = json.dumps(entry, ensure_ascii=False)
            except Exception as e:
                print(f"Error analyzing frame {key}: {e}")
                raise
        with open(response_file, "w", encoding="utf-8") as f:
            json.dump(batch_result, f, indent=2, ensure_ascii=False)
        print(f"API: Wrote batch response to {response_file}")

    # Read and merge batch response
    with open(response_file, "r", encoding="utf-8") as f:
        batch_result = json.load(f)

    analysis.update(batch_result)

    # Write per-frame .json files in frames_dense/ alongside the .jpg
    frames_dir = os.path.join(video_dir, "frames_dense")
    for key, entry in batch_result.items():
        json_path = os.path.join(frames_dir, f"frame_{key}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    newly_done = len(analysis)
    still_remaining = len(all_keys) - newly_done

    print(f"Merged batch. Written {len(batch_result)} txt files. Total analyzed: {newly_done}/{len(all_keys)}")

    if still_remaining > 0:
        print(f"IDE: {still_remaining} frames remaining. Re-run to process next batch.")
        sys.exit(AGENT_NEEDS_ANALYSIS)

    print(f"Analysis complete. Saved to {analysis_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze dense frames with full description + delta")
    parser.add_argument("video_id", help="Video ID in data/")
    parser.add_argument("--batch-size", type=int, default=10, help="Frames per agent batch (default: 10)")
    parser.add_argument(
        "--agent",
        default=os.getenv("AGENT_IMAGES", os.getenv("AGENT", "ide")),
        choices=["openai", "gemini", "ide", "antigravity"],
        help="Agent: ide (IDE as AI agent), openai, gemini (default: ide)",
    )
    args = parser.parse_args()
    run_analysis(args.video_id, args.batch_size, agent=args.agent)
