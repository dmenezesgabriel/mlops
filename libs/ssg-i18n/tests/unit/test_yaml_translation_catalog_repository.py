from pathlib import Path

import pytest
from ssg_i18n.infrastructure.yaml_translation_catalog_repository import (
    YamlTranslationCatalogRepository,
)


def test_load_reads_manual_translation_catalog(tmp_path: Path) -> None:
    # Arrange
    catalog_path = tmp_path / "i18n" / "pt-BR.yaml"
    catalog_path.parent.mkdir()
    catalog_path.write_text(
        "translations:\n"
        "  Learning Site: Site de Aprendizado\n"
        "  Feature store: feature store\n"
        "glossary:\n"
        "  MLflow: MLflow\n",
        encoding="utf-8",
    )

    # Act
    catalog = YamlTranslationCatalogRepository().load(catalog_path)

    # Assert
    assert catalog.translation_for("Learning Site") == "Site de Aprendizado"
    assert catalog.translation_for("Missing") is None
    assert catalog.glossary_terms == {"MLflow": "MLflow"}


@pytest.mark.parametrize("section", ["translations", "glossary"])
@pytest.mark.parametrize(
    "mapping",
    [
        pytest.param("{1: one, '1': uno}", id="int-key-collision"),
        pytest.param("{on: x}", id="yaml-1.1-bool-key"),
    ],
)
def test_load_rejects_non_string_keys(
    tmp_path: Path, section: str, mapping: str
) -> None:
    catalog_path = tmp_path / "pt-BR.yaml"
    catalog_path.write_text(f"{section}: {mapping}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected string key"):
        YamlTranslationCatalogRepository().load(catalog_path)


@pytest.mark.parametrize("section", ["translations", "glossary"])
@pytest.mark.parametrize(
    "mapping",
    [
        pytest.param("{deploy: [x]}", id="list-value"),
        pytest.param("{hello: 42}", id="int-value"),
    ],
)
def test_load_rejects_non_string_values(
    tmp_path: Path, section: str, mapping: str
) -> None:
    catalog_path = tmp_path / "pt-BR.yaml"
    catalog_path.write_text(f"{section}: {mapping}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected string value"):
        YamlTranslationCatalogRepository().load(catalog_path)
