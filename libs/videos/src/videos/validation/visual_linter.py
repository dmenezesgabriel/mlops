from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class VisualLinterResult:
    is_centered_only: bool
    spread_ratio: float


class DensityAnalyzer:
    def analyze(self, image_path: Path) -> VisualLinterResult:
        with Image.open(image_path) as img:
            # Convert to grayscale to simplify analysis
            gray = img.convert("L")

            # Manim background is dark (#1e1e1e = 30 in grayscale)
            # Use a threshold to find content
            threshold = 40
            mask = gray.point(lambda p: 255 if p > threshold else 0)

            # getbbox returns the bounding box of non-zero pixels
            bbox = mask.getbbox()
            if not bbox:
                return VisualLinterResult(is_centered_only=False, spread_ratio=0.0)

            # Calculate spread as a ratio of image height
            # (using height as a proxy for vertical spread across regions)
            img_width, img_height = img.size
            content_height = bbox[3] - bbox[1]
            spread_ratio = content_height / img_height

            # Heuristic: if spread is less than 25% of height, it's likely stuck in one spot
            is_centered_only = spread_ratio < 0.25

            return VisualLinterResult(is_centered_only=is_centered_only, spread_ratio=spread_ratio)
