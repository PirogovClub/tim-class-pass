from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
GOLDEN_ROOT = Path(__file__).resolve().parent / "golden"


def load_json(path: Path) -> dict | list:
    """Load JSON file; return dict or list."""
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def lesson_minimal_root() -> Path:
    return FIXTURES_ROOT / "lesson_minimal"


@pytest.fixture
def lesson_multi_concept_root() -> Path:
    return FIXTURES_ROOT / "lesson_multi_concept"


@pytest.fixture
def lesson_edge_sparse_root() -> Path:
    return FIXTURES_ROOT / "lesson_edge_sparse"


@pytest.fixture
def temp_video_root(tmp_path: Path) -> Path:
    """Temporary video root for pipeline output layout (PipelinePaths)."""
    root = tmp_path / "video_case"
    root.mkdir(parents=True, exist_ok=True)
    return root


# 12-phase2 Part 6b: fixtures for full Lesson 2 regression (run only when RUN_LESSON2_REGRESSION=1)

LESSON2_DATA = PROJECT_ROOT / "data" / "Lesson 2. Levels part 1"
LESSON2_VTT = LESSON2_DATA / "Lesson 2. Levels part 1.vtt"
LESSON2_VISUALS = LESSON2_DATA / "filtered_visual_events.json"


@pytest.fixture
def lesson2_output_dir(tmp_path: Path) -> Path:
    """Path to output_intermediate for Lesson 2 (12-phase2 6b)."""
    out = tmp_path / "lesson2" / "output_intermediate"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def run_lesson2_pipeline(lesson2_output_dir: Path):
    """Run Component 2 pipeline for Lesson 2; writes to lesson2_output_dir.parent as output-root."""

    def _run() -> None:
        output_root = lesson2_output_dir.parent
        cmd = [
            sys.executable,
            "-m",
            "pipeline.component2.main",
            "--vtt",
            str(LESSON2_VTT),
            "--visuals-json",
            str(LESSON2_VISUALS),
            "--output-root",
            str(output_root),
            "--enable-knowledge-events",
            "--enable-evidence-linking",
            "--enable-rule-cards",
            "--enable-ml-prep",
        ]
        subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))

    return _run
