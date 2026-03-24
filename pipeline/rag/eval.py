"""Evaluation harness for the hybrid RAG system."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.rag.config import RAGConfig
from pipeline.rag.retriever import HybridRetriever

STEP31_METRICS_SCHEMA_VERSION = "step31-v2"
STEP31_REQUIRED_METRIC_KEYS: tuple[str, ...] = (
    "recall_at_5",
    "recall_at_10",
    "mrr",
    "concept_detection_success_proxy",
    "evidence_presence_rate",
    "timestamp_presence_rate",
    "evidence_id_rate",
    "example_lookup_evidence_top1_rate",
    "support_policy_evidence_top3_rate",
    "support_policy_visual_evidence_top3_rate",
    "transcript_only_transcript_primary_top1_rate",
    "cross_lesson_concept_top3_rate",
    "timeframe_concept_top3_rate",
)

CURATED_QUERIES: list[dict[str, Any]] = [
    {"query_id": "q001", "query_text": "Как определить уровень для стоп-лосса?", "category": "direct_rule_lookup", "expected_unit_types": ["rule_card"], "expected_concepts": ["Stop Loss"], "relevant_doc_ids": [], "notes": "Direct rule lookup."},
    {"query_id": "q002", "query_text": "Правила постановки тейк-профита", "category": "direct_rule_lookup", "expected_unit_types": ["rule_card"], "expected_concepts": ["Take Profit"], "relevant_doc_ids": [], "notes": "Direct rule lookup."},
    {"query_id": "q003", "query_text": "Что такое BPU в Price Action?", "category": "direct_rule_lookup", "expected_unit_types": ["rule_card", "concept_node"], "expected_concepts": ["BPU"], "relevant_doc_ids": [], "notes": "Definition-style lookup."},
    {"query_id": "q004", "query_text": "Как работает накопление возле уровня?", "category": "direct_rule_lookup", "expected_unit_types": ["rule_card", "knowledge_event"], "expected_concepts": ["Accumulation"], "relevant_doc_ids": [], "notes": "Concept rule lookup."},
    {"query_id": "q005", "query_text": "Правила входа после ложного пробоя", "category": "direct_rule_lookup", "expected_unit_types": ["rule_card"], "expected_concepts": ["Ложный пробой"], "relevant_doc_ids": [], "notes": "Rule lookup for breakout/failure setup."},
    {"query_id": "q006", "query_text": "Когда правило стоп-лосса не работает?", "category": "invalidation", "expected_unit_types": ["rule_card", "knowledge_event"], "expected_concepts": ["Stop Loss"], "relevant_doc_ids": [], "notes": "Invalidation query."},
    {"query_id": "q007", "query_text": "Исключения из правил управления позицией", "category": "invalidation", "expected_unit_types": ["rule_card"], "expected_concepts": ["Trade Management"], "relevant_doc_ids": [], "notes": "Exception lookup."},
    {"query_id": "q008", "query_text": "Условия отмены входа в позицию", "category": "invalidation", "expected_unit_types": ["rule_card", "knowledge_event"], "expected_concepts": ["Trade Management"], "relevant_doc_ids": [], "notes": "Cancellation/invalidation lookup."},
    {"query_id": "q009", "query_text": "Разница между техническим и обычным стоп-лоссом", "category": "concept_comparison", "expected_unit_types": ["rule_card", "concept_relation"], "expected_concepts": ["Technical Stop Loss", "Stop Loss"], "relevant_doc_ids": [], "notes": "Comparison query."},
    {"query_id": "q010", "query_text": "BPU versus обычный бар", "category": "concept_comparison", "expected_unit_types": ["rule_card", "concept_relation"], "expected_concepts": ["BPU"], "relevant_doc_ids": [], "notes": "Cross-language comparison."},
    {"query_id": "q011", "query_text": "Сравнение стоп-лосса и тейк-профита", "category": "concept_comparison", "expected_unit_types": ["rule_card", "concept_relation"], "expected_concepts": ["Stop Loss", "Take Profit"], "relevant_doc_ids": [], "notes": "Comparison query."},
    {"query_id": "q012", "query_text": "Покажи пример накопления на графике", "category": "example_lookup", "expected_unit_types": ["evidence_ref"], "expected_concepts": ["Accumulation"], "relevant_doc_ids": [], "notes": "Evidence-focused query."},
    {"query_id": "q013", "query_text": "Визуальный пример ложного пробоя уровня", "category": "example_lookup", "expected_unit_types": ["evidence_ref"], "expected_concepts": ["Ложный пробой"], "relevant_doc_ids": [], "notes": "Evidence-focused query."},
    {"query_id": "q014", "query_text": "Пример постановки стоп-лосса", "category": "example_lookup", "expected_unit_types": ["evidence_ref", "rule_card"], "expected_concepts": ["Stop Loss"], "relevant_doc_ids": [], "notes": "Evidence plus rule support."},
    {"query_id": "q015", "query_text": "Какие уроки обсуждают volume confirmation?", "category": "lesson_coverage", "expected_unit_types": ["knowledge_event", "concept_node"], "expected_concepts": ["анализ объема"], "relevant_doc_ids": [], "notes": "Lesson coverage query."},
    {"query_id": "q016", "query_text": "О чем рассказывал урок про Price Action?", "category": "lesson_coverage", "expected_unit_types": ["knowledge_event", "rule_card"], "expected_concepts": ["Price Action"], "relevant_doc_ids": [], "notes": "Lesson coverage query."},
    {"query_id": "q017", "query_text": "Что общего между уровнями и стоп-лоссом?", "category": "cross_lesson_conflict", "expected_unit_types": ["concept_relation", "concept_node"], "expected_concepts": ["Уровень", "Stop Loss"], "relevant_doc_ids": [], "notes": "Graph relation query."},
    {"query_id": "q018", "query_text": "Какие правила связаны с анализом таймфреймов?", "category": "cross_lesson_conflict", "expected_unit_types": ["rule_card", "concept_node"], "expected_concepts": ["Анализ таймфреймов"], "relevant_doc_ids": [], "notes": "Concept/rule linkage query."},
    {"query_id": "q019", "query_text": "Концепции связанные с волатильностью", "category": "cross_lesson_conflict", "expected_unit_types": ["concept_node", "concept_relation"], "expected_concepts": ["Волатильность"], "relevant_doc_ids": [], "notes": "Graph expansion query."},
    {"query_id": "q020", "query_text": "Как определить дневной уровень?", "category": "higher_timeframe_dependency", "expected_unit_types": ["rule_card", "knowledge_event"], "expected_concepts": ["Уровень"], "relevant_doc_ids": [], "notes": "Higher timeframe dependency."},
    {"query_id": "q021", "query_text": "Правила торговли на разных таймфреймах", "category": "higher_timeframe_dependency", "expected_unit_types": ["rule_card"], "expected_concepts": ["Анализ таймфреймов"], "relevant_doc_ids": [], "notes": "Timeframe query."},
    {"query_id": "q022", "query_text": "Какие правила подтверждаются только по transcript?", "category": "support_policy", "expected_unit_types": ["rule_card", "knowledge_event"], "expected_concepts": [], "relevant_doc_ids": [], "notes": "Support-basis query."},
    {"query_id": "q023", "query_text": "Какие примеры требуют визуальных доказательств?", "category": "support_policy", "expected_unit_types": ["evidence_ref", "rule_card"], "expected_concepts": [], "relevant_doc_ids": [], "notes": "Evidence policy query."},
    {"query_id": "q024", "query_text": "Stop loss placement rules", "category": "multilingual", "expected_unit_types": ["rule_card"], "expected_concepts": ["Stop Loss"], "relevant_doc_ids": [], "notes": "English query."},
    {"query_id": "q025", "query_text": "Take profit strategy", "category": "multilingual", "expected_unit_types": ["rule_card"], "expected_concepts": ["Take Profit"], "relevant_doc_ids": [], "notes": "English query."},
    {"query_id": "q026", "query_text": "БСУ бар строительный упорный", "category": "multilingual", "expected_unit_types": ["rule_card", "concept_node"], "expected_concepts": ["BPU"], "relevant_doc_ids": [], "notes": "Alias lookup."},
    {"query_id": "q027", "query_text": "Re-test уровня после пробоя", "category": "multilingual", "expected_unit_types": ["rule_card", "concept_node"], "expected_concepts": ["Re-test"], "relevant_doc_ids": [], "notes": "Mixed-language alias lookup."},
]


def _recall_at_k(
    hits: list[dict[str, Any]],
    relevant_doc_ids: list[str],
    expected_unit_types: list[str],
    k: int,
) -> float:
    if relevant_doc_ids:
        found = any(hit.get("doc_id") in relevant_doc_ids for hit in hits[:k])
        return 1.0 if found else 0.0
    if not expected_unit_types:
        return 1.0 if hits else 0.0
    found = any(hit.get("unit_type") in expected_unit_types for hit in hits[:k])
    return 1.0 if found else 0.0


def _mrr(
    hits: list[dict[str, Any]],
    relevant_doc_ids: list[str],
    expected_unit_types: list[str],
) -> float:
    if not expected_unit_types and not relevant_doc_ids:
        return 1.0 if hits else 0.0
    for i, hit in enumerate(hits, 1):
        if relevant_doc_ids and hit.get("doc_id") in relevant_doc_ids:
            return 1.0 / i
        if expected_unit_types and hit.get("unit_type") in expected_unit_types:
            return 1.0 / i
    return 0.0


def _concept_detected(
    expansion: dict[str, Any],
    expected_concepts: list[str],
    normalized_query: str = "",
) -> bool:
    """Match expected concept labels against expansion + normalized query (Step 3.1)."""
    if not expected_concepts:
        return True
    haystack: set[str] = set()
    for key in ("detected_terms", "related_terms", "lexical_expansion_terms"):
        for t in expansion.get(key) or []:
            s = str(t).lower().strip()
            if s:
                haystack.add(s)
    for cid in expansion.get("canonical_concept_ids") or []:
        s = str(cid).lower()
        haystack.add(s)
        if ":" in s:
            tail = s.split(":", 1)[-1].replace("_", " ")
            haystack.add(tail)
    for cid in expansion.get("expanded_concept_ids") or []:
        s = str(cid).lower()
        haystack.add(s)
        if ":" in s:
            haystack.add(s.split(":", 1)[-1].replace("_", " "))
    for d in (expansion.get("exact_alias_matches") or {}, expansion.get("normalized_alias_matches") or {}):
        for k in d:
            s = str(k).lower().strip()
            if s:
                haystack.add(s)
    nq = (normalized_query or "").lower()

    def matches(expected: str) -> bool:
        el = expected.lower().strip()
        if not el:
            return True
        if el in nq:
            return True
        for h in haystack:
            if el in h or h in el:
                return True
        tokens = [t for t in re.split(r"[^\w\u0400-\u04FF]+", el) if len(t) >= 2]
        if not tokens:
            return False
        blob = " ".join(haystack) + " " + nq
        return all(tok.lower() in blob for tok in tokens)

    return all(matches(e) for e in expected_concepts)


def _presence_rate(hits: list[dict[str, Any]], key: str) -> float:
    if not hits:
        return 0.0
    present = sum(1 for hit in hits if hit.get(key))
    return present / len(hits)


def run_eval(
    retriever: HybridRetriever,
    cfg: RAGConfig,
    queries_path: str | None = None,
    k_values: list[int] | None = None,
) -> dict[str, Any]:
    """Run evaluation queries and compute metrics."""
    k_values = k_values or [5, 10]

    queries: list[dict[str, Any]]
    if queries_path:
        queries = json.loads(Path(queries_path).read_text(encoding="utf-8"))
    else:
        queries = CURATED_QUERIES

    cfg.eval_dir.mkdir(parents=True, exist_ok=True)
    (cfg.eval_dir / "eval_queries.json").write_text(
        json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    results: list[dict[str, Any]] = []
    recall_sums: dict[int, float] = {k: 0.0 for k in k_values}
    mrr_sum = 0.0
    concept_hits = 0
    total = len(queries)
    unit_hit_counts: dict[str, int] = {}
    unit_miss_counts: dict[str, int] = {}
    category_scores: dict[str, list[float]] = {}

    for q in queries:
        query_text = q["query_text"]
        expected_unit_types = q.get("expected_unit_types") or []
        expected_concepts = q.get("expected_concepts") or []
        relevant_doc_ids = q.get("relevant_doc_ids") or []
        category = q.get("category", "unknown")

        result = retriever.search(query_text, top_k=max(k_values))
        hits = result["top_hits"]
        expansion = result["expansion"]
        norm_q = str(result.get("normalized_query") or "")
        intent_signals = result.get("intent_signals") or {}

        r_at_k = {
            k: _recall_at_k(hits, relevant_doc_ids, expected_unit_types, k)
            for k in k_values
        }
        mrr_val = _mrr(hits, relevant_doc_ids, expected_unit_types)
        cd = _concept_detected(expansion, expected_concepts, normalized_query=norm_q)
        evidence_ref_in_top3 = any(h.get("unit_type") == "evidence_ref" for h in hits[:3])
        concept_unit_in_top3 = any(
            h.get("unit_type") in {"concept_node", "concept_relation"}
            for h in hits[:3]
        )
        transcript_primary_top1 = bool(hits) and (
            ((hits[0].get("resolved_doc") or {}).get("support_basis") == "transcript_primary")
        )
        evidence_rate = _presence_rate(hits, "evidence_ids")
        timestamp_rate = _presence_rate(hits, "timestamps")
        evidence_id_rate = _presence_rate(hits, "evidence_ids")

        for k in k_values:
            recall_sums[k] += r_at_k[k]
        mrr_sum += mrr_val
        if cd:
            concept_hits += 1

        for expected_unit in expected_unit_types:
            if r_at_k[max(k_values)] > 0:
                unit_hit_counts[expected_unit] = unit_hit_counts.get(expected_unit, 0) + 1
            else:
                unit_miss_counts[expected_unit] = unit_miss_counts.get(expected_unit, 0) + 1

        category_scores.setdefault(category, []).append(r_at_k[max(k_values)])

        results.append({
            "query_id": q["query_id"],
            "query_text": query_text,
            "category": category,
            "expected_unit_types": expected_unit_types,
            "expected_concepts": expected_concepts,
            "relevant_doc_ids": relevant_doc_ids,
            "recall_at_k": r_at_k,
            "mrr": mrr_val,
            "concept_detected": cd,
            "evidence_presence_rate": evidence_rate,
            "timestamp_presence_rate": timestamp_rate,
            "evidence_id_rate": evidence_id_rate,
            "hit_count": len(hits),
            "top_hit_unit_type": hits[0]["unit_type"] if hits else None,
            "top_hit_score": hits[0]["score"] if hits else None,
            "detected_intents": result.get("detected_intents") or [],
            "intent_signals": intent_signals,
            "top_hit_support_basis": ((hits[0].get("resolved_doc") or {}).get("support_basis") if hits else None),
            "top3_unit_types": [h.get("unit_type") for h in hits[:3]],
            "evidence_ref_in_top3": evidence_ref_in_top3,
            "concept_unit_in_top3": concept_unit_in_top3,
            "transcript_primary_top1": transcript_primary_top1,
        })

    ex_rows = [r for r in results if r["category"] == "example_lookup"]
    sp_rows = [r for r in results if r["category"] == "support_policy"]
    visual_support_rows = [
        r for r in results
        if r["category"] == "support_policy"
        and bool((r.get("intent_signals") or {}).get("prefers_visual_evidence"))
    ]
    transcript_rows = [
        r for r in results
        if r["category"] == "support_policy"
        and bool((r.get("intent_signals") or {}).get("prefers_transcript_only"))
    ]
    cross_rows = [r for r in results if r["category"] == "cross_lesson_conflict"]
    timeframe_rows = [r for r in results if r["category"] == "higher_timeframe_dependency"]

    metrics = {
        f"recall_at_{k}": round(recall_sums[k] / total, 4) if total else 0
        for k in k_values
    }
    metrics["mrr"] = round(mrr_sum / total, 4) if total else 0
    metrics["concept_detection_success_proxy"] = round(concept_hits / total, 4) if total else 0
    metrics["evidence_presence_rate"] = round(
        sum(result["evidence_presence_rate"] for result in results) / total, 4
    ) if total else 0
    metrics["timestamp_presence_rate"] = round(
        sum(result["timestamp_presence_rate"] for result in results) / total, 4
    ) if total else 0
    metrics["evidence_id_rate"] = round(
        sum(result["evidence_id_rate"] for result in results) / total, 4
    ) if total else 0
    metrics["example_lookup_evidence_top1_rate"] = (
        round(sum(1 for r in ex_rows if r.get("top_hit_unit_type") == "evidence_ref") / len(ex_rows), 4)
        if ex_rows
        else 1.0
    )
    metrics["support_policy_evidence_top3_rate"] = (
        round(sum(1 for r in sp_rows if r.get("evidence_ref_in_top3")) / len(sp_rows), 4)
        if sp_rows
        else 1.0
    )
    metrics["support_policy_visual_evidence_top3_rate"] = (
        round(
            sum(1 for r in visual_support_rows if r.get("evidence_ref_in_top3")) / len(visual_support_rows),
            4,
        )
        if visual_support_rows
        else 1.0
    )
    metrics["transcript_only_transcript_primary_top1_rate"] = (
        round(sum(1 for r in transcript_rows if r.get("transcript_primary_top1")) / len(transcript_rows), 4)
        if transcript_rows
        else 1.0
    )
    metrics["cross_lesson_concept_top3_rate"] = (
        round(sum(1 for r in cross_rows if r.get("concept_unit_in_top3")) / len(cross_rows), 4)
        if cross_rows
        else 1.0
    )
    metrics["timeframe_concept_top3_rate"] = (
        round(sum(1 for r in timeframe_rows if r.get("concept_unit_in_top3")) / len(timeframe_rows), 4)
        if timeframe_rows
        else 1.0
    )

    report = {
        "query_count": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics_schema_version": STEP31_METRICS_SCHEMA_VERSION,
        "queries_source": str(queries_path) if queries_path else "builtin",
        "metrics": metrics,
        "unit_hit_rates": {
            ut: round(unit_hit_counts.get(ut, 0) / (unit_hit_counts.get(ut, 0) + unit_miss_counts.get(ut, 0)), 4)
            for ut in set(list(unit_hit_counts.keys()) + list(unit_miss_counts.keys()))
        },
        "category_avg_recall": {
            cat: round(sum(scores) / len(scores), 4) if scores else 0
            for cat, scores in sorted(category_scores.items())
        },
        "query_results": results,
    }

    (cfg.eval_dir / "eval_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (cfg.eval_dir / "eval_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return report
