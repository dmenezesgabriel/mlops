# pyright: reportMissingModuleSource=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# manim is an optional extra installed only in the render container and
# ships no type information; this module is the adapters' boundary to it.
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
from videos.domain.value_objects.identifiers import require_quality
from videos.infrastructure.manim._missing import require_manim

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


def _save_last_frame(scene: Scene, output_path: Path) -> None:
    from PIL import Image

    pixels = scene.renderer.get_frame()
    last_frame = Image.fromarray(pixels)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_frame.save(output_path.with_suffix(".png"))


def _find_rendered_mp4(config: Any, search_dir: Path) -> Path | None:
    # partial_movie_files holds per-segment intermediates indistinguishable
    # from the scene output by name — never a final artifact.
    output_file = getattr(config, "output_file", "") or ""
    if output_file:
        named = sorted(search_dir.glob(f"**/{Path(output_file).name}"))
        if named:
            return named[0]
    video_files = [
        path
        for path in search_dir.glob("**/*.mp4")
        if "partial_movie_files" not in path.parts
    ]
    if not video_files:
        return None
    return max(video_files, key=lambda path: path.stat().st_mtime)


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

    # Class-level RLock: manim.config is a module global mutated for the
    # whole window callers render inside quality_context — exclusion has to
    # span the yield and every instance, or concurrent contexts interleave
    # config.quality/media_dir. Reentrant so nested contexts on one thread
    # compose.
    _lock = threading.RLock()

    def __init__(self) -> None:
        # Set only while a quality_context body runs — render() keys the
        # in-context path off this flag, not off media_dir name sniffing.
        self._context_quality: str | None = None

    @contextlib.contextmanager
    def quality_context(self, quality: str) -> Iterator[None]:
        require_quality(quality)
        require_manim()
        with self._lock:
            from manim import config

            with tempfile.TemporaryDirectory(
                prefix="manim_quality_"
            ) as tmp_dir:
                tmp_path = Path(tmp_dir)

                manim_quality = self.QUALITY_MAP[quality]
                snapshot = {
                    attr: getattr(config, attr, None)
                    for attr in _MANIM_CONFIG_ATTRS
                }

                config.quality = manim_quality
                config.pixel_height, config.pixel_width = (
                    self.RESOLUTION_MAP.get(manim_quality, (480, 854))
                )
                _apply_render_dirs(config, tmp_path)

                previous_quality = self._context_quality
                self._context_quality = quality
                try:
                    yield
                finally:
                    self._context_quality = previous_quality
                    _restore_config(config, snapshot)

    def render(
        self, scene_job: Scene, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        require_quality(quality)
        require_manim()
        start = time.monotonic()
        context_quality = self._context_quality
        if context_quality is not None and quality != context_quality:
            raise ValueError(
                f"render(quality={quality!r}) cannot run inside "
                f"quality_context({context_quality!r})"
            )
        try:
            from manim import config

            if context_quality is not None:
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

        manim_quality = self.QUALITY_MAP[quality]

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
    rendered_path = _find_rendered_mp4(config, search_dir)
    if rendered_path is None:
        raise RuntimeError(f"manim produced no final mp4 under {search_dir}")
    shutil.copy2(rendered_path, output_path)


def _render_to_output(
    scene: Scene,
    output_path: Path,
    search_dir: Path,
    config: Any,
    start: float,
) -> RenderResult:
    _render_scene(scene, output_path, search_dir, config)
    return _render_success(output_path, start)
