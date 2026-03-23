# RAG Step 3 Handoff

## Request

The user asked for a plan and then a full implementation of `rag creation/01.md`, which defines Roadmap Step 3: a hybrid RAG retrieval layer built on top of Step 2 corpus outputs.

The user explicitly approved a temporary **in-memory / local-first** implementation instead of Postgres + pgvector, with the condition that:

- storage assumptions must not leak into core retrieval logic
- `store.py` must remain a clean abstraction
- retrieval docs must be persisted as JSONL
- IDs and provenance must stay stable
- index manifests must exist
- the backend must remain replaceable later

## Final Outcome

The Step 3 local-first RAG implementation was completed and verified.

Key results:

- `pipeline/rag/contracts.py` was added
- `pipeline/rag/store.py` now exposes a replaceable store boundary with `InMemoryDocStore`
- retrieval docs were expanded to include spec-required fields like `keywords`, `support_basis`, `evidence_requirement`, `teaching_mode`, and structured `timestamps`
- the corpus loader now validates the full required Step 2 input contract
- lexical search now supports phrase boost, alias boost, lesson/concept filtering, and persisted lexical data
- embedding search now uses an `EmbeddingBackend` abstraction with `SentenceTransformerBackend`
- graph expansion now returns a typed `GraphExpansionResult` and uses alias registry, concept graph, rule family index, and overlap report
- retriever, reranker, answer builder, API, CLI, docs, eval, and tests were all upgraded to match the approved plan

## Main Files Added

- `pipeline/rag/contracts.py`
- `docs/rag_query_examples.md`
- `tests/rag/conftest.py`
- `tests/rag/test_contracts.py`
- `tests/rag/test_retrieval_docs.py`
- `tests/rag/test_corpus_loader.py`
- `tests/rag/test_lexical_index.py`
- `tests/rag/test_embedding_index.py`
- `tests/rag/test_graph_expand.py`
- `tests/rag/test_retriever.py`
- `tests/rag/test_reranker.py`
- `tests/rag/test_api.py`
- `tests/rag/test_eval.py`
- `tests/rag/test_multilingual.py`

## Main Files Updated

- `pipeline/rag/config.py`
- `pipeline/rag/retrieval_docs.py`
- `pipeline/rag/corpus_loader.py`
- `pipeline/rag/store.py`
- `pipeline/rag/lexical_index.py`
- `pipeline/rag/embedding_index.py`
- `pipeline/rag/graph_expand.py`
- `pipeline/rag/retriever.py`
- `pipeline/rag/reranker.py`
- `pipeline/rag/answer_builder.py`
- `pipeline/rag/api.py`
- `pipeline/rag/cli.py`
- `pipeline/rag/eval.py`
- `pipeline/rag/asset_resolver.py`
- `docs/step3_hybrid_rag_notes.md`
- `tests/test_rag.py`

## Real Output Regeneration

`output_rag/` was rebuilt from the real `output_corpus/` data.

Important generated outputs now present:

- `output_rag/retrieval_docs_rule_cards.jsonl`
- `output_rag/retrieval_docs_knowledge_events.jsonl`
- `output_rag/retrieval_docs_evidence_refs.jsonl`
- `output_rag/retrieval_docs_concepts.jsonl`
- `output_rag/retrieval_docs_all.jsonl`
- `output_rag/rag_build_metadata.json`
- `output_rag/index/lexical_index_manifest.json`
- `output_rag/index/lexical_index_data.json`
- `output_rag/index/embedding_manifest.json`
- `output_rag/index/embedding_doc_ids.json`
- `output_rag/eval/eval_queries.json`
- `output_rag/eval/eval_results.json`
- `output_rag/eval/eval_report.json`

## Verification Performed

### Tests

Ran:

```bash
uv run pytest tests/rag tests/test_rag.py -q
```

Result:

- `67 passed`

### Lint / Diagnostics

- No linter errors on changed RAG, docs, and test files

### Real Build

Ran:

```bash
uv run python -m pipeline.rag build --corpus-root output_corpus --rag-root output_rag
```

Observed:

- `Retrieval docs: 1591`
- `Embedding index saved (1591 docs, 384d)`

### Real Eval

Ran:

```bash
uv run python -m pipeline.rag eval --corpus-root output_corpus --rag-root output_rag
```

Reported metrics:

- `Recall@5 = 0.7778`
- `Recall@10 = 0.8148`
- `MRR = 0.7028`
- `concept_detection_success_proxy = 0.3704`
- `evidence_presence_rate = 0.7481`
- `timestamp_presence_rate = 0.8741`
- `evidence_id_rate = 0.7481`

### Real CLI Search

Ran:

```bash
uv run python -m pipeline.rag search --corpus-root output_corpus --rag-root output_rag --query "Stop loss placement rules" --top-k 3
```

Confirmed the response now includes:

- `query_analysis`
- detected concept IDs
- graph expansion trace
- structured top hits
- timestamps
- evidence IDs
- raw lexical/vector scores
- graph boost
- per-hit score breakdown
- `why_retrieved`

## Important Design Decisions

- Postgres + pgvector was **deferred**
- no migration file was created
- `DocStore` is intentionally abstract so persistence can be swapped later
- vector search remains numpy brute-force cosine for now
- no LLM reranker was used
- no frontend explorer beyond API/OpenAPI was implemented

## Known Caveats

- The embedding model still loads from `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- CLI/API startup may rebuild embeddings if older on-disk vector files are incompatible
- current concept detection metrics are acceptable but still weaker than the rest of retrieval quality
- this is suitable for development/evaluation, not long-term concurrency or production-grade serving

## Suggested Next Step

If continuing from this handoff, the next likely options are:

1. create a git commit for the RAG Step 3 rollout
2. prepare an audit bundle / deliverable package
3. start a follow-up pass on retrieval quality, especially concept detection and evidence-first ranking
