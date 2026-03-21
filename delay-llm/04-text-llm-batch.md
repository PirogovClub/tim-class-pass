# Phase 6 -- Batch Spool + Materialize for Component 2 Text LLM Stages

Implementation spec for adding batch spool emission and result materialization
to `pipeline/component2/llm_processor.py` for knowledge extraction and
markdown render stages.

**New code:** Functions added to `pipeline/component2/llm_processor.py`

**Wraps:** `build_knowledge_extract_prompt()`, `parse_knowledge_extraction()`, `KNOWLEDGE_EXTRACT_SYSTEM_PROMPT`, `build_markdown_render_prompt()`, `parse_markdown_render_result()`, `MARKDOWN_RENDER_SYSTEM_PROMPT`

**Artifact contract preserved:** `<lesson>.knowledge_events.json`, `<lesson>.knowledge_debug.json`, `<lesson>.review.md` / `<lesson>.rag_ready.md` must have identical shapes to sync mode. Downstream stages (evidence linker, rule reducer, concept graph, exporters) remain valid.

---

## New functions

### 1. `emit_batch_spool_for_knowledge_extract`

```
emit_batch_spool_for_knowledge_extract(
    *,
    chunks,
    lesson_id,
    video_id,
    paths,
    state_store,
    compaction_cfg,
) -> Path
```

For each adapted chunk:
- Build prompt via `build_knowledge_extract_prompt()`
- Build batch line with `system_instruction = KNOWLEDGE_EXTRACT_SYSTEM_PROMPT`
- Write to lesson-local spool JSONL
- Record requests in SQLite

### 2. `materialize_batch_results_for_knowledge_extract`

```
materialize_batch_results_for_knowledge_extract(
    results_jsonl_path,
    adapted_chunks,
    lesson_name,
    paths,
    state_store,
) -> KnowledgeEventCollection
```

For each result line:
- Extract text
- Call `parse_knowledge_extraction()`
- Accumulate `ChunkExtractionResult` objects
- Feed into `build_knowledge_events_from_extraction_results()`
- Call `save_knowledge_events()` and `save_knowledge_debug()`
- Write `llm_debug` rows in existing schema shape

### 3. `emit_batch_spool_for_markdown_render`

```
emit_batch_spool_for_markdown_render(
    *,
    lesson_id,
    rule_cards,
    evidence_refs,
    paths,
    state_store,
) -> Path
```

Build prompt via `build_markdown_render_prompt()`, write single-request spool JSONL.

### 4. `materialize_batch_results_for_markdown_render`

```
materialize_batch_results_for_markdown_render(
    results_jsonl_path,
    lesson_name,
    paths,
    state_store,
) -> MarkdownRenderResult
```

Extract text, call `parse_markdown_render_result()`, write review/RAG artifacts
via existing exporter path.

---

## Rules

- Do NOT break `process_chunks_knowledge_extract()`, `process_rule_cards_markdown_render()`, or legacy sync behavior.
- Batch materialization must end in the same downstream artifacts as sync mode, so current evidence linker, rule reducer, exporters, validations, and tests remain valid.
- Only batch-render structured inputs; do not feed raw transcript blobs if current deterministic exporter avoids them.

---

## Verification targets

| Test file | Coverage |
|-----------|----------|
| `tests/test_llm_processor_batch.py` (new) | Extraction parses through `parse_knowledge_extraction()`, markdown render parses through `parse_markdown_render_result()`, llm_debug rows in expected shape |
| `tests/test_llm_processor.py` (existing) | Must not regress |
| `tests/test_component2_pipeline.py` (existing) | Must not regress |
