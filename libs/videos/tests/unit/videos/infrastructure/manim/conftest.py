import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.unit.videos.infrastructure.manim._manim_fakes import (
    FakeManim,
    FakeManimConfig,
    make_fake_manim_module,
)


@pytest.fixture()
def fake_manim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[FakeManim]:
    """Serve the named-fake `manim` module via real import machinery."""
    config = FakeManimConfig(tmp_path / "manim_media")
    monkeypatch.setitem(sys.modules, "manim", make_fake_manim_module(config))
    yield FakeManim(config)


@pytest.fixture()
def manim_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    # None in sys.modules turns `import manim` into ImportError even where the
    # real package is installed (docker CI).
    monkeypatch.setitem(sys.modules, "manim", None)
