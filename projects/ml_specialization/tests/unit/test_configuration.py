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
        pytest.param(
            (
                "collection:\n  year: 2023\n  months: [1]\n  taxi_type: yellow",
                "collection: 42",
            ),
            "expected mapping",
            id="non_mapping_collection",
        ),
        pytest.param(
            ("taxi_type: yellow", "taxi_type: 42"),
            "expected string",
            id="non_string_taxi_type",
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


@pytest.mark.parametrize(
    "tracking_uri",
    [
        pytest.param("sqlite:///:memory:", id="in_memory_sqlite"),
        pytest.param("https://tracking.example.com", id="non_sqlite"),
        pytest.param("sqlite:////var/data/mlflow.db", id="absolute_sqlite"),
        pytest.param("sqlite:///", id="empty_sqlite_path"),
    ],
)
def test_project_config_loader_passes_through_non_relative_tracking_uris(
    tmp_path: Path, project_config_yaml: str, tracking_uri: str
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        project_config_yaml.replace(
            "sqlite:///mlflow.db", f'"{tracking_uri}"'
        ),
        encoding="utf-8",
    )

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert — only relative sqlite paths are anchored to the project root.
    assert config.mlflow.tracking_uri == tracking_uri


def test_project_config_loader_accepts_integer_for_float_key(
    tmp_path: Path, project_config_yaml: str
) -> None:
    # Arrange — YAML `1` parses as int; the number contract accepts it.
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        project_config_yaml.replace("max_mae: 1.0", "max_mae: 1"),
        encoding="utf-8",
    )

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert
    assert config.evaluation.max_mae == 1.0
