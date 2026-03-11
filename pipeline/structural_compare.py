from __future__ import annotations

import argparse
import json
import os
import time
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime
from pathlib import Path
from typing import Callable

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
    blur_radius: float,
    artifacts_dir: Path | None,
) -> tuple[str, dict]:
    started = time.perf_counter()
    try:
        comparison = compare_images(
            prev_path,
            cur_path,
            threshold=threshold,
            blur_radius=blur_radius,
            artifacts_dir=artifacts_dir,
        )
    except TypeError:
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


def _format_elapsed(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def run_structural_compare(
    video_id: str,
    *,
    force: bool = False,
    rename_with_diff: bool = True,
    max_workers: int | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> Path:
    started_at = time.perf_counter()

    def _emit(message: str) -> None:
        if progress_callback is not None:
            progress_callback(f"[+{_format_elapsed(time.perf_counter() - started_at)}] {message}")
        else:
            print(message)

    video_dir = Path("data") / video_id
    index_file = video_dir / "dense_index.json"
    out_path = video_dir / "structural_index.json"

    if not index_file.exists():
        raise FileNotFoundError(f"Missing dense index: {index_file}")

    if out_path.exists() and not force:
        _emit(f"Step 1.5: Structural compare skipped (exists): {out_path}")
        return out_path

    cfg = pipeline_config.get_config_for_video(video_id)
    threshold = float(cfg.get("ssim_threshold", 0.95))
    blur_radius = float(cfg.get("compare_blur_radius", 1.5))
    artifacts_dir = video_dir / str(cfg.get("compare_artifacts_dir") or "frames_structural_preprocessed")
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

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
        _emit("Step 1.5: Structural compare found no frames in dense_index.json.")
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

    total_pairs = len(pairs)
    progress_interval = max(1, min(25, max(1, total_pairs // 20))) if total_pairs else 1
    processed_pairs = 0

    def _emit_progress(last_key: str, compare_seconds: float) -> None:
        if total_pairs == 0:
            return
        if processed_pairs == 1 or processed_pairs == total_pairs or processed_pairs % progress_interval == 0:
            _emit(
                "Step 1.5 progress: "
                f"{processed_pairs}/{total_pairs} comparisons complete, "
                f"significant={significant}, unchanged={unchanged}, "
                f"last_key={last_key}, compare_time={compare_seconds:.2f}s."
            )

    _emit(
        "Step 1.5: Starting structural compare "
        f"(frames={len(keys)}, comparisons={total_pairs}, threshold={threshold}, "
        f"blur_radius={blur_radius}, workers={max_workers})."
    )

    if max_workers > 1 and len(pairs) > 1:
        try:
            with ProcessPoolExecutor(max_workers=min(max_workers, len(pairs))) as executor:
                futures = [
                    executor.submit(_compare_pair, key, prev_key, prev_path, cur_path, threshold, blur_radius, artifacts_dir)
                    for key, prev_key, prev_path, cur_path in pairs
                ]
                for future in as_completed(futures):
                    key, data = future.result()
                    results[key] = data
                    if data["is_significant"]:
                        significant += 1
                    else:
                        unchanged += 1
                    processed_pairs += 1
                    _emit_progress(key, float(data.get("compare_seconds", 0.0)))
        except BrokenProcessPool:
            _emit("Step 1.5: Process pool failed; retrying structural compare sequentially.")
            first_key = keys[0]
            results = {
                first_key: {
                    "previous_key": None,
                    "score": 1.0,
                    "is_significant": True,
                    "threshold": threshold,
                    "metadata": {},
                    "compare_seconds": 0.0,
                    "reason": "first_frame",
                }
            }
            significant = 1
            unchanged = 0
            processed_pairs = 0
            for key, prev_key, prev_path, cur_path in pairs:
                _, data = _compare_pair(key, prev_key, prev_path, cur_path, threshold, blur_radius, artifacts_dir)
                results[key] = data
                if data["is_significant"]:
                    significant += 1
                else:
                    unchanged += 1
                processed_pairs += 1
                _emit_progress(key, float(data.get("compare_seconds", 0.0)))
    else:
        for key, prev_key, prev_path, cur_path in pairs:
            _, data = _compare_pair(key, prev_key, prev_path, cur_path, threshold, blur_radius, artifacts_dir)
            results[key] = data
            if data["is_significant"]:
                significant += 1
            else:
                unchanged += 1
            processed_pairs += 1
            _emit_progress(key, float(data.get("compare_seconds", 0.0)))

    renamed = 0
    if rename_with_diff:
        renamed = _rename_frames_with_diff(video_dir, index, results)
        if renamed:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    _emit(
        f"Step 1.5: Structural compare complete. Frames: {len(keys)} | "
        f"significant: {significant} | unchanged: {unchanged} | threshold: {threshold} | blur_radius: {blur_radius}"
    )
    if rename_with_diff:
        _emit(f"Step 1.5: Renamed {renamed} frames with _diff_<value>.")
    _emit(f"Step 1.5: Structural comparison artifacts written to: {artifacts_dir}")
    _emit(f"Step 1.5: Structural index written to: {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute structural diffs between dense frames.")
    parser.add_argument("--video_id", required=True, help="Video ID folder under data/")
    parser.add_argument("--force", action="store_true", help="Recompute even if structural_index.json exists")
    parser.add_argument("--workers", type=int, default=None, help="Max workers for comparisons (cap 8 recommended)")
    args = parser.parse_args()

    def _timestamped_echo(message: str) -> None:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - {message}")

    run_structural_compare(
        args.video_id,
        force=args.force,
        max_workers=args.workers,
        progress_callback=_timestamped_echo,
    )


if __name__ == "__main__":
    main()
