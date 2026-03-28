"""Tests for visual compaction policy (Task 8)."""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    assert_no_raw_visual_blob_leak,
    build_evidence_provenance_payload,
    build_screenshot_candidate_paths,
    build_raw_visual_event_id,
    detect_visual_spam_lines,
    from_pipeline_config,
    strip_raw_visual_blobs_from_metadata,
    summarize_evidence_for_rag_markdown,
    summarize_evidence_for_review_markdown,
    summarize_evidence_for_rule_card,
    summarize_visual_event_for_extraction,
    summarize_visual_events_for_extraction,
    trim_rule_card_visual_refs,
    validate_markdown_visual_compaction,
)


def test_raw_richness_preserved() -> None:
    """Input dict is not mutated by summarize_visual_event_for_extraction."""
    cfg = VisualCompactionConfig()
    event = {
        "frame_key": "000042",
        "timestamp_seconds": 42.0,
        "current_state": {"visible_annotations": ["support level"]},
        "visual_representation_type": "annotated_chart",
        "change_summary": "Level marked.",
    }
    original = copy.deepcopy(event)
    summarize_visual_event_for_extraction(event, cfg)
    assert event == original
    assert event.keys() == original.keys()
    assert event["frame_key"] == original["frame_key"]
    assert event["current_state"] == original["current_state"]


def test_extraction_summaries_compact() -> None:
    """Summaries are capped, no low-value words, length bounded."""
    cfg = VisualCompactionConfig()
    events = [
        {"frame_key": "001", "visual_representation_type": "chart", "change_summary": "Price trend up."},
        {"frame_key": "002", "visual_representation_type": "toolbar", "change_summary": "Toolbar visible."},
        {"frame_key": "003", "visual_representation_type": "panel", "change_summary": "Panel layout."},
        {"frame_key": "004", "visual_representation_type": "annotated_chart", "change_summary": "Support level marked."},
        {"frame_key": "005", "visual_representation_type": "chart", "change_summary": "Resistance line."},
        {"frame_key": "006", "visual_representation_type": "diagram", "change_summary": "Key level highlighted."},
        {"frame_key": "007", "visual_representation_type": "chart", "change_summary": "Volume spike."},
        {"frame_key": "008", "visual_representation_type": "chart", "change_summary": "Breakout pattern."},
    ]
    result = summarize_visual_events_for_extraction(events, cfg)
    assert len(result) <= 5
    for s in result:
        assert "toolbar" not in s.lower()
        assert "panel" not in s.lower()
    margin = 5
    for s in result:
        assert len(s) <= 240 + margin


def test_evidence_provenance_preserved(tmp_path: Path) -> None:
    """frame_ids capped, raw_visual_event_ids match ve_raw_<key>; screenshot paths only existing and capped."""
    cfg = VisualCompactionConfig()
    frame_keys = [f"f{i:03d}" for i in range(20)]
    candidate = SimpleNamespace(frame_keys=frame_keys, visual_events=[SimpleNamespace(change_summary="x")])
    payload = build_evidence_provenance_payload(candidate, video_root=None, cfg=cfg)
    assert len(payload["frame_ids"]) <= 12
    assert payload["raw_visual_event_ids"] == [build_raw_visual_event_id(k) for k in payload["frame_ids"]]
    assert all(s.startswith("ve_raw_") for s in payload["raw_visual_event_ids"])
    # Screenshot paths: two existing files under frames_dense; only existing returned, count capped
    frames_dense = tmp_path / "frames_dense"
    frames_dense.mkdir()
    (frames_dense / "frame_f000.jpg").write_text("x")
    (frames_dense / "frame_f001.png").write_text("x")
    candidate2 = SimpleNamespace(frame_keys=["f000", "f001"], visual_events=[])
    payload2 = build_evidence_provenance_payload(candidate2, video_root=tmp_path, cfg=cfg)
    assert len(payload2["screenshot_paths"]) <= 4
    for p in payload2["screenshot_paths"]:
        assert Path(p).exists()


def test_rule_card_summary_compact() -> None:
    """Rule card summary is single string, length bounded; trim_rule_card_visual_refs caps refs."""
    cfg = VisualCompactionConfig()
    refs = [
        SimpleNamespace(compact_visual_summary="Support level marked on chart."),
        SimpleNamespace(compact_visual_summary="Resistance line drawn."),
        SimpleNamespace(compact_visual_summary="Volume spike visible."),
        SimpleNamespace(compact_visual_summary="Breakout pattern."),
    ]
    result = summarize_evidence_for_rule_card(refs, cfg)
    assert result is None or isinstance(result, str)
    if result:
        assert len(result) <= 180 + 5
    trimmed = trim_rule_card_visual_refs(["id1", "id2", "id3", "id4"], max_refs=3)
    assert len(trimmed) == 3
    assert trimmed == ["id1", "id2", "id3"]


def test_review_vs_rag_bullets() -> None:
    """Review has at most 2 items, RAG at most 1."""
    cfg = VisualCompactionConfig()
    refs = [
        SimpleNamespace(compact_visual_summary="First evidence summary here."),
        SimpleNamespace(compact_visual_summary="Second evidence summary."),
        SimpleNamespace(compact_visual_summary="Third evidence summary."),
    ]
    review = summarize_evidence_for_review_markdown(refs, cfg)
    rag = summarize_evidence_for_rag_markdown(refs, cfg)
    assert len(review) <= 2
    assert len(rag) <= 1


def test_forbidden_keys_stripped() -> None:
    """strip_raw_visual_blobs_from_metadata removes current_state and visual_facts, keeps chunk_index."""
    metadata = {"chunk_index": 1, "current_state": {"x": 1}, "visual_facts": []}
    out = strip_raw_visual_blobs_from_metadata(metadata)
    assert "chunk_index" in out
    assert out["chunk_index"] == 1
    assert "current_state" not in out
    assert "visual_facts" not in out


def test_assert_no_raw_visual_blob_leak_raises() -> None:
    """assert_no_raw_visual_blob_leak raises on forbidden keys, passes otherwise."""
    with pytest.raises(ValueError):
        assert_no_raw_visual_blob_leak({"current_state": {}})
    assert_no_raw_visual_blob_leak({"chunk_index": 1})


def test_detect_visual_spam() -> None:
    """Repeated or frame-by-frame lines are flagged."""
    lines = ["Chart slightly moves.", "Chart slightly moves.", "Next frame shows price."]
    flagged = detect_visual_spam_lines(lines)
    assert len(flagged) >= 1
    markdown = "\n".join(lines)
    flagged_md = validate_markdown_visual_compaction(markdown)
    assert len(flagged_md) >= 1


def test_screenshot_candidates_only_existing(tmp_path: Path) -> None:
    """Only existing files returned; len <= 4. Nonexistent frame_key yields empty or only existing."""
    cfg = VisualCompactionConfig()
    frames_dense = tmp_path / "frames_dense"
    frames_dense.mkdir(parents=True)
    (frames_dense / "frame_abc.jpg").write_text("x")
    result = build_screenshot_candidate_paths(tmp_path, "abc", cfg)
    assert any("frame_abc" in p and p.endswith(".jpg") for p in result)
    assert len(result) <= 4
    result_nonexistent = build_screenshot_candidate_paths(tmp_path, "nonexistent", cfg)
    assert all(Path(p).exists() for p in result_nonexistent)
    assert len(result_nonexistent) <= 4


def test_from_pipeline_config() -> None:
    """from_pipeline_config({}) gives defaults; overrides applied from dict."""
    default_cfg = from_pipeline_config({})
    assert default_cfg.max_visual_summaries_for_extract == 5
    assert default_cfg.max_visual_bullets_rag == 1
    custom = from_pipeline_config({
        "visual_extract_max_summaries": 3,
        "visual_rag_max_bullets": 0,
    })
    assert custom.max_visual_summaries_for_extract == 3
    assert custom.max_visual_bullets_rag == 0
