"""
Run a single batch task file (prompt + images) through the Gemini API and print token usage.
Usage:
  uv run python scripts/run_task_gemini.py <task.json> [--model MODEL] [--video_id ID] [--output PATH]
"""
import argparse
import json
import os
import sys

# Ensure project root is on path so gemini_client and config can be imported
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.chdir(_project_root)

# Load .env so GEMINI_API_KEY is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def resolve_path(p: str, cwd: str) -> str:
    """Return path that exists: try as-is, then relative to cwd."""
    if os.path.isabs(p) and os.path.exists(p):
        return p
    if os.path.exists(p):
        return p
    rel = os.path.join(cwd, p)
    if os.path.exists(rel):
        return os.path.abspath(rel)
    # Try normalizing backslashes for Windows
    norm = os.path.normpath(p)
    if os.path.exists(norm):
        return os.path.abspath(norm)
    return p  # return original so we fail with clear error below


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a task JSON through Gemini and print token usage.")
    parser.add_argument("task_json", help="Path to task JSON (prompt_content + frame_paths)")
    parser.add_argument("--model", default=None, help="Gemini model (e.g. gemini-2.5-flash, gemini-2.5-pro)")
    parser.add_argument("--video_id", default=None, help="Video ID for config-based model when --model not set")
    parser.add_argument("--output", default=None, help="Write response JSON to this path (default: task's response_file)")
    args = parser.parse_args()

    cwd = os.getcwd()
    task_path = os.path.normpath(args.task_json)
    if not os.path.isabs(task_path):
        task_path = os.path.join(cwd, task_path)
    if not os.path.exists(task_path):
        print(f"Error: Task file not found: {task_path}", file=sys.stderr)
        sys.exit(1)

    with open(task_path, "r", encoding="utf-8") as f:
        task = json.load(f)
    if "prompt_content" not in task or "frame_paths" not in task:
        print("Error: Task JSON must contain 'prompt_content' and 'frame_paths'", file=sys.stderr)
        sys.exit(1)

    prompt_content = task["prompt_content"]
    frame_paths = task["frame_paths"]
    resolved = [resolve_path(p, cwd) for p in frame_paths]
    for i, p in enumerate(resolved):
        if not os.path.exists(p):
            print(f"Error: Frame image not found: {frame_paths[i]}", file=sys.stderr)
            sys.exit(1)

    import gemini_client
    from google.genai import types

    model = args.model or gemini_client.get_model_for_step("images", args.video_id)
    parts = [types.Part.from_text(text=prompt_content)]
    for path in resolved:
        with open(path, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))

    contents = [types.Content(role="user", parts=parts)]
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.3,
    )

    print(f"Model: {model} | Images: {len(resolved)}", file=sys.stderr)
    response = gemini_client.generate_with_retry(model=model, contents=contents, config=config)

    # Token usage: support common attribute names
    usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_token_count", None) or getattr(usage, "input_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None) or getattr(usage, "output_token_count", None)
        total = getattr(usage, "total_token_count", None)
        if total is None and prompt_tokens is not None and output_tokens is not None:
            total = prompt_tokens + output_tokens
        print("prompt_token_count:", prompt_tokens if prompt_tokens is not None else "N/A")
        print("candidates_token_count:", output_tokens if output_tokens is not None else "N/A")
        print("total_token_count:", total if total is not None else "N/A")
    else:
        print("usage_metadata: not available on response", file=sys.stderr)

    out_path = args.output or task.get("response_file")
    if out_path:
        out_path = resolve_path(out_path, cwd)
        text = (response.text or "").strip()
        if text:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Response written to: {out_path}", file=sys.stderr)
        else:
            print("Warning: Empty response, not written", file=sys.stderr)


if __name__ == "__main__":
    main()
