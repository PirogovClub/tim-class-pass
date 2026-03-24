from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from PIL import ImageFilter
from skimage.metrics import structural_similarity


@dataclass(frozen=True)
class ComparisonResult:
    score: float
    is_significant: bool
    threshold: float
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _load_for_ssim(
    image_path: Path | str,
    size: tuple[int, int] | None = None,
    *,
    blur_radius: float = 0.0,
) -> Image.Image:
    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")
    if size is not None:
        image = image.resize(size)
    if blur_radius > 0:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    return image


def save_structural_artifact(
    source_image: Path | str,
    destination: Path | str,
    *,
    size: tuple[int, int] | None = None,
    blur_radius: float = 0.0,
) -> list[int]:
    image = _load_for_ssim(source_image, size=size, blur_radius=blur_radius)
    output_path = Path(destination)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return [int(image.size[0]), int(image.size[1])]


def compare_images(
    baseline_image: Path | str,
    current_image: Path | str,
    threshold: float = 0.95,
    *,
    blur_radius: float = 0.0,
    artifacts_dir: Path | str | None = None,
) -> ComparisonResult:
    """
    Compare two screenshots using SSIM.

    This is intentionally only the first sieve. A significant structural change
    does not automatically imply lesson relevance.
    """
    baseline_frame = _load_for_ssim(baseline_image, blur_radius=blur_radius)
    current_frame = _load_for_ssim(
        current_image,
        size=(baseline_frame.size[0], baseline_frame.size[1]),
        blur_radius=blur_radius,
    )
    baseline = np.asarray(baseline_frame, dtype=np.uint8)
    current = np.asarray(current_frame, dtype=np.uint8)

    if artifacts_dir is not None:
        destination = Path(artifacts_dir)
        destination.mkdir(parents=True, exist_ok=True)
        baseline_name = f"{Path(baseline_image).stem}.png"
        current_name = f"{Path(current_image).stem}.png"
        baseline_frame.save(destination / baseline_name)
        current_frame.save(destination / current_name)

    score = float(
        structural_similarity(
            baseline,
            current,
            channel_axis=-1,
            data_range=255,
        )
    )
    return ComparisonResult(
        score=score,
        is_significant=score < threshold,
        threshold=threshold,
        metadata={
            "baseline_size": [int(baseline_frame.size[0]), int(baseline_frame.size[1])],
            "current_size": [int(current_frame.size[0]), int(current_frame.size[1])],
            "blur_radius": blur_radius,
        },
    )
