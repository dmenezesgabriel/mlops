from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from videos.presentation.cli import main


class TestCLI:
    @patch("videos.presentation.cli.Director")
    @patch("videos.presentation.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_calls_register_all_with_definitions_dir(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director: MagicMock,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=Path("out"),
            definitions_dir=Path("defs"),
        )

        # Act
        main()

        # Assert
        mock_register_all.assert_called_once_with(definitions_dir=Path("defs"))

    @patch("videos.presentation.cli.Director")
    @patch("videos.presentation.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_uses_default_definitions_dir(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=Path("out"),
            definitions_dir=Path("videos/definition"),
            quality="preview",
        )

        # Act
        main()

        # Assert
        mock_register_all.assert_called_once_with(
            definitions_dir=Path("videos/definition")
        )

    @patch("videos.presentation.cli.Director")
    @patch("videos.presentation.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_passes_quality_to_director(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=Path("out"),
            definitions_dir=Path("defs"),
            quality="final",
        )
        mock_director = mock_director_class.return_value

        # Act
        main()

        # Assert
        mock_director.produce.assert_called_once_with(quality="final")

    @patch("videos.presentation.cli.Director")
    @patch("videos.presentation.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_exits_on_error(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=Path("out"),
            definitions_dir=Path("defs"),
        )
        mock_director = mock_director_class.return_value
        mock_director.produce.side_effect = Exception("Boom")

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1
