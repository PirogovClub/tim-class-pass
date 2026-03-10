from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity


@dataclass(frozen=True)
class ComparisonResult:
    score: float
    is_significant: bool
    threshold: float
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _load_grayscale(image_path: Path | str, size: tuple[int, int] | None = None) -> np.ndarray:
    image = Image.open(image_path).convert("L")
    if size is not None:
        image = image.resize(size)
    return np.array(image)


def compare_images(
    baseline_image: Path | str,
    current_image: Path | str,
    threshold: float = 0.95,
) -> ComparisonResult:
    """
    Compare two screenshots using SSIM.

    This is intentionally only the first sieve. A significant structural change
    does not automatically imply lesson relevance.
    """
    baseline = _load_grayscale(baseline_image)
    current = _load_grayscale(current_image, size=(baseline.shape[1], baseline.shape[0]))
    score = float(structural_similarity(baseline, current))
    return ComparisonResult(
        score=score,
        is_significant=score < threshold,
        threshold=threshold,
        metadata={
            "baseline_size": [int(baseline.shape[1]), int(baseline.shape[0])],
            "current_size": [int(current.shape[1]), int(current.shape[0])],
        },
    )
