import json
import shutil
from pathlib import Path

from PIL import Image

from helpers import config
from pipeline import dense_analyzer


def _write_frame(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (24, 24), color=color).save(path)


def _setup_video(tmp_path: Path, video_id: str = "video") -> Path:
    video_dir = tmp_path / "data" / video_id
    frames_dir = video_dir / "frames_dense"
    frames_dir.mkdir(parents=True)
    _write_frame(frames_dir / "frame_000001.jpg", (255, 255, 255))
    _write_frame(frames_dir / "frame_000002.jpg", (0, 0, 0))
    with open(video_dir / "dense_index.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "000001": "frames_dense/frame_000001.jpg",
                "000002": "frames_dense/frame_000002.jpg",
            },
            f,
            indent=2,
        )
    return video_dir


def _write_llm_queue(video_dir: Path, keys: list[str]) -> None:
    queue_dir = video_dir / "llm_queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    items: dict[str, dict] = {}
    for key in keys:
        rel = f"frames_dense/frame_{key}.jpg"
        src = video_dir / rel
        dest = queue_dir / src.name
        shutil.copy(src, dest)
        items[key] = {"source": rel, "reason": "test", "diff": 0.2}
    manifest = {"video_id": video_dir.name, "total_selected": len(keys), "items": items}
    with open(queue_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def test_run_analysis_prefills_non_queue_frames(monkeypatch, tmp_path: Path) -> None:
    video_id = "video"
    video_dir = _setup_video(tmp_path, video_id=video_id)
    _write_llm_queue(video_dir, ["000001"])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        config,
        "get_config_for_video",
        lambda video_id: {"ssim_threshold": 0.95, "telemetry_enabled": True},
    )

    def fake_analyze_frame(frame_path: str, prompt_text: str, video_id=None, **kwargs):
        return {
            "frame_timestamp": "00:00:01",
            "material_change": True,
            "lesson_relevant": True,
            "scene_boundary": True,
            "change_summary": ["First frame"],
            "current_state": {"visual_facts": ["Intro slide"], "trading_relevant_interpretation": []},
        }

    monkeypatch.setattr(dense_analyzer, "_analyze_frame_openai", fake_analyze_frame)

    dense_analyzer.run_analysis(video_id, batch_size=2, agent="openai")

    with open(video_dir / "dense_analysis.json", "r", encoding="utf-8") as f:
        analysis = json.load(f)
    with open(video_dir / "processing_status.json", "r", encoding="utf-8") as f:
        status = json.load(f)

    assert analysis["000001"]["material_change"] is True
    assert analysis["000002"]["material_change"] is False
    assert analysis["000002"]["skip_reason"] == "not_in_llm_queue"
    assert status["counts"]["structural_skips"] == 0


def test_run_analysis_only_analyzes_queue_keys(monkeypatch, tmp_path: Path) -> None:
    video_id = "video"
    video_dir = _setup_video(tmp_path, video_id=video_id)
    _write_llm_queue(video_dir, ["000002"])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        config,
        "get_config_for_video",
        lambda video_id: {"ssim_threshold": 0.95, "telemetry_enabled": True},
    )

    seen_keys: list[str] = []

    def fake_analyze_frame(frame_path: str, prompt_text: str, video_id=None, **kwargs):
        seen_keys.append(kwargs.get("frame_key"))
        return {
            "frame_timestamp": "00:00:02",
            "material_change": True,
            "lesson_relevant": True,
            "scene_boundary": True,
            "change_summary": ["Second frame"],
            "current_state": {"visual_facts": ["Second slide"], "trading_relevant_interpretation": []},
        }

    monkeypatch.setattr(dense_analyzer, "_analyze_frame_openai", fake_analyze_frame)

    dense_analyzer.run_analysis(video_id, batch_size=2, agent="openai")

    with open(video_dir / "dense_analysis.json", "r", encoding="utf-8") as f:
        analysis = json.load(f)

    assert seen_keys == ["000002"]
    assert analysis["000001"]["skip_reason"] == "not_in_llm_queue"
    assert analysis["000002"]["material_change"] is True


# ---------------------------------------------------------------------------
# Phase 2 tests: within-batch context carry-forward + scene anchoring
# ---------------------------------------------------------------------------

def _setup_video_3frames(tmp_path: Path, video_id: str = "video3") -> Path:
    video_dir = tmp_path / "data" / video_id
    frames_dir = video_dir / "frames_dense"
    frames_dir.mkdir(parents=True)
    for name, color in [("frame_000001.jpg", (255, 255, 255)), ("frame_000002.jpg", (100, 100, 100)), ("frame_000003.jpg", (0, 0, 0))]:
        Image.new("RGB", (24, 24), color=color).save(frames_dir / name)
    with open(video_dir / "dense_index.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "000001": "frames_dense/frame_000001.jpg",
                "000002": "frames_dense/frame_000002.jpg",
                "000003": "frames_dense/frame_000003.jpg",
            },
            f,
            indent=2,
        )
    return video_dir


def test_batch_carry_forward_passes_batch_relevant_state(monkeypatch, tmp_path: Path) -> None:
    """
    Within-batch context carry-forward: when frame 000001 is relevant and 000002 comes next
    in the same batch, analyze_frame for 000002 must receive frame 000001 as previous_state
    (even though it was not yet flushed to analysis dict on disk).
    """
    video_id = "video3"
    video_dir = _setup_video_3frames(tmp_path, video_id=video_id)
    _write_llm_queue(video_dir, ["000001", "000002", "000003"])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        config,
        "get_config_for_video",
        lambda video_id: {"ssim_threshold": 0.50, "telemetry_enabled": False},
    )

    seen_prompts: list[str] = []
    keys_by_call: list[str] = []

    def fake_analyze_frame(frame_path: str, prompt_text: str, video_id=None, **kwargs):
        seen_prompts.append(prompt_text)
        key = kwargs.get("frame_key") or ""
        keys_by_call.append(key)
        return {
            "frame_timestamp": f"00:00:0{key[-1]}",
            "material_change": True,
            "lesson_relevant": True,
            "scene_boundary": True,
            "change_summary": [f"Frame {key}"],
            "current_state": {"visual_facts": [f"Content of {key}"], "trading_relevant_interpretation": []},
        }

    monkeypatch.setattr(dense_analyzer, "_analyze_frame_openai", fake_analyze_frame)

    # Run with batch_size=3 so all 3 frames go through in one batch
    dense_analyzer.run_analysis(video_id, batch_size=3, agent="openai")

    assert keys_by_call == ["000001", "000002", "000003"]
    assert "Previous frame state: None" in seen_prompts[0]
    assert "Content of 000001" in seen_prompts[1]

