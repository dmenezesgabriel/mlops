from pathlib import Path

import pytest
from mlops_shared.config import YamlMappingLoader


def test_load_yaml_mapping_reads_mapping(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "project.yaml"
    config_path.write_text("name: nyc_taxi\nversion: 1\n", encoding="utf-8")

    # Act
    config = YamlMappingLoader().load(config_path)

    # Assert
    assert config == {"name": "nyc_taxi", "version": 1}


def test_load_yaml_mapping_rejects_non_mapping(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "project.yaml"
    config_path.write_text("- invalid\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="expected YAML mapping"):
        YamlMappingLoader().load(config_path)


def test_load_yaml_mapping_rejects_non_string_keys(tmp_path: Path) -> None:
    # Arrange — int key 1 silently collides with string key "1" under str()
    config_path = tmp_path / "project.yaml"
    config_path.write_text('1: int\n"1": string\n', encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="expected string key") as exc_info:
        YamlMappingLoader().load(config_path)
    assert "1" in str(exc_info.value)
    assert str(config_path) in str(exc_info.value)


def test_load_yaml_mapping_rejects_yaml11_boolean_keys(
    tmp_path: Path,
) -> None:
    # Arrange — YAML-1.1 bool keys coerce to "True"/"False" under str()
    config_path = tmp_path / "project.yaml"
    config_path.write_text("on: value\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="expected string key") as exc_info:
        YamlMappingLoader().load(config_path)
    assert "True" in str(exc_info.value)
