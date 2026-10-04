"""Named fakes for the optional `manim` extra (ADR-0005).

The unit suite runs without `videos[manim]` installed; injecting the fake
module into `sys.modules` exercises the renderer/scene-builder seam locally
instead of only under the docker-marked integration suite.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any


class FakeManimConfig:
    """Attribute surface `renderer.py` reads/mutates on `manim.config`."""

    def __init__(self, media_dir: Path) -> None:
        self.quality = "medium_quality"
        self.pixel_height = 720
        self.pixel_width = 1280
        self.output_file = ""
        self.media_dir = str(media_dir)
        self.log_dir = str(media_dir)
        self.video_dir = str(media_dir / "video")
        self.images_dir = str(media_dir / "images")


class _FakeSceneRenderer:
    def __init__(self, frame: Any) -> None:
        self._frame = frame

    def get_frame(self) -> Any:
        return self._frame


class FakeScene:
    """`render()` writes the configured files under `config.media_dir`, read
    live at call time so `tempconfig`/`quality_context` redirects apply."""

    def __init__(
        self, config: FakeManimConfig, files: dict[str, bytes], frame: Any
    ) -> None:
        self._config = config
        self._files = files
        self.renderer = _FakeSceneRenderer(frame)
        self.render_calls = 0

    def render(self) -> None:
        self.render_calls += 1
        for relative_path, content in self._files.items():
            target = Path(self._config.media_dir) / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


class FakeManim:
    """Fixture handle: the injected module's config plus a scene factory."""

    def __init__(self, config: FakeManimConfig) -> None:
        self.config = config

    def make_scene(
        self, files: dict[str, bytes] | None = None, frame: Any = None
    ) -> FakeScene:
        if frame is None:
            import numpy

            frame = numpy.zeros((4, 4, 3), dtype=numpy.uint8)
        return FakeScene(self.config, files or {}, frame)


def _tempconfig_for(config: FakeManimConfig) -> Any:
    @contextlib.contextmanager
    def fake_tempconfig(settings: dict[str, Any]) -> Iterator[None]:
        snapshot = {key: getattr(config, key, None) for key in settings}
        for key, value in settings.items():
            setattr(config, key, value)
        try:
            yield
        finally:
            for key, value in snapshot.items():
                setattr(config, key, value)

    return fake_tempconfig


def make_fake_manim_module(config: FakeManimConfig) -> ModuleType:
    module = ModuleType("manim")
    module.config = config
    module.tempconfig = _tempconfig_for(config)
    module.Scene = FakeScene
    return module
