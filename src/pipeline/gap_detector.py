import os
import sys
import json
import argparse
import pendulum
from typing import List
from pydantic import BaseModel, root_validator
import glob
from dotenv import load_dotenv

load_dotenv()

class GapTarget(BaseModel):
    exact_timestamp: str # Format HH:MM:SS
    context_snippet: str
    
    @root_validator(pre=True)
    def validate_timestamp(cls, values):
        timestamp = values.get('exact_timestamp')
        if timestamp:
            try:
                if timestamp.count(':') == 1:
                    timestamp = f"00:{timestamp}"
                pendulum.parse(timestamp, exact=True)
                values['exact_timestamp'] = timestamp
            except ValueError:
                raise ValueError(f"Invalid timestamp format: {timestamp}")
        return values

class GapsResponse(BaseModel):
    gaps: List[GapTarget]

def get_system_prompt() -> str:
    return """You are a data engineer analyzing a video transcript. Your task is to identify "Visual Dependency Gaps". 
A visual dependency gap occurs when the speaker references something visual (e.g., "look at this bar", "this level here", 
"look here", "посмотрите сюда", "вот здесь", "смотрите внимательно", "notice this trend", "this candle") but does not 
provide adequate verbal description of what they are pointing at.
You will be provided with a VTT transcript. The transcript contains timestamps and the spoken text.
Return a list of these gaps. For each gap, extract the `exact_timestamp` (in HH:MM:SS format for the line in the VTT) 
and the `context_snippet` (the surrounding 1-3 sentences for context).

IMPORTANT: Output ONLY strictly valid JSON according to this schema:
{
  "gaps": [
    {"exact_timestamp": "HH:MM:SS", "context_snippet": "..."},
    ...
  ]
}
"""

def _extract_gaps_with_provider(provider_name: str, transcript_text: str, video_id: str | None = None) -> tuple[GapsResponse, list[dict]]:
    from helpers.clients.providers import get_provider, resolve_model_for_stage

    response = get_provider(provider_name).generate_text(
        model=resolve_model_for_stage("gaps", video_id=video_id),
        user_text=f"Transcript:\n{transcript_text}",
        system_instruction=get_system_prompt(),
        response_mime_type="application/json",
        response_schema=GapsResponse,
        temperature=0.2,
        stage="gap_detector",
    )
    text = (response.text or "").strip()
    if not text:
        raise ValueError(f"{provider_name} returned empty response for gap detection")
    return GapsResponse.model_validate_json(text), response.usage_records


def extract_gaps_openai(transcript_text: str, video_id: str | None = None) -> GapsResponse:
    response, _ = _extract_gaps_with_provider("openai", transcript_text, video_id=video_id)
    return response

def extract_gaps_gemini(transcript_text: str, video_id: str | None = None) -> GapsResponse:
    response, _ = _extract_gaps_with_provider("gemini", transcript_text, video_id=video_id)
    return response


def extract_gaps_setra(transcript_text: str, video_id: str | None = None) -> GapsResponse:
    response, _ = _extract_gaps_with_provider("setra", transcript_text, video_id=video_id)
    return response

def write_prompt_file(transcript_text: str, vtt_file: str, video_dir: str) -> tuple[str, str]:
    """Write the prompt file for agent-based processing. Returns (prompt_path, response_path)."""
    prompt_file = os.path.join(video_dir, f"gap_prompt_{os.path.basename(vtt_file)}.txt")
    response_file = os.path.join(video_dir, f"gap_response_{os.path.basename(vtt_file)}.json")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(get_system_prompt() + "\n\n" + transcript_text)
    return prompt_file, response_file

def read_response_file(response_file: str) -> GapsResponse:
    """Read the agent-filled JSON response."""
    with open(response_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return GapsResponse(**data)

def process_video(video_id: str, provider: str):
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
    if not os.path.exists(video_dir):
        print(f"Directory {video_dir} not found.")
        return

    vtt_files = glob.glob(os.path.join(video_dir, "*.vtt"))
    vtt_files = [f for f in vtt_files if not f.endswith("_enriched.vtt")]
    
    if not vtt_files:
        print(f"No original VTT files found for {video_id}.")
        return

    targets_data = {}
    request_usage_records: list[dict] = []
    for vtt_file in vtt_files:
        print(f"Processing {vtt_file} with provider: {provider}")
        with open(vtt_file, "r", encoding="utf-8") as f:
            transcript_text = f.read()

        if provider == "openai":
            response, usage_records = _extract_gaps_with_provider("openai", transcript_text, video_id=video_id)
        elif provider == "gemini":
            response, usage_records = _extract_gaps_with_provider("gemini", transcript_text, video_id=video_id)
        elif provider == "setra":
            response, usage_records = _extract_gaps_with_provider("setra", transcript_text, video_id=video_id)
        elif provider == "antigravity":
            # Write prompt file for agent processing then immediately read back the response
            prompt_file, response_file = write_prompt_file(transcript_text, vtt_file, video_dir)
            print(f"ANTIGRAVITY: Prompt written to {prompt_file}")
            if not os.path.exists(response_file):
                print(f"ANTIGRAVITY: Response file not yet at {response_file}")
                print(f"ANTIGRAVITY: Run gap_detector in two-step mode or have the agent fill it in.")
                sys.exit(10)  # Exit with code 10 = "needs agent analysis"
            response = read_response_file(response_file)
            usage_records = []
        else:
            raise ValueError(f"Unknown provider {provider}")
            
        targets_data[os.path.basename(vtt_file)] = response.model_dump()['gaps']
        request_usage_records.extend(usage_records)
        
    output_path = os.path.join(video_dir, "targets.json")
    if request_usage_records:
        targets_data["__request_usage__"] = request_usage_records
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(targets_data, f, indent=2)
    from helpers.usage_report import write_video_usage_summary
    write_video_usage_summary(video_dir)
    
    print(f"Saved gaps to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id", help="Video Directory ID in data/")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "openai"), choices=["openai", "gemini", "antigravity"])
    args = parser.parse_args()
    
    process_video(args.video_id, args.provider)
