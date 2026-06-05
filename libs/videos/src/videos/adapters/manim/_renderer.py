from __future__ import annotations

import logging
import time
from pathlib import Path

from videos.core.ports._renderer import RenderResult

logger = logging.getLogger(__name__)


class ManimRenderer:
    def render(self, scene_job: object, output_path: Path) -> RenderResult:
        start = time.monotonic()
        try:
            from manim import config, tempconfig

            with tempconfig({"quality": "low_quality", "disable_caching": True}):
                config.pixel_height = 480
                config.pixel_width = 854
                scene = scene_job
                scene.render()
                out = config.output_file if hasattr(config, "output_file") else output_path
                rendered_path = Path(out)
                if rendered_path != output_path:
                    import shutil

                    shutil.copy2(rendered_path, output_path)
        except Exception:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(
                "Manim render failed",
                extra={
                    "output_path": str(output_path),
                    "duration_ms": elapsed,
                    "status": "error",
                },
            )
            return RenderResult(output_path=output_path, duration_ms=elapsed, success=False)

        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            "Manim render complete",
            extra={
                "output_path": str(output_path),
                "duration_ms": elapsed,
                "status": "success",
            },
        )
        return RenderResult(output_path=output_path, duration_ms=elapsed, success=True)
