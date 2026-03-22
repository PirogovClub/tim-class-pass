from __future__ import annotations

import json

from pipeline.rag.eval import run_eval


def test_eval_runs_end_to_end(hybrid_retriever, rag_config):
    report = run_eval(hybrid_retriever, rag_config)
    assert report["query_count"] >= 25
    assert (rag_config.eval_dir / "eval_queries.json").exists()
    assert (rag_config.eval_dir / "eval_results.json").exists()
    assert (rag_config.eval_dir / "eval_report.json").exists()


def test_eval_report_contains_metric_keys(hybrid_retriever, rag_config):
    run_eval(hybrid_retriever, rag_config)
    report = json.loads((rag_config.eval_dir / "eval_report.json").read_text(encoding="utf-8"))
    metrics = report["metrics"]
    assert "recall_at_5" in metrics
    assert "mrr" in metrics
    assert "evidence_presence_rate" in metrics
    assert "timestamp_presence_rate" in metrics
