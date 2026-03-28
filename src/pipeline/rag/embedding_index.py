"""Vector embedding index with a replaceable embedding backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class EmbeddingBackend(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def model_id(self) -> str: ...

    def dimension(self) -> int: ...


class SentenceTransformerBackend:
    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        batch_size: int = 256,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        vectors = model.encode(
            texts,
            batch_size=self._batch_size,
            show_progress_bar=True,
            normalize_embeddings=False,
        )
        return np.asarray(vectors, dtype=float).tolist()

    def embed_query(self, text: str) -> list[float]:
        model = self._get_model()
        vector = model.encode([text], normalize_embeddings=False)[0]
        return np.asarray(vector, dtype=float).tolist()

    def model_id(self) -> str:
        return self._model_name

    def dimension(self) -> int:
        return int(self._get_model().get_sentence_embedding_dimension())


def _embedding_text(doc: dict[str, Any]) -> str:
    title = doc.get("title", "")
    keywords = " ".join(doc.get("keywords") or [])
    alias_terms = " ".join(doc.get("alias_terms") or [])
    text = doc.get("text", "")
    return " ".join([title, title, keywords, keywords, alias_terms, text]).strip()


class EmbeddingIndex:
    def __init__(
        self,
        doc_ids: list[str],
        unit_types: list[str],
        lesson_ids: list[str],
        embeddings: np.ndarray,
        backend_name: str = "sentence-transformers",
        model_name: str = "",
        backend: EmbeddingBackend | None = None,
    ) -> None:
        self._doc_ids = doc_ids
        self._unit_types = unit_types
        self._lesson_ids = lesson_ids
        self._embeddings = embeddings
        self._norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        self._norms[self._norms == 0] = 1.0
        self._normalized = embeddings / self._norms
        self._backend_name = backend_name
        self._model_name = model_name
        self._backend = backend
        self._unit_masks: dict[str, np.ndarray] = {}
        arr = np.array(unit_types)
        for ut in set(unit_types):
            self._unit_masks[ut] = arr == ut
        self._lesson_masks: dict[str, np.ndarray] = {}
        lesson_arr = np.array(lesson_ids)
        for lesson_id in set(lesson_ids):
            self._lesson_masks[lesson_id] = lesson_arr == lesson_id

    @property
    def dim(self) -> int:
        return self._embeddings.shape[1] if len(self._embeddings.shape) > 1 else 0

    @property
    def doc_count(self) -> int:
        return len(self._doc_ids)

    @staticmethod
    def build(
        docs: list[dict[str, Any]],
        backend: EmbeddingBackend | None = None,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        batch_size: int = 256,
    ) -> "EmbeddingIndex":
        backend = backend or SentenceTransformerBackend(model_name=model_name, batch_size=batch_size)
        doc_ids: list[str] = []
        unit_types: list[str] = []
        lesson_ids: list[str] = []
        texts: list[str] = []
        for d in docs:
            doc_ids.append(d["doc_id"])
            unit_types.append(d["unit_type"])
            lesson_ids.append(d.get("lesson_id") or "corpus")
            texts.append(_embedding_text(d))

        embeddings = np.asarray(
            backend.embed_documents(texts),
            dtype=float,
        )
        return EmbeddingIndex(
            doc_ids=doc_ids,
            unit_types=unit_types,
            lesson_ids=lesson_ids,
            embeddings=embeddings,
            backend_name="sentence-transformers",
            model_name=backend.model_id(),
            backend=backend,
        )

    def encode_query(self, query: str) -> np.ndarray:
        if self._backend is None:
            self._backend = SentenceTransformerBackend(model_name=self._model_name)
        return np.asarray(self._backend.embed_query(query), dtype=float)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 30,
        unit_types: list[str] | None = None,
        lesson_ids: list[str] | None = None,
        allowed_ids: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        qnorm = np.linalg.norm(query_embedding)
        if qnorm == 0:
            return []
        q_normalized = query_embedding / qnorm
        scores = self._normalized @ q_normalized

        if unit_types:
            mask = np.zeros(len(self._doc_ids), dtype=bool)
            for ut in unit_types:
                if ut in self._unit_masks:
                    mask |= self._unit_masks[ut]
            scores = scores * mask

        if lesson_ids:
            mask = np.zeros(len(self._doc_ids), dtype=bool)
            for lesson_id in lesson_ids:
                if lesson_id in self._lesson_masks:
                    mask |= self._lesson_masks[lesson_id]
            scores = scores * mask

        if allowed_ids is not None:
            id_mask = np.array([did in allowed_ids for did in self._doc_ids])
            scores = scores * id_mask

        top_idx = np.argsort(scores)[::-1][:top_k]
        results: list[tuple[str, float]] = []
        for i in top_idx:
            s = float(scores[i])
            if s <= 0:
                break
            results.append((self._doc_ids[i], s))
        return results

    # ── Persistence ──────────────────────────────────────────────────

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "embeddings.npy", self._embeddings)
        meta = {
            "doc_ids": self._doc_ids,
            "unit_types": self._unit_types,
            "lesson_ids": self._lesson_ids,
        }
        (index_dir / "embedding_doc_ids.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        manifest = {
            "model_name": self._model_name,
            "dimension": self.dim,
            "doc_count": self.doc_count,
            "embedding_backend": self._backend_name,
            "backend": "numpy_brute_force_cosine",
        }
        (index_dir / "embedding_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(
        cls,
        index_dir: Path,
        backend: EmbeddingBackend | None = None,
    ) -> "EmbeddingIndex":
        embeddings = np.load(index_dir / "embeddings.npy", allow_pickle=True)
        meta = json.loads((index_dir / "embedding_doc_ids.json").read_text(encoding="utf-8"))
        manifest = json.loads((index_dir / "embedding_manifest.json").read_text(encoding="utf-8"))
        backend = backend or SentenceTransformerBackend(model_name=manifest.get("model_name", ""))
        return cls(
            doc_ids=meta["doc_ids"],
            unit_types=meta["unit_types"],
            lesson_ids=meta.get("lesson_ids") or ["corpus"] * len(meta["doc_ids"]),
            embeddings=embeddings,
            backend_name=manifest.get("embedding_backend", "sentence-transformers"),
            model_name=manifest.get("model_name", ""),
            backend=backend,
        )
