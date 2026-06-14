from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from videos.infrastructure.cli import main


class TestCLI:
    @patch("videos.infrastructure.cli.Director")
    @patch("videos.infrastructure.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_calls_register_all_with_definitions_dir(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director: MagicMock,
        tmp_path: Path,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=Path("defs"),
        )

        # Act
        main()

        # Assert
        mock_register_all.assert_called_once_with(definitions_dir=Path("defs"))

    @patch("videos.infrastructure.cli.Director")
    @patch("videos.infrastructure.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_uses_default_definitions_dir(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=Path("videos/definition"),
            quality="preview",
        )

        # Act
        main()

        # Assert
        mock_register_all.assert_called_once_with(
            definitions_dir=Path("videos/definition")
        )

    @patch("videos.infrastructure.cli.Director")
    @patch("videos.infrastructure.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_passes_quality_to_director(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=Path("defs"),
            quality="final",
        )
        mock_director = mock_director_class.return_value

        # Act
        main()

        # Assert
        mock_director.produce.assert_called_once_with(quality="final")

    @patch("videos.infrastructure.cli.Director")
    @patch("videos.infrastructure.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_exits_on_error(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=Path("defs"),
        )
        mock_director = mock_director_class.return_value
        mock_director.produce.side_effect = Exception("Boom")

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1

    @patch("videos.infrastructure.cli.Director")
    @patch("videos.infrastructure.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_uses_advanced_linter_if_installed(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=Path("defs"),
            quality="preview",
        )

        mock_advanced_linter_service = MagicMock()
        mock_advanced_linter_class = MagicMock(
            return_value=mock_advanced_linter_service
        )

        # Patch import to succeed and return the mock advanced linter class
        mock_module = MagicMock()
        mock_module.LinterService = mock_advanced_linter_class

        with patch.dict(
            "sys.modules",
            {
                "videos_linter": mock_module,
                "videos_linter.linter_service": mock_module,
            },
        ):
            # Act
            main()

            # Assert
            called_linter = mock_director_class.call_args[1]["linter_service"]
            assert called_linter == mock_advanced_linter_service

    @patch("videos.infrastructure.cli.Director")
    @patch("videos.infrastructure.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_uses_local_linter_if_not_installed(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_director_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        # Arrange
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=Path("defs"),
            quality="preview",
        )

        # Act
        with patch.dict(
            "sys.modules",
            {"videos_linter": None, "videos_linter.linter_service": None},
        ):
            main()

        # Assert
        called_linter = mock_director_class.call_args[1]["linter_service"]
        from videos.infrastructure.validation.linter_service import (
            LinterService as LocalLinterService,
        )

        assert isinstance(called_linter, LocalLinterService)
