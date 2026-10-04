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
            definitions_dir=tmp_path,
        )

        # Act
        main()

        # Assert
        mock_register_all.assert_called_once_with(definitions_dir=tmp_path)

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
            definitions_dir=tmp_path,
            quality="preview",
        )

        # Act
        main()

        # Assert
        mock_register_all.assert_called_once_with(definitions_dir=tmp_path)

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
            definitions_dir=tmp_path,
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
            definitions_dir=tmp_path,
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
            definitions_dir=tmp_path,
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
            definitions_dir=tmp_path,
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

    @patch("videos.infrastructure.cli.Director")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_reports_missing_definitions_dir(
        self,
        mock_parse_args: MagicMock,
        mock_director_class: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — register_all stays unmocked: the check must fire first
        absent = tmp_path / "absent"
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=absent,
            quality="preview",
        )

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        assert "Definitions directory not found" in capsys.readouterr().err
        mock_director_class.assert_not_called()

    @patch("videos.infrastructure.cli.Director")
    @patch("argparse.ArgumentParser.parse_args")
    @pytest.mark.parametrize(
        "bad_yaml", ["concept: [unclosed", "- not\n- a\n- mapping\n"]
    )
    def test_main_exits_cleanly_on_bad_definition_file(
        self,
        mock_parse_args: MagicMock,
        mock_director_class: MagicMock,
        bad_yaml: str,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — real register_all against a dir holding a bad yaml;
        # the error must exit(1) with the file named, not traceback out
        defs = tmp_path / "defs"
        defs.mkdir()
        (defs / "bad.yaml").write_text(bad_yaml)
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=defs,
            quality="preview",
        )

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        assert "bad.yaml" in capsys.readouterr().err

    @patch("videos.infrastructure.cli.Director")
    @patch("videos.infrastructure.cli.register_default_components")
    @patch("videos.infrastructure.cli.register_all")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_exits_cleanly_on_wiring_failure(
        self,
        mock_parse_args: MagicMock,
        mock_register_all: MagicMock,
        mock_register_default_components: MagicMock,
        mock_director_class: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — a wiring failure (not just produce) must be caught
        mock_parse_args.return_value = MagicMock(
            concept_id="test",
            output_dir=tmp_path / "out",
            definitions_dir=tmp_path,
            quality="preview",
        )
        mock_register_default_components.side_effect = TypeError("Boom")

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        assert "Failed to produce video" in capsys.readouterr().err
