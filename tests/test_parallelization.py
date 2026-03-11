import json
from pathlib import Path

from pipeline import dense_capturer
from pipeline import frame_extractor
from pipeline import structural_compare


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_dense_capturer_segments_and_renumbers(monkeypatch, tmp_path: Path) -> None:
    video_id = "video"
    video_dir = tmp_path / "data" / video_id
    video_dir.mkdir(parents=True)
    _touch(video_dir / "video.mp4")

    def fake_probe_duration(_video_file: str) -> float:
        return 130.0

    calls: list[tuple[float, float, str]] = []

    def fake_extract_segment(
        _video_file: str,
        start_seconds: float,
        duration_seconds: float,
        output_dir: str,
        _label: str,
    ) -> bool:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Create two frames per segment to validate merge + renumber.
        for i in range(2):
            _touch(out_dir / f"frame_{i + 1:06d}.jpg")
        calls.append((start_seconds, duration_seconds, output_dir))
        return True

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dense_capturer, "_probe_duration_seconds", fake_probe_duration)
    monkeypatch.setattr(dense_capturer, "_extract_segment", fake_extract_segment)

    dense_capturer.extract_dense_frames(video_id, max_workers=4)

    frames_dir = video_dir / "frames_dense"
    frames = sorted(p.name for p in frames_dir.glob("*.jpg"))
    assert frames == [
        "frame_000001.jpg",
        "frame_000002.jpg",
        "frame_000003.jpg",
        "frame_000004.jpg",
        "frame_000005.jpg",
        "frame_000006.jpg",
    ]
    with open(video_dir / "dense_index.json", "r", encoding="utf-8") as f:
        index = json.load(f)
    assert list(index.keys()) == ["000001", "000002", "000003", "000004", "000005", "000006"]
    assert not any(p.name.startswith("frames_dense_seg_") for p in video_dir.iterdir())
    assert len(calls) == 3


def test_dense_capturer_caps_workers(monkeypatch, tmp_path: Path) -> None:
    video_id = "video"
    video_dir = tmp_path / "data" / video_id
    video_dir.mkdir(parents=True)
    _touch(video_dir / "video.mp4")

    def fake_probe_duration(_video_file: str) -> float:
        return 61.0

    calls: list[str] = []

    def fake_extract_segment(
        _video_file: str,
        _start_seconds: float,
        _duration_seconds: float,
        output_dir: str,
        _label: str,
    ) -> bool:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        _touch(out_dir / "frame_000001.jpg")
        calls.append(output_dir)
        return True

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dense_capturer, "_probe_duration_seconds", fake_probe_duration)
    monkeypatch.setattr(dense_capturer, "_extract_segment", fake_extract_segment)

    dense_capturer.extract_dense_frames(video_id, max_workers=100)

    # 61s => 2 segments; max_workers cap (8) should not increase segments.
    assert len(calls) == 2


def test_structural_compare_parallel_path(monkeypatch, tmp_path: Path) -> None:
    video_id = "video"
    video_dir = tmp_path / "data" / video_id
    frames_dir = video_dir / "frames_dense"
    frames_dir.mkdir(parents=True)
    for name in ["frame_000001.jpg", "frame_000002.jpg", "frame_000003.jpg"]:
        _touch(frames_dir / name)
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

    class FakeComparison:
        def __init__(self, score: float, is_significant: bool, threshold: float) -> None:
            self.score = score
            self.is_significant = is_significant
            self.threshold = threshold
            self.metadata = {"baseline_size": [1, 1], "current_size": [1, 1]}

    def fake_compare(_prev, _cur, threshold=0.95):
        return FakeComparison(0.9, True, threshold)

    created: list[object] = []

    class FakeFuture:
        def __init__(self, result) -> None:
            self._result = result

        def result(self):
            return self._result

    class FakeExecutor:
        def __init__(self, max_workers: int) -> None:
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args, **kwargs):
            return FakeFuture(fn(*args, **kwargs))

    def fake_pool(max_workers: int):
        exec_instance = FakeExecutor(max_workers)
        created.append(exec_instance)
        return exec_instance

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(structural_compare, "compare_images", fake_compare)
    monkeypatch.setattr(structural_compare, "ProcessPoolExecutor", fake_pool)
    monkeypatch.setattr(structural_compare, "as_completed", lambda futures: futures)

    structural_compare.run_structural_compare(
        video_id,
        force=True,
        rename_with_diff=False,
        max_workers=4,
    )

    assert created and created[0].max_workers == 2
    with open(video_dir / "structural_index.json", "r", encoding="utf-8") as f:
        results = json.load(f)
    assert results["000001"]["reason"] == "first_frame"
    assert results["000002"]["previous_key"] == "000001"
    assert results["000003"]["previous_key"] == "000002"


def test_frame_extractor_uses_worker_cap(monkeypatch, tmp_path: Path) -> None:
    video_id = "video"
    video_dir = tmp_path / "data" / video_id
    video_dir.mkdir(parents=True)
    _touch(video_dir / "video.mp4")
    frames_dir = video_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        "lesson.vtt": [
            {"exact_timestamp": "2024-01-01T00:00:01Z"},
            {"exact_timestamp": "2024-01-01T00:00:02Z"},
        ]
    }
    with open(video_dir / "targets.json", "w", encoding="utf-8") as f:
        json.dump(targets, f, indent=2)

    calls: list[str] = []

    def fake_extract(video_path: str, formatted_time: str, frame_path: str):
        _touch(Path(frame_path))
        calls.append(formatted_time)
        return True, None

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(frame_extractor, "_extract_single_frame", fake_extract)

    frame_extractor.extract_frames(video_id, max_workers=100)

    with open(video_dir / "targets.json", "r", encoding="utf-8") as f:
        updated = json.load(f)
    assert all("frame_path" in gap for gap in updated["lesson.vtt"])
    assert len(calls) == 2
