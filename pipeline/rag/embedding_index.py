"""Vector embedding index using sentence-transformers.

Full embedding matrix kept in numpy for brute-force cosine search
(fastest at sub-200K scale with 32 GB RAM).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


class EmbeddingIndex:
    def __init__(
        self,
        doc_ids: list[str],
        unit_types: list[str],
        embeddings: np.ndarray,
        model_name: str = "",
    ) -> None:
        self._doc_ids = doc_ids
        self._unit_types = unit_types
        self._embeddings = embeddings
        self._norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        self._norms[self._norms == 0] = 1.0
        self._normalized = embeddings / self._norms
        self._model_name = model_name
        self._unit_masks: dict[str, np.ndarray] = {}
        arr = np.array(unit_types)
        for ut in set(unit_types):
            self._unit_masks[ut] = arr == ut

    @property
    def dim(self) -> int:
        return self._embeddings.shape[1] if len(self._embeddings.shape) > 1 else 0

    @property
    def doc_count(self) -> int:
        return len(self._doc_ids)

    @staticmethod
    def build(
        docs: list[dict[str, Any]],
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        batch_size: int = 256,
    ) -> EmbeddingIndex:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name)
        doc_ids: list[str] = []
        unit_types: list[str] = []
        texts: list[str] = []
        for d in docs:
            doc_ids.append(d["doc_id"])
            unit_types.append(d["unit_type"])
            texts.append(d.get("text", ""))

        embeddings = model.encode(
            texts, batch_size=batch_size, show_progress_bar=True, normalize_embeddings=False,
        )
        return EmbeddingIndex(doc_ids, unit_types, np.array(embeddings), model_name)

    def encode_query(self, query: str) -> np.ndarray:
        if not hasattr(self, "_model") or self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return np.array(self._model.encode([query]))[0]

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 30,
        unit_types: list[str] | None = None,
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
        }
        (index_dir / "embedding_doc_ids.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        manifest = {
            "model_name": self._model_name,
            "dimension": self.dim,
            "doc_count": self.doc_count,
            "backend": "numpy_brute_force_cosine",
        }
        (index_dir / "embedding_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, index_dir: Path) -> EmbeddingIndex:
        embeddings = np.load(index_dir / "embeddings.npy")
        meta = json.loads((index_dir / "embedding_doc_ids.json").read_text(encoding="utf-8"))
        manifest = json.loads((index_dir / "embedding_manifest.json").read_text(encoding="utf-8"))
        return cls(
            doc_ids=meta["doc_ids"],
            unit_types=meta["unit_types"],
            embeddings=embeddings,
            model_name=manifest.get("model_name", ""),
        )
