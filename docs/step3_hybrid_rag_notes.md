# Step 3: Hybrid RAG – Architecture & Implementation Notes

## Overview

The hybrid RAG system transforms Step 2 corpus exports into a queryable retrieval layer with stable IDs, preserved provenance, and separate retrieval units. It combines lexical search (BM25), vector similarity (sentence-transformers), concept graph expansion, and deterministic reranking, then returns grounded structured responses with timestamps and evidence IDs where available.

## Stack Decision

- Current implementation is intentionally **local-first**:
  - retrieval docs persisted as JSONL
  - lexical index persisted as JSON
  - embeddings persisted as `.npy` + manifest
  - runtime store loaded into memory behind a replaceable `DocStore` protocol
- Postgres + pgvector is still the long-term target, but it is intentionally deferred while retrieval quality, contracts, and evaluation are stabilized.
- This keeps the retrieval behavior backend-independent and limits the future persistence swap to `store.py` and `embedding_index.py`.

## Stack

| Component       | Technology                                | Notes                              |
| --------------- | ----------------------------------------- | ---------------------------------- |
| Lexical index   | `rank_bm25` (BM25Okapi)                  | Pure-Python, pre-tokenized in RAM  |
| Vector index    | `sentence-transformers` + numpy           | `paraphrase-multilingual-MiniLM-L12-v2`, 384-dim, brute-force cosine |
| API             | FastAPI + uvicorn                         | OpenAPI explorer at `/docs`        |
| Persistence     | JSONL + JSON manifests + `.npy`           | Filesystem-based, loaded into RAM  |
| Store abstraction | `DocStore` protocol + `InMemoryDocStore` | Replaceable backend boundary       |
| Reranker        | Deterministic weighted scorer             | No LLM, explainable breakdown     |
| Graph expansion | Alias registry + concept graph + family index + overlap report | Pre-built from corpus              |

## Retrieval Document Design

Five unit types, each with a Pydantic model derived from `RetrievalDocBase`:

| Unit Type            | Source Corpus File                  | Key Fields                                                              |
| -------------------- | ----------------------------------- | ----------------------------------------------------------------------- |
| `rule_card`          | `corpus_rule_cards.jsonl`           | concept, subconcept, rule_text, conditions, invalidation, support basis, teaching mode |
| `knowledge_event`    | `corpus_knowledge_events.jsonl`     | event_type, normalized_text, concept, timestamps, support metadata     |
| `evidence_ref`       | `corpus_evidence_index.jsonl`       | example_role, visual summary, linked_rule_ids, frame_ids, screenshot paths |
| `concept_node`       | `corpus_concept_graph.json` (nodes) | name, aliases, source_lessons, frequency stats                          |
| `concept_relation`   | `corpus_concept_graph.json` (rels)  | source → relation_type → target                                        |

Each doc carries:
- stable `doc_id`
- `unit_type`
- concept/subconcept IDs
- alias terms
- keywords
- provenance
- timestamp ranges
- evidence/source links
- support policy fields (`support_basis`, `evidence_requirement`, `teaching_mode`)

Each doc assembles a structured `text` field for indexing and a `short_text` for display.

## Input Contract

The build reads only Step 2 corpus outputs:

- `output_corpus/schema_versions.json`
- `output_corpus/lesson_registry.json`
- `output_corpus/corpus_metadata.json`
- `output_corpus/corpus_lessons.jsonl`
- `output_corpus/corpus_knowledge_events.jsonl`
- `output_corpus/corpus_rule_cards.jsonl`
- `output_corpus/corpus_evidence_index.jsonl`
- `output_corpus/corpus_concept_graph.json`
- `output_corpus/concept_alias_registry.json`
- `output_corpus/concept_frequencies.json`
- `output_corpus/concept_rule_map.json`
- `output_corpus/rule_family_index.json`
- `output_corpus/concept_overlap_report.json`

## Data Flow

```mermaid
flowchart LR
  corpus[output_corpus] --> loader[corpus_loader.py]
  loader --> docs[retrieval_docs_*.jsonl]
  loader --> store[InMemoryDocStore]
  store --> lexical[lexical_index.py]
  store --> embed[embedding_index.py]
  corpus --> graph[graph_expand.py]
  lexical --> retriever[retriever.py]
  embed --> retriever
  graph --> retriever
  retriever --> reranker[reranker.py]
  reranker --> answer[answer_builder.py]
  answer --> api[api.py]
  retriever --> eval[eval.py]
```

## Indexing Process

1. `corpus_loader.py` validates the full Step 2 corpus contract and writes:
   - `output_rag/retrieval_docs_rule_cards.jsonl`
   - `output_rag/retrieval_docs_knowledge_events.jsonl`
   - `output_rag/retrieval_docs_evidence_refs.jsonl`
   - `output_rag/retrieval_docs_concepts.jsonl`
   - `output_rag/retrieval_docs_all.jsonl`
2. `lexical_index.py` tokenizes title/text/keywords/aliases and persists a BM25-ready data snapshot plus manifest.
3. `embedding_index.py` builds weighted text embeddings and persists vectors plus metadata manifest.

## Search Flow

```
Query → Graph Expansion → [Lexical BM25 | Vector Cosine] → Merge → Rerank → Answer Builder → Response
```

1. Normalize the query and infer a likely unit bias (`mixed`, `rule`, `evidence`, `concept`).
2. Expand the query with alias matches, conservative graph neighbors, overlap hints, and rule-family boosts.
3. Run lexical retrieval with phrase boost, alias boost, and unit/lesson/concept filters.
4. Run vector retrieval over the persisted embedding matrix.
5. Merge candidates by `doc_id` and cap at `merged_top_k`.
6. Rerank with transparent deterministic signals.
7. Build a structured grounded response with grouped hits and citations.

## Reranker Weights

| Signal               | Weight |
| -------------------- | ------ |
| lexical_score        | 0.30   |
| vector_score         | 0.30   |
| concept_exact_match  | 0.15   |
| alias_match          | 0.05   |
| unit_type_relevance  | 0.04   |
| support_basis_relevance | 0.02 |
| teaching_mode_relevance | 0.02 |
| confidence_score     | 0.05   |
| evidence_available   | 0.05   |
| timestamp_available  | 0.05   |
| provenance_richness  | 0.05   |
| lesson_diversity_bonus | 0.03 |
| groundedness         | 0.04   |

## Filters & Facets

Per-query filters: `unit_types`, `lesson_ids`, `concept_ids`, `min_confidence`. Response includes faceted counts by unit type, lesson, and concept.

## API Endpoints

| Method | Path                 | Description                      |
| ------ | -------------------- | -------------------------------- |
| GET    | `/health`            | System health + doc count        |
| POST   | `/rag/search`        | Hybrid search with filters       |
| GET    | `/rag/doc/{doc_id}`  | Fetch single retrieval document  |
| GET    | `/rag/concept/{id}`  | All docs for a concept           |
| GET    | `/rag/lesson/{id}`   | All docs for a lesson            |
| POST   | `/rag/eval/run`      | Run eval harness from API        |
| GET    | `/rag/facets`        | Debug counts by unit/lesson/concept |

## CLI Commands

```bash
python -m pipeline.rag build --corpus-root output_corpus --rag-root output_rag
python -m pipeline.rag search --query "стоп лосс" --top-k 10
python -m pipeline.rag serve --port 8000
python -m pipeline.rag eval
```

## Rebuild Instructions

1. Ensure Step 2 corpus is built: `output_corpus/` has all required files
2. Run `python -m pipeline.rag build` to generate retrieval docs + indexes
3. Run `python -m pipeline.rag eval` to validate retrieval quality
4. Run `python -m pipeline.rag serve` to start the API

## Evaluation

The evaluation harness writes:

- `output_rag/eval/eval_queries.json`
- `output_rag/eval/eval_results.json`
- `output_rag/eval/eval_report.json`

It currently runs 27 curated multilingual queries across:

- direct rule lookup
- invalidation
- concept comparison
- example lookup
- lesson coverage
- cross-lesson / graph queries
- higher-timeframe dependency
- support-policy queries
- multilingual alias queries

Metrics include:

- Recall@5
- Recall@10
- MRR
- concept-detection success proxy
- evidence-presence rate
- timestamp-presence rate
- evidence-ID rate
- per-unit hit rate
- category average recall

## Limitations

- In-memory serving is good for development/evaluation but not for long-term concurrency or durable multi-process serving
- Brute-force cosine (no ANN) — fine at moderate scale, add ANN/pgvector later
- No LLM-based reranking or answer generation (by design)
- Current concept detection still underperforms on some Russian concept-name queries and should be improved in a later pass
- Postgres/pgvector, migrations, and durable serving are intentionally deferred

## What Step 4 Consumes

Step 4 (prediction models / UI) will consume:
- `/rag/search` endpoint for retrieval
- `output_rag/retrieval_docs_all.jsonl` for bulk access
- `output_rag/eval/eval_report.json` for baseline metrics
- The concept expansion API for graph-aware features
