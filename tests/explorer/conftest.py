from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline.explorer.loader import ExplorerRepository
from pipeline.explorer.service import ExplorerService
from pipeline.rag.config import RAGConfig

_RAG_CONFTEST_PATH = Path(__file__).resolve().parents[1] / "rag" / "conftest.py"
_RAG_CONFTEST_SPEC = importlib.util.spec_from_file_location("_rag_test_fixtures", _RAG_CONFTEST_PATH)
if _RAG_CONFTEST_SPEC is None or _RAG_CONFTEST_SPEC.loader is None:
    raise RuntimeError(f"Could not load RAG fixture module from {_RAG_CONFTEST_PATH}")
_rag_test_fixtures = importlib.util.module_from_spec(_RAG_CONFTEST_SPEC)
_RAG_CONFTEST_SPEC.loader.exec_module(_rag_test_fixtures)

FakeEmbeddingBackend = _rag_test_fixtures.FakeEmbeddingBackend
_write_json = _rag_test_fixtures._write_json
_write_jsonl = _rag_test_fixtures._write_jsonl
all_docs = _rag_test_fixtures.all_docs
built_rag_root = _rag_test_fixtures.built_rag_root
concept_expander = _rag_test_fixtures.concept_expander
doc_store = _rag_test_fixtures.doc_store
embedding_index = _rag_test_fixtures.embedding_index
fake_backend = _rag_test_fixtures.fake_backend
hybrid_retriever = _rag_test_fixtures.hybrid_retriever
lexical_index = _rag_test_fixtures.lexical_index
patch_fake_sentence_transformer = _rag_test_fixtures.patch_fake_sentence_transformer
rag_config = _rag_test_fixtures.rag_config
rag_corpus_root = _rag_test_fixtures.rag_corpus_root
rag_output_root = _rag_test_fixtures.rag_output_root

__all__ = [
    "FakeEmbeddingBackend",
    "_write_json",
    "_write_jsonl",
    "all_docs",
    "built_rag_root",
    "concept_expander",
    "doc_store",
    "embedding_index",
    "explorer_client",
    "explorer_repo",
    "explorer_service",
    "fake_backend",
    "hybrid_retriever",
    "lexical_index",
    "patch_fake_sentence_transformer",
    "rag_config",
    "rag_corpus_root",
    "rag_output_root",
    "real_browser_client",
]


@pytest.fixture
def explorer_repo(rag_config: RAGConfig, built_rag_root: Path, patch_fake_sentence_transformer):
    return ExplorerRepository.from_paths(rag_config.rag_root, rag_config.corpus_root)


@pytest.fixture
def explorer_service(explorer_repo: ExplorerRepository, hybrid_retriever):
    return ExplorerService(explorer_repo, hybrid_retriever)


@pytest.fixture
def explorer_client(rag_config: RAGConfig, built_rag_root: Path, patch_fake_sentence_transformer):
    from pipeline.rag.api import app, init_app

    init_app(rag_config)
    return TestClient(app)


@pytest.fixture
def real_browser_client():
    from pipeline.rag.api import app, init_app

    cfg = RAGConfig()
    if not (cfg.rag_root / "retrieval_docs_all.jsonl").exists():
        pytest.skip("Workspace RAG artifacts are required for browser regression tests")
    init_app(cfg)
    return TestClient(app)
