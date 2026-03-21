"""Evaluation harness: curated queries, Recall@k, MRR, per-unit hit rate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.rag.config import RAGConfig
from pipeline.rag.retriever import HybridRetriever

CURATED_QUERIES: list[dict[str, Any]] = [
    # ── Direct rule lookup ───────────────────────────────────────────
    {"query": "Как определить уровень для стоп-лосса?", "category": "direct_rule", "expected_unit": "rule_card", "expected_concept": "Stop Loss"},
    {"query": "Правила постановки тейк-профита", "category": "direct_rule", "expected_unit": "rule_card", "expected_concept": "Take Profit"},
    {"query": "Что такое BPU в Price Action?", "category": "direct_rule", "expected_unit": "rule_card", "expected_concept": "BPU"},
    {"query": "Как работает накопление возле уровня?", "category": "direct_rule", "expected_unit": "rule_card", "expected_concept": "Accumulation"},
    {"query": "Правила входа после ложного пробоя", "category": "direct_rule", "expected_unit": "rule_card", "expected_concept": "Movement near levels"},

    # ── Invalidation / exceptions ────────────────────────────────────
    {"query": "Когда правило стоп-лосса не работает?", "category": "invalidation", "expected_unit": "rule_card", "expected_concept": "Stop Loss"},
    {"query": "Исключения из правил управления позицией", "category": "invalidation", "expected_unit": "rule_card", "expected_concept": "Trade Management"},
    {"query": "Условия отмены входа в позицию", "category": "invalidation", "expected_unit": "rule_card", "expected_concept": "Trade Management"},

    # ── Concept comparison ───────────────────────────────────────────
    {"query": "Разница между техническим и обычным стоп-лоссом", "category": "concept_comparison", "expected_unit": "rule_card", "expected_concept": "Technical Stop Loss"},
    {"query": "BPU versus обычный бар", "category": "concept_comparison", "expected_unit": "rule_card", "expected_concept": "BPU"},
    {"query": "Сравнение стоп-лосса и тейк-профита", "category": "concept_comparison", "expected_unit": "rule_card", "expected_concept": "Stop Loss"},

    # ── Example / evidence lookup ────────────────────────────────────
    {"query": "Покажи пример накопления на графике", "category": "evidence_lookup", "expected_unit": "evidence_ref", "expected_concept": "Accumulation"},
    {"query": "Визуальный пример ложного пробоя уровня", "category": "evidence_lookup", "expected_unit": "evidence_ref", "expected_concept": "Movement near levels"},
    {"query": "Пример постановки стоп-лосса", "category": "evidence_lookup", "expected_unit": "evidence_ref", "expected_concept": "Stop Loss"},

    # ── Lesson coverage ──────────────────────────────────────────────
    {"query": "Какие концепции рассматривались в уроке?", "category": "lesson_coverage", "expected_unit": "knowledge_event", "expected_concept": None},
    {"query": "О чем рассказывал урок про Price Action?", "category": "lesson_coverage", "expected_unit": "knowledge_event", "expected_concept": "Price Action"},

    # ── Cross-lesson / concept graph ─────────────────────────────────
    {"query": "Связь между уровнями и стоп-лоссом", "category": "graph_query", "expected_unit": "concept_relation", "expected_concept": "Stop Loss"},
    {"query": "Какие правила связаны с анализом таймфреймов?", "category": "graph_query", "expected_unit": "rule_card", "expected_concept": "Анализ таймфреймов"},
    {"query": "Концепции связанные с волатильностью", "category": "graph_query", "expected_unit": "concept_node", "expected_concept": "Волатильность"},

    # ── Timeframe dependency ─────────────────────────────────────────
    {"query": "Как определить дневной уровень?", "category": "timeframe", "expected_unit": "rule_card", "expected_concept": None},
    {"query": "Правила торговли на разных таймфреймах", "category": "timeframe", "expected_unit": "rule_card", "expected_concept": "Анализ таймфреймов"},

    # ── Multilingual / alias ─────────────────────────────────────────
    {"query": "Stop loss placement rules", "category": "multilingual", "expected_unit": "rule_card", "expected_concept": "Stop Loss"},
    {"query": "Take profit strategy", "category": "multilingual", "expected_unit": "rule_card", "expected_concept": "Take Profit"},
    {"query": "БСУ бар строительный упорный", "category": "alias", "expected_unit": "rule_card", "expected_concept": "BPU"},
    {"query": "Re-test уровня после пробоя", "category": "alias", "expected_unit": "rule_card", "expected_concept": "Re-test"},
]


def _recall_at_k(hits: list[dict[str, Any]], expected_unit: str | None, k: int) -> float:
    if not expected_unit:
        return 1.0 if hits else 0.0
    found = any(h.get("unit_type") == expected_unit for h in hits[:k])
    return 1.0 if found else 0.0


def _mrr(hits: list[dict[str, Any]], expected_unit: str | None) -> float:
    if not expected_unit:
        return 1.0 if hits else 0.0
    for i, h in enumerate(hits, 1):
        if h.get("unit_type") == expected_unit:
            return 1.0 / i
    return 0.0


def _concept_detected(expansion: dict[str, Any], expected_concept: str | None) -> bool:
    if not expected_concept:
        return True
    ec = expected_concept.lower()
    for det in expansion.get("detected_concepts", []):
        if det.get("matched_term", "").lower() == ec or ec in det.get("matched_term", "").lower():
            return True
    for exp in expansion.get("expanded_concepts", []):
        cid = exp.get("concept_id", "").lower()
        if ec in cid:
            return True
    return False


def _evidence_rate(hits: list[dict[str, Any]]) -> float:
    if not hits:
        return 0.0
    with_ev = sum(1 for h in hits if h.get("evidence_ids"))
    return with_ev / len(hits)


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
        query_text = q["query"]
        expected_unit = q.get("expected_unit")
        expected_concept = q.get("expected_concept")
        category = q.get("category", "unknown")

        result = retriever.search(query_text, top_k=max(k_values))
        hits = result["top_hits"]
        expansion = result["expansion"]

        r_at_k = {k: _recall_at_k(hits, expected_unit, k) for k in k_values}
        mrr_val = _mrr(hits, expected_unit)
        cd = _concept_detected(expansion, expected_concept)
        ev_rate = _evidence_rate(hits)

        for k in k_values:
            recall_sums[k] += r_at_k[k]
        mrr_sum += mrr_val
        if cd:
            concept_hits += 1

        if expected_unit:
            if r_at_k[max(k_values)] > 0:
                unit_hit_counts[expected_unit] = unit_hit_counts.get(expected_unit, 0) + 1
            else:
                unit_miss_counts[expected_unit] = unit_miss_counts.get(expected_unit, 0) + 1

        category_scores.setdefault(category, []).append(r_at_k[max(k_values)])

        results.append({
            "query": query_text,
            "category": category,
            "expected_unit": expected_unit,
            "expected_concept": expected_concept,
            "recall_at_k": r_at_k,
            "mrr": mrr_val,
            "concept_detected": cd,
            "evidence_rate": ev_rate,
            "hit_count": len(hits),
            "top_hit_unit_type": hits[0]["unit_type"] if hits else None,
            "top_hit_score": hits[0]["score"] if hits else None,
        })

    report = {
        "query_count": total,
        "metrics": {
            f"recall_at_{k}": round(recall_sums[k] / total, 4) if total else 0
            for k in k_values
        },
        "mrr": round(mrr_sum / total, 4) if total else 0,
        "concept_detection_accuracy": round(concept_hits / total, 4) if total else 0,
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
