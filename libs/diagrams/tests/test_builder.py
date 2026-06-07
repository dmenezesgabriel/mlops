from unittest.mock import MagicMock, patch

import pytest
from diagrams_generation.adapters.mingrammer_renderer import (
    MingrammerDiagramRenderer,
)
from diagrams_generation.domain.diagram import (
    DiagramDefinition,
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
