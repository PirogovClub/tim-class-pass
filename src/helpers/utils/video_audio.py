"""Extract audio from video files via FFmpeg (AAC .m4a)."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from helpers.ffmpeg_cmd import probe_media_duration_seconds, run_ffmpeg_cmd

logger = logging.getLogger(__name__)


def _parse_ffmpeg_progress_detail(detail: str) -> tuple[float | None, float | None]:
    """Parse ``HH:MM:SS.xx @ Nx`` from :func:`run_ffmpeg_cmd` stderr progress."""
    if " @ " not in detail:
        return None, None
    left, right = detail.rsplit(" @ ", 1)
    right = right.strip()
    if not right.endswith("x"):
        return None, None
    try:
        speed = float(right[:-1].strip())
    except ValueError:
        return None, None
    parts = left.strip().split(":")
    if len(parts) != 3:
        return None, None
    try:
        h, m, sec_s = int(parts[0]), int(parts[1]), float(parts[2])
        current = h * 3600 + m * 60 + sec_s
    except ValueError:
        return None, None
    return current, speed


def _format_eta_compact(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        m, sec = s // 60, s % 60
        return f"{m}m {sec}s" if sec else f"{m}m"
    h, rest = s // 3600, s % 3600
    m, sec = rest // 60, rest % 60
    bits: list[str] = [f"{h}h"]
    if m:
        bits.append(f"{m}m")
    if sec:
        bits.append(f"{sec}s")
    return " ".join(bits)


def _append_eta_to_progress_detail(detail: str, duration_sec: float) -> str:
    """Append ``ETA ~…`` when *duration_sec* and progress *detail* allow it."""
    if duration_sec <= 0:
        return detail
    current, speed = _parse_ffmpeg_progress_detail(detail)
    if current is None or speed is None or speed <= 0:
        return detail
    remaining = duration_sec - current
    if remaining <= 0:
        return f"{detail}  (finishing…)"
    eta_sec = remaining / speed
    return f"{detail}  ETA ~{_format_eta_compact(eta_sec)}"


def _encoding_progress_with_eta(
    inner: Callable[[str], None],
    duration_sec: float,
) -> Callable[[str], None]:
    def wrapper(detail: str) -> None:
        inner(_append_eta_to_progress_detail(detail, duration_sec))

    return wrapper

VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mkv", ".mov", ".webm", ".avi"})


class AudioExtractionError(RuntimeError):
    """FFmpeg failed to extract audio."""


@dataclass(frozen=True)
class ExtractionReport:
    source: Path
    output: Path
    ok: bool
    error: str | None = None


def extract_audio(
    video_path: Path,
    output_path: Path,
    *,
    overwrite: bool = False,
    encoding_progress: Callable[[str], None] | None = None,
    encoding_progress_interval: float = 0.45,
) -> None:
    video_path = Path(video_path).resolve()
    output_path = Path(output_path)
    if not video_path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output exists (use overwrite=True): {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",
        "-map",
        "0:a:0",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
    ]
    if overwrite:
        cmd.append("-y")
    cmd.append(str(output_path))

    stderr_cb: Callable[[str], None] | None = encoding_progress
    if encoding_progress is not None:
        duration_sec = probe_media_duration_seconds(video_path)
        if duration_sec is not None:
            stderr_cb = _encoding_progress_with_eta(encoding_progress, duration_sec)

    ok = run_ffmpeg_cmd(
        cmd,
        stderr_progress=stderr_cb,
        stderr_progress_interval=encoding_progress_interval,
    )
    if not ok:
        raise AudioExtractionError(f"FFmpeg failed for {video_path}")


def extract_audio_from_folder(
    input_dir: Path,
    output_dir: Path | None = None,
    *,
    extensions: frozenset[str] = VIDEO_EXTENSIONS,
    recursive: bool = False,
    overwrite: bool = False,
    progress_callback: Callable[[Mapping[str, Any]], None] | None = None,
    max_workers: int | None = None,
) -> list[ExtractionReport]:
    """Walk *input_dir* for videos and extract audio.

    When more than one video is found, extractions run in parallel using up to
    ``min(len(videos), max(1, (os.cpu_count() or 2) // 2))`` workers by default
    (same idea as the main pipeline’s Step 1 worker cap). Pass ``max_workers=1``
    to force serial processing.

    If *progress_callback* is set, it receives dict events (do not mutate):

    - ``{"event": "batch_start", "total": int, "parallel_workers": int}``
    - ``{"event": "file_start", "index": int, "total": int, "source": Path, "output": Path}``
    - ``{"event": "encode_progress", "index": int, "total": int, "source": Path, "message": str}``
      — *message* may include ``ETA ~…`` when ffprobe reports a duration.
    - ``{"event": "file_end", "index": int, "total": int, "source": Path, "output": Path,
      "ok": bool, "error": str | None}``
    """
    if max_workers is not None and max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    input_dir = Path(input_dir).resolve()
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {input_dir}")
    if output_dir is None:
        output_dir = input_dir / "audio"
    else:
        output_dir = Path(output_dir).resolve()

    progress_lock = threading.Lock()

    def _emit(payload: dict[str, Any]) -> None:
        if progress_callback is None:
            return
        with progress_lock:
            progress_callback(payload)

    pattern = "**/*" if recursive else "*"
    videos = sorted(
        p
        for p in input_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() in extensions
    )
    total = len(videos)

    cores = os.cpu_count() or 2
    default_cap = max(1, cores // 2)
    if total <= 1:
        pool_size = 1
        use_pool = False
    elif max_workers is None:
        pool_size = min(total, default_cap)
        use_pool = pool_size > 1
    else:
        pool_size = min(total, max_workers)
        use_pool = pool_size > 1

    _emit(
        {
            "event": "batch_start",
            "total": total,
            "parallel_workers": pool_size,
        },
    )

    def _process_one(index: int, video_path: Path) -> ExtractionReport:
        rel = video_path.relative_to(input_dir)
        out_path = output_dir / rel.with_suffix(".m4a")
        _emit(
            {
                "event": "file_start",
                "index": index,
                "total": total,
                "source": video_path,
                "output": out_path,
            },
        )

        def _encode_progress(msg: str) -> None:
            _emit(
                {
                    "event": "encode_progress",
                    "index": index,
                    "total": total,
                    "source": video_path,
                    "message": msg,
                },
            )

        try:
            extract_audio(
                video_path,
                out_path,
                overwrite=overwrite,
                encoding_progress=_encode_progress if progress_callback else None,
            )
            logger.info("Extracted: %s -> %s", video_path.name, out_path)
            _emit(
                {
                    "event": "file_end",
                    "index": index,
                    "total": total,
                    "source": video_path,
                    "output": out_path,
                    "ok": True,
                    "error": None,
                },
            )
            return ExtractionReport(source=video_path, output=out_path, ok=True)
        except Exception as exc:
            logger.warning("Failed: %s -- %s", video_path.name, exc)
            _emit(
                {
                    "event": "file_end",
                    "index": index,
                    "total": total,
                    "source": video_path,
                    "output": out_path,
                    "ok": False,
                    "error": str(exc),
                },
            )
            return ExtractionReport(
                source=video_path,
                output=out_path,
                ok=False,
                error=str(exc),
            )

    if not use_pool:
        reports = [_process_one(i, vp) for i, vp in enumerate(videos, start=1)]
    else:
        with ThreadPoolExecutor(max_workers=pool_size) as pool:
            futures = [
                pool.submit(_process_one, i, vp)
                for i, vp in enumerate(videos, start=1)
            ]
            reports = [f.result() for f in futures]

    return reports
