"""Shared FFmpeg subprocess helper (ffmpeg, then uv run ffmpeg fallback)."""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def probe_media_duration_seconds(media_path: str | Path) -> float | None:
    """Return container duration in seconds via ffprobe, or None if unknown."""
    path = str(Path(media_path))
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            d = float(result.stdout.strip())
            if d > 0:
                return d
        except ValueError:
            pass
    cmd_uv = ["uv", "run", "ffprobe"] + cmd[1:]
    result2 = subprocess.run(cmd_uv, capture_output=True, text=True)
    if result2.returncode == 0:
        try:
            d = float(result2.stdout.strip())
            if d > 0:
                return d
        except ValueError:
            pass
    return None

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
_SPEED_RE = re.compile(r"speed=\s*([0-9.]+)x")


def _run_ffmpeg_once_with_progress(
    cmd: list[str],
    on_progress: Callable[[str], None],
    *,
    interval: float,
) -> tuple[int, str]:
    """Run one ffmpeg command; emit throttled progress from parsed stderr. Returns (rc, stderr)."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    chunks: list[bytes] = []
    last_emit = float("-inf")
    last_signature: str | None = None

    def reader() -> None:
        nonlocal last_emit, last_signature
        buf = b""
        assert proc.stderr is not None
        try:
            while True:
                chunk = proc.stderr.read(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                buf += chunk
                if len(buf) > 128_000:
                    buf = buf[-64_000:]
                text = buf.decode("utf-8", errors="replace")
                m = None
                for m in _TIME_RE.finditer(text):
                    pass
                if m is None:
                    continue
                signature = m.group(0)
                if signature == last_signature:
                    continue
                now = time.monotonic()
                if now - last_emit < interval:
                    continue
                last_emit = now
                last_signature = signature
                span = text[max(0, m.start() - 120) : m.end() + 120]
                speed_m = _SPEED_RE.search(span)
                detail = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
                if speed_m:
                    detail += f" @ {speed_m.group(1)}x"
                on_progress(detail)
        finally:
            proc.stderr.close()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    rc = int(proc.wait() or 0)
    t.join(timeout=10.0)
    stderr_text = b"".join(chunks).decode("utf-8", errors="replace")
    return rc, stderr_text


def run_ffmpeg_cmd(
    cmd: list[str],
    *,
    stderr_progress: Callable[[str], None] | None = None,
    stderr_progress_interval: float = 0.45,
) -> bool:
    """Run *cmd* (must start with ``ffmpeg``). Retry with ``uv run ffmpeg`` on failure.

    If *stderr_progress* is set, stderr is streamed and parsed for FFmpeg's ``time=`` / ``speed=``
    stats (works with FFmpeg's carriage-return updates). *stderr_progress* receives short
    human strings like ``01:02:03.45 @ 4.2x`` at most every *stderr_progress_interval* seconds.
    """
    if stderr_progress is None:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            return True
        logger.warning(
            "FFmpeg failed (rc=%d): %s",
            result.returncode,
            result.stderr or "unknown",
        )
        cmd_uv = ["uv", "run", "ffmpeg"] + cmd[1:]
        result2 = subprocess.run(
            cmd_uv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result2.returncode == 0:
            return True
        logger.warning(
            "FFmpeg (uv) failed (rc=%d): %s",
            result2.returncode,
            result2.stderr or "unknown",
        )
        return False

    rc, err = _run_ffmpeg_once_with_progress(
        cmd,
        stderr_progress,
        interval=stderr_progress_interval,
    )
    if rc == 0:
        return True
    logger.warning("FFmpeg failed (rc=%d): %s", rc, err or "unknown")
    cmd_uv = ["uv", "run", "ffmpeg"] + cmd[1:]
    rc2, err2 = _run_ffmpeg_once_with_progress(
        cmd_uv,
        stderr_progress,
        interval=stderr_progress_interval,
    )
    if rc2 == 0:
        return True
    logger.warning("FFmpeg (uv) failed (rc=%d): %s", rc2, err2 or "unknown")
    return False
