from __future__ import annotations

import logging
import time
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

    def render(
        self, scene_job: Scene, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        start = time.monotonic()
        try:
            from manim import config, tempconfig

            manim_quality = self.QUALITY_MAP.get(quality, "low_quality")

            with tempconfig(
                {"quality": manim_quality, "disable_caching": True}
            ):
                if manim_quality == "low_quality":
                    config.pixel_height = 480
                    config.pixel_width = 854
                else:
                    config.pixel_height = 1080
                    config.pixel_width = 1920

                scene = scene_job
                scene.render()

                # Save last frame for visual validation
                from PIL import Image

                # Manim renderer stores the last frame
                pixels = scene.renderer.get_frame()
                last_frame = Image.fromarray(pixels)
                image_path = output_path.with_suffix(".png")
                last_frame.save(image_path)

                out = (
                    config.output_file
                    if hasattr(config, "output_file")
                    else output_path
                )
                rendered_path = Path(out)
                if rendered_path != output_path:
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
