"""Unit tests for timestamp confidence grading (12-phase2, brief Part 1)."""

from pipeline.component2.knowledge_builder import compute_timestamp_confidence


def test_line_confidence_for_compact_dense_span():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=12,
        transcript_anchors=["support", "resistance"],
        anchor_density=2 / 3,
    )
    assert result == "line"


def test_span_confidence_when_span_width_is_four():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=13,
        transcript_anchors=["support", "resistance"],
        anchor_density=0.50,
    )
    assert result == "span"


def test_span_confidence_when_density_is_too_low_for_line():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=12,
        transcript_anchors=["support"],
        anchor_density=1 / 3,
    )
    assert result == "span"


def test_chunk_confidence_when_line_bounds_missing():
    result = compute_timestamp_confidence(
        source_line_start=None,
        source_line_end=None,
        transcript_anchors=["support"],
        anchor_density=1.0,
    )
    assert result == "chunk"


def test_chunk_confidence_when_no_anchors():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=11,
        transcript_anchors=[],
        anchor_density=0.0,
    )
    assert result == "chunk"
