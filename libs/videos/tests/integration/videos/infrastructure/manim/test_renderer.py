import sys

# Clean up sys.path and sys.modules to prevent local tests folder namespace collision with the global manim library
sys.modules.pop("manim", None)
sys.path = [
    p
    for p in sys.path
    if not p.endswith("infrastructure/manim")
    and not p.endswith("manim")
    and "tests/integration/videos/infrastructure" not in p.replace("\\", "/")
]

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.infrastructure.manim.renderer import ManimRenderer  # noqa: E402


def import_real_manim() -> object:
    import sys

    orig_path = list(sys.path)
    # Remove path components ending with infrastructure/manim to prevent local resolution
    sys.path = [
        p
        for p in sys.path
        if "infrastructure/manim" not in p.replace("\\", "/")
    ]
    try:
        import manim

        return manim
    finally:
        sys.path = orig_path


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

    def test_quality_context_configures_and_restores_manim_config(
        self,
    ) -> None:
        manim = import_real_manim()
        config = manim.config
        renderer = ManimRenderer()

        orig_height = config.pixel_height
        orig_width = config.pixel_width

        with renderer.quality_context("preview"):
            assert config.pixel_height == 480
            assert config.pixel_width == 854

        with renderer.quality_context("final"):
            assert config.pixel_height == 1080
            assert config.pixel_width == 1920

        assert config.pixel_height == orig_height
        assert config.pixel_width == orig_width

    def test_quality_context_is_thread_safe(self) -> None:
        import threading
        import time

        renderer = ManimRenderer()
        log = []

        def worker(thread_id: int) -> None:
            with renderer.quality_context("preview"):
                log.append(f"start_{thread_id}")
                time.sleep(0.1)
                log.append(f"end_{thread_id}")

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))

        t1.start()
        time.sleep(0.02)
        t2.start()

        t1.join()
        t2.join()

        assert log == ["start_1", "end_1", "start_2", "end_2"]

    def test_render_cleans_up_temporary_media_files(
        self, tmp_path: Path
    ) -> None:
        import tempfile
        from unittest.mock import patch

        renderer = ManimRenderer()
        output = tmp_path / "test.mp4"

        original_tempdir = tempfile.TemporaryDirectory
        created_dirs = []

        def spy_tempdir(*args, **kwargs) -> tempfile.TemporaryDirectory:
            td = original_tempdir(*args, **kwargs)
            created_dirs.append(td.name)
            return td

        with patch("tempfile.TemporaryDirectory", side_effect=spy_tempdir):
            renderer.render(object(), output)

        assert len(created_dirs) == 1
        assert not Path(created_dirs[0]).exists()
