from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.component2.knowledge_builder import adapt_chunks, load_chunks_json
from pipeline.component2.llm_processor import materialize_batch_results_for_knowledge_extract
from pipeline.contracts import PipelinePaths
from pipeline.orchestrator.models import make_request_key, slugify_lesson_name
from pipeline.orchestrator.state_store import StateStore
from tests.conftest import LESSON2_DATA
from tests.regression_helpers import (
    assert_cross_file_integrity,
    assert_knowledge_events_clean,
)


@pytest.mark.integration
def test_batch_lesson2_parity_from_existing_debug(tmp_path: Path) -> None:
    lesson_name = "Lesson 2. Levels part 1"
    chunks_path = LESSON2_DATA / "output_intermediate" / f"{lesson_name}.chunks.json"
    knowledge_debug_path = LESSON2_DATA / "output_intermediate" / f"{lesson_name}.knowledge_debug.json"
    knowledge_events_path = LESSON2_DATA / "output_intermediate" / f"{lesson_name}.knowledge_events.json"
    rule_cards_path = LESSON2_DATA / "output_intermediate" / f"{lesson_name}.rule_cards.json"
    evidence_index_path = LESSON2_DATA / "output_intermediate" / f"{lesson_name}.evidence_index.json"

    required = [
        chunks_path,
        knowledge_debug_path,
        knowledge_events_path,
        rule_cards_path,
        evidence_index_path,
    ]
    if any(not path.exists() for path in required):
        pytest.skip("Lesson 2 batch parity inputs are not present in this workspace state")

    raw_chunks = load_chunks_json(chunks_path)
    adapted = adapt_chunks(raw_chunks, lesson_id=lesson_name, lesson_title=None)
    debug_rows = json.loads(knowledge_debug_path.read_text(encoding="utf-8"))
    parsed_rows = [row for row in debug_rows if isinstance(row, dict) and row.get("parsed_extraction")]
    if len(parsed_rows) != len(adapted):
        pytest.skip("Lesson 2 knowledge_debug.json does not contain one parsed_extraction per chunk")

    output_root = tmp_path / "lesson2"
    paths = PipelinePaths(video_root=output_root)
    store = StateStore(tmp_path / "state.db")
    store.ensure_video(video_id=lesson_name, video_root=output_root)
    store.ensure_lesson(
        lesson_id=lesson_name,
        video_id=lesson_name,
        lesson_name=lesson_name,
        lesson_root=output_root,
        vtt_path=LESSON2_DATA / f"{lesson_name}.vtt",
    )
    stage_run = store.create_or_reuse_stage_run(
        lesson_id=lesson_name,
        stage_name="knowledge_extract",
        status="READY",
    )
    lesson_slug = slugify_lesson_name(lesson_name)

    result_lines: list[str] = []
    for chunk, row in zip(adapted, parsed_rows):
        request_key = make_request_key(
            video_id=lesson_name,
            lesson_slug=lesson_slug,
            stage_name="knowledge_extract",
            entity_kind="chunk",
            entity_index=str(chunk.chunk_index),
        )
        store.record_spool_request(
            request_key=request_key,
            stage_run_id=stage_run["stage_run_id"],
            video_id=lesson_name,
            lesson_id=lesson_name,
            stage_name="knowledge_extract",
            entity_kind="chunk",
            entity_index=str(chunk.chunk_index),
            payload_sha256=str(chunk.chunk_index),
            spool_file_path=tmp_path / "lesson2_spool.jsonl",
        )
        result_lines.append(
            json.dumps(
                {
                    "key": request_key,
                    "response": {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(row["parsed_extraction"], ensure_ascii=False),
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                },
                ensure_ascii=False,
            )
        )

    result_path = tmp_path / "lesson2_results.jsonl"
    result_path.write_text("\n".join(result_lines) + "\n", encoding="utf-8")

    collection = materialize_batch_results_for_knowledge_extract(
        result_path,
        adapted,
        lesson_name,
        paths,
        store,
    )

    baseline_payload = json.loads(knowledge_events_path.read_text(encoding="utf-8"))
    baseline_events = baseline_payload["events"]
    batch_events = [event.model_dump(mode="json") for event in collection.events]
    assert len(batch_events) == len(baseline_events)
    assert {event["event_id"] for event in batch_events} == {event["event_id"] for event in baseline_events}
    assert_knowledge_events_clean(batch_events)

    baseline_rules = json.loads(rule_cards_path.read_text(encoding="utf-8"))["rules"]
    baseline_evidence = json.loads(evidence_index_path.read_text(encoding="utf-8"))["evidence_refs"]
    assert_cross_file_integrity(batch_events, baseline_rules, baseline_evidence)
