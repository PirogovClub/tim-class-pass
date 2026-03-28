from __future__ import annotations

import io
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from helpers.ffmpeg_cmd import run_ffmpeg_cmd
from helpers.utils import video_audio
from helpers.utils.video_audio import (
    AudioExtractionError,
    ExtractionReport,
    extract_audio,
    extract_audio_from_folder,
)
from helpers.utils.video_audio_cli import main as cli_main


def test_extract_audio_success(tmp_path: Path) -> None:
    vid = tmp_path / "a.mp4"
    vid.write_bytes(b"")
    out = tmp_path / "out.m4a"
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        extract_audio(vid, out)
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd
    assert str(vid.resolve()) in cmd
    assert "-vn" in cmd
    assert "-map" in cmd
    assert "0:a:0" in cmd
    assert "-c:a" in cmd
    assert "aac" in cmd
    assert "-b:a" in cmd
    assert "192k" in cmd
    assert str(out) == cmd[-1]


def test_extract_audio_overwrite_adds_y(tmp_path: Path) -> None:
    vid = tmp_path / "a.mp4"
    vid.touch()
    out = tmp_path / "out.m4a"
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        extract_audio(vid, out, overwrite=True)
    cmd = mock_run.call_args[0][0]
    assert "-y" in cmd


def test_extract_audio_ffmpeg_failure(tmp_path: Path) -> None:
    vid = tmp_path / "a.mp4"
    vid.touch()
    out = tmp_path / "out.m4a"
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        mock_run.side_effect = [
            SimpleNamespace(returncode=1, stderr="fail1"),
            SimpleNamespace(returncode=1, stderr="fail2"),
        ]
        with pytest.raises(AudioExtractionError):
            extract_audio(vid, out, overwrite=True)
    assert mock_run.call_count == 2


def test_run_ffmpeg_cmd_stderr_progress_parsing() -> None:
    stderr_blob = b"frame=100 time=00:00:03.50 speed=4.00x more\r"

    class FakeProc:
        def __init__(self) -> None:
            self.stderr = io.BytesIO(stderr_blob)

        def wait(self) -> int:
            return 0

    msgs: list[str] = []
    with patch("helpers.ffmpeg_cmd.subprocess.Popen", return_value=FakeProc()):
        ok = run_ffmpeg_cmd(
            ["ffmpeg", "-version"],
            stderr_progress=msgs.append,
            stderr_progress_interval=0.0,
        )
    assert ok is True
    assert len(msgs) >= 1
    assert "03.50" in msgs[0]
    assert "4.00" in msgs[0]


def test_run_ffmpeg_cmd_falls_back_to_uv() -> None:
    fail = SimpleNamespace(returncode=1, stderr="not found")
    ok = SimpleNamespace(returncode=0, stderr="")
    with patch("helpers.ffmpeg_cmd.subprocess.run", side_effect=[fail, ok]) as mock_run:
        assert run_ffmpeg_cmd(["ffmpeg", "-i", "in.mp4", "out.m4a"]) is True
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[1][0][0][:3] == ["uv", "run", "ffmpeg"]


def test_extract_audio_video_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "nope.mp4"
    with pytest.raises(FileNotFoundError, match="Video not found"):
        extract_audio(missing, tmp_path / "out.m4a")


def test_extract_audio_output_exists_no_overwrite(tmp_path: Path) -> None:
    vid = tmp_path / "a.mp4"
    vid.touch()
    out = tmp_path / "out.m4a"
    out.write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Output exists"):
        extract_audio(vid, out, overwrite=False)


def test_extract_audio_from_folder_flat_two_videos(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "one.mp4").touch()
    (inp / "two.mp4").touch()
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        reports = extract_audio_from_folder(inp)
    assert len(reports) == 2
    assert all(r.ok for r in reports)
    assert mock_run.call_count == 2
    stems = {r.source.stem for r in reports}
    assert stems == {"one", "two"}
    for r in reports:
        assert r.output.parent == inp / "audio"
        assert r.output.suffix == ".m4a"


def test_extract_audio_from_folder_recursive(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    sub = inp / "sub"
    sub.mkdir(parents=True)
    (sub / "v.mp4").touch()
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        reports = extract_audio_from_folder(inp, recursive=True)
    assert len(reports) == 1
    assert reports[0].ok
    assert reports[0].output == inp / "audio" / "sub" / "v.m4a"


def test_extract_audio_from_folder_ignores_non_video(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "notes.txt").write_text("hi", encoding="utf-8")
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        reports = extract_audio_from_folder(inp)
    assert reports == []
    mock_run.assert_not_called()


def test_extract_audio_from_folder_empty(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        reports = extract_audio_from_folder(inp)
    assert reports == []
    mock_run.assert_not_called()


def test_extract_audio_from_folder_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.touch()
    with pytest.raises(NotADirectoryError):
        extract_audio_from_folder(f)


def test_helpers_utils_package_reexports_extract_audio() -> None:
    from helpers.utils import extract_audio as exp

    assert exp is video_audio.extract_audio


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_main, ["--help"])
    assert result.exit_code == 0
    assert "INPUT_DIR" in result.output or "input_dir" in result.output.lower()
    assert "--max-workers" in result.output


def test_cli_happy_path(tmp_path: Path) -> None:
    input_dir = tmp_path / "videos"
    input_dir.mkdir()
    fake_reports = [
        ExtractionReport(
            source=Path("a.mp4"),
            output=Path("a.m4a"),
            ok=True,
        ),
    ]
    with patch(
        "helpers.utils.video_audio_cli.extract_audio_from_folder",
        return_value=fake_reports,
    ):
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(input_dir)])
    assert result.exit_code == 0
    assert "1 extracted" in result.output


def test_cli_forwards_recursive_and_overwrite(tmp_path: Path) -> None:
    input_dir = tmp_path / "videos"
    input_dir.mkdir()
    with patch("helpers.utils.video_audio_cli.extract_audio_from_folder") as mock_folder:
        mock_folder.return_value = []
        runner = CliRunner()
        result = runner.invoke(
            cli_main,
            [str(input_dir), "--recursive", "--overwrite"],
        )
    assert result.exit_code == 0
    mock_folder.assert_called_once()
    call_kw = mock_folder.call_args.kwargs
    assert call_kw["recursive"] is True
    assert call_kw["overwrite"] is True
    assert callable(call_kw["progress_callback"])
    assert call_kw.get("max_workers") is None


def test_cli_forwards_max_workers(tmp_path: Path) -> None:
    input_dir = tmp_path / "videos"
    input_dir.mkdir()
    with patch("helpers.utils.video_audio_cli.extract_audio_from_folder") as mock_folder:
        mock_folder.return_value = []
        runner = CliRunner()
        result = runner.invoke(
            cli_main,
            [str(input_dir), "--max-workers", "3"],
        )
    assert result.exit_code == 0
    assert mock_folder.call_args.kwargs["max_workers"] == 3


def test_cli_rejects_max_workers_zero(tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli_main, [str(input_dir), "--max-workers", "0"])
    assert result.exit_code != 0
    assert "max-workers" in result.output.lower()


def _fake_run_ffmpeg_ok(
    cmd: list[str],
    *,
    stderr_progress=None,
    stderr_progress_interval: float = 0.45,
) -> bool:
    if stderr_progress is not None:
        stderr_progress("00:00:01.00 @ 2.0x")
    return True


def test_append_eta_to_progress_detail() -> None:
    assert "ETA ~30s" in video_audio._append_eta_to_progress_detail(
        "00:01:00.00 @ 2.0x",
        120.0,
    )
    assert "finishing" in video_audio._append_eta_to_progress_detail(
        "00:02:00.00 @ 2.0x",
        120.0,
    )
    assert video_audio._append_eta_to_progress_detail("no speed", 120.0) == "no speed"


def test_encode_progress_includes_eta_when_duration_probed(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "a.mp4").touch()
    events: list[dict[str, Any]] = []

    def collect(ev: Mapping[str, Any]) -> None:
        events.append(dict(ev))

    def fake_run(
        cmd: list[str],
        *,
        stderr_progress=None,
        stderr_progress_interval: float = 0.45,
    ) -> bool:
        if stderr_progress is not None:
            stderr_progress("00:01:00.00 @ 2.0x")
        return True

    with patch(
        "helpers.utils.video_audio.probe_media_duration_seconds",
        return_value=120.0,
    ):
        with patch("helpers.utils.video_audio.run_ffmpeg_cmd", side_effect=fake_run):
            extract_audio_from_folder(inp, progress_callback=collect)
    enc = [e for e in events if e["event"] == "encode_progress"]
    assert len(enc) == 1
    assert "ETA" in enc[0]["message"]
    assert "30s" in enc[0]["message"]


def test_cli_prints_progress_lines_when_not_quiet(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "one.mp4").touch()
    (inp / "two.mp4").touch()
    with patch("helpers.utils.video_audio.probe_media_duration_seconds", return_value=None):
        with patch("helpers.utils.video_audio.os.cpu_count", return_value=8):
            with patch(
                "helpers.utils.video_audio.run_ffmpeg_cmd",
                side_effect=_fake_run_ffmpeg_ok,
            ):
                runner = CliRunner()
                result = runner.invoke(cli_main, [str(inp)])
    assert result.exit_code == 0
    assert "Found 2 video file(s)" in result.output
    assert "parallel" in result.output.lower()
    assert "[1/2]" in result.output and "[2/2]" in result.output
    assert "one.mp4" in result.output and "two.mp4" in result.output
    assert "00:00:01.00" in result.output
    assert "2.0x" in result.output


def test_cli_quiet_disables_progress_callback(tmp_path: Path) -> None:
    input_dir = tmp_path / "videos"
    input_dir.mkdir()
    with patch("helpers.utils.video_audio_cli.extract_audio_from_folder") as mock_folder:
        mock_folder.return_value = []
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(input_dir), "--quiet"])
    assert result.exit_code == 0
    assert mock_folder.call_args.kwargs["progress_callback"] is None


def test_cli_quiet_hides_progress_lines(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "a.mp4").touch()
    (inp / "b.mp4").touch()
    with patch("helpers.ffmpeg_cmd.subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(inp), "--quiet"])
    assert result.exit_code == 0
    assert "[1/2]" not in result.output
    assert "Found 2 video" not in result.output
    assert "Done:" in result.output


def test_extract_audio_from_folder_progress_callback(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "a.mp4").touch()
    events: list[dict[str, Any]] = []

    def collect(ev: Mapping[str, Any]) -> None:
        events.append(dict(ev))

    with patch("helpers.utils.video_audio.probe_media_duration_seconds", return_value=None):
        with patch(
            "helpers.utils.video_audio.run_ffmpeg_cmd",
            side_effect=_fake_run_ffmpeg_ok,
        ):
            extract_audio_from_folder(inp, progress_callback=collect)

    assert [e["event"] for e in events] == [
        "batch_start",
        "file_start",
        "encode_progress",
        "file_end",
    ]
    assert events[0]["total"] == 1
    assert events[0]["parallel_workers"] == 1
    assert events[1]["index"] == 1 and events[1]["total"] == 1
    assert events[1]["source"].name == "a.mp4"
    assert events[2]["event"] == "encode_progress"
    assert "00:00:01.00" in events[2]["message"]
    assert events[3]["ok"] is True


def test_extract_audio_from_folder_max_workers_invalid(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    with pytest.raises(ValueError, match="max_workers"):
        extract_audio_from_folder(inp, max_workers=0)


def test_extract_audio_from_folder_parallel_workers_cap(tmp_path: Path) -> None:
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "a.mp4").touch()
    (inp / "b.mp4").touch()
    events: list[dict[str, Any]] = []

    def collect(ev: Mapping[str, Any]) -> None:
        events.append(dict(ev))

    with patch("helpers.utils.video_audio.probe_media_duration_seconds", return_value=None):
        with patch(
            "helpers.utils.video_audio.run_ffmpeg_cmd",
            side_effect=_fake_run_ffmpeg_ok,
        ):
            with patch("helpers.utils.video_audio.os.cpu_count", return_value=8):
                extract_audio_from_folder(inp, progress_callback=collect)
    assert events[0]["parallel_workers"] == 2

    events.clear()
    with patch("helpers.utils.video_audio.probe_media_duration_seconds", return_value=None):
        with patch(
            "helpers.utils.video_audio.run_ffmpeg_cmd",
            side_effect=_fake_run_ffmpeg_ok,
        ):
            with patch("helpers.utils.video_audio.os.cpu_count", return_value=8):
                extract_audio_from_folder(
                    inp,
                    progress_callback=collect,
                    max_workers=1,
                )
    assert events[0]["parallel_workers"] == 1


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")
def test_integration_extract_audio_from_tiny_video(tmp_path: Path) -> None:
    video_path = tmp_path / "test_input.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=160x120:rate=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            "-y",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )
    out = tmp_path / "out.m4a"
    extract_audio(video_path, out, overwrite=True)
    assert out.is_file()
    assert out.stat().st_size > 0
    if shutil.which("ffprobe"):
        pr = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "audio" in pr.stdout.lower()


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")
def test_integration_extract_audio_from_folder(tmp_path: Path) -> None:
    inp = tmp_path / "batch"
    inp.mkdir()
    video_path = inp / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=160x120:rate=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            "-y",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )
    reports = extract_audio_from_folder(inp)
    assert len(reports) == 1
    assert reports[0].ok
    assert (inp / "audio" / "clip.m4a").is_file()
