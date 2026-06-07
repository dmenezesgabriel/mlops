from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from diagrams_generation.presentation.cli import main


class TestCLIOrchestration:
    @patch("diagrams_generation.presentation.cli.MingrammerDiagramRenderer")
    @patch("diagrams_generation.presentation.cli.load_from_file")
    @patch(
        "diagrams_generation.presentation.cli.Path.exists", return_value=True
    )
    @patch(
        "sys.argv",
        [
            "diagrams-cli",
            "my_diagram",
            "--definitions-dir",
            "/defs",
            "--output-dir",
            "/out",
        ],
    )
    def test_should_orchestrate_diagram_rendering(
        self,
        mock_exists: MagicMock,
        mock_load_from_file: MagicMock,
        mock_renderer_class: MagicMock,
    ) -> None:
        # Arrange
        mock_definition = MagicMock()
        mock_load_from_file.return_value = mock_definition
        mock_renderer = MagicMock()
        mock_renderer_class.return_value = mock_renderer

        # Act & Assert
        main()  # Should complete without raising any exception

        # Assert calls
        mock_load_from_file.assert_called_once_with(
            Path("/defs/my_diagram.yaml")
        )
        mock_renderer.render.assert_called_once_with(mock_definition, "/out")

    @patch(
        "sys.argv",
        [
            "diagrams-cli",
            "nonexistent_diagram",
            "--definitions-dir",
            "/defs",
            "--output-dir",
            "/out",
        ],
    )
    def test_should_exit_with_error_when_yaml_file_missing(self) -> None:
        # Arrange & Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
