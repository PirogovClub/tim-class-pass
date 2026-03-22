from __future__ import annotations

import pytest

from pipeline.orchestrator.models import (
    make_request_key,
    parse_request_key,
    slugify_lesson_name,
)


def test_slugify_lesson_name_normalizes_spaces_and_case() -> None:
    assert slugify_lesson_name("Lesson 2. Levels part 1") == "lesson_2_levels_part_1"


def test_make_request_key_round_trips() -> None:
    key = make_request_key(
        video_id="video_1",
        lesson_slug="lesson_2_levels_part_1",
        stage_name="knowledge_extract",
        entity_kind="chunk",
        entity_index="3",
    )
    assert parse_request_key(key) == {
        "video_id": "video_1",
        "lesson_slug": "lesson_2_levels_part_1",
        "stage_name": "knowledge_extract",
        "entity_kind": "chunk",
        "entity_index": "3",
    }


def test_parse_request_key_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError):
        parse_request_key("bad__key")
