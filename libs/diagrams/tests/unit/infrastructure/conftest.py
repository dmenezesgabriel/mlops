import sys
from collections.abc import Iterator

import pytest
from tests.unit.infrastructure._diagrams_fakes import (
    RenderRecorder,
    make_fake_diagrams_modules,
)


@pytest.fixture()
def fake_diagrams(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[RenderRecorder]:
    """Serve the named-fake `diagrams` modules via real import machinery."""
    recorder = RenderRecorder()
    for module_name, module in make_fake_diagrams_modules(recorder).items():
        monkeypatch.setitem(sys.modules, module_name, module)
    yield recorder
