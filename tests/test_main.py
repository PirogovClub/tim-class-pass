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
