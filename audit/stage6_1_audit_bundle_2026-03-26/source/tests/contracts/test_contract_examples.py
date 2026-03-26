from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.contracts.contract_models import REQUIRED_ARTIFACT_FILENAMES
from pipeline.contracts.corpus_validator import validate_intermediate_dir

from tests.contracts.conftest import materialize_lesson_corpus


@pytest.mark.parametrize(
    "name",
    ["lesson_minimal", "lesson_multi_concept"],
)
def test_fixture_lesson_conforms_v1(tmp_path: Path, name: str) -> None:
    root = materialize_lesson_corpus(tmp_path, name)
    inter = root / name / "output_intermediate"
    out = validate_intermediate_dir(inter, name, strict=True)
    assert out.passed, out.errors


def test_markdown_not_in_required_primary_set() -> None:
    names = {Path(p).name for p in REQUIRED_ARTIFACT_FILENAMES}
    assert "review_markdown.md" not in names
    assert "rag_ready.md" not in names
