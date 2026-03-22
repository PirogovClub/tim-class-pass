from __future__ import annotations

import json
from pathlib import Path

from pipeline.component2.knowledge_builder import AdaptedChunk, ChunkExtractionResult, ExtractedStatement
from pipeline.component2.llm_processor import (
    MarkdownRenderResult,
    emit_batch_spool_for_knowledge_extract,
    emit_batch_spool_for_markdown_render,
    materialize_batch_results_for_knowledge_extract,
    materialize_batch_results_for_markdown_render,
)
from pipeline.contracts import PipelinePaths
from pipeline.orchestrator.state_store import StateStore
from pipeline.schemas import EvidenceRef, RuleCard


def _seed_store(tmp_path: Path) -> tuple[StateStore, PipelinePaths]:
    store = StateStore(tmp_path / "state.db")
    video_root = tmp_path / "lesson"
    video_root.mkdir(parents=True, exist_ok=True)
    store.ensure_video(video_id="video1", video_root=video_root)
    store.ensure_lesson(
        lesson_id="video1::lesson1",
        video_id="video1",
        lesson_name="lesson1",
        lesson_root=video_root,
        vtt_path=video_root / "lesson1.vtt",
    )
    return store, PipelinePaths(video_root=video_root)


def test_knowledge_extract_batch_emit_and_materialize(tmp_path: Path) -> None:
    store, paths = _seed_store(tmp_path)
    chunk = AdaptedChunk(
        chunk_index=0,
        lesson_id="lesson1",
        lesson_title=None,
        section=None,
        subsection=None,
        start_time_seconds=1.0,
        end_time_seconds=5.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 5.0, "text": "Цена реагирует от уровня."}
        ],
        transcript_text="Цена реагирует от уровня.",
        visual_events=[],
    )
    spool_path = emit_batch_spool_for_knowledge_extract(
        chunks=[chunk],
        lesson_id="video1::lesson1",
        video_id="video1",
        paths=paths,
        state_store=store,
    )
    rows = [json.loads(line) for line in spool_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1

    parsed = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(
                text="Реакция от уровня подтверждает значимость уровня.",
                concept="уровень",
                source_line_indices=[0],
                source_quote="Цена реагирует от уровня.",
            )
        ]
    )
    result_path = tmp_path / "knowledge_results.jsonl"
    result_path.write_text(
        json.dumps(
            {
                "key": rows[0]["key"],
                "response": {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": parsed.model_dump_json()}],
                            }
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    collection = materialize_batch_results_for_knowledge_extract(
        result_path,
        [chunk],
        "video1::lesson1",
        paths,
        store,
    )

    assert collection.events
    assert paths.knowledge_events_path("lesson1").exists()
    assert paths.knowledge_debug_path("lesson1").exists()


def test_markdown_render_batch_emit_and_materialize(tmp_path: Path) -> None:
    store, paths = _seed_store(tmp_path)
    spool_path = emit_batch_spool_for_markdown_render(
        lesson_id="video1::lesson1",
        rule_cards=[
            RuleCard(
                lesson_id="lesson1",
                rule_id="r1",
                concept="уровни",
                rule_text="Покупка от уровня после подтверждения.",
            )
        ],
        evidence_refs=[
            EvidenceRef(
                lesson_id="lesson1",
                evidence_id="e1",
                compact_visual_summary="Скрин с тестом уровня.",
            )
        ],
        paths=paths,
        state_store=store,
        render_mode="review",
        video_id="video1",
    )
    rows = [json.loads(line) for line in spool_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = MarkdownRenderResult(markdown="# Review\n\n- Rule", metadata_tags=["tag1"])
    result_path = tmp_path / "render_results.jsonl"
    result_path.write_text(
        json.dumps(
            {
                "key": rows[0]["key"],
                "response": {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": result.model_dump_json()}],
                            }
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rendered = materialize_batch_results_for_markdown_render(
        result_path,
        "video1::lesson1",
        paths,
        store,
    )

    assert rendered.markdown.startswith("# Review")
    assert paths.review_markdown_path("lesson1").exists()
    assert paths.review_render_debug_path("lesson1").exists()
