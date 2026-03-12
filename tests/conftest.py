from __future__ import annotations

import json
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
