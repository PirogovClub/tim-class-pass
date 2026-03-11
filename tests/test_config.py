from helpers import config


def test_default_workers_use_half_cpu(monkeypatch) -> None:
    monkeypatch.setattr(config.os, "cpu_count", lambda: 8)

    assert config._default_pipeline_workers() == 4
    assert config._default_step2_chunk_workers() == 4


def test_config_exposes_stage_specific_provider_and_model_defaults(monkeypatch) -> None:
    monkeypatch.setattr(config, "load_pipeline_config_for_video", lambda _: None)
    monkeypatch.setattr(config.os, "cpu_count", lambda: 8)
    for env_key in (
        "PROVIDER_IMAGES",
        "PROVIDER_COMPONENT2",
        "PROVIDER_COMPONENT2_REDUCER",
        "PROVIDER_GAPS",
        "PROVIDER_VLM",
        "PROVIDER_ANALYZE_EXTRACT",
        "PROVIDER_ANALYZE_RELEVANCE",
        "MODEL_IMAGES",
        "MODEL_COMPONENT2",
        "MODEL_COMPONENT2_REDUCER",
        "MODEL_GAPS",
        "MODEL_VLM",
        "MODEL_ANALYZE_EXTRACT",
        "MODEL_ANALYZE_RELEVANCE",
        "MODEL_NAME",
        "AGENT_IMAGES",
        "AGENT",
        "LLM_PROVIDER",
        "WORKERS",
        "MAX_WORKERS",
    ):
        monkeypatch.delenv(env_key, raising=False)

    cfg = config.get_config_for_video("video")

    assert cfg["provider_images"] == "ide"
    assert cfg["provider_component2"] == "gemini"
    assert cfg["provider_component2_reducer"] == "gemini"
    assert cfg["provider_gaps"] == "gemini"
    assert cfg["provider_vlm"] == "gemini"
    assert cfg["provider_analyze_extract"] == "gemini"
    assert cfg["provider_analyze_relevance"] == "gemini"
    assert cfg["workers"] == 4
    assert cfg["step2_chunk_workers"] == 4
