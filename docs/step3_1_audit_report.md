# Step 3.1 Audit Report

## Verdict

**Step 3.1 accepted. Timeframe blocker closed. Ready to proceed to Step 4.**

The previous code/artifact drift remains resolved, the higher-timeframe blocker remains closed, and this cleanup pass fixes the main remaining polish items from the follow-up audit: stop-loss example retrieval, clearer support-policy reporting, and explicit rule phrasing for timeframe queries.

## Scope

This report is based on:

- current `output_rag/eval/eval_report.json`
- current `output_rag/eval/eval_results.json`
- current `output_rag/rag_build_metadata.json`
- current full regression run: `python -m pytest tests/rag tests/test_rag.py -v --tb=short`

## Current headline metrics

From `output_rag/eval/eval_report.json`:

- `Recall@5 = 1.0`
- `Recall@10 = 1.0`
- `MRR = 0.9444`
- `concept_detection_success_proxy = 0.7037`
- `example_lookup_evidence_top1_rate = 1.0`
- `support_policy_evidence_top3_rate = 0.5`
- `support_policy_visual_evidence_top3_rate = 1.0`
- `transcript_only_transcript_primary_top1_rate = 1.0`
- `cross_lesson_concept_top3_rate = 1.0`
- `higher_timeframe_dependency category_avg_recall = 1.0`

## What changed in this pass

This cleanup pass added four targeted improvements:

- stop-loss phrase normalization and alias expansion now recognize inflected and phrase-level variants such as `стоп-лосса`, `постановка стоп-лосса`, and `технический стоп`
- stop-loss example queries now seed and rerank matching `evidence_ref` results more aggressively
- support-policy reporting now separates visual-evidence behavior from transcript-only behavior
- explicit rule phrasing now lightly prefers `rule_card` over `knowledge_event` for actionable timeframe queries

The key implementation changes are:

- `intent_signals` now expose `mentions_stoploss` and `prefers_explicit_rules`
- concept expansion now injects stop-loss aliases in the same way the timeframe pass injected compound timeframe aliases
- retriever seeding now explicitly pulls stop-loss evidence when an example query mentions stop-loss phrasing
- reranking now boosts stop-loss `evidence_ref` docs for example queries and gives explicit-rule timeframe queries a light `rule_card` preference
- eval now reports `support_policy_visual_evidence_top3_rate` separately from the blended backward-compatible metric

## Key query outcomes

### `q014` — `Пример постановки стоп-лосса`

- `recall@5 = 1.0`
- `recall@10 = 1.0`
- `top_hit_unit_type = evidence_ref`
- `top3_unit_types = ["evidence_ref", "evidence_ref", "evidence_ref"]`
- `intent_signals.mentions_stoploss = true`

This query is now properly grounded as a stop-loss example lookup and no longer drifts into generic example material.

### `q020` — `Как определить дневной уровень?`

- `recall@5 = 1.0`
- `recall@10 = 1.0`
- `top_hit_unit_type = knowledge_event`
- `top3_unit_types = ["knowledge_event", "rule_card", "knowledge_event"]`
- `intent_signals.prefers_actionable_rules = true`

This remains in the correct actionable timeframe retrieval family and continues to avoid concept-heavy top hits.

### `q021` — `Правила торговли на разных таймфреймах`

- `recall@5 = 1.0`
- `recall@10 = 1.0`
- `top_hit_unit_type = rule_card`
- `top3_unit_types = ["rule_card", "rule_card", "knowledge_event"]`
- `intent_signals.prefers_actionable_rules = true`
- `intent_signals.prefers_explicit_rules = true`

The explicit `Правила ...` phrasing now produces the cleaner `rule_card`-first outcome the audit recommended.

### `q022` / `q023` — support-policy split

- blended `support_policy_evidence_top3_rate` remains `0.5` for backward compatibility
- `support_policy_visual_evidence_top3_rate = 1.0`
- `transcript_only_transcript_primary_top1_rate = 1.0`

The saved artifacts now make the real behavior explicit instead of forcing reviewers to infer it from a blended metric.

## No-regression checks

The previously repaired Step 3.1 behaviors remain stable while the cleanup pass improves the weaker example/rule-routing cases:

- `example_lookup_evidence_top1_rate` improved from `0.6667` to `1.0`
- `support_policy_evidence_top3_rate` remains `0.5` as a backward-compatible blended metric
- `support_policy_visual_evidence_top3_rate` is now reported separately at `1.0`
- `transcript_only_transcript_primary_top1_rate` stayed at `1.0`
- `cross_lesson_concept_top3_rate` stayed at `1.0`
- `higher_timeframe_dependency category_avg_recall` stayed at `1.0`

## Tests

Current regression run:

- `92 passed`

New coverage in this pass includes:

- stop-loss example intent detection
- stop-loss evidence-first reranking
- explicit rule-surface-form preference for timeframe queries
- split support-policy metric coverage
- actionable timeframe intent detection
- timeframe rule-vs-relation reranking
- stronger eval gate on `higher_timeframe_dependency`

## Bottom line

The saved artifacts now support all four polish items from the follow-up audit:

- stop-loss example retrieval is evidence-first
- support-policy visual and transcript-only behaviors are reported separately
- explicit timeframe rule phrasing returns `rule_card` at rank 1
- the report wording clearly states that Step 3.1 is complete and Step 4 can begin

The next audit bundle should be generated from this refreshed state and should include the updated eval report, refreshed API samples, this report, and a short handoff note highlighting the `q014` and `q021` improvements plus the new split support-policy metric.
