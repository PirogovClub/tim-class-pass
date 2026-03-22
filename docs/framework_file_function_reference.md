# Framework File and Function Reference

This document lists Python files in the repository with their functions and a short description of each one.

Total Python files documented: 122

## helpers/__init__.py
- No functions defined in this file.

## helpers/analyze.py
- _parse_json_from_response() - Parse json from response.
- _fallback_relevance_decision() - Fallback relevance decision.
- _stringify_visible_facts() - Stringify visible facts.
- _as_list() - As list.
- _canonical_visual_type() - Canonical visual type.
- _canonical_extraction_mode() - Canonical extraction mode.
- _canonical_screen_type() - Canonical screen type.
- _looks_canonical() - Looks canonical.
- _raw_indicates_no_change() - True if the model output clearly indicates no material change.
- _normalize_entity_list() - Preserve rich structured entity items (objects with type/label/value_description)
- _normalize_string_list() - Normalize string list.
- _canonical_example_type() - Canonical example type.
- _normalize_readability() - Normalize readability.
- _normalize_annotations() - Preserve structured annotation objects ({text, location, language}) from Gemini-style payloads.
- _normalize_drawn_objects() - Normalize drawn objects.
- _normalize_chart_layout() - Normalize chart layout.
- _normalize_extraction_output() - Normalize model output into the project's canonical frame schema.
- _get_cfg() - Get cfg.
- _resolve_agent() - Resolve agent.
- _call_agent() - Call agent.
- build_extraction_prompt() - Build extraction prompt.
- build_relevance_prompt() - Build relevance prompt.
- extract_with_agent() - Extract with agent.
- judge_relevance() - Judge relevance.
- analyze_frame() - Analyze frame.

## helpers/benchmarking/__init__.py
- No functions defined in this file.

## helpers/benchmarking/benchmark_models.py
- _serialize_results() - Prepare JSON-safe report rows.
- _write_report() - Write the current benchmark state so finished models are persisted immediately.
- estimate_gemini_cost() - Estimate Gemini API cost from token counts and current per-model pricing.
- _resolve_openai_benchmark_model() - Allow raw OpenAI model ids or an explicit openai: prefix in --models.
- estimate_openai_cost() - Estimate OpenAI API cost from token counts and current per-model pricing.
- estimate_benchmark_cost() - Estimate API cost for benchmark runs across supported providers.
- _is_general_benchmark_gemini_model() - Keep general multimodal generateContent models, skip aliases and specialized variants.
- list_gemini_benchmark_models() - List current Gemini generateContent models suitable for the benchmark.
- build_benchmark_prompt() - Compact prompt for benchmarking parse reliability and scoring fields.
- score_output() - Score a normalized output against the gold reference.
- _parse_first_json_object() - Extract and parse the first complete JSON object when response has 'Extra data' after it.
- benchmark_model() - Run one frame through a model and score it. Uses streaming client for live progress.
- main() - Main.

## helpers/clients/__init__.py
- No functions defined in this file.

## helpers/clients/gemini_client.py
- require_gemini_key() - Require gemini key.
- get_client() - Get client.
- get_model_for_step() - Get model for step.
- _is_retryable() - Is retryable.
- generate_content_result() - Generate content result.
- generate_with_retry() - Generate with retry.
- generate_content_stream_result() - Stream generation; returns structured provider response.
- generate_with_retry_stream() - Generate with retry stream.

## helpers/clients/mlx_client.py
- normalize_mlx_host() - Return MLX service base URL from env or argument (for display / scripts).
- _base_url() - Base url.
- health_check() - GET /health on the MLX service. Returns response JSON on success.
- _path_on_server() - Convert local path to server path if mapping is configured.
- _is_retryable() - Is retryable.
- list_models() - Return list of vision task names for the MLX API (mlx-vision_ocr, mlx-vision_strategy).
- chat_image_result() - Send image + prompt to MLX POST /api/v1/chat. Accepts a path: client reads the file,
- chat_image() - Chat image.
- _chat_image_impl() - Chat image impl.

## helpers/clients/openai_client.py
- require_openai_key() - Require openai key.
- get_client() - Return OpenAI client; uses OPENAI_API_KEY from env.
- get_model_for_step() - Resolve model name. step: images, gaps, vlm. Precedence: config > MODEL_* env > default.
- _is_retryable() - Is retryable.
- chat_completion_result() - Chat completion result.
- chat_completion() - Single completion; returns message content.
- chat_completion_with_image_result() - Chat completion with image result.
- chat_completion_with_image() - Send one user message with text + image (base64); returns assistant content.

## helpers/clients/provider_types.py
- AIProvider.generate_text() - Generate text.
- AIProvider.generate_text_with_image() - Generate text with image.

## helpers/clients/providers.py
- _response_format_for_request() - Response format for request.
- GeminiProvider.generate_text() - Generate text.
- GeminiProvider.generate_text_with_image() - Generate text with image.
- OpenAIProvider.generate_text() - Generate text.
- OpenAIProvider.generate_text_with_image() - Generate text with image.
- MLXProvider.generate_text() - Generate text.
- MLXProvider.generate_text_with_image() - Generate text with image.
- SetraProvider.generate_text() - Generate text.
- SetraProvider.generate_text_with_image() - Generate text with image.
- get_provider() - Get provider.
- _provider_key_for_stage() - Provider key for stage.
- _model_key_for_stage() - Model key for stage.
- resolve_provider_for_stage() - Resolve provider for stage.
- resolve_model_for_stage() - Resolve model for stage.

## helpers/clients/setra_client.py
- require_setra_config() - Require setra config.
- get_client() - Get client.
- get_model_for_step() - Get model for step.
- _is_retryable() - Is retryable.
- chat_completion_result() - Chat completion result.
- chat_completion() - Chat completion.
- chat_completion_with_image_result() - Chat completion with image result.
- chat_completion_with_image() - Chat completion with image.

## helpers/clients/stream_events.py
- emit() - Emit one stream event to the callback if provided.

## helpers/clients/usage.py
- _get_value() - Get value.
- _as_int() - As int.
- normalize_usage_record() - Normalize usage record.
- summarize_usage_records() - Summarize usage records.

## helpers/config.py
- _default_pipeline_workers() - Default pipeline workers.
- _default_step2_chunk_workers() - Default step2 chunk workers.
- _parse_int() - Parse int.
- _parse_float() - Parse float.
- _parse_bool() - Parse bool.
- load_pipeline_config_for_video() - Load pipeline.yml from project folder data/<video_id>/pipeline.yml. Returns raw dict or None.
- get_config_for_video() - Return effective config from the project folder (data/<video_id>/).

## helpers/usage_report.py
- is_usage_record() - Is usage record.
- collect_usage_records() - Collect usage records.
- _load_json() - Load json.
- build_video_usage_summary() - Build video usage summary.
- write_video_usage_summary() - Write video usage summary.

## helpers/utils/__init__.py
- No functions defined in this file.

## helpers/utils/compare.py
- ComparisonResult.to_dict() - To dict.
- _load_grayscale() - Load grayscale.
- save_structural_artifact() - Save structural artifact.
- compare_images() - Compare two screenshots using SSIM.

## helpers/utils/frame_schema.py
- key_to_timestamp() - Convert frame key (zero-padded seconds) to HH:MM:SS.
- minimal_no_change_frame() - Produce a minimal frame record when SSIM says no meaningful change.
- minimal_relevance_skip_frame() - Produce a frame record when extraction ran but relevance gate said skip.
- ensure_material_change() - No-op: do not overwrite material_change from lesson_relevant.

## pipeline/__init__.py
- No functions defined in this file.

## pipeline/build_llm_prompts.py
- _build_prompt() - Build prompt.
- build_llm_prompts() - Build llm prompts.
- main() - Main.

## pipeline/component2/__init__.py
- No functions defined in this file.

## pipeline/component2/canonical_lexicon.py
- lookup_canonical() - Return canonical slug if text (lowercased, trimmed) matches the CONCEPT_ALIASES registry, else None. Maps known Russian/English trading terms to stable slugs.

## pipeline/component2/canonicalization.py
- _transliterate() - Transliterate Cyrillic characters to Latin equivalents using a character map.
- normalize_label() - Lowercase, trim, collapse whitespace, strip punctuation noise; NFKC normalize.
- _slugify() - Convert normalized label to a slug: transliterate, lowercase, underscores only.
- make_canonical_id() - Return e.g. 'concept:level'. Lexicon lookup first, falls back to slugification.
- canonicalize_concept() - Return canonical concept_id or None if text is empty/None.
- canonicalize_subconcept() - Return canonical subconcept_id or None if text is empty/None.
- canonicalize_short_statement() - For conditions/invalidations/exceptions: return a canonical_id slug.
- classify_rule_type() - Map an event_type to its rule_type classification (e.g. rule_statement -> rule).

## pipeline/component2/concept_graph.py
- normalize_text() - Collapse whitespace and strip; return empty string for None or blank.
- normalize_concept_id() - Turn a concept/subconcept name into a stable slug (lowercase, alphanumeric + underscore).
- get_rule_concept() - Return normalized concept text, or None if blank.
- get_rule_subconcept() - Return normalized subconcept text, or None if blank.
- get_rule_source_chunk_indexes() - Return sorted unique chunk indexes from rule metadata.
- get_rule_source_sections() - Return normalized source section names from rule metadata.
- get_rule_source_subsections() - Return normalized source subsection names from rule metadata.
- collect_concept_names() - Collect unique (concept_id -> name) and (subconcept_id -> name) from rules.
- infer_parent_concept_id_for_subconcept() - Return the concept_id most often paired with this subconcept in rules.
- dedupe_nodes() - Merge nodes by concept_id; merge aliases and metadata for duplicates.
- create_concept_nodes() - Build concept and subconcept nodes from rules; infer parent for each subconcept.
- make_relation_id() - Build a unique relation id from source, type, and target.
- create_parent_child_relations() - Add parent_of and child_of relations for each rule that has both concept and subconcept.
- create_sibling_related_relations() - Add related_to (both directions) between subconcepts that share the same concept.
- average_source_chunk_index() - Return mean of rule's source chunk indexes, or None if none.
- group_rules_by_concept_family() - Group rules by normalized concept id (or 'unclassified' if no concept).
- create_precedes_relations() - Add precedes relations from source chunk order within each concept family.
- has_dependency_cue() - True if text contains any DEPENDENCY_CUES phrase.
- create_depends_on_relations() - Add depends_on (subconcept -> concept) when rule text has dependency cues.
- has_contrast_cue() - True if text contains any CONTRAST_CUES phrase.
- create_contrasts_with_relations() - Add contrasts_with from CONTRAST_NAME_PAIRS and from contrast cues in rule text.
- looks_supporting_subconcept() - True if subconcept_id contains rating/confirmation/validation/strength.
- create_supports_relations() - Add supports (subconcept -> concept) when subconcept name looks support-like.
- dedupe_relations() - Merge relations by (source_id, relation_type, target_id); merge list metadata.
- build_concept_graph() - Build a lesson-level concept graph and debug rows from rule cards.
- load_rule_cards() - Load and validate RuleCardCollection from JSON file.
- save_concept_graph() - Write ConceptGraph to JSON atomically.
- save_concept_graph_debug() - Write concept graph relation debug rows to JSON atomically.

## pipeline/component2/evidence_linker.py
- load_chunks_json() - Load *.chunks.json as a list of chunk dicts.
- load_knowledge_events() - Load KnowledgeEventCollection from JSON and return .events.
- _change_summary_to_str() - Normalize change_summary from list or str to single str.
- adapt_visual_events_from_chunks() - Build AdaptedVisualEvent list from chunk dicts; preserve chunk context.
- enrich_visual_event_from_dense_analysis() - Merge richer metadata from dense_analysis by frame_key; return copy or same.
- _normalize_concept_hint() - Normalize concept hint.
- extract_visual_concept_hints() - Extract (concept_hints, subconcept_hints) from annotations, entities, change_summary, etc.
- group_visual_events_into_candidates() - Group nearby events into teaching-example-level candidates.
- _dedupe_preserve_order() - Dedupe preserve order.
- backfill_knowledge_event_evidence_refs() - Backfill knowledge event evidence refs.
- backfill_evidence_linked_rule_ids() - Backfill evidence linked rule ids.
- _norm_text() - Norm text.
- _contains_any() - Contains any.
- _is_generic_teaching_visual() - Is generic teaching visual.
- _has_explicit_negative_semantics() - Has explicit negative semantics.
- infer_example_role() - Heuristic example role (13-phase2, 14-phase2). Positive only with concrete market visuals; counterexample only with explicit negative event types.
- classify_evidence_strength() - Classify evidence strength: weak, moderate, or strong. Evidence is always supporting.
- classify_evidence_role_detail() - Return a granular role label for the evidence reference (illustrates_rule, shows_setup, shows_failure, shows_counterexample, ambiguous_chart_context).
- _event_time_range_seconds() - Return (start_sec, end_sec) or None if not parseable.
- score_candidate_event_match() - Score match; return (total, breakdown). Weights: chunk 0.40, time 0.25, concept 0.20, subconcept 0.10, type 0.05; cap 1.0.
- link_candidates_to_knowledge_events() - For each candidate, link events with score >= threshold; return (pairs, debug_rows).
- _visual_type_to_schema() - Visual type to schema.
- _example_role_to_schema() - Example role to schema.
- candidate_to_evidence_ref() - Build EvidenceRef from candidate and linked events.
- build_evidence_index() - Adapt visuals from chunks, optionally enrich, group, link, convert to EvidenceRef; return (EvidenceIndex, debug_rows).
- save_evidence_index() - Write EvidenceIndex as JSON.
- save_evidence_debug() - Write debug rows as JSON array.

## pipeline/component2/exporters.py
- load_rule_cards() - Load and validate RuleCardCollection from JSON.
- load_evidence_index() - Load and validate EvidenceIndex from JSON.
- load_knowledge_events() - Load KnowledgeEventCollection from JSON. Return None if file is missing.
- build_export_context() - Build a normalized export context from collections.
- group_rule_cards_for_export() - Group rule cards by concept; use 'Unclassified' when concept is missing.
- sort_rule_cards() - Deterministic order: section, subsection, concept, subconcept, confidence desc, rule_id.
- format_bullet_block() - Format a titled bullet list; return empty string if items empty.
- format_compact_text_list() - Return trimmed, non-empty items from list.
- dedupe_preserve_order() - Deduplicate while preserving first occurrence order.
- clean_markdown_text() - Trim and normalize whitespace for markdown.
- _rule_evidence_refs_compact() - Compact line of evidence refs for a rule.
- _rule_source_events_compact() - Compact line of source event ids for a rule.
- _review_rule_block() - Single rule as review markdown block; omit empty sections.
- render_review_markdown_deterministic() - Full review markdown: lesson title, concept groups, rule blocks, compact refs. Omit empty sections.
- _rag_rule_block() - Compact RAG rule block: no verbose provenance.
- render_rag_markdown_deterministic() - Compact RAG markdown; no verbose provenance.
- render_review_markdown() - Review markdown: deterministic or LLM (render_mode=review). Returns (markdown, usage_records).
- render_rag_markdown() - RAG markdown: deterministic or LLM (render_mode=rag). Returns (markdown, usage_records).
- ensure_parent_dir() - Create parent directory of path if it does not exist.
- save_review_markdown() - Write review markdown to file.
- save_rag_markdown() - Write RAG markdown to file.
- save_export_debug() - Write debug rows as JSON.
- write_export_manifest() - Write export manifest JSON (lesson_id, paths, counts, LLM flags).
- _write_render_debug() - Write optional debug JSON (usage + preview) when LLM render was used.
- _format_concept_relationships_section() - Compact markdown lines for Concept relationships (Task 12 optional).
- export_review_markdown() - Load artifacts, build context, render review markdown, save. Returns (markdown, usage).
- export_rag_markdown() - Load artifacts, build context, render RAG markdown, save. Returns (markdown, usage).

## pipeline/component2/knowledge_builder.py
- _lesson_slug() - Lesson slug.
- AdaptedChunk.candidate_visual_frame_keys() - Candidate visual frame keys.
- AdaptedChunk.candidate_visual_types() - Candidate visual types.
- AdaptedChunk.candidate_example_types() - Candidate example types.
- load_chunks_json() - Load and validate *.chunks.json as a list of chunk dicts.
- build_transcript_text() - Join non-empty stripped line texts; ignore blanks.
- build_numbered_transcript_text() - Render transcript lines with chunk-local zero-based indices and mm:ss spans.
- get_transcript_time_bounds() - Use first/last line start/end if present, else fallbacks.
- adapt_chunk() - Normalize a raw chunk dict into AdaptedChunk.
- adapt_chunks() - Adapt a list of raw chunk dicts.
- ExtractedStatement.normalize_source_line_indices() - Normalize source line indices.
- build_knowledge_extraction_prompt() - Build the extraction prompt with transcript and compact visual summaries.
- LLMExtractionClient.generate_extraction() - Generate extraction.
- extract_chunk_knowledge() - Call LLM, parse JSON into ChunkExtractionResult, return result and debug payload.
- infer_concept_from_text() - Conservative keyword-based concept/subconcept from text.
- infer_concept_from_visuals() - Conservative concept from visual annotation/example_type.
- resolve_concept() - Prefer LLM-provided, then transcript keywords, then visual hints.
- score_transcript_support() - Compute a 0..1 transcript support score based on anchor quality and text clarity.
- score_visual_support() - Estimate how much visual evidence in this chunk supports any event.
- score_event_confidence() - Transcript-first heuristic label and score in [0, 1].
- normalize_statement_text() - Strip and collapse whitespace.
- dedupe_statements() - Case-insensitive, whitespace-normalized exact-text dedupe.
- clamp_line_indices() - Clamp line indices.
- find_line_indices_by_quote() - Find line indices by quote.
- build_transcript_anchors() - Build transcript anchors.
- compute_anchor_span_width() - Compute anchor span width.
- compute_anchor_density() - Compute anchor density.
- is_near_contiguous() - Is near contiguous.
- compute_timestamp_confidence() - Return line/span/chunk from line bounds and density (brief 11-phase2).
- finalize_anchor_provenance() - Return dict with timestamp_confidence for tests (brief 11-phase2).
- classify_timestamp_confidence() - Returns:
- derive_event_timestamps_from_line_indices() - Returns:
- resolve_statement_anchors() - Returns:
- extraction_result_to_knowledge_events() - Map extraction buckets to KnowledgeEvents with provenance and deterministic ids.
- build_knowledge_events_from_extraction_results() - Build KnowledgeEventCollection from pre-extracted chunk results (no LLM call).
- build_knowledge_events_from_chunks() - Extract per chunk, aggregate events, collect debug rows.
- build_knowledge_events_from_file() - Load chunks from file, adapt, then build from chunks.
- save_knowledge_events() - Write KnowledgeEventCollection as JSON. Uses full model_dump so Phase 2A and diagnostic fields are preserved.
- save_knowledge_debug() - Write debug records as JSON array.

## pipeline/component2/llm_processor.py
- _stage_for_llm_mode() - Stage for llm mode.
- _resolve_model_for_llm_mode() - Resolve model for llm mode.
- _resolve_provider_for_llm_mode() - Resolve provider for llm mode.
- build_knowledge_extract_prompt() - Build minimal user prompt: content-focused, no instruction block (instructions are in system prompt).
- build_markdown_render_prompt() - Build markdown render prompt.
- build_legacy_markdown_prompt() - Build legacy markdown prompt.
- parse_knowledge_extraction() - Parse knowledge extraction.
- parse_markdown_render_result() - Parse markdown render result.
- parse_legacy_enriched_markdown_chunk() - Parse legacy enriched markdown chunk.
- _max_tokens_for_llm_mode() - Cap model output. Large knowledge JSON can exceed provider defaults and truncate mid-string.
- _is_truncated_json_validation_error() - Is truncated json validation error.
- _call_provider_for_mode() - Call provider for mode.
- process_chunk_knowledge_extract() - Process chunk knowledge extract.
- process_chunks_knowledge_extract() - Process chunks knowledge extract.
- process_rule_cards_markdown_render() - Process rule cards markdown render.
- _call_provider_legacy() - Call provider legacy.
- process_chunk_legacy_markdown() - Process chunk legacy markdown.
- process_chunks_legacy_markdown() - Process chunks legacy markdown.
- format_final_markdown() - Format final markdown.
- assemble_legacy_video_markdown() - Assemble legacy video markdown.
- legacy_debug_rows() - Convert legacy processed_chunks (chunk, enriched, usage) to rows for write_llm_debug.
- write_llm_debug() - Write llm debug.
- _resolve_model() - Resolve model.
- _resolve_provider() - Resolve provider.

## pipeline/component2/main.py
- _default_output_root() - Use VTT file's parent directory as output root when not specified.
- _derive_lesson_name() - Derive lesson name from VTT filename stem.
- _format_elapsed() - Format elapsed seconds as MM:SS.
- maybe_add_output() - Add path to outputs dict only if it exists.
- require_artifact() - Return True if path exists; otherwise print skip message and return False.
- _merge_rule_debug_rows() - Merge debug row lists; either may be empty.
- run_component2_pipeline() - Run Component 2 pipeline: filter, chunk, optional knowledge/evidence/rule-cards/concept-graph/exporters, legacy markdown. Returns dict of written paths.
- main() - Click entry point for the standalone Component 2 + Step 3 markdown pipeline.

## pipeline/component2/ml_prep.py
- normalize_text() - Collapse whitespace and strip; return empty string for None or blank.
- dedupe_preserve_order() - Return unique non-blank strings in original order.
- normalize_feature_name() - Normalize to lowercase snake_case identifier for feature names.
- get_rule_family_key() - Prefer subconcept, then concept, for ML feature lookup.
- pick_top_items() - Return up to limit deduplicated non-blank items for use in guidance templates.
- sentence_join() - Join items into a single sentence with commas and final 'and'.
- infer_candidate_features() - Derive candidate algorithmic feature names from rule concept, subconcept, and text.
- build_evidence_lookup() - Build evidence_id -> EvidenceRef from index (uses evidence_refs).
- get_linked_evidence_for_rule() - Resolve rule.evidence_refs to list of EvidenceRef.
- is_evidence_ml_eligible() - True iff evidence has an ML-eligible role and required links (brief 11-phase2).
- _evidence_ref_to_dict() - Convert EvidenceRef to dict for is_evidence_ml_eligible and build_ml_examples.
- is_evidence_ml_eligible_for_rule() - Adapter: EvidenceRef + RuleCard -> dict then brief's is_evidence_ml_eligible.
- _norm_text() - Strip and lower for marker checks; avoid clash with normalize_text in this module.
- _contains_any() - Contains any.
- is_generic_evidence() - Is generic evidence.
- has_explicit_negative_evidence() - Has explicit negative evidence.
- should_emit_labeling_task() - True iff we should emit a labeling task for this ref (11-phase2: ML-eligible only).
- distribute_example_refs_for_ml() - Map evidence roles into ML buckets (11-phase2: ML_ELIGIBLE_ROLES only; illustration excluded).
- build_labeling_guidance() - Generate compact deterministic labeling instruction from conditions + invalidation + rule_text.
- enrich_rule_card_for_ml() - Enrich a single rule with candidate_features, example buckets, and labeling_guidance. Preserves provenance.
- enrich_rule_card_collection_for_ml() - Enrich all rules in the collection for ML; return new collection.
- build_ml_examples() - Only export eligible evidence rows (brief 11-phase2).
- attach_rule_example_refs() - Only eligible evidence may populate rule example refs (brief 11-phase2).
- build_labeling_tasks() - Return tasks only for ML-eligible evidence (12-phase2 unit-test helper).
- build_ml_manifest() - Build lesson-level ML manifest (rules + examples); 11-phase2: trainable-only, no illustration.
- build_labeling_manifest() - Build manifest of labeling tasks (one per rule+evidence in ML buckets).
- compute_ml_readiness_coverage() - Report how many rules/evidence have ML-ready fields (for QA).
- save_ml_manifest() - Write ML manifest JSON atomically.

## pipeline/component2/models.py
- No functions defined in this file.

## pipeline/component2/orchestrator.py
- prepare_component2_run() - Run preflight inspection, write pipeline_inspection.json, return artifact paths.

## pipeline/component2/parser.py
- timestamp_to_seconds() - Timestamp to seconds.
- seconds_to_timestamp() - Seconds to timestamp.
- seconds_to_mmss() - Seconds to mmss.
- clean_vtt_text() - Clean vtt text.
- _parse_vtt_manually() - Parse vtt manually.
- parse_vtt() - Parse vtt.
- parse_filtered_visual_events() - Parse filtered visual events.
- _line_ends_sentence() - Line ends sentence.
- create_lesson_chunks() - Create lesson chunks.
- parse_and_sync() - Parse and sync.
- write_lesson_chunks() - Write lesson chunks.

## pipeline/component2/provenance.py
- dedupe_preserve_order() - Dedupe preserve order.
- compact_nonempty_strs() - Compact nonempty strs.
- compact_nonempty_ints() - Compact nonempty ints.
- prune_none_values() - Prune none values.
- build_knowledge_event_provenance() - Build compact metadata dict for KnowledgeEvent.metadata (provenance only).
- build_evidence_ref_provenance() - Build normalized provenance dict for EvidenceRef fields.
- merge_source_event_ids() - Merge source event ids.
- merge_evidence_refs() - Merge evidence refs.
- merge_source_sections() - Merge source sections.
- merge_source_subsections() - Merge source subsections.
- merge_source_chunk_indexes() - Merge source chunk indexes.
- build_rule_card_provenance() - Build compact provenance for RuleCard (source_event_ids, evidence_refs, optional metadata).
- validate_knowledge_event_provenance() - Return list of provenance warnings for a KnowledgeEvent.
- validate_evidence_ref_provenance() - Return list of provenance warnings for an EvidenceRef.
- validate_rule_card_provenance() - Return list of provenance warnings for a RuleCard.
- validate_rule_card_for_final_provenance() - Return hard errors from provenance warnings; use at final export to reject rules.
- compute_provenance_coverage() - Return counts for provenance coverage (QA/manifest).
- format_compact_provenance() - Format a short provenance block for review markdown (Evidence refs / Source events).

## pipeline/component2/quant_reducer.py
- _resolve_reducer_model() - Resolve reducer model.
- _resolve_reducer_provider() - Resolve reducer provider.
- synthesize_full_document() - Synthesize full document.

## pipeline/component2/rule_compat.py
- _collect_text_fields() - Concatenate textual fields from a rule dict for directional keyword scanning.
- infer_rule_direction() - Return a directional tag for a rule using deterministic keyword matching (bullish_above, bearish_below, breakout_up/down, reversal_up/down, neutral, unknown).
- _has_conflict() - True if any pair in a list of directions is in OPPOSITE_PAIRS.
- are_directions_conflicting() - True if two direction tags are semantically opposite.
- is_positive_example_compatible() - Return True only if evidence can safely be a positive example for this rule. Blocks when evidence is linked to multiple rules with conflicting directions.
- is_evidence_safe_for_ml() - Return True only if evidence has no cross-rule directional conflicts. Single-rule evidence is always safe.

## pipeline/component2/rule_reducer.py
- load_knowledge_events() - Load and validate KnowledgeEventCollection from JSON.
- load_evidence_index() - Load and validate EvidenceIndex from JSON.
- normalize_text_for_match() - Lowercase, normalize whitespace, strip trivial punctuation.
- simple_text_similarity() - Token-set overlap similarity in [0, 1]. No LLM.
- is_role_compatible() - True if event can attach to this candidate by role.
- _event_chunk_index() - Event chunk index.
- _candidate_chunk_indexes() - Candidate chunk indexes.
- score_event_candidate_match() - Score how well event fits candidate. Returns (score in [0,1], breakdown dict).
- _route_event_into_candidate() - Append event to the appropriate list on candidate.
- group_events_into_rule_candidates() - Group events into rule candidates; return (candidates, debug_rows).
- _candidate_event_ids() - Candidate event ids.
- attach_evidence_to_candidates() - Attach EvidenceRefs to candidates when source_event_ids overlap.
- merge_duplicate_primary_events() - Dedupe primary events by normalized text; keep one per group.
- split_overbroad_candidate() - Split when multiple subconcepts or distinct primary rules; prefer over-splitting.
- choose_canonical_rule_text() - Pick one canonical sentence: rule_statement > definition > condition.
- _dedupe_short() - Dedupe short.
- collect_condition_texts() - Collect condition texts.
- collect_invalidation_texts() - Collect invalidation texts.
- collect_exception_texts() - Collect exception texts.
- collect_comparison_texts() - Collect comparison texts.
- collect_algorithm_notes() - Collect algorithm notes.
- _slug() - Slug.
- make_rule_id() - Make rule id.
- distribute_example_refs() - Map example_role to positive/negative/ambiguous evidence_id lists.
- _aggregate_transcript_support() - Aggregate transcript support from source events. Returns (avg_score, total_anchors, repetition_count).
- _aggregate_visual_support() - Aggregate visual support from source events.
- score_rule_candidate_confidence() - Transcript-first confidence: strong transcript grounding lifts score even without visual evidence.
- candidate_to_rule_card() - Convert RuleCandidate to RuleCard.
- build_rule_cards() - Group  attach evidence  merge duplicates  split  convert to RuleCards; return collection and debug rows.
- save_rule_cards() - Write RuleCardCollection to JSON.
- save_rule_debug() - Write debug rows to JSON.

## pipeline/component2/support_policy.py
- DEFAULT_EVENT_POLICY - Dict mapping event_type to default teaching_mode and evidence_requirement.
- classify_teaching_mode() - Classify how the concept is taught: theory, example, or mixed.
- classify_evidence_requirement() - Determine whether visual evidence is required, optional, or unnecessary.
- classify_support_basis() - Determine the primary grounding source: transcript_primary, transcript_plus_visual, visual_primary, inferred.
- classify_transcript_support_level() - Bucket a transcript support score into weak/moderate/strong.
- classify_visual_support_level() - Classify the strength of visual support for a rule or event.
- should_require_visual_evidence() - Return True only when the entity actually needs linked visual evidence.

## pipeline/component2/visual_compaction.py
- _int_default() - Int default.
- from_pipeline_config() - Build VisualCompactionConfig from pipeline config dict (e.g. get_config_for_video).
- extract_frame_key() - Extract frame key.
- extract_timestamp_seconds() - Extract timestamp seconds.
- build_raw_visual_event_id() - Build raw visual event id.
- extract_visual_type() - Extract visual type.
- extract_example_type() - Extract example type.
- normalize_visual_text() - Normalize visual text.
- is_layout_or_ui_noise() - Is layout or ui noise.
- is_frame_by_frame_motion_narration() - Is frame by frame motion narration.
- is_low_value_visual_phrase() - Is low value visual phrase.
- dedupe_visual_phrases() - Dedupe visual phrases.
- clamp_text_length() - Clamp text length.
- _change_summary_to_str() - Normalize change_summary from list or str to single str.
- _extract_visible_annotations() - Extract visible annotations.
- _extract_entities() - Extract entities.
- summarize_visual_event_for_extraction() - Summarize visual event for extraction.
- summarize_visual_events_for_extraction() - Summarize visual events for extraction.
- build_screenshot_candidate_paths() - Build screenshot candidate paths.
- summarize_visual_candidate_for_evidence() - Summarize visual candidate for evidence.
- build_evidence_provenance_payload() - Build evidence provenance payload.
- summarize_evidence_for_rule_card() - Summarize evidence for rule card.
- trim_rule_card_visual_refs() - Trim rule card visual refs.
- summarize_evidence_for_review_markdown() - Summarize evidence for review markdown.
- summarize_evidence_for_rag_markdown() - Summarize evidence for rag markdown.
- strip_raw_visual_blobs_from_metadata() - Strip raw visual blobs from metadata.
- assert_no_raw_visual_blob_leak() - Assert no raw visual blob leak.
- detect_visual_spam_lines() - Detect visual spam lines.
- validate_markdown_visual_compaction() - Validate markdown visual compaction.

## pipeline/component2/visual_policy_debug.py
- collect_candidate_summary_debug() - Build one debug record for a candidate (evidence or chunk).
- collect_dropped_phrases_from_text() - Split text into phrases and return those that are low-value (for debug).
- collect_blocked_metadata_keys() - Return keys that would be stripped by strip_raw_visual_blobs_from_metadata.
- write_visual_compaction_debug() - Write output_intermediate/<lesson>.visual_compaction_debug.json.

## pipeline/contracts.py
- PipelinePaths.filtered_visuals_path() - Path to filtered visual events JSON after invalidation filter.
- PipelinePaths.filtered_visuals_debug_path() - Path to filtered visual events debug JSON.
- PipelinePaths.output_intermediate_dir() - Directory for intermediate pipeline artifacts (chunks, knowledge, evidence, rules).
- PipelinePaths.output_rag_ready_dir() - Directory for RAG-ready markdown and export outputs.
- PipelinePaths.output_review_dir() - Directory for review markdown and export manifests.
- PipelinePaths.lesson_chunks_path() - Path to lesson chunks JSON (synced transcript + visual events).
- PipelinePaths.pass1_markdown_path() - Path to pass-1 intermediate markdown.
- PipelinePaths.llm_debug_path() - Path to LLM chunk processing debug JSON.
- PipelinePaths.reducer_usage_path() - Path to quant reducer usage JSON.
- PipelinePaths.rag_ready_markdown_path() - Path to legacy RAG-ready markdown (post reducer).
- PipelinePaths.review_markdown_path() - Path to exporter-generated review markdown.
- PipelinePaths.rag_ready_export_path() - Path to exporter-generated RAG-ready markdown.
- PipelinePaths.review_render_debug_path() - Path to review render debug JSON (when using LLM render).
- PipelinePaths.rag_render_debug_path() - Path to RAG render debug JSON (when using LLM render).
- PipelinePaths.knowledge_events_path() - Path to extracted knowledge events JSON.
- PipelinePaths.knowledge_debug_path() - Path to knowledge extraction debug JSON.
- PipelinePaths.evidence_index_path() - Path to evidence index JSON (linked visual evidence).
- PipelinePaths.evidence_debug_path() - Path to evidence linking debug JSON.
- PipelinePaths.rule_cards_path() - Path to rule cards JSON (normalized rules from knowledge + evidence).
- PipelinePaths.rule_debug_path() - Path to rule reducer debug JSON.
- PipelinePaths.concept_graph_path() - Path to lesson-level concept graph JSON (Task 12).
- PipelinePaths.concept_graph_debug_path() - Path to concept graph relation debug JSON.
- PipelinePaths.ml_manifest_path() - Path to lesson-level ML manifest (Task 13).
- PipelinePaths.labeling_manifest_path() - Path to lesson-level labeling manifest (Task 13).
- PipelinePaths.export_manifest_path() - Path to exporter artifact manifest JSON for a lesson.
- PipelinePaths.inspection_report_path() - Path to pipeline inspection report JSON (preflight).
- PipelinePaths.ensure_output_dirs() - Create output_intermediate, output_review, output_rag_ready if needed.

## pipeline/corpus/__init__.py
- No functions defined in this file. Package init for corpus-level export layer (Step 2).

## pipeline/corpus/__main__.py
- Invokes `pipeline.corpus.cli.main()` to allow running as `python -m pipeline.corpus`.

## pipeline/corpus/adapters.py
- _load_json() - Load JSON from a file path.
- find_artifact() - Find an artifact file by suffix pattern in the intermediate dir.
- load_lesson_knowledge_events() - Load and validate KnowledgeEventCollection from JSON.
- load_lesson_rule_cards() - Load and validate RuleCardCollection from JSON.
- load_lesson_evidence_index() - Load and validate EvidenceIndex from JSON.
- load_lesson_concept_graph() - Load and validate ConceptGraph from JSON.
- globalize_event() - Return a copy of a KnowledgeEvent dict with global IDs (event_id, evidence_refs, source_event_ids).
- globalize_rule() - Return a copy of a RuleCard dict with global IDs (rule_id, source_event_ids, evidence_refs, example_refs).
- globalize_evidence() - Return a copy of an EvidenceRef dict with global IDs (evidence_id, linked_rule_ids, source_event_ids).
- globalize_concept_node() - Return a copy of a ConceptNode dict with global IDs (concept_id via node slug, source_rule_ids, parent_id).
- globalize_concept_relation() - Return a copy of a ConceptRelation dict with global IDs using a node_id_map for endpoint resolution.

## pipeline/corpus/cli.py
- main() - Click CLI entry point: `python -m pipeline.corpus --input-root <path> --output-root <path> [--strict]`. Runs build_corpus and prints summary.

## pipeline/corpus/contracts.py
- load_schema_versions() - Load schema version strings from schema_versions.json.
- LessonRecord (Pydantic model) - Per-lesson metadata: lesson_id, slug, available artifacts, counts, content hashes, status, warnings.
- CorpusMetadata (Pydantic model) - Aggregate corpus info: version, timestamp, entity counts, validation status. Re-exports KnowledgeEvent, RuleCard, EvidenceRef, ConceptNode, ConceptRelation, ConceptGraph as frozen v1 contract.

## pipeline/corpus/corpus_builder.py
- _write_jsonl() - Write a list of dicts as JSONL (one JSON object per line).
- _write_json() - Write data as pretty-printed JSON.
- _merge_concept_graphs() - Deduplicate concept nodes by global_id, merge aliases/source_rule_ids/source_lessons. Deduplicate relations by relation_id, merge weights and provenance.
- _build_concept_alias_registry() - Build canonical concept -> aliases + source lessons mapping.
- _build_concept_frequencies() - Compute per-concept counts of rules, events, evidence, and lessons.
- _build_concept_rule_map() - Map concept global_id -> list of global rule IDs.
- _build_rule_family_index() - Group rules by normalized concept+subconcept key.
- _build_concept_overlap_report() - List concepts appearing in multiple lessons, sorted by overlap degree.
- build_corpus() - Main orchestrator: discover lessons, validate, load/globalize artifacts, merge JSONL exports, merge concept graph, build enrichments, write metadata and validation report. Returns summary dict.

## pipeline/corpus/id_utils.py
- _transliterate_char() - Map a single character from Cyrillic to Latin equivalent.
- _slugify() - Lowercase, transliterate Cyrillic, collapse non-alnum to underscores.
- slugify_lesson_id() - Convert a human-readable lesson ID into a stable slug.
- make_global_id() - Build a global ID like 'event:lesson_slug:local_id'. Deterministic and stable across reruns.
- make_global_node_id() - Build cross-lesson concept node ID like 'node:slugified_concept'. Keyed by normalized name.
- make_global_relation_id() - Build deterministic relation ID from source, type, and target: 'rel:src:type:dst'.

## pipeline/corpus/lesson_registry.py
- _sha256_file() - Compute SHA-256 hash of a file for change detection.
- _count_entities() - Count entities in a JSON file by looking at len(data[list_key]).
- discover_lessons() - Scan input_root for directories with output_intermediate/ containing artifacts. Returns sorted list of LessonRecord.
- build_registry() - Convert lesson records to serializable dicts for lesson_registry.json.
- save_registry() - Write registry as pretty-printed JSON.

## pipeline/corpus/validator.py
- ValidationResult (class) - Accumulates errors and warnings with add_error/add_warning. Properties: has_errors, status. Serializable via to_dict().
- validate_lesson() - Validate a single lesson's artifacts: file existence, JSON parse, Pydantic schema, non-empty IDs, intra-lesson referential integrity. Supports strict mode.
- _check_intra_lesson_integrity() - Check referential integrity within a single lesson: rule->event, rule->evidence, evidence->rule.
- validate_cross_lesson() - Check cross-lesson constraints: no global ID collisions, no duplicate lessons, all relation endpoints exist, referential integrity across merged artifacts.
- save_validation_report() - Write validation report as pretty-printed JSON.

## pipeline/dense_analyzer.py
- _normalize_agent() - Accept 'antigravity' as alias for 'ide'.
- _parse_json_from_response() - Extract JSON from API response, handling markdown code blocks.
- _encode_image() - Encode image.
- _single_frame_prompt() - Build prompt text for analyzing one frame (for API call).
- _analyze_frame_provider() - Analyze frame provider.
- _analyze_frame_openai() - Analyze frame openai.
- _analyze_frame_gemini() - Analyze frame gemini.
- _analyze_frame_mlx() - Analyze frame mlx.
- _analyze_frame_setra() - Analyze frame setra.
- get_batch_prompt() - Returns the production prompt for the agent to analyze a batch of frames
- get_batch_prompt_independent() - Same as get_batch_prompt but without previous_state (Option B: independent batches).
- _previous_frame_key() - Previous frame key.
- _last_relevant_key() - Last relevant key.
- _write_processing_status() - Write processing status.
- _load_structural_index() - Load structural index.
- _chunk_label() - Chunk label.
- partition_queue_keys() - Partition queue keys.
- _resolve_step2_chunk_workers() - Resolve step2 chunk workers.
- _write_analysis_outputs() - Write analysis outputs.
- _entries_meaningfully_different() - Entries meaningfully different.
- _process_chunk_sequential() - Process chunk sequential.
- _reprocess_chunk_boundary() - Reprocess chunk boundary.
- _merge_chunk_results() - Merge chunk results.
- run_analysis() - Run analysis.
- cli() - Analyze dense frames with full description + delta.

## pipeline/dense_capturer.py
- _frame_number_to_key() - Frame number to key.
- _run_ffmpeg_cmd() - Run ffmpeg cmd.
- _probe_duration_seconds() - Probe duration seconds.
- _extract_segment() - Extract segment.
- extract_dense_frames() - Extract dense frames. video_file_override: optional filename (e.g. from pipeline.yml)

## pipeline/downloader.py
- extract_video_id() - Uses yt-dlp to just extract the video id without downloading.
- download_video_and_transcript() - Downloads the best mp4 video and vtt transcripts from a YouTube URL to data/<video_id>/.

## pipeline/frame_extractor.py
- _extract_single_frame() - Extract single frame.
- extract_frames() - Extract frames.

## pipeline/gap_detector.py
- GapTarget.validate_timestamp() - Validate timestamp.
- get_system_prompt() - Get system prompt.
- _extract_gaps_with_provider() - Extract gaps with provider.
- extract_gaps_openai() - Extract gaps openai.
- extract_gaps_gemini() - Extract gaps gemini.
- extract_gaps_setra() - Extract gaps setra.
- write_prompt_file() - Write the prompt file for agent-based processing. Returns (prompt_path, response_path).
- read_response_file() - Read the agent-filled JSON response.
- process_video() - Process video.

## pipeline/inspection.py
- resolve_callable() - Resolve a dotted path to a callable (e.g. 'pipeline.main.main').
- inspect_stages() - Verify each stage in the registry can be imported and is callable.
- inspect_artifacts() - Check presence of known artifacts under video_root (and optionally for a lesson).
- build_report() - Build a full inspection report for the given video root and optional lesson.
- write_report() - Write the inspection report as JSON to output_path.

## pipeline/invalidation_filter.py
- _sort_key() - Sort key.
- _timestamp_to_seconds() - Timestamp to seconds.
- _entry_timestamp_seconds() - Entry timestamp seconds.
- load_dense_analysis() - Load dense analysis.
- is_valid_visual_event() - Is valid visual event.
- rejection_reason() - Rejection reason.
- _sequence_has_content() - Sequence has content.
- _dict_has_content() - Dict has content.
- _contains_instructional_keyword() - Contains instructional keyword.
- _has_instructional_signal() - Has instructional signal.
- _normalize_visual_event() - Normalize visual event.
- filter_visual_events() - Filter visual events.
- build_debug_report() - Build debug report.
- write_filtered_events() - Write filtered events.
- write_debug_report() - Write debug report.
- run_invalidation_filter() - Run invalidation filter.

## pipeline/io_utils.py
- atomic_write_text() - Write text to path atomically (temp file + os.replace).
- atomic_write_json() - Write JSON to path atomically.
- write_text_file() - Convenience wrapper for atomic_write_text.
- write_json_file() - Convenience wrapper for atomic_write_json.
- write_artifact_manifest() - Write artifact manifest JSON atomically.
- build_export_manifest() - Build export manifest with only existing artifacts.

## pipeline/main.py
- main() - Multimodal YouTube Video Transcript Enrichment Pipeline (Dense Mode).

## pipeline/schemas.py
- normalize_text() - Single-line normalized text (strip, collapse whitespace).
- is_placeholder_text() - True if value is empty or a known placeholder after normalization.
- is_compact_summary() - True if value is None or normalized length <= max_len.
- SchemaBase.save_json() - Save json.
- KnowledgeEvent.must_not_be_blank() - Must not be blank.
- RuleCard.required_text_must_not_be_blank() - Required text must not be blank.
- validate_knowledge_event() - Return list of validation errors/warnings for a KnowledgeEvent.
- validate_rule_card() - Return list of validation errors/warnings for a RuleCard. Empty list = valid.
- validate_evidence_ref() - Return list of validation errors/warnings for an EvidenceRef.
- dedupe_preserve_order() - Deduplicate list of strings while preserving order.
- validate_rule_card_for_export() - Strict export-level validation; use before writing rule_cards.json or ML manifests.
- validate_rule_card_collection_for_export() - Filter collection to export-valid rules only; return (valid_collection, debug_rows for rejected).
- validate_knowledge_event_for_export() - Validate knowledge event for export.
- validate_knowledge_event_collection_for_export() - Validate knowledge event collection for export.
- validate_evidence_ref_for_export() - Validate evidence ref for export.
- validate_evidence_index_for_export() - Validate evidence index for export.

## pipeline/select_llm_frames.py
- _parse_diff_from_name() - Parse diff from name.
- build_llm_queue() - Build llm queue.
- main() - Main.

## pipeline/stage_registry.py
- No functions defined in this file.

## pipeline/stitcher.py
- parse_vtt_timestamps() - Parse vtt timestamps.
- is_time_between() - Is time between.
- stitch_transcript() - Stitch transcript.
- run_stitcher() - Run stitcher.

## pipeline/structural_compare.py
- _base_stem() - Base stem.
- _rename_frames_with_diff() - Rename frames with diff.
- _compare_pair() - Compare pair.
- _format_elapsed() - Format elapsed.
- run_structural_compare() - Run structural compare.
- main() - Main.

## pipeline/usage_report.py
- main() - Main.

## pipeline/validation.py
- _walk_forbidden_keys() - Walk forbidden keys.
- validate_no_visual_blob_leakage() - Recursively check for forbidden raw visual blob keys. Returns list of error messages.
- validate_knowledge_event_collection_integrity() - Validate knowledge event collection: ids, confidence, no forbidden keys.
- validate_evidence_index_integrity() - Validate evidence index: ids, visual provenance, source_event_ids, no forbidden keys.
- validate_rule_card_collection_integrity() - Validate rule card collection: ids, source_event_ids, confidence, no forbidden keys.
- validate_concept_graph_integrity() - Validate concept graph: node ids unique, relation source/target exist.
- validate_ml_manifest_integrity() - Validate ML manifest structure and no forbidden keys.
- validate_export_quality() - Validate review vs RAG export: both non-empty, not identical, RAG more compact.
- validate_cross_artifact_references() - Validate that all cross-references between knowledge_events, evidence_index, and rule_cards resolve.

## pipeline/vlm_translator.py
- get_vlm_prompt() - Get vlm prompt.
- encode_image() - Encode image.
- _translate_with_provider() - Translate with provider.
- translate_openai() - Translate openai.
- translate_gemini() - Translate gemini.
- translate_setra() - Translate setra.
- write_vlm_prompt() - Write the VLM prompt file for agent processing. Returns (prompt_path, response_path).
- run_translator() - Run translator.

## scripts/benchmark_models.py
- No functions defined in this file.

## scripts/build_benchmark_frame_prompt.py
- _parse_timestamp() - Parse VTT timestamps (HH:MM:SS.mmm) into seconds.
- _clean_transcript_line() - Remove enriched visual context or empty transcript lines.
- load_vtt_cues() - Parse a basic WebVTT file into cues with timestamps.
- extract_transcript_window() - Split transcript lines into before/after buckets for the given window.
- build_transcript_prompt() - Build a transcript-assisted prompt for the benchmark frame.
- build_prompt_from_vtt() - Build prompt from vtt.
- main() - Main.

## scripts/count_video_duration.py
- get_duration_seconds() - Get video duration in seconds using ffprobe. Returns None on error.
- main() - Main.

## scripts/dump_benchmark_payload.py
- main() - Main.

## scripts/list_mlx_models.py
- main() - Main.

## scripts/run_ide_batch_loop.py
- frame_path_to_key() - Extract 6-digit frame key from path like .../frame_000171.jpg
- frame_key_to_timestamp() - Frame key (1-based index at 1fps) -> HH:MM:SS. Frame 1 = 00:00:01.
- write_no_change_batch_response() - Write a JSON object keyed by frame number with material_change false and timestamps.
- main() - Main.

## scripts/run_task_gemini.py
- resolve_path() - Return path that exists: try as-is, then relative to cwd.
- main() - Main.

## scripts/validate_11phase2.py
- No functions defined in this file.

## scripts/validate_gemini.py
- _run_tier_check() - Send _TIER_CHECK_REQUESTS rapid requests; return (success_count, rate_limited_count).
- main() - Main.

## src/tim_class_pass/__init__.py
- No functions defined in this file.

## src/tim_class_pass/main.py
- main() - Main.

## src/tim_class_pass/usage_report.py
- main() - Main.

## tests/conftest.py
- load_json() - Load JSON file; return dict or list.
- lesson_minimal_root() - Lesson minimal root.
- lesson_multi_concept_root() - Lesson multi concept root.
- lesson_edge_sparse_root() - Lesson edge sparse root.
- temp_video_root() - Temporary video root for pipeline output layout (PipelinePaths).
- lesson2_output_dir() - Path to output_intermediate for Lesson 2 (12-phase2 6b).
- run_lesson2_pipeline() - Run Component 2 pipeline for Lesson 2; writes to lesson2_output_dir.parent as output-root.

## tests/integration/__init__.py
- No functions defined in this file.

## tests/integration/test_lesson2_artifact_regression.py
- load_json() - Load json.
- _assert_lesson2_artifacts() - Shared Phase 2A assertion block (brief lines 479-564).
- test_lesson2_final_artifacts_regression() - 6a: Assert Phase 2A guarantees on existing Lesson 2 artifacts; skip if any missing.
- test_lesson2_final_artifacts_regression_full() - 6b: Run pipeline then assert Phase 2A guarantees. Run only when RUN_LESSON2_REGRESSION=1.

## tests/test_analyze.py
- _write_image() - Write image.
- test_analyze_frame_with_on_event_emits_stages_and_returns_same_result() - With on_event, analyze_frame must emit start/end for extract and relevance and return same dict.
- test_analyze_frame_calls_extract_then_relevance() - Test analyze frame calls extract then relevance.
- test_analyze_frame_marks_irrelevant_changes() - Test analyze frame marks irrelevant changes.
- test_normalize_preserves_no_change() - Raw no-change response must stay no-change after normalization (no promotion to change).
- test_ensure_material_change_not_overwritten_by_lesson_relevant() - material_change must not be derived from lesson_relevant (semantic separation).
- test_normalize_preserves_rich_visual_facts_and_interpretation() - Richer current_state.visual_facts and trading_relevant_interpretation must survive normalization.
- test_normalize_schema_shaped_but_noncanonical_output() - Schema-shaped Qwen output should still be canonicalized for downstream use.
- test_gemini_frame_591_shape_alignment() - Representative shape from Gemini batch 000591: rich visual_facts, trading_relevant_interpretation, material_change.
- _load_gold() - Load gold.
- test_gold_591_normalization_preserves_representation_type() - After normalization, abstract_bar_diagram must stay abstract_bar_diagram (not collapse to candlestick_sketch).
- test_gold_591_normalization_preserves_visual_facts_density() - After normalization, visual_facts must contain all 6 Gemini sentences (density gate).
- test_gold_591_normalization_preserves_interpretation_list() - After normalization, trading_relevant_interpretation must be a list with >= 2 items.
- test_gold_591_normalization_preserves_structural_pattern() - After normalization, structural_pattern_visible must include 'price_action_around_level'.
- test_gold_591_normalization_preserves_conceptual_level_values() - After normalization, level_values from Gemini reference must not be discarded.
- test_gold_591_normalization_preserves_conceptual_stop_values() - After normalization, stop_values from Gemini reference must not be discarded.
- test_gold_591_normalization_preserves_drawn_objects_structure() - After normalization, drawn_objects from dict-of-lists Gemini format must yield structured items.
- test_gold_591_normalization_preserves_annotations_with_location() - After normalization, visible_annotations from Gemini's structured format must preserve text content.
- test_gold_591_educational_event_type_passthrough() - Gemini-style educational_event_type items that are in our vocab must pass through normalization.
- test_gold_591_conceptual_entities_from_gemini_format() - Object-shaped level_values and stop_values from Gemini must survive normalization as non-empty lists.
- test_canonical_visual_type_abstract_bar_diagram_variants() - All common model phrasings for abstract_bar_diagram must normalize to the canonical value.
- test_canonical_visual_type_candlestick_sketch_variants() - Test canonical visual type candlestick sketch variants.
- test_canonical_visual_type_hand_drawn_variants() - Test canonical visual type hand drawn variants.
- test_structural_pattern_string_becomes_list() - When Gemini returns structural_pattern_visible as a string, normalization must convert to list.
- test_visible_annotations_dict_objects_preserved() - Structured annotation objects {text, location, language} must be preserved through normalization.
- test_n_a_entity_values_become_empty_lists() - 'N/A' values in extracted_entities must be normalized to empty lists.
- test_screen_type_chart_with_instructor_passthrough() - 'chart_with_instructor' must be accepted as a valid screen_type.
- test_gemini_expanded_educational_event_types_passthrough() - Gemini-expanded event types (concept_introduction, level_explanation, stop_loss_placement) must pass through.

## tests/test_canonicalization.py
- TestNormalizeLabel (class) - Tests for normalize_label: lowercase, whitespace collapse, punctuation strip, NFKC.
- TestLookupCanonical (class) - Tests for lookup_canonical: known Russian/English terms, case insensitivity, unknown returns None.
- TestMakeCanonicalId (class) - Tests for make_canonical_id: known concepts, Russian terms, fallback slugification.
- TestCanonicalizeHelpers (class) - Tests for canonicalize_concept/subconcept: None handling, known terms, fallback.
- TestCanonicalizeShortStatement (class) - Tests for canonicalize_short_statement: condition/invalidation prefixes.
- TestClassifyRuleType (class) - Tests for classify_rule_type: all event types mapped, unknown returns None.
- TestLexiconCoverage (class) - Tests that all CONCEPT_ALIASES keys are lowercase and values are valid slugs.
- TestNoEnglishLabels (class) - Tests that canonical IDs are ASCII with no spaces.

## tests/test_compare.py
- _write_image() - Write image.
- test_compare_images_skips_near_identical_frames() - Test compare images skips near identical frames.
- test_compare_images_detects_significant_change() - Test compare images detects significant change.
- test_compare_images_writes_structural_artifacts() - Test compare images writes structural artifacts.

## tests/test_component2_pipeline.py
- _sample_json_path() - Sample json path.
- test_filter_visual_events_sample_json_uses_instructional_frames_only() - Test filter visual events sample json uses instructional frames only.
- test_create_lesson_chunks_carries_previous_visual_state() - Test create lesson chunks carries previous visual state.
- test_invalidation_filter_keeps_unknown_frame_with_annotation_signal() - Test invalidation filter keeps unknown frame with annotation signal.
- test_build_user_prompt_contains_xml_sections_and_timestamps() - Test build user prompt contains xml sections and timestamps.
- test_parse_enriched_markdown_chunk_validates_json() - Test parse enriched markdown chunk validates json.
- test_assemble_video_markdown_adds_header_and_tags() - Test assemble video markdown adds header and tags.
- test_run_component2_pipeline_writes_outputs() - Test run component2 pipeline writes outputs.
- test_component2_main_help() - Test component2 main help.
- test_pipeline_written_knowledge_events_contains_phase2a_fields() - Saved knowledge_events.json from a pipeline run contains Phase 2A fields (run after full Component 2).
- test_pipeline_outputs_not_all_events_are_line_confidence() - Pipeline output has a mix of line/span/chunk confidence (run after full Component 2).
- test_knowledge_events_json_preserves_line_anchors() - Build collection with source_line_indices, save to knowledge_events.json, assert line-anchored event.
- test_final_saved_knowledge_events_contain_evidence_refs_after_evidence_linking() - After evidence linking, backfill overwrites knowledge_events.json with evidence_refs populated.
- test_final_saved_evidence_contains_linked_rule_ids_after_rule_build() - After rule cards are built, backfill overwrites evidence_index.json with linked_rule_ids populated.

## tests/test_concept_graph.py
- _minimal_rule() - Minimal rule.
- _relation_tuples() - Relation tuples.
- _node_ids() - Node ids.
- test_create_concept_and_subconcept_nodes() - RuleCardCollection with one rule concept='level', subconcept='level_rating'; graph has nodes level and level_rating.
- test_parent_child_relation() - Single rule with concept and subconcept; relations contain parent_of and child_of.
- test_sibling_related_relation() - Two rules same concept 'level', subconcepts 'level_recognition' and 'level_rating'; related_to in both directions.
- test_precedes_relation_from_source_order() - Two rules same concept, different subconcepts, source_chunk_indexes [1] and [5]; first precedes second.
- test_contrasts_with_relation() - Two rules with subconcepts false_breakout and break_confirmation (name pair); contrasts_with in one direction.
- test_relation_dedupe() - Two rules with same concept and subconcept; exactly one parent_of (and one child_of) relation.
- test_graph_serialization() - build_concept_graph then ConceptGraph.model_validate_json(graph.model_dump_json()); lesson_id and node count match.
- test_empty_rules_produce_empty_graph_and_serializes() - With empty RuleCardCollection, build_concept_graph returns graph with lesson_id, no nodes, no relations; it serializes.
- test_save_concept_graph_writes_file() - save_concept_graph writes JSON to path; empty graph round-trips.

## tests/test_corpus.py
- TestSchemaContract (class, 6 tests) - Schema versions load correctly, LessonRecord/CorpusMetadata validate, re-exported KnowledgeEvent/RuleCard work.
- TestLessonRegistry (class, 4 tests) - Registry discovers lessons with correct counts, skips empty dirs, produces serializable output.
- TestDeterministicIds (class, 6 tests) - Slugification is stable, global IDs are deterministic, adding a lesson does not change existing IDs, node/relation IDs are cross-lesson.
- TestReferentialIntegrity (class, 4 tests) - Rule->event, rule->evidence, evidence->rule references resolve in corpus exports. Graph relation endpoints exist in node set.
- TestCorpusExports (class, 4 tests) - JSONL files exist and are non-empty, metadata/schema/validation/enrichment files present, counts in metadata match.
- TestConceptDedup (class, 3 tests) - Same concept in two lessons maps to one canonical node with both lessons in provenance. Aliases merged. Overlap report generated.
- TestValidatorCatchesBadData (class, 5 tests) - Missing required artifact detected, strict mode promotes warnings, duplicate global IDs caught, orphan evidence warned, dangling graph relations detected.

## tests/test_config.py
- test_default_workers_use_half_cpu() - Test default workers use half cpu.
- test_config_exposes_stage_specific_provider_and_model_defaults() - Test config exposes stage specific provider and model defaults.
- test_get_config_for_video_returns_visual_defaults() - get_config_for_video returns visual_* keys with expected defaults when no pipeline.yml.

## tests/test_dense_analyzer.py
- _write_frame() - Write frame.
- _setup_video() - Setup video.
- _write_llm_queue() - Write llm queue.
- test_run_analysis_prefills_non_queue_frames() - Test run analysis prefills non queue frames.
- test_run_analysis_only_analyzes_queue_keys() - Test run analysis only analyzes queue keys.
- test_run_analysis_persists_request_usage() - Test run analysis persists request usage.
- _setup_video_3frames() - Setup video 3frames.
- _setup_video_4frames() - Setup video 4frames.
- test_batch_carry_forward_passes_batch_relevant_state() - Within-batch context carry-forward: when frame 000001 is relevant and 000002 comes next
- test_partition_queue_keys_splits_in_stable_order() - Test partition queue keys splits in stable order.
- test_chunk_workers_are_capped_to_cpu_minus_two() - None uses cpu_count-2; explicit values are capped at 8 (see dense_analyzer).
- test_chunk_mode_reprocesses_boundary_and_replays_chunk() - Test chunk mode reprocesses boundary and replays chunk.
- test_chunk_mode_disabled_falls_back_to_sequential() - Test chunk mode disabled falls back to sequential.

## tests/test_evidence_linker.py
- test_adapt_visual_events_from_chunks_preserves_chunk_index_and_fields() - Given a mock chunk in real format, verify AdaptedVisualEvents are created correctly.
- test_enrich_visual_event_from_dense_analysis_adds_metadata() - Given a visual event and matching dense analysis entry, verify enrichment preserves frame_key and adds richer metadata.
- test_enrich_visual_event_missing_frame_key_unchanged() - If no dense analysis entry for frame_key, return event unchanged.
- test_group_visual_events_same_chunk_close_time_one_candidate() - Same chunk, same example type, close timestamps -> one VisualEvidenceCandidate.
- test_group_visual_events_split_on_chunk_or_gap() - Different chunk or large time gap -> multiple candidates.
- test_extract_visual_concept_hints_false_breakout_level() - Annotation text like 'false breakout level' yields concept hints including level and false_breakout.
- test_score_candidate_event_match_above_threshold_same_chunk_concept() - Same chunk + matching concept -> score >= 0.50.
- test_score_candidate_event_match_below_threshold_different_chunk_unrelated_concept() - Different chunk + unrelated concept -> score < 0.50.
- test_candidate_to_evidence_ref_has_timestamps_frame_ids_source_event_ids() - Final EvidenceRef contains timestamps, frame_ids, source_event_ids, compact summary, example role.
- test_evidence_index_serialization() - EvidenceIndex serializes to JSON and parses back.
- test_enable_evidence_linking_false_no_evidence_files() - When enable_evidence_linking=False, pipeline does not write evidence files (legacy unchanged).
- test_enable_evidence_linking_true_with_knowledge_events_writes_evidence_files() - When enable_evidence_linking and enable_knowledge_events are True, evidence_index and evidence_debug are written.
- test_load_chunks_json_valid_array() - load_chunks_json returns list of dicts.
- test_load_chunks_json_not_array_raises() - load_chunks_json raises when root is not an array.
- test_save_evidence_index_and_debug() - save_evidence_index and save_evidence_debug write files.
- test_build_evidence_index_returns_index_and_debug() - build_evidence_index returns EvidenceIndex and debug list from chunks and knowledge events.
- test_load_knowledge_events() - load_knowledge_events returns list of KnowledgeEvent from KnowledgeEventCollection JSON.
- test_summarize_visual_candidate_for_evidence() - summarize_visual_candidate_for_evidence produces short summary from events and hints.
- test_backfill_knowledge_event_evidence_refs_populates_events() - Test backfill knowledge event evidence refs populates events.
- test_backfill_evidence_linked_rule_ids_populates_evidence() - Test backfill evidence linked rule ids populates evidence.
- test_infer_example_role_unlinked_generic_defaults_to_illustration() - Test infer example role unlinked generic defaults to illustration.
- test_infer_example_role_intro_or_setup_returns_illustration() - Candidate with intro/overview in summary or hints gets illustration, not counterexample.
- test_infer_example_role_diagram_without_invalidation_returns_illustration() - Diagram/hand_drawing visual with definition-linked events and no strong invalidation content  illustration.
- test_infer_example_role_counterexample_only_with_invalidation_event() - Counterexample assigned when linked event has invalidation/exception/warning type.
- test_intro_slide_with_overlay_is_illustration_not_counterexample() - 06-phase1: intro slide with overlay stays illustration, not counterexample.
- test_explicit_failed_breakout_can_be_counterexample() - 06-phase1: explicit failed breakout with invalidation event can be counterexample.

## tests/test_exporters.py
- _minimal_rule() - Minimal rule.
- _minimal_evidence() - Minimal evidence.
- rule_cards_path() - Rule cards path.
- evidence_index_path() - Evidence index path.
- test_load_rule_cards() - Test load rule cards.
- test_load_evidence_index() - Test load evidence index.
- test_load_knowledge_events_missing() - Test load knowledge events missing.
- test_load_knowledge_events_present() - Test load knowledge events present.
- test_build_export_context() - Test build export context.
- test_group_rule_cards_for_export() - Test group rule cards for export.
- test_sort_rule_cards_deterministic() - Test sort rule cards deterministic.
- test_format_bullet_block() - Test format bullet block.
- test_dedupe_preserve_order() - Test dedupe preserve order.
- test_clean_markdown_text() - Test clean markdown text.
- test_render_review_markdown_deterministic_includes_structure() - Test render review markdown deterministic includes structure.
- test_review_empty_sections_omitted() - Test review empty sections omitted.
- test_render_rag_markdown_deterministic_compact() - Test render rag markdown deterministic compact.
- test_render_review_markdown_deterministic_returns_empty_usage() - Test render review markdown deterministic returns empty usage.
- test_render_rag_markdown_deterministic_returns_empty_usage() - Test render rag markdown deterministic returns empty usage.
- test_ensure_parent_dir_and_save_review_markdown() - Test ensure parent dir and save review markdown.
- test_save_rag_markdown() - Test save rag markdown.
- test_save_export_debug() - Test save export debug.
- test_write_export_manifest() - Test write export manifest.
- test_export_review_markdown_writes_file() - Test export review markdown writes file.
- test_export_rag_markdown_writes_file() - Test export rag markdown writes file.
- test_export_review_markdown_with_missing_knowledge_events() - Test export review markdown with missing knowledge events.
- test_llm_render_receives_structured_inputs_only() - When use_llm=True, process_rule_cards_markdown_render is called with only structured inputs (no raw chunks).
- test_deterministic_export_does_not_require_raw_chunks() - Deterministic render uses only ExportContext (rule_cards + evidence); no chunk/transcript input.

## tests/test_knowledge_builder.py
- test_extraction_result_to_knowledge_events_uses_line_indices_for_tighter_timestamps() - Test extraction result to knowledge events uses line indices for tighter timestamps.
- test_extraction_result_to_knowledge_events_falls_back_to_source_quote_match() - Test extraction result to knowledge events falls back to source quote match.
- test_extraction_result_to_knowledge_events_invalid_line_indices_fall_back_to_chunk_bounds() - Test extraction result to knowledge events invalid line indices fall back to chunk bounds.
- _real_shape_chunk() - Chunk dict matching LessonChunk.model_dump() / *.chunks.json.
- test_adapt_chunk_from_real_shape() - Test adapt chunk from real shape.
- test_build_transcript_text_normalizes_blanks_and_spaces() - Test build transcript text normalizes blanks and spaces.
- test_summarize_visual_events_non_empty_capped_no_raw_dump() - Test summarize visual events non empty capped no raw dump.
- _sample_adapted_chunk() - Sample adapted chunk.
- test_extraction_mapping_and_deterministic_ids() - Test extraction mapping and deterministic ids.
- test_provenance_metadata_present() - Test provenance metadata present.
- test_collection_serialization_roundtrip() - Test collection serialization roundtrip.
- test_feature_flag_safe_when_disabled() - When enable_knowledge_events=False, pipeline does not call knowledge builder or write knowledge files.
- test_blank_and_short_statements_skipped() - Test blank and short statements skipped.
- test_dedupe_statements_removes_duplicates() - Test dedupe statements removes duplicates.
- test_normalize_statement_text() - Test normalize statement text.
- test_load_chunks_json() - Test load chunks json.
- test_save_knowledge_events_preserves_phase2a_fields() - Phase 2A fields survive save/load round-trip.
- test_extraction_result_to_knowledge_events_emits_phase2a_fields() - Builder populates Phase 2A fields on KnowledgeEvent.
- test_compact_explicit_anchor_gets_line_confidence() - Test compact explicit anchor gets line confidence.
- test_broader_local_anchor_gets_span_confidence() - Test broader local anchor gets span confidence.
- test_sparse_anchor_downgrades_to_chunk() - Test sparse anchor downgrades to chunk.
- test_line_confidence_for_compact_dense_span() - 11-phase2: span_width <= 3 and density >= 0.60 -> line.
- test_span_confidence_for_width_four() - 11-phase2: span_width >= 4 -> span.
- test_chunk_confidence_without_line_bounds() - 11-phase2: no line bounds -> chunk.
- test_save_knowledge_events_and_debug() - Test save knowledge events and debug.
- test_build_knowledge_events_from_file_uses_adapt_and_extract() - Test build knowledge events from file uses adapt and extract.

## tests/test_labeling_manifest.py
- test_labeling_manifest_skips_generic_intro_counterexample() - 06-phase1: generic intro visual marked counterexample does not get a labeling task.

## tests/test_llm_processor.py
- test_build_legacy_markdown_prompt_produces_expected_structure() - Test build legacy markdown prompt produces expected structure.
- test_build_knowledge_extract_prompt_contains_transcript_and_visuals() - Test build knowledge extract prompt contains transcript and visuals.
- test_build_knowledge_extract_prompt_renders_numbered_transcript_lines() - Test build knowledge extract prompt renders numbered transcript lines.
- test_parse_knowledge_extraction_accepts_source_line_indices_and_source_quote() - Test parse knowledge extraction accepts source line indices and source quote.
- test_build_markdown_render_prompt_uses_rule_cards_and_evidence() - Test build markdown render prompt uses rule cards and evidence.
- test_call_provider_for_mode_returns_parsed_and_usage() - Test call provider for mode returns parsed and usage.
- test_process_chunk_knowledge_extract_returns_chunk_extraction_result() - Test process chunk knowledge extract returns chunk extraction result.
- test_process_rule_cards_markdown_render_returns_markdown_render_result() - Test process rule cards markdown render returns markdown render result.
- test_parse_legacy_enriched_markdown_chunk() - Test parse legacy enriched markdown chunk.
- test_write_llm_debug_writes_rows() - Test write llm debug writes rows.
- test_write_llm_debug_legacy_debug_rows() - Test write llm debug legacy debug rows.
- test_backward_compatibility_process_chunks_alias() - Test backward compatibility process chunks alias.

## tests/test_main.py
- test_key_to_timestamp() - Test key to timestamp.
- test_pipeline_main_help() - Main CLI (Click) prints help and exits 0.
- test_pipeline_main_step3_runs_component2() - Test pipeline main step3 runs component2.

## tests/test_ml_prep.py
- test_infer_candidate_features_level_rating() - RuleCard with concept=level, subconcept=level_rating yields expected feature names.
- test_distribute_example_refs_for_ml() - Evidence refs: only positive and counterexample (with explicit negative) in buckets (06-phase1).
- test_build_labeling_guidance() - Rule with conditions and invalidation produces compact guidance with both phrases.
- test_enrich_rule_card_for_ml_preserves_provenance() - Enriching a rule keeps source_event_ids, evidence_refs, confidence unchanged.
- test_build_ml_manifest() - Generated manifest has lesson_id, rules, examples and is JSON-serializable.
- test_compute_ml_readiness_coverage() - Coverage counts match a small sample.
- test_save_ml_manifest() - save_ml_manifest writes valid JSON and creates parent dir.
- test_feature_flag_safe_no_ml_prep() - With enable_ml_prep=False, no ML manifest is created when pipeline would not run ML prep.
- test_enrich_rule_card_collection_for_ml() - Whole-collection enrichment returns new collection with enriched rules. Evidence must be ML-eligible (04-phase1).
- test_build_evidence_lookup() - Evidence lookup maps evidence_id to EvidenceRef.
- test_is_evidence_ml_eligible_false_when_empty_linked_rule_ids() - Ref with empty linked_rule_ids is not ML-eligible.
- test_is_evidence_ml_eligible_false_when_empty_source_event_ids() - Ref with empty source_event_ids is not ML-eligible.
- test_is_evidence_ml_eligible_false_when_illustration_role() - Ref with example_role illustration is not ML-eligible.
- test_is_evidence_ml_eligible_true_when_eligible_positive_example() - Ref with positive_example, linked to rule, non-empty source_event_ids, non-intro summary  eligible.
- test_is_evidence_ml_eligible_false_when_intro_summary() - 11-phase2: intro summary no longer gated; positive_example with links is eligible.
- test_distribute_example_refs_for_ml_excludes_ineligible_counterexample() - Counterexample ref without linked_rule_ids is not placed in negative_example_refs.
- test_distribute_example_refs_for_ml_includes_eligible_counterexample() - Eligible counterexample ref (explicit negative in summary) is placed in negative_example_refs (06-phase1).
- test_generic_teaching_visual_not_ml_eligible() - 06-phase1: illustration with generic intro summary is not ML eligible.
- test_generic_visual_marked_counterexample_is_rejected_by_ml_gate() - 11-phase2: counterexample with links is eligible (generic summary no longer gated).
- test_explicit_negative_evidence_is_ml_eligible() - 06-phase1: counterexample with explicit negative in summary is ML eligible.
- test_illustration_is_not_ml_eligible() - 11-phase2: illustration is not ML-eligible (brief dict-based).
- test_positive_example_is_ml_eligible() - 11-phase2: positive_example with links is ML-eligible (brief dict-based).
- test_labeling_manifest_empty_when_only_illustrations() - 11-phase2: labeling manifest has no tasks when all evidence is illustration.
- test_ml_examples_excludes_illustrations() - 11-phase2: build_ml_examples excludes illustration (brief).

## tests/test_mlx_client.py
- test_chat_image_converts_path_to_base64_and_sends_image_base64() - When given an image path, client must read the file, encode as base64, and send image_base64 to /api/v1/chat (no image_path).
- test_chat_image_with_on_event_emits_events_after_non_stream_response() - With on_event, we use non-streaming (no stream in payload); after full response we emit start/chunk/end.

## tests/test_output_layout.py
- test_pipeline_paths_deterministic() - Test pipeline paths deterministic.
- test_ensure_output_dirs() - Test ensure output dirs.
- test_legacy_and_new_rag_paths_do_not_conflict() - Test legacy and new rag paths do not conflict.
- test_atomic_write_json() - Test atomic write json.
- test_build_export_manifest_only_existing() - Test build export manifest only existing.

## tests/test_parallelization.py
- _touch() - Touch.
- test_dense_capturer_segments_and_renumbers() - Test dense capturer segments and renumbers.
- test_dense_capturer_caps_workers() - Test dense capturer caps workers.
- test_structural_compare_parallel_path() - Test structural compare parallel path.
- test_frame_extractor_uses_worker_cap() - Test frame extractor uses worker cap.

## tests/test_phase1_export_validation.py
- test_placeholder_rule_removed_before_final_export() - Placeholder rule is filtered out by validate_rule_card_collection_for_export.
- test_ml_enrichment_no_guidance_for_invalid_rule() - Invalid rule gets no labeling_guidance, no candidate_features, no ML example refs.
- test_ml_manifest_skips_invalid_rules() - build_ml_manifest omits invalid rules from manifest['rules'].
- test_false_breakout_not_auto_counterexample() - Visual with 'false breakout' and rule_statement link is not labeled counterexample.
- test_post_ml_validation_catches_bad_rules() - Export validation helper quarantines invalid rule from enriched collection.
- test_final_evidence_export_rejects_empty_source_event_ids() - Test final evidence export rejects empty source event ids.
- test_final_evidence_export_rejects_empty_linked_rule_ids() - Test final evidence export rejects empty linked rule ids.
- test_final_knowledge_export_rejects_placeholder_event() - Test final knowledge export rejects placeholder event.
- test_final_knowledge_export_allows_empty_source_event_ids_when_event_is_otherwise_valid() - Valid knowledge event with empty source_event_ids is still allowed by export validation (05-phase1).

## tests/test_phase1_validation.py
- test_reject_placeholder_rule_card() - RuleCard with placeholder rule_text and empty source_event_ids must fail validation.
- test_accept_minimal_valid_rule_card() - Rule with non-empty rule_text and non-empty source_event_ids passes validation.
- test_reject_empty_knowledge_event_text() - Event with empty or placeholder normalized_text is rejected by validator (or builder does not emit).
- test_reject_evidence_with_no_frames_and_no_raw_visual_ids() - EvidenceRef with both frame_ids and raw_visual_event_ids empty must fail validation.
- test_allow_unlinked_evidence_pre_reduction() - EvidenceRef with empty linked_rule_ids passes when allow_unlinked_rules=True (pre-reduction).
- test_blank_labeling_guidance_for_invalid_rule() - Invalid/placeholder rule is quarantined and does not receive labeling_guidance in final artifact.
- test_placeholder_helpers() - normalize_text and is_placeholder_text behave as specified.

## tests/test_pipeline_cross_artifact_refs.py
- _load_knowledge_events() - Load knowledge events.
- _load_evidence_index() - Load evidence index.
- _load_rule_cards() - Load rule cards.
- test_cross_artifact_references_validator_consistent_returns_empty() - When knowledge_events, evidence_index, and rule_cards are consistent, validator returns no errors.
- test_knowledge_event_source_event_ids_are_not_required_for_cross_artifact_integrity() - Events can be roots; evidence and rules point to them. Empty KnowledgeEvent.source_event_ids is valid (05-phase1).
- test_evidence_source_events_resolve() - Every EvidenceRef.source_event_ids id exists in knowledge_events.events.
- test_rule_source_events_resolve() - Every RuleCard.source_event_ids id exists in knowledge_events.events.
- test_rule_evidence_refs_resolve() - Every RuleCard.evidence_refs id exists in evidence_index.evidence_refs.
- test_ml_example_refs_resolve() - Every positive/negative/ambiguous_example_refs id exists in evidence_index.evidence_refs.
- test_cross_artifact_references_validator_rejects_broken_refs() - Validator returns errors when a rule references a non-existent source event.

## tests/test_pipeline_degraded_inputs.py
- test_sparse_transcript_pipeline_survives() - Load lesson_edge_sparse chunks and dense_analysis; build knowledge_events from minimal
- test_weak_visuals_pipeline_survives() - Use chunks with strong transcript but few/empty visual_events. Run evidence_linker
- test_ambiguous_examples_do_not_become_positive() - Use in-memory rule_cards with ambiguous_example_refs and evidence with
- test_missing_concepts_do_not_crash_pipeline() - Use in-memory KnowledgeEventCollection with some events having concept=None.

## tests/test_pipeline_exports.py
- lesson_minimal_rule_cards_path() - Lesson minimal rule cards path.
- lesson_minimal_evidence_index_path() - Lesson minimal evidence index path.
- lesson_minimal_knowledge_events_path() - Lesson minimal knowledge events path.
- exported_review_markdown() - Produce review markdown from lesson_minimal fixtures (deterministic, no LLM).
- exported_rag_markdown() - Produce RAG markdown from lesson_minimal fixtures (deterministic, no LLM).
- test_review_markdown_structure() - Review markdown has concept/rule structure (headers, rule, level) and optional provenance.
- test_rag_markdown_compact() - RAG markdown is more compact than review, or validate_export_quality passes.
- test_export_outputs_distinct() - validate_export_quality(review_md, rag_md) returns no errors.
- test_no_transcript_replay_in_markdown() - Final markdown does not contain raw chunk transcript markers or long verbatim replay.
- test_markdown_passes_visual_spam_validator() - validate_markdown_visual_compaction on review and RAG returns empty or acceptably small flagged list.

## tests/test_pipeline_inspection.py
- test_inspect_stages_resolves_core_modules() - Stage inspection resolves main pipeline and Step 3 callables.
- test_pipeline_paths_matches_output_structure() - Path contract matches current output_intermediate/ and output_rag_ready/ layout.
- test_preflight_report_generation() - prepare_component2_run writes pipeline_inspection.json with expected keys.
- test_build_report_includes_artifact_checks() - build_report with lesson_name includes lesson-specific artifact paths.
- test_feature_flags_default_to_legacy() - All new feature flags default to legacy/disabled behavior.
- test_run_component2_pipeline_creates_inspection_and_same_output_keys() - Preflight runs and run_component2_pipeline still returns the same output dict keys.

## tests/test_pipeline_integration.py
- test_step3_to_step4_integration() - Build evidence index from knowledge_events, chunks, dense_analysis; validate integrity and cross-refs.
- test_step4_to_step5_integration() - Build rule cards from knowledge_events + evidence_index; assert rules and source_event_ids.
- test_rule_cards_to_concept_graph_integration() - Build concept graph from rule_cards; assert nodes/relations and validate_concept_graph_integrity.
- test_rule_cards_to_ml_prep_integration() - Enrich rule cards for ML and build ML manifest; assert enriched rules and manifest.
- test_rule_cards_to_exporters_integration() - Export review and RAG markdown (deterministic); assert non-empty output.
- test_full_structured_pipeline_smoke() - Copy fixtures to temp layout, run pipeline from knowledge+evidence to exports; validate all artifacts.

## tests/test_pipeline_invariants.py
- _load_lesson_minimal_root() - Use pytest fixture path if provided, else fallback to fixtures/lesson_minimal.
- test_every_knowledge_event_has_event_id() - Load knowledge_events.json as KnowledgeEventCollection; assert every event has event_id.
- test_every_knowledge_event_has_phase1_provenance_fields() - KnowledgeEvent provenance in Phase 1 is event_id + lesson_id + chunk_index + timestamps, not source_event_ids.
- test_every_evidence_ref_has_evidence_id() - Load evidence_index.json; assert every evidence_ref has evidence_id.
- test_every_rule_card_has_rule_id() - Load rule_cards.json; assert every rule has rule_id.
- test_every_rule_card_has_source_event_ids() - Load rule_cards; assert every rule has non-empty source_event_ids.
- test_every_evidence_ref_has_visual_provenance() - Load evidence_index; assert every ref has frame_ids or raw_visual_event_ids.
- test_every_evidence_ref_has_source_event_ids() - Load evidence_index; assert every ref has source_event_ids.
- test_confidence_fields_valid() - For knowledge_events and rule_cards, assert confidence in (low, medium, high) and confidence_score in [0,1] if present.
- test_no_visual_blob_leakage_in_structured_outputs() - Load knowledge_events, evidence_index, rule_cards; run validate_no_visual_blob_leakage on each; assert no errors.
- test_visual_summaries_compact() - Load rule_cards; assert every rule.visual_summary has len <= MAX_VISUAL_SUMMARY_LENGTH if present.
- test_export_outputs_distinct() - Call exporters to produce review_md and rag_md from fixture, then validate_export_quality; assert no errors.

## tests/test_pipeline_optional_live.py
- _has_provider_credentials() - True if at least one supported provider has an API key set.
- _skip_if_no_credentials() - Skip if no credentials.
- lesson_minimal_chunks_path() - Lesson minimal chunks path.
- test_live_provider_extraction_optional() - If credentials not set, skip. Otherwise call real knowledge extraction for one chunk
- test_live_provider_markdown_render_optional() - If credentials not set, skip. Otherwise call real markdown render with minimal input;

## tests/test_pipeline_regression.py
- _load_fixture_artifacts() - Load knowledge_events, evidence_index, rule_cards from a fixture root with Pydantic.
- test_lesson_minimal_regression_counts() - Assert lesson_minimal fixture meets golden min counts and concept/rule-id constraints.
- test_lesson_multi_concept_regression_counts() - Assert lesson_multi_concept fixture meets golden min counts and concept/rule-id constraints.
- test_exporter_output_structure_regression() - Run exporters from lesson_minimal to tmp_path; assert RAG line cap and structural elements.

## tests/test_provenance.py
- test_dedupe_preserve_order() - Test dedupe preserve order.
- test_compact_nonempty_strs() - Test compact nonempty strs.
- test_compact_nonempty_ints() - Test compact nonempty ints.
- test_prune_none_values() - Test prune none values.
- test_build_knowledge_event_provenance() - Test build knowledge event provenance.
- test_build_evidence_ref_provenance() - Test build evidence ref provenance.
- test_build_rule_card_provenance() - Test build rule card provenance.
- test_validate_rule_card_provenance_warns_on_missing_source_ids() - Test validate rule card provenance warns on missing source ids.
- test_validate_knowledge_event_provenance_warnings() - Test validate knowledge event provenance warnings.
- test_validate_evidence_ref_provenance_warnings() - Test validate evidence ref provenance warnings.
- test_compute_provenance_coverage() - Test compute provenance coverage.
- test_merge_source_event_ids_deduped_and_ordered() - Test merge source event ids deduped and ordered.
- test_merge_evidence_refs_deduped_and_ordered() - Test merge evidence refs deduped and ordered.
- test_format_compact_provenance() - Test format compact provenance.
- test_format_compact_provenance_returns_none_when_empty() - Test format compact provenance returns none when empty.

## tests/test_rule_compat.py
- TestContradictoryPositiveBlocked (class, 5 tests) - Bullish/bearish conflict blocks positive example; single-rule always compatible; same direction allowed; breakout_up vs down blocked; unknown multi-rule blocked.
- TestMLSafetyConservative (class, 5 tests) - Conflicting directions unsafe; unknown multi-rule unsafe; single-rule safe; no linked rules unsafe; compatible multi-rule safe.
- TestInferRuleDirection (class, 9 tests) - Keyword detection for bullish, bearish, breakout_up/down, reversal_up/down, neutral, unknown, empty.
- TestAreDirectionsConflicting (class, 4 tests) - Same not conflicting; bullish/bearish conflicting; unknown always conflicting; neutral with itself not conflicting.
- TestRussianBackfill (class, 6 tests) - KnowledgeEvent/RuleCard/EvidenceRef *_ru fields populated when Russian, default None otherwise.
- TestLanguageAwareSummary (class, 5 tests) - Russian summary goes to summary_ru; English does not; legacy compact_visual_summary preserved; ambiguous/empty stays safe; mixed language detection.

## tests/test_support_policy.py
- TestDefaultEventPolicy (class, 3 tests) - All event types present, theory types require no evidence, example requires evidence.
- TestClassifyTeachingMode (class, 6 tests) - definition→theory, comparison→theory, example→example, rule_statement mixed with visual language, defaults.
- TestClassifyEvidenceRequirement (class, 4 tests) - example mode requires, definition none, rule_statement optional, unknown defaults.
- TestClassifySupportBasis (class, 5 tests) - transcript_primary, transcript_plus_visual, visual_primary, inferred, edge thresholds.
- TestClassifyTranscriptSupportLevel (class, 5 tests) - strong/moderate/weak boundaries.
- TestClassifyVisualSupportLevel (class, 6 tests) - none, illustration, counterexample, ambiguous, strong_example, supporting_example.
- TestShouldRequireVisualEvidence (class, 3 tests) - example requires, theory does not, optional does not.

## tests/test_transcript_first_validation.py
- TestSchemaFieldsExist (class, 3 tests) - KnowledgeEvent, RuleCard, EvidenceRef new fields present and settable.
- TestValidationPolicy (class, 3 tests) - evidence_requirement=none suppresses warnings, optional warns on visual_summary.
- TestTranscriptSupportScoring (class, 3 tests) - line confidence high score, chunk confidence lower, longer text boosts.
- TestConfidenceScoringTranscriptFirst (class, 2 tests) - High transcript_support_score lifts confidence for events and rule candidates.
- TestEvidenceClassifiers (class, 4 tests) - Evidence strength weak/moderate/strong classification, role detail classification.
- TestKnowledgeEventNewFields (class, 2 tests) - Extraction populates support fields, theory event gets transcript_primary.

## tests/test_rule_reducer.py
- test_load_valid_knowledge_events() - Valid KnowledgeEventCollection loads and validates.
- test_load_valid_evidence_index() - Valid EvidenceIndex loads and validates.
- test_load_empty_collections() - Empty but valid collections are tolerated.
- _make_event() - Make event.
- test_group_compatible_events_same_concept_subconcept_section() - Same concept, subconcept, section, compatible roles  one candidate.
- test_do_not_merge_different_subconcepts() - Same concept but different subconcepts  separate candidates.
- test_do_not_merge_unrelated_rule_statements() - Unrelated rule statements with low text similarity stay separate.
- test_attach_evidence_by_source_event_ids() - Evidence whose source_event_ids overlap candidate event ids links correctly.
- test_split_overbroad_candidate_multiple_subconcepts() - Candidate with two distinct subconcepts splits.
- test_split_overbroad_candidate_low_similarity_primaries() - Candidate with multiple primary events with low text similarity splits.
- test_choose_canonical_rule_text_prefers_rule_statement() - Given multiple primary events, rule_statement is chosen over definition/condition.
- test_choose_canonical_rule_text_single_sentence() - Canonical rule text is one sentence, not concatenation.
- test_build_final_rule_card_has_required_fields() - RuleCard contains rule_text, conditions, invalidation, evidence_refs, source_event_ids.
- test_distribute_example_refs_maps_to_ml_fields() - positive_example / counterexample / ambiguous_example map to correct ML fields.
- test_confidence_scoring_stronger_above_weaker() - Stronger candidate (primary + concept + evidence) scores above weaker one.
- test_rule_card_collection_serializes() - RuleCardCollection round-trips via JSON.
- test_build_rule_cards_returns_valid_collection() - build_rule_cards returns RuleCardCollection that serializes.
- test_enable_rule_cards_false_no_rule_files() - When enable_rule_cards=False, no rule_cards/rule_debug files; legacy unchanged.
- test_save_rule_cards_and_debug() - save_rule_cards and save_rule_debug write files.
- test_normalize_text_for_match() - normalize_text_for_match lowercases and strips punctuation.
- test_simple_text_similarity() - simple_text_similarity returns value in [0, 1].
- test_summarize_evidence_for_rule_card_one_ref() - One evidence ref with compact_visual_summary is used for rule card visual summary.
- test_collect_condition_and_invalidation_texts() - collect_condition_texts and collect_invalidation_texts dedupe and preserve order.

## tests/test_schemas.py
- test_knowledge_event_with_line_confidence_requires_anchor_fields() - timestamp_confidence='line' requires source_line_start, source_line_end, and transcript_anchors.
- test_line_confidence_requires_anchor_diagnostics() - Test line confidence requires anchor diagnostics.
- test_valid_knowledge_event() - Construct a valid KnowledgeEvent and ensure serialization works.
- test_blank_text_rejected() - Blank raw_text or normalized_text should fail.
- test_valid_rule_card() - Construct a minimal valid RuleCard and assert serialization.
- test_rule_card_requires_concept_and_rule_text() - Blank concept or rule_text should fail.
- test_confidence_score_bounds() - confidence_score must be in [0.0, 1.0]; 1.2 and -0.1 should fail.
- test_unknown_field_rejected() - Passing an extra keyword should raise ValidationError (extra='forbid').
- test_valid_evidence_ref() - Build EvidenceRef with empty lists; assert JSON has [] not null.
- test_bundle_serialization() - Build LessonKnowledgeBundle with one event, one evidence ref, one rule card.

## tests/test_stream_events.py
- test_emit_invokes_callback_with_event_shape() - emit() must call the callback with provider, stage, kind and optional fields.
- test_emit_no_op_when_callback_none() - emit() with None callback must not raise.

## tests/test_usage_report.py
- test_build_video_usage_summary_collects_records() - Test build video usage summary collects records.
- test_write_video_usage_summary_writes_default_file() - Test write video usage summary writes default file.

## tests/test_visual_compaction.py
- test_raw_richness_preserved() - Input dict is not mutated by summarize_visual_event_for_extraction.
- test_extraction_summaries_compact() - Summaries are capped, no low-value words, length bounded.
- test_evidence_provenance_preserved() - frame_ids capped, raw_visual_event_ids match ve_raw_<key>; screenshot paths only existing and capped.
- test_rule_card_summary_compact() - Rule card summary is single string, length bounded; trim_rule_card_visual_refs caps refs.
- test_review_vs_rag_bullets() - Review has at most 2 items, RAG at most 1.
- test_forbidden_keys_stripped() - strip_raw_visual_blobs_from_metadata removes current_state and visual_facts, keeps chunk_index.
- test_assert_no_raw_visual_blob_leak_raises() - assert_no_raw_visual_blob_leak raises on forbidden keys, passes otherwise.
- test_detect_visual_spam() - Repeated or frame-by-frame lines are flagged.
- test_screenshot_candidates_only_existing() - Only existing files returned; len <= 4. Nonexistent frame_key yields empty or only existing.
- test_from_pipeline_config() - from_pipeline_config({}) gives defaults; overrides applied from dict.

## tests/unit/__init__.py
- No functions defined in this file.

## tests/unit/test_labeling_manifest_filtering.py
- test_labeling_manifest_empty_when_only_illustrations() - Test labeling manifest empty when only illustrations.

## tests/unit/test_ml_eligibility.py
- test_illustration_is_not_ml_eligible() - Test illustration is not ml eligible.
- test_positive_example_is_ml_eligible() - Test positive example is ml eligible.
- test_counterexample_is_ml_eligible() - Test counterexample is ml eligible.
- test_ml_eligibility_requires_linked_rule_ids() - Test ml eligibility requires linked rule ids.
- test_ml_eligibility_requires_source_event_ids() - Test ml eligibility requires source event ids.

## tests/unit/test_ml_manifest_filtering.py
- test_build_ml_examples_excludes_illustrations() - Test build ml examples excludes illustrations.
- test_build_ml_examples_returns_empty_for_illustration_only_input() - Test build ml examples returns empty for illustration only input.
- test_attach_rule_example_refs_ignores_illustrations() - Test attach rule example refs ignores illustrations.
- test_attach_rule_example_refs_maps_roles_correctly() - Test attach rule example refs maps roles correctly.

## tests/unit/test_timestamp_confidence.py
- test_line_confidence_for_compact_dense_span() - Test line confidence for compact dense span.
- test_span_confidence_when_span_width_is_four() - Test span confidence when span width is four.
- test_span_confidence_when_density_is_too_low_for_line() - Test span confidence when density is too low for line.
- test_chunk_confidence_when_line_bounds_missing() - Test chunk confidence when line bounds missing.
- test_chunk_confidence_when_no_anchors() - Test chunk confidence when no anchors.

---

# pipeline/rag/ — Hybrid RAG Retrieval System (Step 3)

## pipeline/rag/__init__.py
- Package init.

## pipeline/rag/__main__.py
- Entrypoint for `python -m pipeline.rag`, delegates to `cli.main()`.

## pipeline/rag/config.py
- UnitType — Literal type for the 5 retrieval unit types.
- ALL_UNIT_TYPES — List of all valid unit types.
- RAGConfig — Pydantic BaseModel with all RAG settings: paths, model names, top-k defaults, reranker weights.
- RAGConfig.index_dir — Property returning `rag_root / "index"`.
- RAGConfig.eval_dir — Property returning `rag_root / "eval"`.

## pipeline/rag/retrieval_docs.py
- RetrievalDocBase — Base Pydantic model for all retrieval documents: doc_id, unit_type, lesson_id, text, provenance, etc.
- RuleCardDoc — Retrieval doc for rule cards. `from_corpus(raw)` builds from corpus JSONL.
- KnowledgeEventDoc — Retrieval doc for knowledge events. `from_corpus(raw)` builds from corpus JSONL.
- EvidenceRefDoc — Retrieval doc for evidence refs. `from_corpus(raw)` builds from corpus JSONL.
- ConceptNodeDoc — Retrieval doc for concept graph nodes. `from_corpus(raw, frequencies)` builds from graph JSON.
- ConceptRelationDoc — Retrieval doc for concept graph relations. `from_corpus(raw, node_name_map)` builds from graph JSON.

## pipeline/rag/corpus_loader.py
- load_corpus_and_build_docs(cfg) — Load all Step 2 corpus exports, transform to typed retrieval docs, return DocStore.
- build_and_persist(cfg) — Build retrieval docs and persist to `output_rag/` as JSONL + metadata.

## pipeline/rag/store.py
- DocStore — In-memory document store backed by JSONL persistence. Indexes by doc_id, unit_type, lesson_id, concept_id.
- DocStore.add(doc) — Add a RetrievalDocBase to the store.
- DocStore.get(doc_id) — Retrieve single doc by ID.
- DocStore.get_all() — Return all docs.
- DocStore.get_by_ids(doc_ids) — Batch retrieve by IDs.
- DocStore.get_by_unit(unit_type) — All docs of a given unit type.
- DocStore.get_by_lesson(lesson_id) — All docs for a lesson.
- DocStore.get_by_concept(concept_id) — All docs for a concept.
- DocStore.filter_ids(unit_types, lesson_ids, concept_ids, min_confidence) — Intersection filter returning doc IDs.
- DocStore.facets(doc_ids) — Compute faceted counts by unit_type, lesson, concept.
- DocStore.save(path) / DocStore.load(path) — JSONL persistence.

## pipeline/rag/asset_resolver.py
- AssetResolver — Resolve screenshot/frame paths on local filesystem. Methods: resolve_screenshot, resolve_lesson_dir.

## pipeline/rag/lexical_index.py
- tokenize(text) — Whitespace + lowercase + Cyrillic-aware regex tokenizer.
- LexicalIndex — BM25Okapi index over retrieval docs with unit-type masking.
- LexicalIndex.build(docs) — Build index from list of doc dicts.
- LexicalIndex.search(query, top_k, unit_types, allowed_ids) — BM25 search returning scored doc_ids.
- LexicalIndex.save(index_dir) / LexicalIndex.load_from_store(docs) — Persistence.

## pipeline/rag/embedding_index.py
- EmbeddingIndex — Sentence-transformer embedding index with numpy brute-force cosine search.
- EmbeddingIndex.build(docs, model_name, batch_size) — Encode all docs, build index.
- EmbeddingIndex.encode_query(query) — Encode a single query string.
- EmbeddingIndex.search(query_embedding, top_k, unit_types, allowed_ids) — Cosine search returning scored doc_ids.
- EmbeddingIndex.save(index_dir) / EmbeddingIndex.load(index_dir) — npy + JSON persistence.

## pipeline/rag/graph_expand.py
- ConceptExpander — Concept graph expansion: alias registry, adjacency list, 1-hop expansion.
- ConceptExpander.from_corpus(corpus_root) — Build from corpus JSON files.
- ConceptExpander.expand_query(query) — Detect concepts, resolve aliases, expand neighbors, return boosted IDs.

## pipeline/rag/reranker.py
- RerankerCandidate — Container for a candidate doc with lexical/vector scores and signal breakdown.
- rerank(candidates, query_concept_ids, query_alias_terms, boosted_rule_ids, weights) — Deterministic weighted reranking with min-max normalization.

## pipeline/rag/retriever.py
- HybridRetriever — Orchestrator combining lexical + vector + graph expansion + reranking.
- HybridRetriever.search(query, top_k, unit_types, lesson_ids, concept_ids, min_confidence) — Full hybrid search pipeline.

## pipeline/rag/answer_builder.py
- build_answer(retrieval_result, return_summary) — Structure hits into grounded response payload with groups, citations, extractive summary.

## pipeline/rag/api.py
- FastAPI app with endpoints: GET /health, POST /rag/search, GET /rag/doc/{doc_id}, GET /rag/concept/{id}, GET /rag/lesson/{id}, POST /rag/eval/run.
- init_app(cfg) — Load all indexes into memory and wire up the retriever.
- SearchRequest / SearchResponse — Pydantic request/response models.

## pipeline/rag/cli.py
- Click CLI group with subcommands: build, search, serve, eval.
- build — Build retrieval docs and indexes from corpus.
- search — One-shot search against the RAG index.
- serve — Start the FastAPI RAG server.
- eval — Run the evaluation harness.

## pipeline/rag/eval.py
- CURATED_QUERIES — 25 curated evaluation queries across 7 categories.
- run_eval(retriever, cfg, queries_path, k_values) — Run eval queries, compute Recall@k, MRR, concept detection accuracy, per-unit hit rates. Writes eval_results.json and eval_report.json.

## tests/test_rag.py
- TestRetrievalDocBuild — 8 tests: docs created, unit types present, field validation, short_text populated.
- TestLexicalRetrieval — 5 tests: search returns results, concept query, unit type filter, tokenizer, empty query.
- TestVectorRetrieval — 3 tests: build and shape, persist and load, search returns results.
- TestGraphExpansion — 4 tests: detect concept, alias resolution, expansion neighbors, empty expansion.
- TestHybridMerge — 1 test: merge deduplicates doc_ids.
- TestReranking — 3 tests: breakdown present, exact beats partial, empty candidates.
- TestAPI — 3 tests: health endpoint, search 503 uninitialized, doc 503 uninitialized.
- TestEvalHarness — 2 tests: curated queries exist, categories covered.
- TestMultilingual — 3 tests: Russian query, English query, mixed query.
- TestStorePersistence — 3 tests: save/load roundtrip, filter by unit, facets.

