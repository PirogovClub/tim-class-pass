from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from helpers import config as pipeline_config
from helpers.utils.compare import compare_images


def _base_stem(stem: str) -> str:
    if stem.endswith("_same_as_before"):
        stem = stem[: -len("_same_as_before")]
    if "_diff_" in stem:
        stem = stem.split("_diff_")[0]
    return stem


def _rename_frames_with_diff(
    video_dir: Path,
    index: dict[str, str],
    results: dict[str, dict],
) -> int:
    renamed = 0
    for key, info in results.items():
        rel_path = index.get(key)
        if not rel_path:
            continue
        path = video_dir / rel_path
        if not path.exists():
            continue
        score = info.get("score")
        diff = 1.0 - float(score) if score is not None else None
        diff_tag = f"{diff:.4f}" if diff is not None else "unknown"
        base = _base_stem(path.stem)
        new_path = path.with_name(f"{base}_diff_{diff_tag}{path.suffix}")
        if path == new_path:
            index[key] = new_path.relative_to(video_dir).as_posix()
            continue
        if new_path.exists():
            index[key] = new_path.relative_to(video_dir).as_posix()
            continue
        path.rename(new_path)
        index[key] = new_path.relative_to(video_dir).as_posix()
        renamed += 1
    return renamed


def _compare_pair(
    current_key: str,
    previous_key: str,
    prev_path: Path,
    cur_path: Path,
    threshold: float,
) -> tuple[str, dict]:
    started = time.perf_counter()
    comparison = compare_images(prev_path, cur_path, threshold=threshold)
    compare_seconds = round(time.perf_counter() - started, 4)
    return (
        current_key,
        {
            "previous_key": previous_key,
            "score": comparison.score,
            "is_significant": comparison.is_significant,
            "threshold": comparison.threshold,
            "metadata": comparison.metadata,
            "compare_seconds": compare_seconds,
        },
    )


def run_structural_compare(
    video_id: str,
    *,
    force: bool = False,
    rename_with_diff: bool = True,
    max_workers: int | None = None,
) -> Path:
    video_dir = Path("data") / video_id
    index_file = video_dir / "dense_index.json"
    out_path = video_dir / "structural_index.json"

    if not index_file.exists():
        raise FileNotFoundError(f"Missing dense index: {index_file}")

    if out_path.exists() and not force:
        print(f"Step 1.5: Structural compare skipped (exists): {out_path}")
        return out_path

    cfg = pipeline_config.get_config_for_video(video_id)
    threshold = float(cfg.get("ssim_threshold", 0.95))

    with open(index_file, "r", encoding="utf-8") as f:
        index = json.load(f)

    keys = sorted(index.keys())
    results: dict[str, dict] = {}
    prev_key: str | None = None
    significant = 0
    unchanged = 0

    max_workers = int(max_workers) if max_workers is not None else 1
    if max_workers < 1:
        max_workers = 1
    if max_workers > 8:
        max_workers = 8

    if not keys:
        return out_path

    results[keys[0]] = {
        "previous_key": None,
        "score": 1.0,
        "is_significant": True,
        "threshold": threshold,
        "metadata": {},
        "compare_seconds": 0.0,
        "reason": "first_frame",
    }
    significant += 1

    pairs = []
    for i in range(1, len(keys)):
        prev_key = keys[i - 1]
        key = keys[i]
        prev_path = video_dir / index[prev_key]
        cur_path = video_dir / index[key]
        pairs.append((key, prev_key, prev_path, cur_path))

    if max_workers > 1 and len(pairs) > 1:
        with ProcessPoolExecutor(max_workers=min(max_workers, len(pairs))) as executor:
            futures = [
                executor.submit(_compare_pair, key, prev_key, prev_path, cur_path, threshold)
                for key, prev_key, prev_path, cur_path in pairs
            ]
            for future in as_completed(futures):
                key, data = future.result()
                results[key] = data
                if data["is_significant"]:
                    significant += 1
                else:
                    unchanged += 1
    else:
        for key, prev_key, prev_path, cur_path in pairs:
            _, data = _compare_pair(key, prev_key, prev_path, cur_path, threshold)
            results[key] = data
            if data["is_significant"]:
                significant += 1
            else:
                unchanged += 1

    renamed = 0
    if rename_with_diff:
        renamed = _rename_frames_with_diff(video_dir, index, results)
        if renamed:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(
        f"Step 1.5: Structural compare complete. Frames: {len(keys)} | "
        f"significant: {significant} | unchanged: {unchanged} | threshold: {threshold}"
    )
    if rename_with_diff:
        print(f"Step 1.5: Renamed {renamed} frames with _diff_<value>.")
    print(f"Step 1.5: Structural index written to: {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute structural diffs between dense frames.")
    parser.add_argument("--video_id", required=True, help="Video ID folder under data/")
    parser.add_argument("--force", action="store_true", help="Recompute even if structural_index.json exists")
    parser.add_argument("--workers", type=int, default=None, help="Max workers for comparisons (cap 8 recommended)")
    args = parser.parse_args()

    run_structural_compare(args.video_id, force=args.force, max_workers=args.workers)


if __name__ == "__main__":
    main()
