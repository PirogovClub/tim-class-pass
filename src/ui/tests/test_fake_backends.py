from __future__ import annotations

import json

from ui.testing.fake_provider import FakeProvider
from ui.testing.fake_payloads import fake_batch_result_text_for_request_key


def test_fake_provider_returns_deterministic_json_for_text_schema():
    provider = FakeProvider("fake")

    response = provider.generate_text(
        model="fake-model",
        user_text="hello",
        system_instruction="system",
        response_schema=None,
        stage="fake_component2_reducer",
    )

    assert response.provider == "fake"
    assert "Fake Lesson" in response.text


def test_fake_batch_payload_for_vision_request_is_valid_json():
    payload_text = fake_batch_result_text_for_request_key("video_a__lesson_a__vision__frame__000001")
    parsed = json.loads(payload_text)

    assert parsed["material_change"] is True
    assert parsed["visual_representation_type"] == "text_slide"

