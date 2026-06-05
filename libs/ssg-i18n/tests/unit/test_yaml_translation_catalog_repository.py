from pathlib import Path

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
