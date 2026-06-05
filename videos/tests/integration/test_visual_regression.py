"""Option B: Render each scene via Docker and validate frames with PIL.

Uses manim's ``-s`` flag to render a single frame per scene, then
checks for basic rendering sanity and text-overlap artifacts.

Run with:  pytest tests/integration/ -m docker
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

_MANIM_IMAGE = "manimcommunity/manim:latest"
_SCENES: list[tuple[str, str]] = [
    ("bias_variance_tradeoff", "BiasVarianceTradeoffScene"),
    ("crisp_dm", "CrispDmScene"),
    ("mlops_lifecycle", "MlopsLifecycleScene"),
    ("underfit_vs_overfit", "UnderfitVsOverfitScene"),
]
_SRC_MOUNT = Path(__file__).resolve().parents[3] / "videos" / "src"


def _non_overlapping_text_regions(image: Image.Image) -> list[tuple[int, int, int, int]]:
    """Find text pixel regions and return overlapping bounding box pairs."""
    gray = image.convert("L")
    arr = np.array(gray)

    # Manim dark background (~#1e1e1e = 30), text is white (~255).
    # Threshold for text-like bright pixels.
    binary = arr > 200

    # Group consecutive rows that contain text.
    row_has_text = binary.any(axis=1)
    regions: list[tuple[int, int]] = []
    in_region = False
    start = 0
    for row in range(len(row_has_text)):
        if row_has_text[row] and not in_region:
            start = row
            in_region = True
        elif not row_has_text[row] and in_region:
            regions.append((start, row - 1))
            in_region = False
    if in_region:
        regions.append((start, len(row_has_text) - 1))

    if len(regions) < 2:
        return []

    # Check horizontal overlap of each region's text content.
    overlaps: list[tuple[int, int, int, int]] = []
    for i, (r1_start, r1_end) in enumerate(regions):
        cols_i = np.where(binary[r1_start : r1_end + 1].any(axis=0))[0]
        if len(cols_i) == 0:
            continue
        left_i, right_i = int(cols_i.min()), int(cols_i.max())

        for r2_start, r2_end in regions[i + 1 :]:
            cols_j = np.where(binary[r2_start : r2_end + 1].any(axis=0))[0]
            if len(cols_j) == 0:
                continue
            left_j, right_j = int(cols_j.min()), int(cols_j.max())

            if left_i < right_j and left_j < right_i:
                # Vertical gap between regions
                gap = r2_start - r1_end
                horizontal_overlap_ratio = (
                    min(right_i, right_j) - max(left_i, left_j)
                ) / max(right_i - left_i, right_j - left_j)
                if horizontal_overlap_ratio > 0.3 and gap < 50:
                    overlaps.append((r1_start, r1_end, r2_start, r2_end))

    return overlaps


# --- fixtures ---

_SCENE_LOOKUP = {s[0]: s[1] for s in _SCENES}


@pytest.fixture(params=list(_SCENE_LOOKUP.keys()), ids=list(_SCENE_LOOKUP.keys()))
def scene_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def _scene_class(scene_name: str) -> str:
    return _SCENE_LOOKUP[scene_name]


@pytest.fixture
def frame_path(scene_name: str, _scene_class: str, tmp_path: Path) -> Path:
    """Render one frame of the scene inside Docker and return the local path."""
    subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{_SRC_MOUNT}:/videos_src:ro",
            "-v", f"{tmp_path}:/output:delegated",
            _MANIM_IMAGE,
            "sh", "-lc",
            f"PYTHONPATH=/videos_src /opt/venv/bin/python -m manim -s -ql "
            f"/videos_src/mlops_videos/concepts/{scene_name}.py {_scene_class} "
            f"--media_dir /tmp/manim && "
            f"find /tmp/manim -name '*.png' -type f -exec cp {{}} /output/{scene_name}.png \\;",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )

    pngs = list(tmp_path.glob("*.png"))
    if not pngs:
        raise RuntimeError(f"No PNG frame produced for {scene_name}")
    return pngs[0]


@pytest.mark.docker
class TestSceneFrames:
    def test_each_scene_renders_non_blank_frame(self, scene_name: str, frame_path: Path) -> None:
        img = Image.open(frame_path).convert("L")
        arr = np.array(img)

        # Not entirely uniform
        assert arr.std() > 10, (
            f"{scene_name}: frame std={arr.std():.1f} — likely blank"
        )

        # Has some bright (text) pixels
        bright_ratio = (arr > 200).mean()
        assert bright_ratio > 0.001, (
            f"{scene_name}: only {bright_ratio:.4f} bright pixels — no visible content"
        )

    def test_no_text_overlap_between_lines(self, scene_name: str, frame_path: Path) -> None:
        img = Image.open(frame_path)
        overlaps = _non_overlapping_text_regions(img)
        assert len(overlaps) == 0, (
            f"{scene_name}: {len(overlaps)} overlapping text region(s): {overlaps}"
        )
