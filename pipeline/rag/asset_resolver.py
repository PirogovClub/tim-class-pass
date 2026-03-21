"""Resolve screenshot / frame asset paths.

Local filesystem for now; swap to S3-style object storage later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class AssetResolver:
    def __init__(self, data_root: Path = Path("data")) -> None:
        self._data_root = data_root

    def resolve_screenshot(self, lesson_id: str, frame_id: str) -> str | None:
        candidate = self._data_root / lesson_id / "frames_dense" / f"{frame_id}.jpg"
        if candidate.exists():
            return str(candidate)
        candidate_png = candidate.with_suffix(".png")
        if candidate_png.exists():
            return str(candidate_png)
        return None

    def resolve_lesson_dir(self, lesson_id: str) -> Path | None:
        d = self._data_root / lesson_id
        return d if d.is_dir() else None
