"""Concept graph expansion for query enrichment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.rag.contracts import GraphExpansionResult, GraphExpansionTraceStep


_NON_WORD_RE = re.compile(r"[^a-zA-Zа-яА-ЯёЁ0-9]+")


def _query_mentions_term(query_lower: str, term_lower: str) -> bool:
    """Tier-1 exact match: short tokens allow substring; longer terms use word-boundary style match."""
    if not term_lower:
        return False
    if len(term_lower) < 4:
        return term_lower in query_lower
    try:
        return (
            re.search(
                r"(?<![a-zа-яё0-9])" + re.escape(term_lower) + r"(?![a-zа-яё0-9])",
                query_lower,
            )
            is not None
        )
    except re.error:
        return term_lower in query_lower


def _normalized_contains_phrase(normalized_query: str, phrase: str) -> bool:
    if not phrase:
        return False
    return f" {phrase} " in f" {normalized_query} "


def _conservative_token_match(normalized_query: str, phrase: str) -> bool:
    """Fallback for inflected/plural forms: require per-token 4-char prefix agreement."""
    if not normalized_query or not phrase:
        return False
    q_tokens = [tok for tok in normalized_query.split() if tok]
    p_tokens = [tok for tok in phrase.split() if tok]
    if not q_tokens or not p_tokens:
        return False

    def _token_matches(a: str, b: str) -> bool:
        if a == b:
            return True
        if len(a) < 5 or len(b) < 5:
            return False
        return a[:4] == b[:4]

    used: set[int] = set()
    for pt in p_tokens:
        found = False
        for idx, qt in enumerate(q_tokens):
            if idx in used:
                continue
            if _token_matches(qt, pt):
                used.add(idx)
                found = True
                break
        if not found:
            return False
    return True


def normalize_term(text: str) -> str:
    lowered = text.strip().lower()
    return _NON_WORD_RE.sub(" ", lowered).strip()


def _augment_timeframe_aliases(alias_registry: dict[str, Any]) -> dict[str, Any]:
    """Inject high-value compound timeframe aliases missing from the corpus export."""
    timeframe_aliases: dict[str, tuple[str, ...]] = {
        "node:analiz_taymfreymov": (
            "дневной таймфрейм",
            "локальный таймфрейм",
            "старший таймфрейм",
            "старшие таймфреймы",
            "младший таймфрейм",
            "разные таймфреймы",
            "дневка",
            "часовик",
        ),
        "node:soglasovannost_taymfreymov": (
            "согласованность таймфреймов",
        ),
        "node:vybor_urovney": (
            "дневной уровень",
            "уровень с дневки",
        ),
        "node:taymfreym": (
            "таймфрейм",
        ),
        "node:taymfreymy": (
            "таймфреймы",
        ),
    }
    for gid, extra_aliases in timeframe_aliases.items():
        info = alias_registry.get(gid)
        if not isinstance(info, dict):
            continue
        aliases = list(info.get("aliases") or [])
        for alias in extra_aliases:
            if alias not in aliases:
                aliases.append(alias)
        info["aliases"] = aliases
    return alias_registry


def _augment_stoploss_aliases(alias_registry: dict[str, Any]) -> dict[str, Any]:
    """Inject high-value stop-loss phrase aliases missing from the corpus export."""
    stoploss_aliases: dict[str, tuple[str, ...]] = {
        "node:stop_loss": (
            "стоп-лосс",
            "стоп лосс",
            "стоп-лосса",
            "стоп лосса",
            "стоплосс",
            "stop-loss",
            "постановка стоп-лосса",
            "постановки стоп-лосса",
            "пример стоп-лосса",
            "пример постановки стоп-лосса",
            "где ставить стоп",
            "куда ставить стоп",
        ),
        "node:raschetnyy_stop_loss": (
            "расчетный стоп",
            "расчетный стоп-лосс",
        ),
        "node:razmer_stop_lossa": (
            "размер стоп-лосса",
            "размер стопа",
        ),
        "node:tekhnicheskiy_stop_loss": (
            "технический стоп-лосс",
            "технический стоп",
        ),
        "node:technical_stop_loss": (
            "technical stop",
            "technical stop loss",
        ),
    }
    for gid, extra_aliases in stoploss_aliases.items():
        info = alias_registry.get(gid)
        if not isinstance(info, dict):
            continue
        aliases = list(info.get("aliases") or [])
        for alias in extra_aliases:
            if alias not in aliases:
                aliases.append(alias)
        info["aliases"] = aliases
    return alias_registry


class ConceptExpander:
    def __init__(
        self,
        alias_registry: dict[str, Any],
        concept_rule_map: dict[str, list[str]],
        graph: dict[str, Any],
        rule_family_index: dict[str, list[str]],
        overlap_report: list[dict[str, Any]],
        max_hops: int = 1,
        max_expanded_per_concept: int = 3,
    ) -> None:
        alias_registry = _augment_stoploss_aliases(_augment_timeframe_aliases(alias_registry))
        self._max_hops = max_hops
        self._max_expanded = max_expanded_per_concept
        self._concept_rule_map = concept_rule_map
        self._rule_family_index = rule_family_index
        self._overlap_report = overlap_report

        self._name_to_id: dict[str, str] = {}
        self._normalized_name_to_id: dict[str, str] = {}
        self._alias_to_id: dict[str, str] = {}
        self._normalized_alias_to_id: dict[str, str] = {}
        self._concept_name_by_id: dict[str, str] = {}
        for gid, info in alias_registry.items():
            name = (info.get("name") or "").strip()
            if name:
                self._concept_name_by_id[gid] = name
                self._name_to_id[name.lower()] = gid
                self._normalized_name_to_id[normalize_term(name)] = gid
            for alias in info.get("aliases") or []:
                a = alias.strip()
                if a:
                    self._alias_to_id[a.lower()] = gid
                    self._normalized_alias_to_id[normalize_term(a)] = gid

        self._adjacency: dict[str, list[tuple[str, str]]] = {}
        for rel in graph.get("relations", []):
            src = rel.get("source_id", "")
            tgt = rel.get("target_id", "")
            rtype = rel.get("relation_type", "")
            self._adjacency.setdefault(src, []).append((tgt, rtype))
            self._adjacency.setdefault(tgt, []).append((src, rtype))

    @classmethod
    def from_corpus(cls, corpus_root: Path, max_hops: int = 1, max_expanded: int = 3) -> "ConceptExpander":
        alias_reg = json.loads((corpus_root / "concept_alias_registry.json").read_text(encoding="utf-8"))
        crm = json.loads((corpus_root / "concept_rule_map.json").read_text(encoding="utf-8"))
        graph = json.loads((corpus_root / "corpus_concept_graph.json").read_text(encoding="utf-8"))
        rule_family_index = json.loads((corpus_root / "rule_family_index.json").read_text(encoding="utf-8"))
        overlap_report = json.loads((corpus_root / "concept_overlap_report.json").read_text(encoding="utf-8"))
        return cls(
            alias_reg,
            crm,
            graph,
            rule_family_index,
            overlap_report,
            max_hops=max_hops,
            max_expanded_per_concept=max_expanded,
        )

    def _detect_concepts(
        self,
        query: str,
    ) -> tuple[list[str], dict[str, str], dict[str, str], dict[str, str]]:
        lowered = query.strip().lower()
        normalized = normalize_term(query)
        detected_terms: list[str] = []
        exact_alias_matches: dict[str, str] = {}
        normalized_alias_matches: dict[str, str] = {}
        token_alias_matches: dict[str, str] = {}

        matched_gids: set[str] = set()

        for name, gid in sorted(self._name_to_id.items(), key=lambda x: -len(x[0])):
            if _query_mentions_term(lowered, name):
                exact_alias_matches[name] = gid
                matched_gids.add(gid)
                if name not in detected_terms:
                    detected_terms.append(name)

        for alias, gid in sorted(self._alias_to_id.items(), key=lambda x: -len(x[0])):
            if _query_mentions_term(lowered, alias):
                exact_alias_matches[alias] = gid
                matched_gids.add(gid)
                if alias not in detected_terms:
                    detected_terms.append(alias)

        for name, gid in self._normalized_name_to_id.items():
            if (
                name
                and _normalized_contains_phrase(normalized, name)
                and gid not in matched_gids
            ):
                normalized_alias_matches[name] = gid
                matched_gids.add(gid)
                if name not in detected_terms:
                    detected_terms.append(name)

        for alias, gid in self._normalized_alias_to_id.items():
            if (
                alias
                and _normalized_contains_phrase(normalized, alias)
                and gid not in matched_gids
            ):
                normalized_alias_matches[alias] = gid
                matched_gids.add(gid)
                if alias not in detected_terms:
                    detected_terms.append(alias)

        for name, gid in self._normalized_name_to_id.items():
            if name and gid not in matched_gids and _conservative_token_match(normalized, name):
                token_alias_matches[name] = gid
                matched_gids.add(gid)
                if name not in detected_terms:
                    detected_terms.append(name)

        for alias, gid in self._normalized_alias_to_id.items():
            if alias and gid not in matched_gids and _conservative_token_match(normalized, alias):
                token_alias_matches[alias] = gid
                matched_gids.add(gid)
                if alias not in detected_terms:
                    detected_terms.append(alias)

        return detected_terms, exact_alias_matches, normalized_alias_matches, token_alias_matches

    def _expand_neighbors(self, concept_id: str) -> list[tuple[str, str]]:
        neighbors = self._adjacency.get(concept_id, [])
        return neighbors[: self._max_expanded]

    def _family_rule_boosts(self, detected_terms: list[str]) -> tuple[list[str], list[GraphExpansionTraceStep]]:
        boosted_rule_ids: list[str] = []
        trace: list[GraphExpansionTraceStep] = []
        normalized_terms = {normalize_term(term) for term in detected_terms}
        for family_key, rule_ids in self._rule_family_index.items():
            if normalize_term(family_key) in normalized_terms:
                boosted_rule_ids.extend(rule_ids)
                trace.append(GraphExpansionTraceStep(
                    step_type="rule_family",
                    source=family_key,
                    reason=f"Matched rule family '{family_key}'",
                ))
        return list(dict.fromkeys(boosted_rule_ids)), trace

    def expand_query(self, query: str) -> GraphExpansionResult:
        lowered = query.strip().lower()
        detected_terms, exact_matches, normalized_matches, token_matches = self._detect_concepts(query)
        matched_concept_ids: list[str] = list(dict.fromkeys(
            list(exact_matches.values()) + list(normalized_matches.values()) + list(token_matches.values())
        ))
        all_concept_ids: set[str] = set(matched_concept_ids)
        expanded_concept_ids: list[str] = []
        related_terms: list[str] = []
        trace: list[GraphExpansionTraceStep] = []

        for term, gid in exact_matches.items():
            trace.append(GraphExpansionTraceStep(
                step_type="exact_alias_match",
                source=term,
                target=gid,
                reason=f"Exact alias or concept match for '{term}'",
            ))
        for term, gid in normalized_matches.items():
            trace.append(GraphExpansionTraceStep(
                step_type="normalized_alias_match",
                source=term,
                target=gid,
                reason=f"Normalized alias match for '{term}'",
            ))
        for term, gid in token_matches.items():
            trace.append(GraphExpansionTraceStep(
                step_type="token_alias_match",
                source=term,
                target=gid,
                reason=f"Token-prefix alias match for '{term}'",
            ))

        for gid in matched_concept_ids:
            concept_name = self._concept_name_by_id.get(gid, gid)
            if self._max_hops > 0:
                neighbors = self._expand_neighbors(gid)
                for nid, rtype in neighbors:
                    if nid not in all_concept_ids:
                        all_concept_ids.add(nid)
                        expanded_concept_ids.append(nid)
                        trace.append(GraphExpansionTraceStep(
                            step_type="graph_neighbor",
                            source=gid,
                            target=nid,
                            relation=rtype,
                            reason=f"1-hop {rtype} from {concept_name}",
                        ))

        for row in self._overlap_report:
            concept_id = row.get("concept_id")
            name = row.get("name")
            if concept_id in all_concept_ids and name:
                if name not in related_terms:
                    related_terms.append(name)
                trace.append(GraphExpansionTraceStep(
                    step_type="cross_lesson_overlap",
                    source=concept_id,
                    target=concept_id,
                    reason=f"Concept '{name}' appears across lessons",
                ))

        boosted_rule_ids: list[str] = []
        for cid in all_concept_ids:
            boosted_rule_ids.extend(self._concept_rule_map.get(cid, []))
        boosted_rule_ids = list(dict.fromkeys(boosted_rule_ids))
        family_boosts, family_trace = self._family_rule_boosts(detected_terms)
        boosted_rule_ids = list(dict.fromkeys(boosted_rule_ids + family_boosts))
        trace.extend(family_trace)

        lexical_expansion_terms: list[str] = []
        for rt in related_terms:
            if rt and rt not in lexical_expansion_terms:
                lexical_expansion_terms.append(rt)
        for cid in all_concept_ids:
            nm = self._concept_name_by_id.get(cid, "")
            if nm and nm not in lexical_expansion_terms:
                lexical_expansion_terms.append(nm)
        for term in detected_terms:
            if term and term not in lexical_expansion_terms:
                lexical_expansion_terms.append(term)

        return GraphExpansionResult(
            detected_terms=detected_terms,
            exact_alias_matches=exact_matches,
            normalized_alias_matches=normalized_matches,
            canonical_concept_ids=matched_concept_ids,
            expanded_concept_ids=expanded_concept_ids,
            boosted_rule_ids=boosted_rule_ids,
            related_terms=related_terms,
            expansion_trace=trace,
            lexical_expansion_terms=list(dict.fromkeys(lexical_expansion_terms)),
        )
