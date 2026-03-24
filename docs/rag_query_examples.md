# Hybrid RAG Query Examples

## Practical Queries

| Query | Expected Best Unit Type(s) | Why It Should Work |
| --- | --- | --- |
| `what are all rules about level` | `rule_card`, `knowledge_event` | Matches rule statements and normalized event text around level concepts. |
| `what invalidates a breakout setup` | `rule_card`, `knowledge_event` | Pulls invalidation language from rule cards and warning events. |
| `what is the difference between acceptance and false breakout` | `concept_relation`, `rule_card` | Comparison phrasing should boost concept relations and linked rules. |
| `show all examples tied to retest` | `evidence_ref`, `rule_card` | Example phrasing biases retrieval toward evidence refs and rule-linked visuals. |
| `what lessons discuss volume confirmation` | `knowledge_event`, `concept_node` | Lesson coverage and concept expansion surface lesson-linked knowledge events. |
| `what rule conflicts exist across lessons` | `concept_relation`, `rule_card` | Cross-lesson overlap and concept graph expansion help surface related rules. |
| `what rules depend on higher timeframe context` | `rule_card`, `knowledge_event` | Timeframe terminology maps into linked rules and events. |
| `stop loss placement rules` | `rule_card` | English multilingual query should still match the same stop-loss concept family. |
| `take profit strategy` | `rule_card`, `knowledge_event` | English query should hit take-profit rules and related supporting events. |
| `show chart example of accumulation` | `evidence_ref` | Example/chart wording should push evidence docs higher. |
| `false breakout invalidation` | `rule_card`, `knowledge_event` | Strong lexical match on false-breakout invalidation language. |
| `technical stop loss versus calculation stop` | `rule_card`, `concept_relation` | Comparison query should retrieve rule comparisons and related concept edges. |
| `rules with transcript primary support` | `rule_card`, `knowledge_event` | Support-policy metadata is indexed as searchable retrieval text. |
| `examples that require visual evidence` | `evidence_ref`, `rule_card` | Evidence-policy wording should retrieve visually grounded units. |
| `breakout failure examples with timestamps` | `evidence_ref`, `knowledge_event` | Timestamp-bearing evidence and event docs are both good candidates. |

## Russian Examples

| Query | Expected Best Unit Type(s) | Why It Should Work |
| --- | --- | --- |
| `покажи пример накопления на графике` | `evidence_ref`, `knowledge_event` | Example wording plus accumulation concept should surface evidence-linked docs. |
| `когда правило стоп-лосса не работает` | `rule_card`, `knowledge_event` | Invalidation wording should boost rule/event hits with stop-loss grounding. |
| `разница между техническим и обычным стоп-лоссом` | `rule_card`, `concept_relation` | Comparison phrasing should retrieve both rule and relation units. |
| `какие правила связаны с анализом таймфреймов` | `rule_card`, `concept_node` | Graph expansion should pull linked timeframe concepts and their rules. |
| `ложный пробой отменяет продолжение` | `knowledge_event`, `rule_card` | Strong lexical match for failure/invalidation wording. |

## Notes

- Evidence-oriented queries work best when the corpus contains `evidence_ref` docs with concept-linked summaries.
- Comparison queries benefit most from concept aliases plus graph expansion.
- Lesson coverage queries depend on `lesson_id`, `lesson_slug`, and preserved provenance in the retrieval docs.
- Support-policy queries rely on indexed `support_basis`, `evidence_requirement`, and `teaching_mode` fields.

### Step 3.1 API fields

`/rag/search` returns `query_analysis.detected_intents` (multi-label tags such as `example_lookup`, `support_policy`, `concept_comparison`) and `query_analysis.intent_signals` (e.g. transcript-only vs visual-evidence preference). Example/chart phrasing should produce `example_lookup` and surface `evidence_ref` units at the top of `top_hits` when the corpus has matching evidence docs.

### Comprehensive audit bundle

To produce a single zip for external review (16 saved searches with full `score_breakdown`, health, doc/concept samples, `output_rag/`, corpus subset, `pytest -v` log, `config_used.env`, `run_commands.txt`, `step3_1.diff`): run `python -m pipeline.rag export-audit-comprehensive` (see `docs/step3_hybrid_rag_notes.md`).

The export commands now fail fast if `output_rag/eval/eval_report.json` is stale or missing required Step 3.1 metrics, so the bundle cannot silently mix newer code with older eval artifacts.
