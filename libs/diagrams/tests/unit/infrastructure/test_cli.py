import sys
from pathlib import Path

import pytest
from diagrams_generation.infrastructure.cli import main
from tests.unit.infrastructure._diagrams_fakes import RenderRecorder

_DEFINITION_YAML = """name: "MLOps Lifecycle"
filename: "mlops_lifecycle"
direction: "LR"
nodes:
  - id: raw_data
    label: "Raw Data"
    type: "onprem.mlops.Mlflow"
"""


def _argv(
    definitions_dir: Path, output_dir: Path, diagram_id: str
) -> list[str]:
    return [
        "diagrams-cli",
        diagram_id,
        "--definitions-dir",
        str(definitions_dir),
        "--output-dir",
        str(output_dir),
    ]


class TestCLIOrchestration:
    def test_should_orchestrate_load_and_render(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        fake_diagrams: RenderRecorder,
    ) -> None:
        # Arrange — real definition file through the real loader into the
        # real renderer, with only the mingrammer boundary faked.
        definitions_dir = tmp_path / "defs"
        definitions_dir.mkdir()
        (definitions_dir / "my_diagram.yaml").write_text(_DEFINITION_YAML)
        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            _argv(definitions_dir, output_dir, "my_diagram"),
        )

        # Act
        main()

        # Assert
        assert fake_diagrams.diagram_calls[0]["name"] == "MLOps Lifecycle"
        assert fake_diagrams.diagram_calls[0]["filename"] == str(
            output_dir / "mlops_lifecycle"
        )
        assert fake_diagrams.node_labels == ["Raw Data"]

    def test_should_fall_back_to_yml_extension(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        fake_diagrams: RenderRecorder,
    ) -> None:
        # Arrange
        definitions_dir = tmp_path / "defs"
        definitions_dir.mkdir()
        (definitions_dir / "legacy.yml").write_text(_DEFINITION_YAML)
        monkeypatch.setattr(
            sys,
            "argv",
            _argv(definitions_dir, tmp_path / "out", "legacy"),
        )

        # Act
        main()

        # Assert
        assert fake_diagrams.diagram_calls[0]["filename"].endswith(
            "mlops_lifecycle"
        )

    def test_should_exit_with_error_when_yaml_file_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange
        monkeypatch.setattr(
            sys,
            "argv",
            _argv(tmp_path, tmp_path / "out", "nonexistent_diagram"),
        )

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        assert "Missing diagram definition" in capsys.readouterr().err

    def test_should_exit_with_error_when_definition_malformed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange
        definitions_dir = tmp_path / "defs"
        definitions_dir.mkdir()
        (definitions_dir / "bad.yaml").write_text(
            'name: "n"\nfilename: "f"\nnodes: 42\n'
        )
        monkeypatch.setattr(
            sys, "argv", _argv(definitions_dir, tmp_path / "out", "bad")
        )

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        assert "expected list" in capsys.readouterr().err
