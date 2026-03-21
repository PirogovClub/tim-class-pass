"""BM25 lexical index over retrieval documents.

Tokenizes on whitespace with lowercase and basic punctuation stripping.
Pre-loaded in RAM for sub-ms query latency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class LexicalIndex:
    def __init__(
        self,
        doc_ids: list[str],
        unit_types: list[str],
        tokenized_corpus: list[list[str]],
    ) -> None:
        self._doc_ids = doc_ids
        self._unit_types = unit_types
        self._index = BM25Okapi(tokenized_corpus)
        self._unit_masks: dict[str, np.ndarray] = {}
        arr = np.array(unit_types)
        for ut in set(unit_types):
            self._unit_masks[ut] = arr == ut

    @staticmethod
    def build(docs: list[dict[str, Any]]) -> LexicalIndex:
        doc_ids: list[str] = []
        unit_types: list[str] = []
        corpus: list[list[str]] = []
        for d in docs:
            doc_ids.append(d["doc_id"])
            unit_types.append(d["unit_type"])
            combined = " ".join([
                d.get("title", ""),
                d.get("text", ""),
                " ".join(d.get("alias_terms") or []),
                " ".join(d.get("canonical_concept_ids") or []),
            ])
            corpus.append(tokenize(combined))
        return LexicalIndex(doc_ids, unit_types, corpus)

    def search(
        self,
        query: str,
        top_k: int = 30,
        unit_types: list[str] | None = None,
        allowed_ids: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._index.get_scores(tokens)

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
        manifest = {
            "backend": "rank_bm25",
            "doc_count": len(self._doc_ids),
            "tokenizer": "whitespace_lowercase_cyrillic",
        }
        (index_dir / "lexical_index_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        data = {
            "doc_ids": self._doc_ids,
            "unit_types": self._unit_types,
        }
        (index_dir / "lexical_doc_ids.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load_from_store(cls, docs: list[dict[str, Any]], index_dir: Path | None = None) -> LexicalIndex:
        """Rebuild BM25 from doc store (fast enough for in-memory startup)."""
        return cls.build(docs)
