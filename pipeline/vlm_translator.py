import os
import sys
import json
import argparse
import base64
from dotenv import load_dotenv

load_dotenv()

def get_vlm_prompt(context: str) -> str:
    return f"""You are a financial transcriber. Look at this trading chart. 
The teacher just said: '{context}'. 
Describe exactly what candlestick shapes, price levels, or indicators the teacher is pointing out. 
Write a formal, clear, and descriptive paragraph replacing their ambiguous visual references."""

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def _translate_with_provider(provider_name: str, frame_path: str, context: str, video_id: str | None = None) -> tuple[str, list[dict]]:
    from helpers.clients.providers import get_provider, resolve_model_for_stage
    prompt = get_vlm_prompt(context)
    response = get_provider(provider_name).generate_text_with_image(
        model=resolve_model_for_stage("vlm", video_id=video_id),
        prompt=prompt,
        image_path=frame_path,
        max_tokens=300,
        stage="vlm_translator",
    )
    return response.text, response.usage_records


def translate_openai(frame_path: str, context: str, video_id: str | None = None) -> str:
    return _translate_with_provider("openai", frame_path, context, video_id=video_id)[0]

def translate_gemini(frame_path: str, context: str, video_id: str | None = None) -> str:
    return _translate_with_provider("gemini", frame_path, context, video_id=video_id)[0]


def translate_setra(frame_path: str, context: str, video_id: str | None = None) -> str:
    return _translate_with_provider("setra", frame_path, context, video_id=video_id)[0]

def write_vlm_prompt(frame_path: str, context: str, gap_id: str, video_dir: str) -> tuple[str, str]:
    """Write the VLM prompt file for agent processing. Returns (prompt_path, response_path)."""
    prompt_file = os.path.join(video_dir, f"vlm_prompt_{gap_id}.txt")
    response_file = os.path.join(video_dir, f"vlm_response_{gap_id}.txt")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(f"Image Path: {frame_path}\n\n{get_vlm_prompt(context)}")
    return prompt_file, response_file

def run_translator(video_id: str, provider: str):
    if provider == "gemini":
        from helpers.clients import gemini_client
        gemini_client.require_gemini_key()
    elif provider == "openai":
        from helpers.clients import openai_client
        openai_client.require_openai_key()
    elif provider == "setra":
        from helpers.clients import setra_client
        setra_client.require_setra_config()
    video_dir = os.path.join("data", video_id)
    targets_file = os.path.join(video_dir, "targets.json")

    if not os.path.exists(targets_file):
        print(f"Error: {targets_file} not found.")
        return

    with open(targets_file, "r", encoding="utf-8") as f:
        targets_data = json.load(f)

    pending_prompts = []  # (gap_id, prompt_file, response_file) for agent to fill
    request_usage_records: list[dict] = []

    print(f"Translating visual gaps for video {video_id} using {provider}")
    for vtt_filename, gaps in targets_data.items():
        if str(vtt_filename).startswith("__"):
            continue
        for index, gap in enumerate(gaps):
            if 'vlm_description' in gap:
                print(f"  Gap at {gap['exact_timestamp']} already has a description.")
                continue
                
            frame_path = gap.get('frame_path')
            if not frame_path or not os.path.exists(frame_path):
                print(f"  Warning: No frame found for gap at {gap['exact_timestamp']}")
                continue
                
            print(f"  Translating frame {frame_path}...")
            context = gap.get('context_snippet', '')
            gap_id = f"{video_id}_{index}"
            
            try:
                if provider == "openai":
                    description, usage_records = _translate_with_provider("openai", frame_path, context, video_id=video_id)
                    gap['vlm_description'] = description
                    gap['request_usage'] = usage_records
                    request_usage_records.extend(usage_records)
                elif provider == "gemini":
                    description, usage_records = _translate_with_provider("gemini", frame_path, context, video_id=video_id)
                    gap['vlm_description'] = description
                    gap['request_usage'] = usage_records
                    request_usage_records.extend(usage_records)
                elif provider == "setra":
                    description, usage_records = _translate_with_provider("setra", frame_path, context, video_id=video_id)
                    gap['vlm_description'] = description
                    gap['request_usage'] = usage_records
                    request_usage_records.extend(usage_records)
                elif provider == "antigravity":
                    prompt_file, response_file = write_vlm_prompt(frame_path, context, gap_id, video_dir)
                    if os.path.exists(response_file):
                        with open(response_file, "r", encoding="utf-8") as f:
                            gap['vlm_description'] = f.read().strip()
                    else:
                        print(f"  ANTIGRAVITY: Prompt written to {prompt_file}")
                        print(f"  ANTIGRAVITY: Response needed at {response_file}")
                        pending_prompts.append((gap_id, prompt_file, response_file))
                else:
                    raise ValueError(f"Unknown provider: {provider}")

            except Exception as e:
                print(f"  Error translating frame {frame_path}: {e}")

    # Save what we have so far
    if request_usage_records:
        targets_data["__request_usage__"] = list(targets_data.get("__request_usage__", [])) + request_usage_records
    with open(targets_file, "w", encoding="utf-8") as f:
        json.dump(targets_data, f, indent=2)
    from helpers.usage_report import write_video_usage_summary
    write_video_usage_summary(video_dir)

    if pending_prompts:
        print(f"\nANTIGRAVITY: {len(pending_prompts)} frame(s) need agent analysis.")
        for gap_id, prompt_file, response_file in pending_prompts:
            print(f"  Gap: {gap_id} | Prompt: {prompt_file} | Response: {response_file}")
        sys.exit(10)  # Exit code 10 = needs agent analysis

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id", help="Video ID directory in data/")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "openai"), choices=["openai", "gemini", "antigravity"])
    args = parser.parse_args()
    
    run_translator(args.video_id, args.provider)
