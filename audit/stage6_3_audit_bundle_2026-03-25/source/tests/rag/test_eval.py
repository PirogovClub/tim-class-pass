from __future__ import annotations

import json

from pipeline.rag.eval import STEP31_METRICS_SCHEMA_VERSION, STEP31_REQUIRED_METRIC_KEYS, run_eval


def test_eval_runs_end_to_end(hybrid_retriever, rag_config):
    report = run_eval(hybrid_retriever, rag_config)
    assert report["query_count"] >= 34
    assert (rag_config.eval_dir / "eval_queries.json").exists()
    assert (rag_config.eval_dir / "eval_results.json").exists()
    assert (rag_config.eval_dir / "eval_report.json").exists()
    assert (rag_config.eval_dir / "rag_eval_queries.json").exists()
    assert (rag_config.eval_dir / "rag_eval_report.json").exists()


def test_eval_report_contains_metric_keys(hybrid_retriever, rag_config):
    run_eval(hybrid_retriever, rag_config)
    report = json.loads((rag_config.eval_dir / "eval_report.json").read_text(encoding="utf-8"))
    metrics = report["metrics"]
    for key in STEP31_REQUIRED_METRIC_KEYS:
        assert key in metrics
    # Step 3.1 regression gates on the synthetic fixture corpus
    assert metrics["example_lookup_evidence_top1_rate"] >= 1.0
    assert metrics["support_policy_evidence_top3_rate"] >= 0.5
    assert metrics["support_policy_visual_evidence_top3_rate"] >= 1.0
    assert metrics["transcript_only_transcript_primary_top1_rate"] >= 1.0
    assert metrics["concept_detection_success_proxy"] >= 0.25
    assert "category_avg_recall" in report
    assert report["category_avg_recall"]["higher_timeframe_dependency"] >= 0.9
    assert report["metrics_schema_version"] == STEP31_METRICS_SCHEMA_VERSION
    assert report["generated_at"]
