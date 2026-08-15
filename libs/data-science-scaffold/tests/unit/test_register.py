from pathlib import Path

import pytest
from data_science_scaffold.register import register_project


def test_register_project_adds_slug_to_all_lists(tmp_path: Path) -> None:
    # Arrange
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(_sample_pyproject(), encoding="utf-8")

    # Act
    changed = register_project("dummy_test_proj", pyproject_path)

    # Assert
    assert changed is True
    updated = pyproject_path.read_text(encoding="utf-8")
    assert '  "projects/dummy_test_proj",\n' in updated
    assert '  "dummy_test_proj",\n' in updated
    assert updated.count('  "dummy_test_proj",\n') == 2
    assert (
        '"dummy_test_proj"'
        in updated.split(
            'name = "Shared libraries do not import projects"', 1
        )[1].split("\n\n", 1)[0]
    )


def test_register_project_is_idempotent(tmp_path: Path) -> None:
    # Arrange
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(_sample_pyproject(), encoding="utf-8")
    register_project("dummy_test_proj", pyproject_path)
    text_after_first_run = pyproject_path.read_text(encoding="utf-8")

    # Act
    changed = register_project("dummy_test_proj", pyproject_path)

    # Assert
    assert changed is False
    assert pyproject_path.read_text(encoding="utf-8") == text_after_first_run


def test_register_project_leaves_unrelated_contracts_untouched(
    tmp_path: Path,
) -> None:
    # Arrange
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(_sample_pyproject(), encoding="utf-8")

    # Act
    register_project("dummy_test_proj", pyproject_path)

    # Assert
    updated = pyproject_path.read_text(encoding="utf-8")
    assert 'forbidden_modules = ["ssg.infrastructure"]\n' in updated


def test_register_project_rejects_invalid_slug(tmp_path: Path) -> None:
    # Arrange
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(_sample_pyproject(), encoding="utf-8")

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid project slug"):
        register_project("Invalid-Slug", pyproject_path)


def _sample_pyproject() -> str:
    return """[tool.uv.workspace]
members = [
  "libs/mlops-shared",
  "projects/nyc_taxi_demand_forecasting",
]

[tool.deptry]
known_first_party = [
  "mlops_shared",
  "nyc_taxi_demand_forecasting",
]

[tool.importlinter]
root_packages = [
  "mlops_shared",
  "nyc_taxi_demand_forecasting",
]

[[tool.importlinter.contracts]]
name = "Shared libraries do not import projects"
type = "forbidden"
source_modules = ["mlops_shared"]
forbidden_modules = ["nyc_taxi_demand_forecasting"]

[[tool.importlinter.contracts]]
name = "Videos library does not import projects"
type = "forbidden"
source_modules = ["videos"]
forbidden_modules = ["nyc_taxi_demand_forecasting"]

[[tool.importlinter.contracts]]
name = "Site domain stays independent"
type = "forbidden"
source_modules = ["ssg.domain"]
forbidden_modules = ["ssg.infrastructure"]
"""
