# RAG contract v1 (Stage 6.3)

## Purpose

Hybrid retrieval over **Stage 6.2 unified corpus** JSONL/JSON outputs. Structured artifacts (`corpus_rule_cards.jsonl`, `corpus_knowledge_events.jsonl`, `corpus_evidence_index.jsonl`, `corpus_concept_graph.json`) are the source of truth—not lesson markdown.

## Retrieval unit types

| `unit_type`        | Role                          | Stable id field on doc |
|--------------------|-------------------------------|-------------------------|
| `rule_card`        | High-level actionable rules   | `doc_id` = corpus `global_id` |
| `knowledge_event`  | Nuance, conditions, examples  | `doc_id` = corpus `global_id` |
| `evidence_ref`     | Timestamped grounding         | `doc_id` = corpus `global_id` |
| `concept_node`     | Canonical concepts + aliases  | `doc_id` = `global_id` |
| `concept_relation` | Graph edges between concepts  | `doc_id` = `relation_id` |

Units are **not merged** into a single document type in storage; each row keeps `unit_type`.

## Embedding text policy

Embedding and lexical text are built in `retrieval_docs.py` from normalized structured fields only (titles, rule/event text, conditions, invalidation, concept labels, evidence summaries)—not raw transcript dumps.

## Metadata and vectors

- **Metadata**: `retrieval_docs_all.jsonl` plus relational mirror `rag_metadata.sqlite` (table `retrieval_unit`, full JSON payload per row, versioning columns).
- **Vectors**: NumPy archives under `output_rag/index/` with manifest; cosine retrieval via `EmbeddingIndex`.
- **Lexical**: BM25 (`rank_bm25`) via `LexicalIndex`.

## Hybrid retrieval policy

1. Query normalization + intent signals (`query_intents.py`).
2. Concept / alias / graph expansion (`graph_expand.py`).
3. Parallel **lexical** and **vector** candidate generation.
4. Merge, cap, then **deterministic reranking** (`reranker.py`) using lexical, vector, graph, evidence/timestamp presence, confidence, and intent-aware unit weights.

## API (FastAPI)

Mounted under `/rag` (see `rag_routes.py`):

- `POST /rag/search` — body: `SearchRequest` (`query`, `top_k`, `unit_types`, `filters`, `return_summary`, `require_evidence`).
- `POST /rag/search/explain` — same body; returns `{ "search_response": …, "retrieval_trace": … }` (expansion, per-hit lexical/vector scores).
- `GET /rag/item/{unit_type}/{doc_id}` — typed fetch; `doc_id` may contain `:` (path segment).
- `GET /rag/related/{unit_type}/{doc_id}` — linked evidence, events, rules, concepts.
- `GET /rag/explore/lesson/{lesson_id}` — grouped unit summaries for a lesson.
- Legacy: `GET /rag/doc/{doc_id}`, `/rag/lesson/...`, `/rag/concept/...`, `POST /rag/eval/run`, `GET /rag/facets`.

## Provenance (required on hits)

Each search hit includes at minimum: `doc_id` / `global_id`, `unit_type`, `lesson_id`, `concept`, `subconcept`, `timestamps`, `evidence_ids`, `source_event_ids`, `source_rule_ids`, scores and `resolved_doc` for full structured fields.

## Known limitations

- Default stack uses **SQLite + file-backed vectors**, not Postgres/pgvector; swap via new store/index adapters.
- `require_evidence` filters to docs with non-empty `evidence_ids` after rerank; may return fewer than `top_k` hits.

## Deferred work

- Incremental per-lesson upsert; pgvector backend; LLM reranker; richer cross-lesson conflict mining.
