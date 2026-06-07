from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Protocol


class RenderResult:
    def __init__(
        self, output_path: Path, duration_ms: float, success: bool
    ) -> None:
        self.output_path = output_path
        self.duration_ms = duration_ms
        self.success = success


class Renderer(Protocol):
    def quality_context(
        self, quality: str
    ) -> contextlib.AbstractContextManager[None]:
        return contextlib.nullcontext()

    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult: ...
