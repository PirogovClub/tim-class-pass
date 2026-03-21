"""Concept graph expansion for query enrichment.

Detects concept mentions, resolves aliases, expands through relations,
and returns boosted concept/rule IDs for retrieval scoring.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ConceptExpander:
    def __init__(
        self,
        alias_registry: dict[str, Any],
        concept_rule_map: dict[str, list[str]],
        graph: dict[str, Any],
        max_hops: int = 1,
        max_expanded_per_concept: int = 3,
    ) -> None:
        self._max_hops = max_hops
        self._max_expanded = max_expanded_per_concept
        self._concept_rule_map = concept_rule_map

        self._name_to_id: dict[str, str] = {}
        self._alias_to_id: dict[str, str] = {}
        for gid, info in alias_registry.items():
            name = (info.get("name") or "").strip().lower()
            if name:
                self._name_to_id[name] = gid
            for alias in info.get("aliases") or []:
                a = alias.strip().lower()
                if a:
                    self._alias_to_id[a] = gid

        self._adjacency: dict[str, list[tuple[str, str]]] = {}
        for rel in graph.get("relations", []):
            src = rel.get("source_id", "")
            tgt = rel.get("target_id", "")
            rtype = rel.get("relation_type", "")
            self._adjacency.setdefault(src, []).append((tgt, rtype))
            self._adjacency.setdefault(tgt, []).append((src, rtype))

    @classmethod
    def from_corpus(cls, corpus_root: Path, max_hops: int = 1, max_expanded: int = 3) -> ConceptExpander:
        alias_reg = json.loads((corpus_root / "concept_alias_registry.json").read_text(encoding="utf-8"))
        crm = json.loads((corpus_root / "concept_rule_map.json").read_text(encoding="utf-8"))
        graph = json.loads((corpus_root / "corpus_concept_graph.json").read_text(encoding="utf-8"))
        return cls(alias_reg, crm, graph, max_hops=max_hops, max_expanded_per_concept=max_expanded)

    def _detect_concepts(self, query: str) -> list[tuple[str, str, str]]:
        """Return (concept_id, matched_term, match_type) for concepts found in query."""
        q = query.strip().lower()
        hits: list[tuple[str, str, str]] = []
        seen: set[str] = set()

        for name, gid in sorted(self._name_to_id.items(), key=lambda x: -len(x[0])):
            if name in q and gid not in seen:
                hits.append((gid, name, "exact_name"))
                seen.add(gid)

        for alias, gid in sorted(self._alias_to_id.items(), key=lambda x: -len(x[0])):
            if alias in q and gid not in seen:
                hits.append((gid, alias, "alias"))
                seen.add(gid)

        return hits

    def _expand_neighbors(self, concept_id: str) -> list[tuple[str, str]]:
        """1-hop expansion through graph edges. Returns (neighbor_id, relation_type)."""
        neighbors = self._adjacency.get(concept_id, [])
        return neighbors[: self._max_expanded]

    def expand_query(self, query: str) -> dict[str, Any]:
        detected = self._detect_concepts(query)
        detected_concepts = [{"concept_id": gid, "matched_term": term, "match_type": mt} for gid, term, mt in detected]

        expanded_concepts: list[dict[str, Any]] = []
        all_concept_ids: set[str] = {gid for gid, _, _ in detected}
        expansion_trace: list[dict[str, Any]] = []

        for gid, term, mt in detected:
            if self._max_hops > 0:
                neighbors = self._expand_neighbors(gid)
                for nid, rtype in neighbors:
                    if nid not in all_concept_ids:
                        all_concept_ids.add(nid)
                        expanded_concepts.append({"concept_id": nid, "via": gid, "relation": rtype})
                        expansion_trace.append({
                            "from": gid,
                            "to": nid,
                            "relation": rtype,
                            "reason": f"1-hop {rtype} from {term}",
                        })

        boosted_rule_ids: list[str] = []
        for cid in all_concept_ids:
            boosted_rule_ids.extend(self._concept_rule_map.get(cid, []))
        boosted_rule_ids = list(dict.fromkeys(boosted_rule_ids))

        return {
            "detected_concepts": detected_concepts,
            "expanded_concepts": expanded_concepts,
            "all_concept_ids": sorted(all_concept_ids),
            "boosted_rule_ids": boosted_rule_ids,
            "expansion_trace": expansion_trace,
        }
