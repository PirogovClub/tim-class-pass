"""Atomic file writes and export manifest builder for the pipeline."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text to path atomically (temp file + os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        delete=False,
        dir=str(path.parent),
        newline="\n",
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def atomic_write_json(path: Path, payload: dict | list, encoding: str = "utf-8") -> None:
    """Write JSON to path atomically."""
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    atomic_write_text(path, text, encoding=encoding)


def write_text_file(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Convenience wrapper for atomic_write_text."""
    atomic_write_text(path, text, encoding=encoding)


def write_json_file(path: Path, payload: dict | list, encoding: str = "utf-8") -> None:
    """Convenience wrapper for atomic_write_json."""
    atomic_write_json(path, payload, encoding=encoding)


def write_artifact_manifest(path: Path, payload: dict[str, Any], encoding: str = "utf-8") -> None:
    """Write artifact manifest JSON atomically."""
    atomic_write_json(path, payload, encoding=encoding)


def build_export_manifest(
    *,
    lesson_id: str,
    video_root: Path,
    artifact_paths: dict[str, Path],
    flags: dict[str, bool],
) -> dict[str, Any]:
    """Build export manifest with only existing artifacts."""
    existing_artifacts = {
        name: str(path)
        for name, path in artifact_paths.items()
        if path.exists()
    }
    return {
        "lesson_id": lesson_id,
        "video_root": str(video_root),
        "artifacts": existing_artifacts,
        "flags": flags,
    }
