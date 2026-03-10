"""
Validate Gemini API key and connectivity; print usage from one minimal request.
Optionally infer free vs paid tier by sending several rapid requests (free ≈10 RPM).

Usage:
  uv run python scripts/validate_gemini.py [--model MODEL] [--check-tier]

To confirm tier in the dashboard: https://ai.dev/rate-limit or Google AI Studio → API keys.
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.chdir(_project_root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Number of rapid requests to infer tier (free tier ~10 RPM for gemini-2.5-flash)
_TIER_CHECK_REQUESTS = 12


def _run_tier_check(client, model: str) -> tuple[int, int]:
    """Send _TIER_CHECK_REQUESTS rapid requests; return (success_count, rate_limited_count)."""
    from google.genai import errors

    ok = 0
    rate_limited = 0
    for i in range(_TIER_CHECK_REQUESTS):
        try:
            client.models.generate_content(model=model, contents="Say OK")
            ok += 1
        except errors.ClientError as e:
            if e.status_code == 429 or "RESOURCE_EXHAUSTED" in (str(e).upper() or ""):
                rate_limited += 1
            else:
                raise
    return ok, rate_limited


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Validate Gemini API key and run one minimal request.")
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--check-tier",
        action="store_true",
        help="Send several rapid requests to infer free vs paid tier (free ~10 RPM)",
    )
    args = parser.parse_args()

    import gemini_client

    print("Validating Gemini API key and connectivity...", file=sys.stderr)
    gemini_client.require_gemini_key()
    client = gemini_client.get_client()
    model = args.model or "gemini-2.5-flash"
    print(f"Model: {model}", file=sys.stderr)

    # One minimal text-only request
    response = gemini_client.generate_with_retry(
        model=model,
        contents="Reply with exactly: OK",
    )

    text = (response.text or "").strip()
    print("Response:", text or "(empty)")
    if not text:
        print("Warning: Empty response.", file=sys.stderr)

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

    if args.check_tier:
        print(file=sys.stderr)
        print(f"Sending {_TIER_CHECK_REQUESTS} rapid requests to infer tier...", file=sys.stderr)
        ok, rate_limited = _run_tier_check(client, model)
        print(f"Result: {ok} succeeded, {rate_limited} rate-limited (429).", file=sys.stderr)
        if rate_limited > 0:
            print("Tier hint: FREE (hit rate limit at ~10 RPM).", file=sys.stderr)
        else:
            print("Tier hint: PAID (or free with headroom; no rate limit hit).", file=sys.stderr)

    print(file=sys.stderr)
    print("Validation OK. Key is valid and the API responded.", file=sys.stderr)
    print("To confirm tier in dashboard: https://ai.dev/rate-limit", file=sys.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
