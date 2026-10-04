"""Unit coverage for `ManimRenderer` via the named-fake manim module — the
docker-marked suite only runs where the real extra is installed."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from tests.unit.videos.infrastructure.manim._manim_fakes import FakeManim
from videos.infrastructure.manim.renderer import ManimRenderer


def test_render_inside_quality_context_produces_artifact(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    renderer = ManimRenderer()
    output = tmp_path / "out.mp4"
    scene = fake_manim.make_scene(files={"video/final.mp4": b"FINAL"})
    with renderer.quality_context("preview"):
        result = renderer.render(scene, output, quality="preview")
    assert result.success is True
    assert output.read_bytes() == b"FINAL"


def test_render_quality_arg_mismatch_inside_context_raises(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    renderer = ManimRenderer()
    scene = fake_manim.make_scene(files={"video/final.mp4": b"FINAL"})
    with renderer.quality_context("preview"):
        with pytest.raises(ValueError, match="final.*preview|preview.*final"):
            renderer.render(scene, tmp_path / "out.mp4", quality="final")


def test_render_outside_context_ignores_ambient_media_dir(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    ambient = tmp_path / "manim_quality_backup"
    ambient.mkdir()
    fake_manim.config.media_dir = str(ambient)
    renderer = ManimRenderer()
    output = tmp_path / "out.mp4"
    scene = fake_manim.make_scene(files={"video/final.mp4": b"FINAL"})
    result = renderer.render(scene, output, quality="final")
    assert result.success is True
    assert output.read_bytes() == b"FINAL"
    assert list(ambient.rglob("*.mp4")) == []


def test_render_only_partial_segments_returns_failure(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    renderer = ManimRenderer()
    output = tmp_path / "out.mp4"
    scene = fake_manim.make_scene(
        files={"video/partial_movie_files/seg0.mp4": b"SEG"}
    )
    result = renderer.render(scene, output)
    assert result.success is False
    assert not output.exists()


def test_render_prefers_final_mp4_over_partial_segments(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    renderer = ManimRenderer()
    output = tmp_path / "out.mp4"
    scene = fake_manim.make_scene(
        files={
            "video/partial_movie_files/seg0.mp4": b"SEG",
            "video/final.mp4": b"FINAL",
        }
    )
    result = renderer.render(scene, output)
    assert result.success is True
    assert output.read_bytes() == b"FINAL"


def test_render_no_mp4_produced_returns_failure(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    renderer = ManimRenderer()
    output = tmp_path / "out.mp4"
    result = renderer.render(fake_manim.make_scene(), output)
    assert result.success is False
    assert not output.exists()


def test_render_stale_output_file_not_copied(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    stale = tmp_path / "stale.mp4"
    stale.write_bytes(b"STALE")
    fake_manim.config.output_file = str(stale)
    renderer = ManimRenderer()
    output = tmp_path / "out.mp4"
    result = renderer.render(fake_manim.make_scene(), output)
    assert result.success is False
    assert not output.exists()


def test_render_named_output_file_inside_media_dir_preferred(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    fake_manim.config.output_file = "scene.mp4"
    renderer = ManimRenderer()
    output = tmp_path / "out.mp4"
    scene = fake_manim.make_scene(
        files={
            "video/partial_movie_files/seg0.mp4": b"SEG",
            "video/scene.mp4": b"SCENE",
        }
    )
    result = renderer.render(scene, output)
    assert result.success is True
    assert output.read_bytes() == b"SCENE"


def test_quality_context_applies_and_restores_config(
    fake_manim: FakeManim,
) -> None:
    config = fake_manim.config
    original_dir = config.media_dir
    with ManimRenderer().quality_context("final"):
        assert config.quality == "high_quality"
        assert config.pixel_height == 1080
        assert "manim_quality_" in config.media_dir
    assert config.quality == "medium_quality"
    assert config.media_dir == original_dir


def test_render_in_temp_dir_restores_config(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    config = fake_manim.config
    renderer = ManimRenderer()
    scene = fake_manim.make_scene(files={"video/final.mp4": b"FINAL"})
    result = renderer.render(scene, tmp_path / "out.mp4", quality="final")
    assert result.success is True
    assert config.quality == "medium_quality"
    assert config.media_dir.endswith("manim_media")


def test_quality_context_serializes_concurrent_renders(
    fake_manim: FakeManim,
) -> None:
    # Class-level exclusion on the shared module-global manim.config is the
    # documented invariant — concurrent contexts interleave config otherwise.
    renderer = ManimRenderer()
    worker_entered = threading.Event()

    def worker() -> None:
        with renderer.quality_context("final"):
            worker_entered.set()

    with renderer.quality_context("preview"):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        assert not worker_entered.wait(timeout=0.5)
    assert worker_entered.wait(timeout=5)
    thread.join(timeout=5)


def test_quality_context_rejects_unknown_quality(
    fake_manim: FakeManim,
) -> None:
    with pytest.raises(ValueError, match="quality"):
        with ManimRenderer().quality_context("bogus"):
            pass


def test_render_rejects_unknown_quality(
    fake_manim: FakeManim, tmp_path: Path
) -> None:
    renderer = ManimRenderer()
    scene = fake_manim.make_scene(files={"video/final.mp4": b"FINAL"})
    with pytest.raises(ValueError, match="quality"):
        renderer.render(scene, tmp_path / "out.mp4", quality="bogus")


def test_quality_context_manim_absent_raises_named_error(
    manim_absent: None,
) -> None:
    with pytest.raises(RuntimeError, match=r"videos\[manim\]"):
        with ManimRenderer().quality_context("preview"):
            pass


def test_render_manim_absent_raises_named_error(
    manim_absent: None, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match=r"videos\[manim\]"):
        ManimRenderer().render(object(), tmp_path / "out.mp4")


def test_nested_quality_context_completes(
    fake_manim: FakeManim,
) -> None:
    # Runs in a daemon thread: a reintroduced non-reentrant lock times out
    # here instead of hanging the suite. Keep last in the file — a poisoned
    # class lock blocks every later render.
    renderer = ManimRenderer()
    done = threading.Event()

    def nested() -> None:
        with (
            renderer.quality_context("preview"),
            renderer.quality_context("final"),
        ):
            pass
        done.set()

    thread = threading.Thread(target=nested, daemon=True)
    thread.start()
    assert done.wait(timeout=5)
