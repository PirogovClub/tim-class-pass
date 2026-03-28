"""Tests for shared streaming event contract."""
from helpers.clients.stream_events import emit


def test_emit_invokes_callback_with_event_shape() -> None:
    """emit() must call the callback with provider, stage, kind and optional fields."""
    seen = []

    def on_event(ev):
        seen.append(ev)

    emit(
        on_event,
        provider="openai",
        stage="extract",
        kind="start",
        frame_key="000591",
    )
    assert len(seen) == 1
    assert seen[0]["provider"] == "openai"
    assert seen[0]["stage"] == "extract"
    assert seen[0]["kind"] == "start"
    assert seen[0]["frame_key"] == "000591"
    assert "text_delta" not in seen[0]

    emit(
        on_event,
        provider="gemini",
        stage="gemini_images",
        kind="chunk",
        text_delta='{"x": 1}',
    )
    assert len(seen) == 2
    assert seen[1]["kind"] == "chunk"
    assert seen[1]["text_delta"] == '{"x": 1}'


def test_emit_no_op_when_callback_none() -> None:
    """emit() with None callback must not raise."""
    emit(None, provider="openai", stage="chat", kind="end")
