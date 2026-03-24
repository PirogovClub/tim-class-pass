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

1. Normalize the query, run **intent analysis** (`detected_intents` + sidecar signals), and infer legacy unit bias (`mixed`, `rule`, `evidence`, `concept`).
2. Expand the query with alias matches, conservative graph neighbors, overlap hints, rule-family boosts, and `lexical_expansion_terms`.
3. Run lexical retrieval with phrase boost, alias boost, and unit/lesson/concept filters.
4. Run vector retrieval over the persisted embedding matrix.
5. Merge candidates by `doc_id` and cap at `merged_top_k`.
6. Rerank with transparent deterministic signals.
7. Build a structured grounded response with grouped hits and citations.

## Step 3.1: Intent-aware retrieval quality

Step 3.1 adds **deterministic multi-label query intents** (see `pipeline/rag/query_intents.py`) such as `example_lookup`, `support_policy`, `concept_comparison`, `timeframe_lookup`, and `cross_lesson_conflict_lookup`. These drive:

- **Unit-type priors** in `retriever.py` (`_unit_weight_map`) — e.g. example-style queries up-weight `evidence_ref` and down-weight `knowledge_event` / `rule_card` when appropriate.
- **Reranker signals** in `reranker.py` — including `intent_evidence_priority_boost` (strong preference for `evidence_ref` when the query asks for examples or visual proof), `intent_timeframe_boost`, `intent_cross_lesson_boost`, and metadata hooks (`evidence_requirement`, `evidence_strength`, `support_basis`, `teaching_mode`).
- **Graph / lexical enrichment** in `graph_expand.py` — `lexical_expansion_terms` plus tiered alias matching feed BM25 alias boost and optional vector query expansion.
- **Answer shaping** in `answer_builder.py` — summaries prefer evidence snippets vs concept/rule snippets based on `detected_intents`; limitations call out missing evidence or weak intent alignment.

API responses expose `query_analysis.detected_intents` and a compact `query_analysis.intent_signals` object (transcript vs visual preference, timeframe/cross-lesson flags, etc.). Legacy `detected_unit_bias` is still derived from intents for backward compatibility.

## Reranker Weights

Defaults are defined in `pipeline/rag/config.py` (`reranker_weights`). As of Step 3.1:

| Signal | Weight |
| ------ | ------ |
| lexical_score | 0.26 |
| vector_score | 0.26 |
| concept_exact_match | 0.12 |
| alias_match | 0.05 |
| unit_type_relevance | 0.06 |
| support_basis_relevance | 0.04 |
| teaching_mode_relevance | 0.03 |
| evidence_requirement_relevance | 0.04 |
| evidence_strength_relevance | 0.03 |
| confidence_score | 0.04 |
| evidence_available | 0.06 |
| timestamp_available | 0.05 |
| provenance_richness | 0.04 |
| lesson_diversity_bonus | 0.02 |
| groundedness | 0.04 |
| intent_cross_lesson_boost | 0.02 |
| intent_timeframe_boost | 0.02 |
| intent_evidence_priority_boost | 0.28 |

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
- concept-detection success proxy (expansion + query-aware string match)
- evidence-presence rate
- timestamp-presence rate
- evidence-ID rate
- **example_lookup_evidence_top1_rate** — fraction of example-category queries whose top hit is `evidence_ref`
- **support_policy_evidence_top3_rate** — fraction of support-policy queries with an `evidence_ref` in the top 3 (visual-proof style)
- per-unit hit rate
- category average recall

### Re-audit acceptance (Step 3.1)

After changing retrieval logic, run in order:

1. `python -m pipeline.rag build` (if corpus or build inputs changed)
2. `python -m pytest tests/rag/ -q`
3. `python -m pipeline.rag eval` (writes `eval_report.json`)
4. Optional bundle: `python -m pipeline.rag export-audit` (smaller sample set + eval artifacts; see CLI help)
5. **Comprehensive external audit zip:** `python -m pipeline.rag export-audit-comprehensive` — stages **16** UTF-8 `POST /rag/search` samples (example, invalidation, timeframe, cross-lesson, support-policy, comparison, rule lookup), `GET /health`, **3** doc + **3** concept samples, full `output_rag/`, Step 2 **corpus subset**, `pytest_output.txt` (`pytest -v`), `run_commands.txt`, `config_used.env`, `step3_1.diff`, `README_AUDIT_BUNDLE.md`, and `pyproject.toml`. The zip root folder is `audit_step3_comprehensive/` by default.
6. Both export commands now validate that `output_rag/eval/eval_report.json` exists, has the required Step 3.1 metric keys, matches the current metrics schema version, and is not older than `rag_build_metadata.json`. If not, export fails and you must rerun `build` / `eval`.

Gate on: tests green; `eval_report.json` metrics not regressing vs your saved baseline; spot-check that `q012`-style responses list `evidence_ref` first and `query_analysis.detected_intents` matches the query shape.

## Limitations

- In-memory serving is good for development/evaluation but not for long-term concurrency or durable multi-process serving
- Brute-force cosine (no ANN) — fine at moderate scale, add ANN/pgvector later
- No LLM-based reranking or answer generation (by design)
- Intent and alias detection remain heuristic; rare phrasings may still miss the intended category
- Postgres/pgvector, migrations, and durable serving are intentionally deferred

## What Step 4 Consumes

Step 4 (prediction models / UI) will consume:
- `/rag/search` endpoint for retrieval
- `output_rag/retrieval_docs_all.jsonl` for bulk access
- `output_rag/eval/eval_report.json` for baseline metrics
- The concept expansion API for graph-aware features
