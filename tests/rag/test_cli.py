from __future__ import annotations

import json

from pipeline.rag.cli import export_audit_bundle, run_build


def test_run_build_writes_manifest_paths(rag_config, patch_fake_sentence_transformer):
    result = run_build(rag_config)

    build_meta = json.loads((rag_config.rag_root / "rag_build_metadata.json").read_text(encoding="utf-8"))
    assert result["meta"]["total_retrieval_docs"] == 19
    assert build_meta["lexical_manifest_path"].endswith("lexical_index_manifest.json")
    assert build_meta["embedding_manifest_path"].endswith("embedding_manifest.json")


def test_export_audit_bundle_preserves_utf8_queries(
    rag_config,
    built_rag_root,
    patch_fake_sentence_transformer,
    tmp_path,
):
    pytest_output_path = tmp_path / "pytest_output.txt"
    pytest_output_path.write_text("67 passed\n", encoding="utf-8")

    audit_root = tmp_path / "audit_export"
    zip_path = tmp_path / "audit_export.zip"
    result = export_audit_bundle(
        rag_config,
        audit_root=audit_root,
        zip_path=zip_path,
        pytest_output_path=pytest_output_path,
    )

    cli_sample = json.loads((audit_root / "cli_samples" / "q001_stop_loss_level.json").read_text(encoding="utf-8"))
    api_sample = json.loads((audit_root / "api_samples" / "search_accumulation_example.json").read_text(encoding="utf-8"))
    manifest = json.loads((audit_root / "sample_manifest.json").read_text(encoding="utf-8"))

    assert cli_sample["query"] == "Как определить уровень для стоп-лосса?"
    assert api_sample["request"]["query"] == "Покажи пример накопления на графике"
    assert (audit_root / "api_samples" / "doc_sample_1.json").exists()
    assert (audit_root / "api_samples" / "doc_sample_2.json").exists()
    assert (audit_root / "api_samples" / "concept_sample_1.json").exists()
    assert (audit_root / "api_samples" / "concept_sample_2.json").exists()
    assert zip_path.exists()
    assert result["zip_path"].endswith("audit_export.zip")
    assert len(manifest["doc_sample_ids"]) == 2
    assert len(manifest["concept_sample_ids"]) == 2
    assert manifest["included_docs"] == ["step3_hybrid_rag_notes.md", "rag_query_examples.md"]
