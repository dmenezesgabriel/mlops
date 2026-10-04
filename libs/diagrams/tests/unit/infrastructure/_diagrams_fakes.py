"""Named fakes for the optional `diagrams` (mingrammer) dependency.

The package env lacks the `[diagrams]` extra, so these stand-ins are injected
into `sys.modules` — the real `importlib.import_module` machinery serves them
to `MingrammerDiagramRenderer`, keeping the dynamic-import boundary under test
(ADR-0005 named fakes, not patched `importlib`/`MagicMock` webs).
"""

import types
from typing import ClassVar


class RenderRecorder:
    """Collects the calls the renderer makes through the fake diagrams API."""

    def __init__(self) -> None:
        self.diagram_calls: list[dict[str, object]] = []
        self.cluster_calls: list[tuple[str, dict[str, str]]] = []
        self.node_labels: list[str] = []
        self.edges: list[tuple[str, str | None, str]] = []


class FakeDiagram:
    """Stand-in for `diagrams.Diagram`: records ctor kwargs; no-op context."""

    recorder: ClassVar[RenderRecorder]

    def __init__(self, **kwargs: object) -> None:
        self.recorder.diagram_calls.append(kwargs)

    def __enter__(self) -> "FakeDiagram":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        return None


class FakeCluster:
    """Stand-in for `diagrams.Cluster`: records name + graph_attr."""

    recorder: ClassVar[RenderRecorder]

    def __init__(self, name: str, *, graph_attr: dict[str, str]) -> None:
        self.recorder.cluster_calls.append((name, graph_attr))

    def __enter__(self) -> "FakeCluster":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        return None


class FakeEdge:
    """Stand-in for `diagrams.Edge` — carries the label through `>>`."""

    def __init__(self, label: str) -> None:
        self.label = label


class FakeNode:
    """Stand-in for mingrammer node classes (`cls(label)` + `>>` chaining)."""

    recorder: ClassVar[RenderRecorder]

    def __init__(self, label: str) -> None:
        self.label = label
        self.recorder.node_labels.append(label)

    def __rshift__(self, other: object) -> "_PendingFakeEdge | FakeNode":
        if isinstance(other, FakeEdge):
            return _PendingFakeEdge(self, other)
        if not isinstance(other, FakeNode):
            raise TypeError(f"expected FakeNode, got {other!r}")
        self.recorder.edges.append((self.label, None, other.label))
        return self


class _PendingFakeEdge:
    """Result of `node >> edge`; the next `>> node` completes the chain."""

    def __init__(self, source: FakeNode, edge: FakeEdge) -> None:
        self._source = source
        self._edge = edge

    def __rshift__(self, other: object) -> "_PendingFakeEdge":
        if not isinstance(other, FakeNode):
            raise TypeError(f"expected FakeNode, got {other!r}")
        self._source.recorder.edges.append(
            (self._source.label, self._edge.label, other.label)
        )
        return self


def make_fake_diagrams_modules(
    recorder: RenderRecorder,
) -> dict[str, types.ModuleType]:
    """Build the `diagrams` package + `diagrams.onprem.mlops` leaf module."""
    diagrams_module = types.ModuleType("diagrams")
    diagrams_module.Diagram = FakeDiagram
    diagrams_module.Cluster = FakeCluster
    diagrams_module.Edge = FakeEdge
    mlops_module = types.ModuleType("diagrams.onprem.mlops")
    mlops_module.Mlflow = FakeNode
    custom_module = types.ModuleType("diagrams.custom")
    custom_module.Custom = FakeNode
    FakeDiagram.recorder = recorder
    FakeCluster.recorder = recorder
    FakeNode.recorder = recorder
    return {
        "diagrams": diagrams_module,
        "diagrams.onprem.mlops": mlops_module,
        "diagrams.custom": custom_module,
    }
