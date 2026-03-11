from helpers.utils.frame_schema import key_to_timestamp


def test_key_to_timestamp() -> None:
    assert key_to_timestamp("000600") == "00:10:00"


def test_pipeline_main_help() -> None:
    """Main CLI (Click) prints help and exits 0."""
    from click.testing import CliRunner
    from pipeline.main import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Multimodal YouTube" in result.output
    assert "--url" in result.output
    assert "--video_id" in result.output
    assert "--agent-dedup" not in result.output


def test_pipeline_main_step3_runs_component2(monkeypatch, tmp_path) -> None:
    from click.testing import CliRunner
    from pipeline.main import main
    from helpers import config
    import json

    video_id = "video"
    video_dir = tmp_path / "data" / video_id
    video_dir.mkdir(parents=True)
    (video_dir / "lesson.vtt").write_text(
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\nПривет.\n",
        encoding="utf-8",
    )
    (video_dir / "dense_index.json").write_text(json.dumps({"000001": "frames_dense/frame_000001.jpg"}), encoding="utf-8")
    (video_dir / "dense_analysis.json").write_text(json.dumps({"000001": {"material_change": True}}), encoding="utf-8")
    (video_dir / "frames_dense").mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        config,
        "get_config_for_video",
        lambda _: {
            "agent_images": "openai",
            "batch_size": 10,
            "workers": 1,
            "video_file": None,
            "vtt_file": "lesson.vtt",
            "parallel_batches": False,
            "model_component2": None,
        },
    )

    from helpers.clients import gemini_client
    monkeypatch.setattr(gemini_client, "require_gemini_key", lambda: None)

    from pipeline import dense_capturer, structural_compare, select_llm_frames, build_llm_prompts, dense_analyzer

    monkeypatch.setattr(dense_capturer, "extract_dense_frames", lambda *args, **kwargs: None)
    monkeypatch.setattr(structural_compare, "run_structural_compare", lambda *args, **kwargs: None)
    monkeypatch.setattr(select_llm_frames, "build_llm_queue", lambda *args, **kwargs: None)
    monkeypatch.setattr(build_llm_prompts, "build_llm_prompts", lambda *args, **kwargs: None)
    monkeypatch.setattr(dense_analyzer, "run_analysis", lambda *args, **kwargs: None)

    seen = {}

    def fake_run_component2_pipeline(**kwargs):
        seen.update(kwargs)
        return {
            "filtered_events_path": video_dir / "filtered_visual_events.json",
            "filtered_debug_path": video_dir / "filtered_visual_events.debug.json",
            "chunk_debug_path": video_dir / "output_markdown" / "lesson.chunks.json",
            "llm_debug_path": video_dir / "output_markdown" / "lesson.llm_debug.json",
            "markdown_path": video_dir / "output_markdown" / "lesson.md",
        }

    monkeypatch.setattr("pipeline.component2.main.run_component2_pipeline", fake_run_component2_pipeline)

    runner = CliRunner()
    result = runner.invoke(main, ["--video_id", video_id])

    assert result.exit_code == 0
    assert seen["video_id"] == video_id
    assert seen["vtt_path"].resolve() == (video_dir / "lesson.vtt").resolve()
    assert seen["visuals_json_path"].resolve() == (video_dir / "dense_analysis.json").resolve()
