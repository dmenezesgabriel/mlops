import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.unit.infrastructure._diagrams_fakes import (
    FakeDiagram,
    RenderRecorder,
    make_fake_diagrams_modules,
)


class _FileWritingFakeDiagram(FakeDiagram):
    """FakeDiagram that also emits the artifact the real `Diagram` writes.

    The scenarios assert the artifact exists on disk, so the fake honors the
    `filename=`/`outformat="png"` contract by writing `<filename>.png` when
    the diagram context closes.
    """

    def __init__(self, **kwargs: object) -> None:
        self._filename = str(kwargs["filename"])
        super().__init__(**kwargs)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        Path(f"{self._filename}.png").write_bytes(b"\x89PNG-fake")
        return super().__exit__(exc_type, exc_value, traceback)


@pytest.fixture()
def fake_diagrams(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[RenderRecorder]:
    """Serve the named-fake `diagrams` modules via real import machinery."""
    recorder = RenderRecorder()
    modules = make_fake_diagrams_modules(recorder)
    modules["diagrams"].Diagram = _FileWritingFakeDiagram
    for module_name, module in modules.items():
        monkeypatch.setitem(sys.modules, module_name, module)
    yield recorder
