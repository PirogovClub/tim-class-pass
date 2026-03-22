from __future__ import annotations

from pipeline.rag.embedding_index import EmbeddingIndex


def test_embeddings_are_persisted(all_docs, fake_backend, tmp_path):
    index = EmbeddingIndex.build(all_docs, backend=fake_backend)
    index.save(tmp_path)
    loaded = EmbeddingIndex.load(tmp_path, backend=fake_backend)
    assert loaded.doc_count == index.doc_count
    assert loaded.dim == fake_backend.dimension()


def test_query_search_returns_candidates(embedding_index):
    hits = embedding_index.search(embedding_index.encode_query("stop loss"), top_k=3)
    assert hits
    assert hits[0][1] > 0


def test_backend_abstraction_works(fake_backend):
    assert fake_backend.model_id() == "fake-multilingual"
    assert fake_backend.dimension() == 4
