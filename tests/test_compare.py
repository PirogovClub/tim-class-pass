from pathlib import Path

from PIL import Image

from helpers.utils import compare


def _write_image(path: Path, color: int) -> None:
    Image.new("L", (32, 32), color=color).save(path)


def test_compare_images_skips_near_identical_frames(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.png"
    current = tmp_path / "current.png"
    _write_image(baseline, 255)
    _write_image(current, 255)

    result = compare.compare_images(baseline, current)

    assert result.score >= 0.95
    assert result.is_significant is False
    assert result.metadata["baseline_size"] == [32, 32]
    assert result.metadata["blur_radius"] == 0.0


def test_compare_images_detects_significant_change(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.png"
    current = tmp_path / "current.png"
    _write_image(baseline, 255)
    _write_image(current, 0)

    result = compare.compare_images(baseline, current)

    assert result.score < 0.95
    assert result.is_significant is True


def test_compare_images_writes_structural_artifacts(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.png"
    current = tmp_path / "current.png"
    artifacts_dir = tmp_path / "artifacts"
    _write_image(baseline, 255)
    _write_image(current, 128)

    result = compare.compare_images(
        baseline,
        current,
        blur_radius=1.5,
        artifacts_dir=artifacts_dir,
    )

    assert result.metadata["blur_radius"] == 1.5
    assert (artifacts_dir / "baseline.png").is_file()
    assert (artifacts_dir / "current.png").is_file()
