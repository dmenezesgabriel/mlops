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
