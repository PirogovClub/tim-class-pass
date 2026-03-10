from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


DIFF_PATTERN = re.compile(r"_diff_([0-9]*\.[0-9]+)")


def _parse_diff_from_name(name: str) -> float:
    match = DIFF_PATTERN.search(name)
    if not match:
        return 0.0
    try:
        return float(match.group(1))
    except ValueError:
        return 0.0


def build_llm_queue(video_id: str, *, threshold: float = 0.14) -> Path:
    video_dir = Path("data") / video_id
    index_path = video_dir / "dense_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing dense index: {index_path}")

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    keys = sorted(index.keys())
    selected: dict[str, dict] = {}

    for idx, key in enumerate(keys):
        rel_path = index.get(key)
        if not rel_path:
            continue
        filename = Path(rel_path).name
        diff = _parse_diff_from_name(filename)
        if diff > threshold:
            selected[key] = {
                "reason": "above_threshold",
                "diff": diff,
                "source": rel_path,
            }
            if idx > 0:
                prev_key = keys[idx - 1]
                if prev_key not in selected:
                    prev_path = index.get(prev_key)
                    selected[prev_key] = {
                        "reason": "previous_of_threshold",
                        "diff": _parse_diff_from_name(Path(prev_path).name) if prev_path else 0.0,
                        "source": prev_path,
                    }

    out_dir = video_dir / "llm_queue"
    out_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for key, info in selected.items():
        rel_path = info.get("source")
        if not rel_path:
            continue
        src = video_dir / rel_path
        if not src.exists():
            continue
        dst = out_dir / src.name
        if dst.exists():
            continue
        shutil.copy2(src, dst)
        copied += 1

    manifest_path = out_dir / "manifest.json"
    manifest = {
        "video_id": video_id,
        "threshold": threshold,
        "total_selected": len(selected),
        "copied": copied,
        "items": dict(sorted(selected.items())),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(
        f"Step 1.6: LLM queue built. Selected: {len(selected)} | copied: {copied} | "
        f"threshold: {threshold} | path: {out_dir}"
    )
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Select frames for LLM processing.")
    parser.add_argument("--video_id", required=True, help="Video ID folder under data/")
    parser.add_argument("--threshold", type=float, default=0.14, help="Diff threshold (default 0.14)")
    args = parser.parse_args()

    build_llm_queue(args.video_id, threshold=args.threshold)


if __name__ == "__main__":
    main()
