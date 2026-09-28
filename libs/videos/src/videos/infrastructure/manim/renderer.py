from __future__ import annotations

import contextlib
import logging
import shutil
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from videos.application.ports.renderer import RenderResult

if TYPE_CHECKING:
    from manim import Scene

logger = logging.getLogger(__name__)

_MANIM_CONFIG_ATTRS = (
    "quality",
    "pixel_height",
    "pixel_width",
    "media_dir",
    "log_dir",
    "video_dir",
    "images_dir",
)


def _apply_render_dirs(config: Any, tmp_path: Path) -> None:
    # Redirect directories to our writable temp directory
    config.media_dir = str(tmp_path)
    config.log_dir = str(tmp_path)
    config.video_dir = str(tmp_path / "video")
    config.images_dir = str(tmp_path / "images")


def _restore_config(config: Any, snapshot: dict[str, Any]) -> None:
    for attr, value in snapshot.items():
        if value is not None:
            setattr(config, attr, value)


def _is_temp_media_dir(config: Any) -> bool:
    # media_dir is already redirected when running inside quality_context
    return "manim_quality_" in str(config.media_dir) or "manim_render_" in str(
        config.media_dir
    )


def _save_last_frame(scene: Scene, output_path: Path) -> None:
    from PIL import Image

    pixels = scene.renderer.get_frame()
    last_frame = Image.fromarray(pixels)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_frame.save(output_path.with_suffix(".png"))


def _find_rendered_mp4(
    config: Any, search_dir: Path, output_path: Path
) -> Path:
    rendered_path = Path(
        config.output_file if hasattr(config, "output_file") else output_path
    )
    video_files = list(search_dir.glob("**/*.mp4"))
    if video_files:
        rendered_path = video_files[0]
    return rendered_path


def _copy_if_exists(rendered_path: Path, output_path: Path) -> None:
    if rendered_path.exists():
        shutil.copy2(rendered_path, output_path)


def _render_success(output_path: Path, start: float) -> RenderResult:
    elapsed = (time.monotonic() - start) * 1000
    logger.info(
        "Manim render complete",
        extra={
            "output_path": str(output_path),
            "duration_ms": elapsed,
            "status": "success",
        },
    )
    return RenderResult(
        output_path=output_path, duration_ms=elapsed, success=True
    )


def _render_failure(
    output_path: Path, start: float, exc: Exception
) -> RenderResult:
    elapsed = (time.monotonic() - start) * 1000
    logger.exception(
        f"Manim render failed: {exc}",
        extra={
            "output_path": str(output_path),
            "duration_ms": elapsed,
            "status": "error",
        },
    )
    return RenderResult(
        output_path=output_path, duration_ms=elapsed, success=False
    )


class ManimRenderer:
    QUALITY_MAP = {
        "preview": "low_quality",
        "final": "high_quality",
    }

    RESOLUTION_MAP = {
        "low_quality": (480, 854),
        "high_quality": (1080, 1920),
    }

    _lock = threading.Lock()

    @contextlib.contextmanager
    def quality_context(self, quality: str) -> Iterator[None]:
        with self._lock:
            try:
                from manim import config
            except ImportError:
                yield
                return

            with tempfile.TemporaryDirectory(
                prefix="manim_quality_"
            ) as tmp_dir:
                tmp_path = Path(tmp_dir)

                manim_quality = self.QUALITY_MAP.get(quality, "low_quality")
                snapshot = {
                    attr: getattr(config, attr, None)
                    for attr in _MANIM_CONFIG_ATTRS
                }

                config.quality = manim_quality
                config.pixel_height, config.pixel_width = (
                    self.RESOLUTION_MAP.get(manim_quality, (480, 854))
                )
                _apply_render_dirs(config, tmp_path)

                try:
                    yield
                finally:
                    _restore_config(config, snapshot)

    def render(
        self, scene_job: Scene, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        start = time.monotonic()
        try:
            from manim import config

            if _is_temp_media_dir(config):
                return _render_to_output(
                    scene_job,
                    output_path,
                    Path(config.media_dir),
                    config,
                    start,
                )
            return self._render_in_temp_dir(
                scene_job, output_path, quality, start
            )
        except Exception as exc:
            return _render_failure(output_path, start, exc)

    def _render_in_temp_dir(
        self,
        scene_job: Scene,
        output_path: Path,
        quality: str,
        start: float,
    ) -> RenderResult:
        from manim import config, tempconfig

        manim_quality = self.QUALITY_MAP.get(quality, "low_quality")

        # Fallback if quality_context was not used: wrap manually
        with (
            self._lock,
            tempfile.TemporaryDirectory(prefix="manim_render_") as tmp_dir,
        ):
            tmp_path = Path(tmp_dir)

            with tempconfig(
                {
                    "quality": manim_quality,
                    "disable_caching": True,
                    "media_dir": str(tmp_path),
                    "log_dir": str(tmp_path),
                    "video_dir": str(tmp_path / "video"),
                    "images_dir": str(tmp_path / "images"),
                }
            ):
                config.pixel_height, config.pixel_width = (
                    self.RESOLUTION_MAP.get(manim_quality, (480, 854))
                )
                _render_scene(scene_job, output_path, tmp_path, config)
        return _render_success(output_path, start)


def _render_scene(
    scene: Scene, output_path: Path, search_dir: Path, config: Any
) -> None:
    scene.render()
    # Save last frame for visual validation
    _save_last_frame(scene, output_path)
    # Find generated mp4 recursively in our isolated temp folder
    rendered_path = _find_rendered_mp4(config, search_dir, output_path)
    _copy_if_exists(rendered_path, output_path)


def _render_to_output(
    scene: Scene,
    output_path: Path,
    search_dir: Path,
    config: Any,
    start: float,
) -> RenderResult:
    _render_scene(scene, output_path, search_dir, config)
    return _render_success(output_path, start)
