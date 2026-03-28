"""Persisted BM25 lexical index over retrieval documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_]+")
_PHRASE_RE = re.compile(r'"([^"]+)"')


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class LexicalIndex:
    def __init__(
        self,
        doc_ids: list[str],
        unit_types: list[str],
        lesson_ids: list[str],
        concept_ids: list[list[str]],
        alias_terms: list[list[str]],
        titles: list[str],
        texts: list[str],
        keywords: list[list[str]],
        tokenized_corpus: list[list[str]],
    ) -> None:
        self._doc_ids = doc_ids
        self._unit_types = unit_types
        self._lesson_ids = lesson_ids
        self._concept_ids = concept_ids
        self._alias_terms = alias_terms
        self._titles = titles
        self._texts = texts
        self._keywords = keywords
        self._tokenized_corpus = tokenized_corpus
        self._index = BM25Okapi(tokenized_corpus)
        self._unit_masks: dict[str, np.ndarray] = {}
        arr = np.array(unit_types)
        for ut in set(unit_types):
            self._unit_masks[ut] = arr == ut
        self._lesson_masks: dict[str, np.ndarray] = {}
        lesson_arr = np.array(lesson_ids)
        for lesson_id in set(lesson_ids):
            self._lesson_masks[lesson_id] = lesson_arr == lesson_id

    @staticmethod
    def build(docs: list[dict[str, Any]]) -> LexicalIndex:
        doc_ids: list[str] = []
        unit_types: list[str] = []
        lesson_ids: list[str] = []
        concept_ids: list[list[str]] = []
        alias_terms: list[list[str]] = []
        titles: list[str] = []
        texts: list[str] = []
        keywords: list[list[str]] = []
        corpus: list[list[str]] = []
        for d in docs:
            doc_ids.append(d["doc_id"])
            unit_types.append(d["unit_type"])
            lesson_ids.append(d.get("lesson_id") or "corpus")
            concept_ids.append(list(d.get("canonical_concept_ids") or []))
            alias_terms.append(list(d.get("alias_terms") or []))
            titles.append(d.get("title", ""))
            texts.append(d.get("text", ""))
            keywords.append(list(d.get("keywords") or []))
            combined = " ".join([
                d.get("title", ""),
                d.get("text", ""),
                " ".join(d.get("keywords") or []),
                " ".join(d.get("alias_terms") or []),
                " ".join(d.get("canonical_concept_ids") or []),
            ])
            corpus.append(tokenize(combined))
        return LexicalIndex(
            doc_ids=doc_ids,
            unit_types=unit_types,
            lesson_ids=lesson_ids,
            concept_ids=concept_ids,
            alias_terms=alias_terms,
            titles=titles,
            texts=texts,
            keywords=keywords,
            tokenized_corpus=corpus,
        )

    def search(
        self,
        query: str,
        top_k: int = 30,
        unit_types: list[str] | None = None,
        lesson_ids: list[str] | None = None,
        concept_ids: list[str] | None = None,
        allowed_ids: set[str] | None = None,
        alias_terms: list[str] | None = None,
        phrase_boost: float = 0.35,
        alias_boost: float = 0.20,
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

        if lesson_ids:
            mask = np.zeros(len(self._doc_ids), dtype=bool)
            for lesson_id in lesson_ids:
                if lesson_id in self._lesson_masks:
                    mask |= self._lesson_masks[lesson_id]
            scores = scores * mask

        if concept_ids:
            concept_id_set = set(concept_ids)
            concept_mask = np.array([
                bool(concept_id_set & set(doc_concepts))
                for doc_concepts in self._concept_ids
            ])
            scores = scores * concept_mask

        if allowed_ids is not None:
            id_mask = np.array([did in allowed_ids for did in self._doc_ids])
            scores = scores * id_mask

        phrase_terms = [phrase.lower() for phrase in _PHRASE_RE.findall(query)]
        if not phrase_terms and len(tokens) > 1:
            phrase_terms = [" ".join(tokens)]
        for phrase in phrase_terms:
            if not phrase:
                continue
            phrase_mask = np.array([
                phrase in f"{title} {text}".lower()
                for title, text in zip(self._titles, self._texts, strict=False)
            ], dtype=float)
            scores = scores + (phrase_mask * phrase_boost)

        alias_term_set = {term.lower() for term in (alias_terms or []) if term.strip()}
        if alias_term_set:
            alias_match_scores = np.array([
                len(alias_term_set & {term.lower() for term in doc_alias_terms})
                for doc_alias_terms in self._alias_terms
            ], dtype=float)
            scores = scores + (alias_match_scores * alias_boost)

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
            "avg_doc_length": self._index.avgdl,
        }
        (index_dir / "lexical_index_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        data = {
            "doc_ids": self._doc_ids,
            "unit_types": self._unit_types,
            "lesson_ids": self._lesson_ids,
            "concept_ids": self._concept_ids,
            "alias_terms": self._alias_terms,
            "titles": self._titles,
            "texts": self._texts,
            "keywords": self._keywords,
            "tokenized_corpus": self._tokenized_corpus,
            "doc_lengths": [len(tokens) for tokens in self._tokenized_corpus],
        }
        (index_dir / "lexical_index_data.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, index_dir: Path) -> "LexicalIndex":
        data = json.loads((index_dir / "lexical_index_data.json").read_text(encoding="utf-8"))
        return cls(
            doc_ids=data["doc_ids"],
            unit_types=data["unit_types"],
            lesson_ids=data["lesson_ids"],
            concept_ids=data["concept_ids"],
            alias_terms=data["alias_terms"],
            titles=data["titles"],
            texts=data["texts"],
            keywords=data["keywords"],
            tokenized_corpus=data["tokenized_corpus"],
        )

    @classmethod
    def load_from_store(cls, docs: list[dict[str, Any]], index_dir: Path | None = None) -> "LexicalIndex":
        if index_dir and (index_dir / "lexical_index_data.json").exists():
            return cls.load(index_dir)
        return cls.build(docs)
