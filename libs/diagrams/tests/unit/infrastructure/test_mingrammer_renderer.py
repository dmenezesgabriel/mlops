import sys
from pathlib import Path

import pytest
from diagrams_generation.domain import (
    DiagramCluster,
    DiagramDefinition,
    DiagramNode,
)
from diagrams_generation.domain.value_objects.diagram_connection import (
    DiagramConnection,
)
from diagrams_generation.infrastructure.mingrammer_renderer import (
    MingrammerDiagramRenderer,
)
from tests.unit.infrastructure._diagrams_fakes import (
    FakeCluster,
    FakeNode,
    RenderRecorder,
)


class TestMingrammerDiagramRendererDependencyCheck:
    def test_should_raise_import_error_when_diagrams_library_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Arrange — sys.modules[name]=None makes the import machinery raise
        # ImportError, so this arm holds whether or not the extra is installed.
        monkeypatch.setitem(sys.modules, "diagrams", None)
        renderer = MingrammerDiagramRenderer()
        definition = DiagramDefinition(
            name="Test",
            filename="test",
            direction="LR",
            nodes=(),
            clusters=(),
            connections=(),
        )

        # Act & Assert
        with pytest.raises(ImportError) as exc_info:
            renderer.render(definition, output_directory=str(tmp_path))
        assert "diagrams-generation[diagrams]" in str(exc_info.value)


class TestMingrammerDiagramRendererRender:
    def test_should_render_definition_and_return_png_path(
        self, fake_diagrams: RenderRecorder, tmp_path: Path
    ) -> None:
        # Arrange
        output_dir = tmp_path / "out"
        definition = DiagramDefinition(
            name="Pipeline",
            filename="pipeline",
            direction="LR",
            nodes=(
                DiagramNode(
                    identifier="train",
                    label="Train Model",
                    node_type="onprem.mlops.Mlflow",
                ),
            ),
            clusters=(
                DiagramCluster(
                    name="Data Processing",
                    nodes=(
                        DiagramNode(
                            identifier="raw",
                            label="Raw Data",
                            node_type="onprem.mlops.Mlflow",
                        ),
                    ),
                ),
            ),
            connections=(
                DiagramConnection(
                    from_node="raw", to_node="train", label="feeds"
                ),
                DiagramConnection(from_node="train", to_node="train"),
            ),
            graph_attr={"pad": "0.4"},
            node_attr={"fontsize": "14"},
        )

        # Act
        output = MingrammerDiagramRenderer().render(
            definition, output_directory=str(output_dir)
        )

        # Assert
        target = output_dir / "pipeline"
        assert output == f"{target}.png"
        assert output_dir.is_dir()
        assert fake_diagrams.diagram_calls == [
            {
                "name": "Pipeline",
                "filename": str(target),
                "direction": "LR",
                "show": False,
                "outformat": "png",
                "graph_attr": {"pad": "0.4"},
                "node_attr": {"fontsize": "14"},
            }
        ]
        assert fake_diagrams.cluster_calls == [
            ("Data Processing", {"margin": "20", "fontsize": "13"})
        ]
        assert fake_diagrams.node_labels == ["Train Model", "Raw Data"]
        assert fake_diagrams.edges == [
            ("Raw Data", "feeds", "Train Model"),
            ("Train Model", None, "Train Model"),
        ]


class TestMingrammerDiagramRendererNodeResolution:
    def test_should_resolve_correct_node_class_dynamically(
        self, fake_diagrams: RenderRecorder
    ) -> None:
        # Arrange
        renderer = MingrammerDiagramRenderer()

        # Act
        resolved_class = renderer._resolve_node_class("onprem.mlops.Mlflow")

        # Assert
        assert resolved_class is FakeNode

    def test_should_resolve_two_part_custom_node_type(
        self, fake_diagrams: RenderRecorder
    ) -> None:
        # Arrange — `custom.ClassName` is a legal 2-part type (audit P7):
        # module `diagrams.custom`, class `Custom`.
        renderer = MingrammerDiagramRenderer()

        # Act
        resolved_class = renderer._resolve_node_class("custom.Custom")

        # Assert
        assert resolved_class is FakeNode

    def test_should_raise_value_error_when_node_type_has_no_module_path(
        self, fake_diagrams: RenderRecorder, tmp_path: Path
    ) -> None:
        # Arrange
        renderer = MingrammerDiagramRenderer()
        definition = DiagramDefinition(
            name="Test",
            filename="test",
            direction="LR",
            nodes=(
                DiagramNode(identifier="a", label="A", node_type="Mlflow"),
            ),
            clusters=(),
            connections=(),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid node type 'Mlflow'"):
            renderer.render(definition, output_directory=str(tmp_path))

    def test_should_raise_value_error_when_node_module_not_found(
        self, fake_diagrams: RenderRecorder, tmp_path: Path
    ) -> None:
        # Arrange
        renderer = MingrammerDiagramRenderer()
        definition = DiagramDefinition(
            name="Test",
            filename="test",
            direction="LR",
            nodes=(
                DiagramNode(
                    identifier="a", label="A", node_type="aws.compute.EC2"
                ),
            ),
            clusters=(),
            connections=(),
        )

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Could not import module 'diagrams.aws.compute'",
        ):
            renderer.render(definition, output_directory=str(tmp_path))

    def test_should_raise_value_error_when_node_class_missing_in_module(
        self, fake_diagrams: RenderRecorder, tmp_path: Path
    ) -> None:
        # Arrange
        renderer = MingrammerDiagramRenderer()
        definition = DiagramDefinition(
            name="Test",
            filename="test",
            direction="LR",
            nodes=(
                DiagramNode(
                    identifier="a", label="A", node_type="onprem.mlops.S3"
                ),
            ),
            clusters=(),
            connections=(),
        )

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Class 'S3' not found in module 'diagrams.onprem.mlops'",
        ):
            renderer.render(definition, output_directory=str(tmp_path))


class TestMingrammerDiagramRendererClusterMargin:
    def test_should_pass_margin_graph_attr_to_cluster_constructor(
        self, fake_diagrams: RenderRecorder
    ) -> None:
        # Cluster boxes must have inner padding so long labels (e.g.
        # "Pre-process Data & Engineer Features") do not touch the border.
        # The renderer must forward graph_attr={"margin": "20"} to Cluster().

        renderer = MingrammerDiagramRenderer()
        definition = DiagramDefinition(
            name="Test",
            filename="test",
            direction="LR",
            nodes=(),
            clusters=(
                DiagramCluster(
                    name="Data Processing",
                    nodes=(
                        DiagramNode(
                            identifier="n1",
                            label="Pre-process Data & Engineer Features",
                            node_type="onprem.mlops.Mlflow",
                        ),
                    ),
                ),
            ),
            connections=(),
        )

        renderer._instantiate_clusters(
            definition=definition,
            instances={},
            cluster_class=FakeCluster,
        )

        # The cluster must be constructed with margin and larger fontsize in graph_attr
        assert fake_diagrams.cluster_calls == [
            ("Data Processing", {"margin": "20", "fontsize": "13"})
        ]
