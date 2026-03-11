"""
Core benchmark runner for optional model comparisons.

Usage (via wrapper):
    python scripts/benchmark_models.py [--host URL] [--models MODEL1,MODEL2] [--gold-dir tests/gold]
    python scripts/benchmark_models.py --ps   # use available models from local MLX server (mlx_client.list_models)
    python scripts/benchmark_models.py --ps --gemini   # add current general Gemini models from live API (requires GEMINI_API_KEY in .env)

Results are written to benchmark-reports/benchmark_<timestamp>.json (or -o PATH). Each entry
includes the prompt used and the model's JSON output so you can compare prompts vs results.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
import sys
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_REPORTS_DIR = ROOT / "benchmark-reports"
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from pydantic import BaseModel

from helpers.analyze import _normalize_extraction_output
from helpers.clients import mlx_client
from helpers.clients import gemini_client
from scripts.build_benchmark_frame_prompt import build_prompt_from_vtt

GOLD_DIR = ROOT / "tests" / "gold"
FRAME_DIR = ROOT / "data" / "Lesson 2. Levels part 1" / "frames_dense"
BENCHMARK_TRANSCRIPT_PATH = ROOT / "data" / "Lesson 2. Levels part 1" / "Lesson 2. Levels part 1.vtt"
BENCHMARK_TRANSCRIPT_WINDOW_SECONDS = 7.0

CANDIDATE_MODELS = [
    "mlx-vision_ocr",                # MLX local vision task
    "mlx-vision_strategy",           # MLX local vision task
]

# llm_queue frame path (same lesson data dir)
FRAME_DIR_LLM_QUEUE = ROOT / "data" / "Lesson 2. Levels part 1" / "llm_queue"

GOLD_FRAMES = {
    "000628": "frame_000591_gemini.json",  # reuse gold; no 000628-specific gold yet
}

FRAME_PATHS = {
    "000628": str(FRAME_DIR_LLM_QUEUE / "frame_000628_diff_0.0951.jpg"),
}

# Exclude models that are too heavy or unreliable for benchmark (e.g. qwen 32B didn't fly)
EXCLUDE_MODELS = frozenset({"qwen2.5:32b-instruct-q4_K_M", "qwen2.5vl:32b"})

# Cap output size so runaway generations do not dominate the benchmark.
BENCHMARK_MAX_OUTPUT_TOKENS = 3000
BENCHMARK_BULK_IMAGE_COUNT = 100_000

# Gemini Developer API standard pricing per 1M tokens (current benchmarked model families).
# Note: preview/stable variants in the same family use the same benchmark pricing bucket here.
GEMINI_PRICING_USD_PER_MTOK = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash-lite-preview-09-2025": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50},
}


class BenchmarkEntity(BaseModel):
    label: str
    value_description: str


class BenchmarkCurrentState(BaseModel):
    visual_facts: list[str]
    structural_pattern_visible: list[str]
    trading_relevant_interpretation: list[str]


class BenchmarkExtractedEntities(BaseModel):
    level_values: list[BenchmarkEntity]
    stop_values: list[BenchmarkEntity]


class BenchmarkResponse(BaseModel):
    frame_timestamp: str
    material_change: bool
    visual_representation_type: Literal[
        "live_chart",
        "static_chart_screenshot",
        "abstract_bar_diagram",
        "candlestick_sketch",
        "hand_drawn_pattern",
        "whiteboard_explanation",
        "text_slide",
        "mixed_visual",
        "unknown",
    ]
    current_state: BenchmarkCurrentState
    extracted_entities: BenchmarkExtractedEntities


def _serialize_results(all_results: list[dict]) -> list[dict]:
    """Prepare JSON-safe report rows."""
    to_write: list[dict] = []
    for r in all_results:
        row = {k: v for k, v in r.items() if k not in ("model_output", "prompt") and not callable(v)}
        row["prompt"] = r.get("prompt")
        row["model_output"] = r.get("model_output")
        to_write.append(row)
    return to_write


def _write_report(out_path: Path, all_results: list[dict]) -> None:
    """Write the current benchmark state so finished models are persisted immediately."""
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(_serialize_results(all_results), f, indent=2, ensure_ascii=False)


def estimate_gemini_cost(model: str, prompt_tokens: int | None, output_tokens: int | None) -> dict[str, float] | None:
    """Estimate Gemini API cost from token counts and current per-model pricing."""
    pricing = GEMINI_PRICING_USD_PER_MTOK.get(model)
    if pricing is None or prompt_tokens is None or output_tokens is None:
        return None
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total = input_cost + output_cost
    return {
        "estimated_input_cost_usd": round(input_cost, 8),
        "estimated_output_cost_usd": round(output_cost, 8),
        "estimated_total_cost_usd": round(total, 8),
        "estimated_cost_per_100k_images_usd": round(total * BENCHMARK_BULK_IMAGE_COUNT, 2),
    }


def _is_general_benchmark_gemini_model(name: str) -> bool:
    """Keep general multimodal generateContent models, skip aliases and specialized variants."""
    skip_substrings = (
        "image-generation",
        "image-preview",
        "flash-image",
        "preview-tts",
        "customtools",
        "computer-use",
        "robotics",
    )
    if any(part in name for part in skip_substrings):
        return False
    if name.endswith("-latest") or name.endswith("-001"):
        return False
    return True


def list_gemini_benchmark_models() -> list[str]:
    """List current Gemini generateContent models suitable for the benchmark."""
    gemini_client.require_gemini_key()
    client = gemini_client.get_client()
    names: list[str] = []
    for model in client.models.list():
        raw_name = getattr(model, "name", "") or ""
        actions = getattr(model, "supported_actions", []) or []
        if "generateContent" not in actions:
            continue
        if not raw_name.startswith("models/gemini-"):
            continue
        short_name = raw_name.split("/", 1)[1]
        if _is_general_benchmark_gemini_model(short_name):
            names.append(short_name)
    return sorted(set(names))


def build_benchmark_prompt(frame_key: str, gold: dict) -> str:
    """Compact prompt for benchmarking parse reliability and scoring fields."""
    timestamp = gold.get("frame_timestamp") or frame_key
    transcript_block = ""
    if BENCHMARK_TRANSCRIPT_PATH.exists():
        try:
            transcript_block = build_prompt_from_vtt(
                frame_key=frame_key,
                vtt_path=BENCHMARK_TRANSCRIPT_PATH,
                window_seconds=BENCHMARK_TRANSCRIPT_WINDOW_SECONDS,
                timestamp=timestamp,
            ).strip()
        except Exception as exc:
            transcript_block = f"(Transcript context unavailable: {exc})"
    if transcript_block:
        transcript_block = f"{transcript_block}\n\n"
    return f"""{transcript_block}You are extracting a compact benchmark JSON from one trading-education frame.

Return ONLY strict JSON. No markdown fences. No comments. No prose outside JSON. No trailing commas.
Use only the keys shown below.

Task:
- classify `visual_representation_type`
- produce 4-6 full-sentence `visual_facts`
- produce 2-3 short low-inference `trading_relevant_interpretation` items
- include `structural_pattern_visible` as an array of generic pattern names
- include conceptual `level_values` and `stop_values` with exact visible labels when readable

Rules:
- Describe only the chart/diagram/drawing and its text annotations.
- Ignore instructor/person/laptop/background unless they cover or point at the diagram.
- Read titles/headers/label boxes/numeric markers first and copy them exactly as shown.
- If text is Russian/Cyrillic, copy it exactly and do not translate in extraction fields.
- Prefer visible labels over inferred meaning.
- For bars/candles interacting with a level in a teaching diagram, use `abstract_bar_diagram`.
- For level interaction, use `price_action_around_level` in `structural_pattern_visible` when applicable.
- `trading_relevant_interpretation` must be grounded in what is visibly drawn or labeled.
- Avoid calling a level "support/resistance" unless the image text says so.
- Avoid directional claims unless explicitly drawn (e.g., arrows) or labeled.
- Keep strings concise.
- If there is no visible level/stop label, return an empty array for that entity list.
- `material_change` should be true for this frame unless the image is effectively blank or unchanged.

Return this exact shape:
{{
  "frame_timestamp": "{timestamp}",
  "material_change": true,
  "visual_representation_type": "abstract_bar_diagram",
  "current_state": {{
    "visual_facts": ["...", "...", "...", "..."],
    "structural_pattern_visible": ["price_action_around_level"],
    "trading_relevant_interpretation": ["...", "..."]
  }},
  "extracted_entities": {{
    "level_values": [
      {{"label": "<visible label>", "value_description": "conceptual price level"}}
    ],
    "stop_values": [
      {{"label": "<visible label>", "value_description": "area above or below level"}}
    ]
  }}
}}"""


def score_output(out: dict, gold: dict) -> dict[str, bool | str]:
    """Score a normalized output against the gold reference."""
    results: dict[str, bool | str] = {}

    # Representation type
    results["repr_type_correct"] = (
        out.get("visual_representation_type") == gold.get("visual_representation_type")
    )

    # visual_facts density
    facts = (out.get("current_state") or {}).get("visual_facts", [])
    results["visual_facts_count"] = len(facts)
    results["visual_facts_dense"] = len(facts) >= 4

    # trading_relevant_interpretation list shape + density
    interp = (out.get("current_state") or {}).get("trading_relevant_interpretation", [])
    results["interpretation_is_list"] = isinstance(interp, list)
    results["interpretation_count"] = len(interp)
    results["interpretation_dense"] = len(interp) >= 2

    # structural_pattern_visible
    patterns = (out.get("current_state") or {}).get("structural_pattern_visible", [])
    gold_patterns = (gold.get("current_state") or {}).get("structural_pattern_visible", "")
    if isinstance(gold_patterns, str):
        gold_patterns = [gold_patterns]
    results["pattern_match"] = bool(set(patterns) & set(gold_patterns)) if gold_patterns else True

    # level_values non-empty
    level_vals = (out.get("extracted_entities") or {}).get("level_values", [])
    results["level_values_present"] = len(level_vals) >= 1

    # stop_values non-empty
    stop_vals = (out.get("extracted_entities") or {}).get("stop_values", [])
    results["stop_values_present"] = len(stop_vals) >= 1

    # Overall pass
    results["passes"] = all([
        results["repr_type_correct"],
        results["visual_facts_dense"],
        results["interpretation_dense"],
        results["interpretation_is_list"],
        results["pattern_match"],
        results["level_values_present"],
        results["stop_values_present"],
    ])

    return results


def _parse_first_json_object(text: str) -> dict:
    """Extract and parse the first complete JSON object when response has 'Extra data' after it."""
    text = text.strip()
    start = text.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise json.JSONDecodeError("Unclosed JSON object", text, start)


def benchmark_model(
    model: str,
    frame_key: str,
    frame_path: str,
    gold: dict,
    host: str | None = None,
    index: int | None = None,
    total: int | None = None,
) -> dict:
    """Run one frame through a model and score it. Uses streaming client for live progress."""
    prefix = f"  ({index}/{total}) " if index is not None and total is not None else "  "
    print(f"\n{prefix}Model: {model}")
    if not Path(frame_path).exists():
        return {"error": f"Frame not found: {frame_path}", "model": model, "prompt": None, "model_output": None}

    prompt = build_benchmark_prompt(frame_key, gold)
    t0 = time.perf_counter()
    stream_chars = [0]  # mutable so callback can update
    usage_capture: list[dict | None] = [None]

    def on_event(ev: dict) -> None:
        kind = ev.get("kind")
        if kind == "start":
            print(f"    [streaming...]", flush=True)
        elif kind == "chunk":
            delta = ev.get("text_delta") or ""
            if delta:
                stream_chars[0] += len(delta)
                if stream_chars[0] % 200 < len(delta):  # progress every ~200 chars
                    print(f"\r    [streaming... {stream_chars[0]} chars]", end="", flush=True)
        elif kind == "end":
            print(f"\r    [done in {round(time.perf_counter() - t0, 1)}s]", flush=True)
            u = (ev.get("meta") or {}).get("usage")
            if u:
                usage_capture[0] = u
        elif kind == "retry":
            print(f"    [retry {ev.get('attempt', 1)}]", flush=True)

    try:
        if model.startswith("gemini-"):
            from google.genai import types
            with open(frame_path, "rb") as f:
                image_bytes = f.read()
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    ],
                )
            ]
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BenchmarkResponse,
                temperature=0.3,
                max_output_tokens=BENCHMARK_MAX_OUTPUT_TOKENS,
            )
            raw_text = gemini_client.generate_with_retry_stream(
                model=model,
                contents=contents,
                config=config,
                on_event=on_event,
                stage="benchmark",
                frame_key=frame_key,
            ).strip()
        elif model.startswith("mlx-"):
            raw_text = mlx_client.chat_image(
                model,
                prompt,
                frame_path,
                host=host,
                on_event=on_event,
                stage="benchmark",
                frame_key=frame_key,
            )
        else:
            raise ValueError(f"Unsupported model prefix for benchmark: {model}")
    except Exception as e:
        print(f"    [error: {e}]", flush=True)
        return {"error": str(e), "elapsed": round(time.perf_counter() - t0, 2), "model": model, "prompt": prompt, "model_output": None}
    elapsed = round(time.perf_counter() - t0, 2)

    try:
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
        to_parse = (match.group(1).strip() if match else raw_text).strip()
        try:
            raw_json = json.loads(to_parse)
        except json.JSONDecodeError as je:
            if "Extra data" in str(je):
                # Model returned valid JSON then more text; take first JSON object only
                raw_json = _parse_first_json_object(to_parse)
            else:
                raise
    except Exception as e:
        return {"error": f"JSON parse failed: {e}", "elapsed": elapsed, "raw_text": raw_text[:500], "model": model, "prompt": prompt, "model_output": None}

    normalized = _normalize_extraction_output(frame_key, raw_json)
    score = score_output(normalized, gold)
    score["elapsed_s"] = elapsed
    score["model"] = model
    score["model_output"] = normalized  # JSON received from model (normalized), for --output
    score["prompt"] = prompt  # prompt used for this run (prompts vs results)

    # Tokens-per-second metering (reading context = input, generation = output)
    usage = usage_capture[0]
    if usage:
        pt = usage.get("prompt_tokens") or 0
        ot = usage.get("output_tokens") or 0
        ped_ns = usage.get("prompt_eval_duration_ns")
        ed_ns = usage.get("eval_duration_ns")
        score["prompt_tokens"] = pt
        score["output_tokens"] = ot
        if ped_ns is not None and ped_ns > 0 and pt:
            score["input_tokens_per_sec"] = round(pt / (ped_ns / 1e9), 1)
        else:
            score["input_tokens_per_sec"] = None
        if ed_ns is not None and ed_ns > 0 and ot:
            score["output_tokens_per_sec"] = round(ot / (ed_ns / 1e9), 1)
        elif ot and elapsed and elapsed > 0:
            score["output_tokens_per_sec"] = round(ot / elapsed, 1)
        else:
            score["output_tokens_per_sec"] = None
    else:
        score["prompt_tokens"] = None
        score["output_tokens"] = None
        score["input_tokens_per_sec"] = None
        score["output_tokens_per_sec"] = None

    cost_estimate = estimate_gemini_cost(model, score.get("prompt_tokens"), score.get("output_tokens"))
    if cost_estimate is not None:
        score.update(cost_estimate)
    else:
        score["estimated_input_cost_usd"] = None
        score["estimated_output_cost_usd"] = None
        score["estimated_total_cost_usd"] = None
        score["estimated_cost_per_100k_images_usd"] = None

    # Print quick summary (ASCII-safe for Windows console)
    tick = lambda b: "ok" if b else "no"
    in_tps = score.get("input_tokens_per_sec")
    out_tps = score.get("output_tokens_per_sec")
    tps_line = ""
    if in_tps is not None or out_tps is not None:
        tps_parts = []
        if in_tps is not None:
            tps_parts.append(f"in: {in_tps} tok/s")
        if out_tps is not None:
            tps_parts.append(f"out: {out_tps} tok/s")
        tps_line = f"    tokens: {'  '.join(tps_parts)}\n"
    print(tps_line, end="")
    if score.get("estimated_total_cost_usd") is not None:
        print(
            f"    cost:       ${score['estimated_total_cost_usd']:.8f} / image"
            f"  (${score['estimated_cost_per_100k_images_usd']:.2f} / 100k)",
            flush=True,
        )
    print(f"    repr_type:  {tick(score['repr_type_correct'])} ({normalized.get('visual_representation_type')})")
    print(f"    facts:      {score['visual_facts_count']} items {tick(score['visual_facts_dense'])}")
    print(f"    interp:     {score['interpretation_count']} items {tick(score['interpretation_dense'])}")
    print(f"    pattern:    {tick(score['pattern_match'])} {(normalized.get('current_state') or {}).get('structural_pattern_visible')}")
    print(f"    level_vals: {tick(score['level_values_present'])}")
    print(f"    stop_vals:  {tick(score['stop_values_present'])}")
    print(f"    PASSES:     {tick(score['passes'])}  ({elapsed}s)")

    return score


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local VLMs against Gemini gold set")
    parser.add_argument("--host", default=None, help="MLX server host, e.g. http://192.168.1.5:11434")
    parser.add_argument("--models", default="", help="Comma-separated list of models to benchmark")
    parser.add_argument("--gold-dir", default=str(GOLD_DIR), help="Path to gold JSON files")
    parser.add_argument("--ps", action="store_true", help="Use available models from server (mlx_client.list_models)")
    parser.add_argument("--gemini", action="store_true", help="Also benchmark all current general Gemini generateContent models (requires GEMINI_API_KEY)")
    parser.add_argument("--output", "-o", default=None, help="Results JSON path (default: benchmark-reports/benchmark_<timestamp>.json)")
    args = parser.parse_args()

    if args.ps:
        models = mlx_client.list_models(host=args.host)
        if not models:
            print("No models returned from server. Check host and that the MLX service is running.")
            return
        models = [m for m in models if m not in EXCLUDE_MODELS]
        print(f"Using {len(models)} model(s) from server: {', '.join(models)}")
    elif args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        models = [m for m in models if m not in EXCLUDE_MODELS]
    else:
        models = [m for m in CANDIDATE_MODELS if m not in EXCLUDE_MODELS]

    if args.gemini:
        gemini_models = list_gemini_benchmark_models()
        seen = frozenset(models)
        for m in gemini_models:
            if m not in seen:
                models.append(m)
                seen = seen | {m}
        n_local = len([m for m in models if not m.startswith("gemini-")])
        n_gemini = len(models) - n_local
        if n_gemini:
            print(f"Added {n_gemini} Gemini model(s) from live API. Total: {n_local} local + {n_gemini} Gemini.")

    if any(m.startswith("gemini-") for m in models):
        gemini_client.require_gemini_key()

    mlx_models = [m for m in models if m.startswith("mlx-")]
    if mlx_models:
        try:
            health = mlx_client.health_check(host=args.host)
            print(f"MLX server OK: {health.get('service', 'mlx')} (max_parallel={health.get('max_parallel', '?')})")
        except Exception as e:
            print(f"MLX health check failed: {e}")
            print("Fix connectivity or start the MLX service, then re-run.")
            return

    gold_dir = Path(args.gold_dir)

    print("=" * 60)
    print("Local Model Benchmark — Gemini Parity Acceptance Test")
    print("=" * 60)
    print(f"Benchmarking {len(models)} model(s). Frame: {list(GOLD_FRAMES.keys())}. Host: {args.host or 'from env'}")
    print(f"Output cap: {BENCHMARK_MAX_OUTPUT_TOKENS} tokens", flush=True)
    print("Progress: streaming = active; wait for [done] per model.", flush=True)

    out_path = Path(args.output) if args.output else (
        BENCHMARK_REPORTS_DIR / f"benchmark_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []
    _write_report(out_path, all_results)
    print(f"Report path: {out_path}", flush=True)
    total_models = len(models)

    for frame_key, gold_filename in GOLD_FRAMES.items():
        gold_path = gold_dir / gold_filename
        if not gold_path.exists():
            print(f"Gold file not found: {gold_path}")
            continue

        with open(gold_path, "r", encoding="utf-8") as f:
            gold = json.load(f)

        frame_path = FRAME_PATHS.get(frame_key, "")
        resolved = Path(frame_path).resolve() if frame_path else None
        if resolved and not resolved.exists():
            # Fallback: try same path relative to cwd (ROOT may differ when run via uv/cache)
            try:
                rel = resolved.relative_to(ROOT)
                cwd_fallback = Path.cwd() / rel
                if cwd_fallback.exists():
                    resolved = cwd_fallback
            except ValueError:
                pass
        frame_path = str(resolved) if resolved and resolved.exists() else (frame_path or "")
        print(f"\nFrame: {frame_key}  ({frame_path})", flush=True)

        for idx, model in enumerate(models, start=1):
            result = benchmark_model(
                model, frame_key, frame_path, gold, host=args.host, index=idx, total=total_models
            )
            result["frame_key"] = frame_key
            all_results.append(result)
            _write_report(out_path, all_results)

    # Summary table
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in all_results:
        status = "PASS" if r.get("passes") else "FAIL"
        err = f" [error: {r.get('error', '')[:200]}]" if "error" in r else ""
        elapsed = r.get("elapsed_s")
        cost = r.get("estimated_total_cost_usd")
        cost_text = f" ${cost:.8f}" if isinstance(cost, (float, int)) else ""
        print(f"  [{status}] {r.get('model', '?')} frame={r.get('frame_key', '?')} ({elapsed}s){cost_text}{err}")

    passing = [r for r in all_results if r.get("passes")]
    if passing:
        fastest = min(passing, key=lambda r: r.get("elapsed_s", 9999))
        print(f"\nRecommended model: {fastest['model']} (passes + fastest at {fastest['elapsed_s']}s)")
    else:
        print("\nNo model passed all acceptance checks. Consider improving prompts or upgrading model.")

    _write_report(out_path, all_results)
    print(f"\nReport (prompts + model JSONs) written to: {out_path}")


if __name__ == "__main__":
    main()
