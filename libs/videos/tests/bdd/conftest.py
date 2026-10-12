"""Named fakes + fixtures for the videos-cli BDD feature.

Only the absent `manim` extra is faked: `cli.ManimRenderer` /
`cli.ManimSceneBuilder` are swapped for fakes that honor the real artifact
contract (decodable PNG preview + mp4 the linter can open). Everything else
in `cli.main()` — argv, registry, pipeline, artifact store, and the real
videos-linter seam — runs for real.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import pytest
import videos.infrastructure.cli as cli
from videos.application.components import ComponentRegistry
from videos.application.ports.renderer import Renderer, RenderResult

from tests._fakes import FakeSceneBuilder


@dataclass
class RenderPlan:
    """Which artifacts the fake renderer emits: `good` passes the real
    linters; `blank`/`corrupt` fail them with named violations."""

    image: str = "good"
    video: str = "good"


def _write_preview_image(path: Path, mode: str) -> None:
    from PIL import Image, ImageDraw

    if mode == "blank":
        Image.new("RGB", (854, 480), color=(30, 30, 30)).save(path)
        return
    img = Image.new("RGB", (854, 480), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    draw.rectangle([300, 50, 500, 80], fill=(255, 255, 255))
    draw.rectangle([200, 200, 600, 300], fill=(255, 255, 255))
    img.save(path)


def _write_scene_video(path: Path, mode: str) -> None:
    if mode == "corrupt":
        path.write_bytes(b"not a video")
        return
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 64)
    )
    frame = np.full((64, 64, 3), 30, dtype=np.uint8)
    for _ in range(6):
        writer.write(frame)
    writer.release()


class _FakeCliRenderer(Renderer):
    """Writes real artifacts both linters can decode; the plan knob flips
    them into the failure shapes a scenario needs."""

    plan: ClassVar[RenderPlan] = RenderPlan()

    @contextlib.contextmanager
    def quality_context(self, quality: str) -> Iterator[None]:
        yield

    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_preview_image(output_path.with_suffix(".png"), self.plan.image)
        _write_scene_video(output_path, self.plan.video)
        return RenderResult(
            output_path=output_path, duration_ms=10.0, success=True
        )


class _CliSceneBuilder(FakeSceneBuilder):
    """`cli.main()` constructs `ManimSceneBuilder(registry=...)`; the shared
    FakeSceneBuilder's ctor takes `log` — this subclass adapts the call
    shape without touching its `build`/`build_storyboard` behavior."""

    def __init__(self, registry: ComponentRegistry) -> None:
        super().__init__()


@pytest.fixture(autouse=True)
def cli_fakes(monkeypatch: pytest.MonkeyPatch) -> Iterator[RenderPlan]:
    plan = RenderPlan()
    _FakeCliRenderer.plan = plan
    monkeypatch.setattr(cli, "ManimRenderer", _FakeCliRenderer)
    monkeypatch.setattr(cli, "ManimSceneBuilder", _CliSceneBuilder)
    yield plan
    # setup_structured_logging binds one StreamHandler to the *current*
    # sys.stdout; without the clear, later scenarios log into the closed
    # capture of the scenario that ran first.
    logging.getLogger("videos").handlers.clear()
