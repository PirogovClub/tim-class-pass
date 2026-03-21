# Step 3: Hybrid RAG – Architecture & Implementation Notes

## Overview

The hybrid RAG system transforms Step 2 corpus exports (rule cards, knowledge events, evidence refs, concept graph) into a queryable retrieval layer. It combines lexical search (BM25), vector similarity (sentence-transformers), concept graph expansion, and deterministic reranking.

## Hardware Constraints & Design Rationale

- **32 GB RAM available** — all indexes and documents live in-memory at startup
- **Target: 250 lessons** (~140K retrieval documents, ~1.4 GB total RAM usage)
- No external database required at this scale; everything is loaded from JSONL/npy persistence files
- DB (pgvector) deferred to 500+ lesson scale or concurrent write needs

## Stack

| Component       | Technology                                | Notes                              |
| --------------- | ----------------------------------------- | ---------------------------------- |
| Lexical index   | `rank_bm25` (BM25Okapi)                  | Pure-Python, pre-tokenized in RAM  |
| Vector index    | `sentence-transformers` + numpy           | `paraphrase-multilingual-MiniLM-L12-v2`, 384-dim, brute-force cosine |
| API             | FastAPI + uvicorn                         | OpenAPI explorer at `/docs`        |
| Persistence     | JSONL + `.npy`                            | Filesystem-based, loaded into RAM  |
| Reranker        | Deterministic weighted scorer             | No LLM, explainable breakdown     |
| Graph expansion | In-memory alias registry + adjacency list | Pre-built from corpus              |

## Retrieval Document Design

Five unit types, each with a Pydantic model derived from `RetrievalDocBase`:

| Unit Type            | Source Corpus File                  | Key Fields                                                              |
| -------------------- | ----------------------------------- | ----------------------------------------------------------------------- |
| `rule_card`          | `corpus_rule_cards.jsonl`           | concept, subconcept, rule_text, conditions, invalidation, visual_summary |
| `knowledge_event`    | `corpus_knowledge_events.jsonl`     | event_type, normalized_text, concept, timestamps                        |
| `evidence_ref`       | `corpus_evidence_index.jsonl`       | example_role, visual_summary, linked_rule_ids, frame_ids                |
| `concept_node`       | `corpus_concept_graph.json` (nodes) | name, aliases, source_lessons, frequency stats                          |
| `concept_relation`   | `corpus_concept_graph.json` (rels)  | source → relation_type → target                                        |

Each doc assembles a structured `text` field for indexing (concept tags, sections, Russian text). A `short_text` (first 200 chars) is kept for display.

## Indexing Process

1. **Corpus Loader** reads JSONL/JSON corpus files → builds typed retrieval docs → writes `output_rag/retrieval_docs_all.jsonl`
2. **Lexical Index** tokenizes docs (whitespace + lowercase + Cyrillic-aware) → builds BM25Okapi → saves manifest
3. **Embedding Index** encodes all doc texts with sentence-transformer → saves `embeddings.npy` + `embedding_doc_ids.json`

## Search Flow

```
Query → Graph Expansion → [Lexical BM25 | Vector Cosine] → Merge → Rerank → Answer Builder → Response
```

1. **Graph Expansion**: detect concepts in query via alias registry; 1-hop expansion through relations; collect boosted rule IDs
2. **Lexical Search**: BM25 top-k with optional unit-type and filter-id masking
3. **Vector Search**: cosine similarity on pre-normalized embeddings with same filters
4. **Merge**: union candidate sets by doc_id, carry both scores
5. **Rerank**: weighted combination of 8 signals (lexical, vector, concept match, alias match, confidence, evidence, timestamps, provenance)
6. **Answer Builder**: group by unit type, build citations, optional extractive summary from top rules

## Reranker Weights

| Signal               | Weight |
| -------------------- | ------ |
| lexical_score        | 0.30   |
| vector_score         | 0.30   |
| concept_exact_match  | 0.15   |
| alias_match          | 0.05   |
| confidence_score     | 0.05   |
| evidence_available   | 0.05   |
| timestamp_available  | 0.05   |
| provenance_richness  | 0.05   |

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

25 curated queries across 7 categories: direct rule lookup, invalidation, concept comparison, evidence lookup, lesson coverage, graph query, multilingual. Metrics: Recall@5, Recall@10, MRR, concept detection accuracy, per-unit hit rate.

## Limitations

- Brute-force cosine (no ANN) — fine at 140K docs, add HNSW at 500K+
- No LLM-based reranking or answer generation (by design)
- Single-process; no concurrent writes to indexes
- Embedding model loaded per query in CLI `search` (server keeps it in memory)

## What Step 4 Consumes

Step 4 (prediction models / UI) will consume:
- `/rag/search` endpoint for retrieval
- `output_rag/retrieval_docs_all.jsonl` for bulk access
- `output_rag/eval/eval_report.json` for baseline metrics
- The concept expansion API for graph-aware features
