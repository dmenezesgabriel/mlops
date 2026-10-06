from pathlib import Path

import pytest
from ml_specialization.configuration import ProjectConfigLoader


def test_project_config_loader_resolves_project_paths(
    tmp_path: Path, project_config_yaml: str
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(project_config_yaml, encoding="utf-8")

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert
    assert config.paths.raw_data == tmp_path / "data" / "raw"
    assert config.collection.taxi_type == "yellow"


def test_project_config_loader_anchors_relative_mlflow_uri_to_project_root(
    tmp_path: Path, project_config_yaml: str
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(project_config_yaml, encoding="utf-8")

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert
    assert config.mlflow.tracking_uri == f"sqlite:////{tmp_path / 'mlflow.db'}"


@pytest.mark.parametrize(
    ("config_edit", "match"),
    [
        pytest.param(
            ("months: [1]", "months: [1]\n  1: a\n  '1': b"),
            "expected string key",
            id="non_string_collection_keys",
        ),
        pytest.param(
            ("months: [1]", "months: [1]\n  on: x"),
            "expected string key",
            id="yaml_bool_collection_key",
        ),
        pytest.param(
            ("months: [1]", "months: [on, off]"),
            "expected integer list",
            id="bool_months",
        ),
        pytest.param(
            ("year: 2023", "year: yes"),
            "expected integer",
            id="bool_year",
        ),
        pytest.param(
            ("test_size: 0.2", "test_size: on"),
            "expected number",
            id="bool_test_size",
        ),
    ],
)
def test_project_config_loader_rejects_yaml_coerced_values(
    tmp_path: Path,
    project_config_yaml: str,
    config_edit: tuple[str, str],
    match: str,
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    old, new = config_edit
    config_path.write_text(
        project_config_yaml.replace(old, new), encoding="utf-8"
    )

    # Act / Assert
    with pytest.raises(ValueError, match=match):
        ProjectConfigLoader().load(config_path)


def test_project_config_loader_rejects_config_outside_configs_dir(
    tmp_path: Path, project_config_yaml: str
) -> None:
    # Arrange
    config_path = tmp_path / "project.yaml"
    config_path.write_text(project_config_yaml, encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="configs/"):
        ProjectConfigLoader().load(config_path)


def test_project_config_loader_passes_through_in_memory_sqlite_uri(
    tmp_path: Path, project_config_yaml: str
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        project_config_yaml.replace(
            "sqlite:///mlflow.db", '"sqlite:///:memory:"'
        ),
        encoding="utf-8",
    )

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert
    assert config.mlflow.tracking_uri == "sqlite:///:memory:"
