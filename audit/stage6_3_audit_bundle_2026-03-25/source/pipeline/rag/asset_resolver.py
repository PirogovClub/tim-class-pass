"""Resolve screenshot / frame asset paths.

Local filesystem for now; swap to S3-style object storage later.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.rag.config import RAGConfig


class AssetResolver:
    def __init__(self, asset_root: Path | None = None, cfg: RAGConfig | None = None) -> None:
        if cfg is not None:
            self._asset_root = cfg.asset_root
        else:
            self._asset_root = asset_root or Path("data")

    def resolve_screenshot(self, lesson_id: str, frame_id: str) -> str | None:
        candidate = self._asset_root / lesson_id / "frames_dense" / f"{frame_id}.jpg"
        if candidate.exists():
            return str(candidate)
        candidate_png = candidate.with_suffix(".png")
        if candidate_png.exists():
            return str(candidate_png)
        return None

    def resolve_lesson_dir(self, lesson_id: str) -> Path | None:
        d = self._asset_root / lesson_id
        return d if d.is_dir() else None

    def resolve_url(self, lesson_id: str, frame_id: str) -> str | None:
        resolved = self.resolve_screenshot(lesson_id, frame_id)
        return resolved if resolved else None
