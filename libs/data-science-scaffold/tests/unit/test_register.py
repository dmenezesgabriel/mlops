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


def test_register_project_fails_loudly_when_anchors_are_missing(
    tmp_path: Path,
) -> None:
    # Arrange — a drifted pyproject with no anchors must not report
    # "already registered"; it must raise and leave the file untouched.
    pyproject_path = tmp_path / "pyproject.toml"
    original = _sample_pyproject().replace(
        "nyc_taxi_demand_forecasting", "other_proj"
    )
    pyproject_path.write_text(original, encoding="utf-8")

    # Act & Assert
    with pytest.raises(RuntimeError, match="not found"):
        register_project("dummy_test_proj", pyproject_path)
    assert pyproject_path.read_text(encoding="utf-8") == original


def test_register_project_fails_loudly_on_partial_anchors(
    tmp_path: Path,
) -> None:
    # Arrange — only the members anchor survives; module anchors are gone.
    # The bare-module replace deliberately keeps "projects/nyc_taxi…" intact.
    pyproject_path = tmp_path / "pyproject.toml"
    original = _sample_pyproject().replace(
        '"nyc_taxi_demand_forecasting"', '"other_proj"'
    )
    pyproject_path.write_text(original, encoding="utf-8")

    # Act & Assert — partial anchors must not produce a partial write
    with pytest.raises(RuntimeError, match="not found"):
        register_project("dummy_test_proj", pyproject_path)
    assert pyproject_path.read_text(encoding="utf-8") == original


def test_register_project_fails_when_section_is_missing(
    tmp_path: Path,
) -> None:
    # Arrange — the whole [tool.deptry] table is gone, not just the anchor.
    pyproject_path = tmp_path / "pyproject.toml"
    original = _sample_pyproject().replace(
        '[tool.deptry]\nknown_first_party = [\n  "mlops_shared",\n'
        '  "nyc_taxi_demand_forecasting",\n]\n\n',
        "",
    )
    pyproject_path.write_text(original, encoding="utf-8")

    # Act & Assert
    with pytest.raises(RuntimeError, match="tool.deptry"):
        register_project("dummy_test_proj", pyproject_path)
    assert pyproject_path.read_text(encoding="utf-8") == original


def test_register_project_fails_when_list_is_missing(
    tmp_path: Path,
) -> None:
    # Arrange — the root_packages key vanished from [tool.importlinter].
    pyproject_path = tmp_path / "pyproject.toml"
    original = _sample_pyproject().replace(
        'root_packages = [\n  "mlops_shared",\n'
        '  "nyc_taxi_demand_forecasting",\n]\n',
        "",
    )
    pyproject_path.write_text(original, encoding="utf-8")

    # Act & Assert
    with pytest.raises(RuntimeError, match="root_packages"):
        register_project("dummy_test_proj", pyproject_path)
    assert pyproject_path.read_text(encoding="utf-8") == original


def test_register_project_skips_slug_present_off_anchor(
    tmp_path: Path,
) -> None:
    # Arrange — slug already in members, not adjacent to the anchor: a
    # post-anchor lookahead alone cannot see it, so the whole list is checked.
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        _sample_pyproject().replace(
            '  "projects/nyc_taxi_demand_forecasting",\n',
            '  "projects/dummy_test_proj",\n'
            '  "projects/nyc_taxi_demand_forecasting",\n',
        ),
        encoding="utf-8",
    )

    # Act
    changed = register_project("dummy_test_proj", pyproject_path)

    # Assert — no duplicate member; other lists still got the slug
    assert changed is True
    updated = pyproject_path.read_text(encoding="utf-8")
    assert updated.count('"projects/dummy_test_proj"') == 1
    assert '  "dummy_test_proj",\n' in updated


def test_register_project_extends_multiline_forbidden_contract(
    tmp_path: Path,
) -> None:
    # Arrange — a multi-line forbidden_modules whose items use a non-2-space
    # indent: neither the module-anchor literal nor the single-line contract
    # pattern may reach it, yet the contract must still gain the slug.
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        _sample_pyproject().replace(
            'forbidden_modules = ["nyc_taxi_demand_forecasting"]',
            "forbidden_modules = [\n"
            '        "nyc_taxi_demand_forecasting",\n'
            "    ]",
            1,
        ),
        encoding="utf-8",
    )

    # Act
    register_project("dummy_test_proj", pyproject_path)

    # Assert
    updated = pyproject_path.read_text(encoding="utf-8")
    assert '        "dummy_test_proj",\n' in updated


def test_register_project_never_touches_unrelated_lists(
    tmp_path: Path,
) -> None:
    # Arrange — a coverage-omit list carrying the module-anchor literal at
    # 2-space indent: the module sub must stay inside its own TOML sections.
    omit_block = (
        "\n[tool.coverage.report]\n"
        "omit = [\n"
        '  "nyc_taxi_demand_forecasting",\n'
        "]\n"
    )
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        _sample_pyproject() + omit_block, encoding="utf-8"
    )

    # Act
    register_project("dummy_test_proj", pyproject_path)

    # Assert
    assert omit_block in pyproject_path.read_text(encoding="utf-8")


def test_register_project_fails_when_no_contract_guards_projects(
    tmp_path: Path,
) -> None:
    # Arrange — no forbidden_modules lists the anchor, so no contract guards
    # project imports: registering silently would leave the slug unguarded.
    pyproject_path = tmp_path / "pyproject.toml"
    original = _sample_pyproject().replace(
        'forbidden_modules = ["nyc_taxi_demand_forecasting"]',
        'forbidden_modules = ["other_proj"]',
    )
    pyproject_path.write_text(original, encoding="utf-8")

    # Act & Assert
    with pytest.raises(RuntimeError, match="forbidden_modules"):
        register_project("dummy_test_proj", pyproject_path)
    assert pyproject_path.read_text(encoding="utf-8") == original


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
