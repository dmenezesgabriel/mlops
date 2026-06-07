from pathlib import Path

import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.infrastructure.manim.renderer import ManimRenderer  # noqa: E402


class TestManimRenderer:
    def test_renderer_creation(self) -> None:
        renderer = ManimRenderer()
        assert renderer is not None

    def test_render_returns_result(self, tmp_path: Path) -> None:
        renderer = ManimRenderer()
        output = tmp_path / "test.mp4"
        result = renderer.render(object(), output)
        assert result.output_path == output
        assert result.success is False
