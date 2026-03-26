"""summary_ru is aligned with summary_language in exporters (Task 18 / evidence_linker)."""

from __future__ import annotations

from pipeline.component2.evidence_linker import detect_summary_language
from pipeline.contracts.corpus_validator import validate_intermediate_dir

from tests.contracts.conftest import materialize_lesson_corpus


def test_evidence_linker_sets_summary_ru_only_for_ru() -> None:
    en = "Chart shows stop placement."
    assert detect_summary_language(en) == "en"
    ru = "График показывает стоп."
    assert detect_summary_language(ru) == "ru"


def test_fixture_evidence_has_no_en_summary_with_populated_summary_ru(tmp_path: Path) -> None:
    """Contract fixtures: no summary_language=en with non-empty summary_ru."""
    root = materialize_lesson_corpus(tmp_path, "lesson_minimal")
    inter = root / "lesson_minimal" / "output_intermediate"
    out = validate_intermediate_dir(inter, "lesson_minimal", strict=True)
    assert out.passed
    assert not any(e["category"] == "summary_ru" for e in out.errors)
