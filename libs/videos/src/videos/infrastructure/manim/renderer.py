from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from videos.application.ports.renderer import RenderResult

if TYPE_CHECKING:
    from manim import Scene

logger = logging.getLogger(__name__)


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

            import tempfile

            with tempfile.TemporaryDirectory(
                prefix="manim_quality_"
            ) as tmp_dir:
                tmp_path = Path(tmp_dir)

                manim_quality = self.QUALITY_MAP.get(quality, "low_quality")

                old_quality = getattr(config, "quality", None)
                old_height = getattr(config, "pixel_height", None)
                old_width = getattr(config, "pixel_width", None)
                old_media_dir = getattr(config, "media_dir", None)
                old_log_dir = getattr(config, "log_dir", None)
                old_video_dir = getattr(config, "video_dir", None)
                old_images_dir = getattr(config, "images_dir", None)

                config.quality = manim_quality
                config.pixel_height, config.pixel_width = (
                    self.RESOLUTION_MAP.get(manim_quality, (480, 854))
                )

                # Redirect directories to our writable temp directory
                config.media_dir = str(tmp_path)
                config.log_dir = str(tmp_path)
                config.video_dir = str(tmp_path / "video")
                config.images_dir = str(tmp_path / "images")

                try:
                    yield
                finally:
                    if old_quality is not None:
                        config.quality = old_quality
                    if old_height is not None:
                        config.pixel_height = old_height
                    if old_width is not None:
                        config.pixel_width = old_width
                    if old_media_dir is not None:
                        config.media_dir = old_media_dir
                    if old_log_dir is not None:
                        config.log_dir = old_log_dir
                    if old_video_dir is not None:
                        config.video_dir = old_video_dir
                    if old_images_dir is not None:
                        config.images_dir = old_images_dir

    def render(
        self, scene_job: Scene, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        start = time.monotonic()
        try:
            from manim import config, tempconfig

            manim_quality = self.QUALITY_MAP.get(quality, "low_quality")

            # Check if config.media_dir has already been redirected to a temp dir
            is_temp_dir = "manim_quality_" in str(
                config.media_dir
            ) or "manim_render_" in str(config.media_dir)

            if is_temp_dir:
                scene = scene_job
                scene.render()

                from PIL import Image

                pixels = scene.renderer.get_frame()
                last_frame = Image.fromarray(pixels)
                image_path = output_path.with_suffix(".png")

                output_path.parent.mkdir(parents=True, exist_ok=True)
                last_frame.save(image_path)

                rendered_path = Path(
                    config.output_file
                    if hasattr(config, "output_file")
                    else output_path
                )
                video_files = list(Path(config.media_dir).glob("**/*.mp4"))
                if video_files:
                    rendered_path = video_files[0]

                if rendered_path.exists():
                    import shutil

                    shutil.copy2(rendered_path, output_path)

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

            # Fallback if quality_context was not used: wrap manually
            import tempfile

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

                    scene = scene_job
                    scene.render()

                    # Save last frame for visual validation
                    from PIL import Image

                    pixels = scene.renderer.get_frame()
                    last_frame = Image.fromarray(pixels)
                    image_path = output_path.with_suffix(".png")

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    last_frame.save(image_path)

                    # Find generated mp4 recursively in our isolated temp folder
                    rendered_path = Path(
                        config.output_file
                        if hasattr(config, "output_file")
                        else output_path
                    )
                    video_files = list(tmp_path.glob("**/*.mp4"))
                    if video_files:
                        rendered_path = video_files[0]

                    if rendered_path.exists():
                        import shutil

                        shutil.copy2(rendered_path, output_path)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception(
                f"Manim render failed: {e}",
                extra={
                    "output_path": str(output_path),
                    "duration_ms": elapsed,
                    "status": "error",
                },
            )
            return RenderResult(
                output_path=output_path, duration_ms=elapsed, success=False
            )

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
