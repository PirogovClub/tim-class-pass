"""
Write the exact JSON payload the benchmark sends to the MLX server (vision_ocr / vision_strategy).
Use the output path with: curl -X POST http://HOST:11434/api/v1/chat -H "Content-Type: application/json" -d @payload.json
"""
from pathlib import Path
import sys
import json
import base64

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from helpers.benchmarking.benchmark_models import (
    build_benchmark_prompt,
    GOLD_DIR,
    FRAME_PATHS,
    GOLD_FRAMES,
)


def main() -> None:
    frame_key = "000591"
    gold_path = GOLD_DIR / GOLD_FRAMES[frame_key]
    with open(gold_path, "r", encoding="utf-8") as f:
        gold = json.load(f)
    prompt = build_benchmark_prompt(frame_key, gold)
    frame_path = Path(FRAME_PATHS[frame_key])
    image_b64 = base64.b64encode(frame_path.read_bytes()).decode("ascii")

    for task in ("vision_ocr", "vision_strategy"):
        payload = {"task": task, "prompt": prompt, "image_base64": image_b64}
        out_path = ROOT / f"benchmark-reports/payload_{task}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Written {out_path} ({len(image_b64)} chars base64)")
    print()
    base = "http://192.168.51.252:11434"
    print("# Test on server (vision_ocr):")
    print(f'curl -X POST "{base}/api/v1/chat" -H "Content-Type: application/json" -d @benchmark-reports/payload_vision_ocr.json')
    print()
    print("# Test on server (vision_strategy):")
    print(f'curl -X POST "{base}/api/v1/chat" -H "Content-Type: application/json" -d @benchmark-reports/payload_vision_strategy.json')


if __name__ == "__main__":
    main()
