from unittest.mock import MagicMock, patch

import pytest
from diagrams_generation.adapters.mingrammer_renderer import (
    MingrammerDiagramRenderer,
)
from diagrams_generation.domain.diagram import (
    DiagramCluster,
    DiagramDefinition,
    DiagramNode,
)


class TestMingrammerDiagramRendererDependencyCheck:
    def test_should_raise_import_error_when_diagrams_library_missing(
        self,
    ) -> None:
        # Arrange
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
        with patch(
            "importlib.import_module",
            side_effect=ImportError("mocked diagrams library missing"),
        ):
            with pytest.raises(ImportError) as exc_info:
                renderer.render(
                    definition,
                    output_directory="/tmp",
                )
            assert "The 'diagrams' package is not installed" in str(
                exc_info.value
            )


class TestMingrammerDiagramRendererNodeResolution:
    @patch("importlib.import_module")
    def test_should_resolve_correct_node_class_dynamically(
        self, mock_import_module: MagicMock
    ) -> None:
        # Arrange
        mock_module = MagicMock()
        mock_class = MagicMock()
        mock_module.Mlflow = mock_class
        mock_import_module.return_value = mock_module
        renderer = MingrammerDiagramRenderer()

        # Act
        resolved_class = renderer._resolve_node_class("onprem.mlops.Mlflow")

        # Assert
        assert resolved_class == mock_class
        mock_import_module.assert_called_once_with("diagrams.onprem.mlops")


class TestMingrammerDiagramRendererClusterMargin:
    @patch("importlib.import_module")
    def test_should_pass_margin_graph_attr_to_cluster_constructor(
        self, mock_import_module: MagicMock
    ) -> None:
        # Cluster boxes must have inner padding so long labels (e.g.
        # "Pre-process Data & Engineer Features") do not touch the border.
        # The renderer must forward graph_attr={"margin": "20"} to Cluster().

        mock_node_module = MagicMock()
        mock_node_module.Action = MagicMock()
        mock_import_module.return_value = mock_node_module

        mock_cluster_class = MagicMock()
        mock_cluster_class.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        mock_cluster_class.return_value.__exit__ = MagicMock(
            return_value=False
        )

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
                            node_type="programming.flowchart.Action",
                        ),
                    ),
                ),
            ),
            connections=(),
        )

        renderer._instantiate_clusters(
            definition=definition,
            instances={},
            cluster_class=mock_cluster_class,
        )

        # The cluster must be constructed with margin and larger fontsize in graph_attr
        mock_cluster_class.assert_called_once_with(
            "Data Processing",
            graph_attr={"margin": "20", "fontsize": "13"},
        )
