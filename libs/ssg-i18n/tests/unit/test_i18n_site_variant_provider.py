import json
from pathlib import Path

from ssg.domain.site import BuildContext, ContentCollection, Page, Site
from ssg_i18n.application.i18n_site_variant_provider import (
    I18nSiteVariantProvider,
)
from ssg_i18n.application.translation import InMemoryTextTranslator
from ssg_i18n.infrastructure.yaml_translation_catalog_repository import (
    YamlTranslationCatalogRepository,
)


def test_variants_create_localized_site_and_translated_sources(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    source_path = source_root / "README.md"
    source_path.write_text(
        "# Overview\n\nUse `MLflow` for tracking.\n", encoding="utf-8"
    )
    page = Page(slug="overview", title="Overview", source_path=source_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="Build machine learning systems.",
        collections=(collection,),
        extensions={
            "i18n": {
                "default_locale": "en",
                "locales": "en,pt-BR",
                "generated_path": ".ssg/generated-i18n",
            }
        },
    )
    translator = InMemoryTextTranslator(
        {
            "Learning Site": "Site de Aprendizado",
            "Build machine learning systems.": "Construa sistemas de machine learning.",
            "Sample Collection": "Colecao de Exemplo",
            "Overview": "Visao Geral",
            "Use {99900} for tracking.": ("Use {99900} para rastreamento."),
        }
    )
    context = BuildContext(
        config_path=tmp_path / "site" / "site.yaml",
        output_path=tmp_path / "build",
        collection_name=None,
        correlation_id="test-correlation",
    )

    # Act
    variants = I18nSiteVariantProvider(translator).variants(site, context)

    # Assert
    english_variant, portuguese_variant = variants
    translated_page = portuguese_variant.site.collections[0].pages[0]
    assert english_variant.output_path == tmp_path / "build"
    assert portuguese_variant.output_path == tmp_path / "build" / "pt-BR"
    assert portuguese_variant.site.title == "Site de Aprendizado"
    assert (
        portuguese_variant.site.description
        == "Construa sistemas de machine learning."
    )
    assert portuguese_variant.site.collections[0].title == "Colecao de Exemplo"
    assert translated_page.title == "Visao Geral"
    assert translated_page.source_path.read_text(encoding="utf-8") == (
        "# Visao Geral\n\nUse `MLflow` para rastreamento.\n"
    )


def test_variants_translate_notebook_markdown_cells_without_code_cells(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    notebook_path = source_root / "notebook.ipynb"
    notebook_path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": "# Feature Engineering\n\nRun `train_model()` after validation.",
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": "def train_model():\n    return 'ok'\n",
                    },
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )
    page = Page(slug="notebook", title="Notebook", source_path=notebook_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(collection,),
        extensions={"i18n": {"default_locale": "en", "locales": "en,pt-BR"}},
    )
    translator = InMemoryTextTranslator(
        {
            "Feature Engineering": "Engenharia de Features",
            "Run {99900} after validation.": (
                "Execute {99900} apos a validacao."
            ),
            "Learning Site": "Site de Aprendizado",
            "Notebook": "Caderno",
            "Sample Collection": "Colecao de Exemplo",
        }
    )
    context = BuildContext(
        tmp_path / "site.yaml", tmp_path / "build", None, "test"
    )

    # Act
    variants = I18nSiteVariantProvider(translator).variants(site, context)

    # Assert
    translated_path = variants[1].site.collections[0].pages[0].source_path
    translated_notebook = json.loads(
        translated_path.read_text(encoding="utf-8")
    )
    assert translated_notebook["cells"][0]["source"] == (
        "# Engenharia de Features\n\nExecute `train_model()` apos a validacao."
    )
    assert (
        translated_notebook["cells"][1]["source"]
        == "def train_model():\n    return 'ok'\n"
    )


def test_variants_fall_back_to_source_text_when_machine_translation_drops_code_marker(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    source_path = source_root / "README.md"
    source_path.write_text("Use `MLflow` for tracking.\n", encoding="utf-8")
    page = Page(slug="overview", title="Overview", source_path=source_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(collection,),
        extensions={"i18n": {"default_locale": "en", "locales": "en,pt-BR"}},
    )
    translator = InMemoryTextTranslator(
        {"Use {99900} for tracking.": "Traducao sem marcador"}
    )
    context = BuildContext(
        tmp_path / "site.yaml", tmp_path / "build", None, "test"
    )

    # Act
    variants = I18nSiteVariantProvider(translator).variants(site, context)

    # Assert
    translated_path = variants[1].site.collections[0].pages[0].source_path
    assert (
        translated_path.read_text(encoding="utf-8")
        == "Use `MLflow` for tracking.\n"
    )


def test_variants_translate_wikilink_labels_while_preserving_targets(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    source_path = source_root / "README.md"
    source_path.write_text("See [[overview|Overview]].\n", encoding="utf-8")
    page = Page(slug="overview", title="Overview", source_path=source_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(collection,),
        extensions={"i18n": {"default_locale": "en", "locales": "en,pt-BR"}},
    )
    translator = InMemoryTextTranslator(
        {
            "Overview": "Visao Geral",
            "See {99900}.": "Veja {99900}.",
        }
    )
    context = BuildContext(
        tmp_path / "site.yaml", tmp_path / "build", None, "test"
    )

    # Act
    variants = I18nSiteVariantProvider(translator).variants(site, context)

    # Assert
    translated_path = variants[1].site.collections[0].pages[0].source_path
    assert (
        translated_path.read_text(encoding="utf-8")
        == "Veja [[overview|Visao Geral]].\n"
    )


def test_variants_protects_entire_wikilink_from_machine_translation(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    source_path = source_root / "README.md"
    source_path.write_text("See [[overview|Overview]].\n", encoding="utf-8")
    page = Page(slug="overview", title="Overview", source_path=source_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(collection,),
        extensions={"i18n": {"default_locale": "en", "locales": "en,pt-BR"}},
    )
    # The translator is called with pre-translated label and main sentence mapping:
    translator = InMemoryTextTranslator(
        {
            "Overview": "Visão Geral",
            "See {99900}.": "Veja {99900}.",
        }
    )
    context = BuildContext(
        tmp_path / "site.yaml", tmp_path / "build", None, "test"
    )

    # Act
    variants = I18nSiteVariantProvider(translator).variants(site, context)

    # Assert
    translated_path = variants[1].site.collections[0].pages[0].source_path
    assert (
        translated_path.read_text(encoding="utf-8")
        == "Veja [[overview|Visão Geral]].\n"
    )


def test_variants_preserves_latex_expressions_in_machine_translation(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    source_path = source_root / "README.md"
    source_path.write_text(
        "Optimize over strength $\\alpha$ using $$\\alpha = 0.5$$.\n",
        encoding="utf-8",
    )
    page = Page(slug="overview", title="Overview", source_path=source_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(collection,),
        extensions={"i18n": {"default_locale": "en", "locales": "en,pt-BR"}},
    )
    # The translator expects the protected LaTeX markers:
    translator = InMemoryTextTranslator(
        {
            "Optimize over strength {99900} using {99901}.": (
                "Otimize sobre a forca {99900} usando {99901}."
            )
        }
    )
    context = BuildContext(
        tmp_path / "site.yaml", tmp_path / "build", None, "test"
    )

    # Act
    variants = I18nSiteVariantProvider(translator).variants(site, context)

    # Assert
    translated_path = variants[1].site.collections[0].pages[0].source_path
    assert (
        translated_path.read_text(encoding="utf-8")
        == "Otimize sobre a forca $\\alpha$ usando $$\\alpha = 0.5$$.\n"
    )


def test_variants_uses_catalog_glossary_to_protect_and_translate_technical_terms(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    source_path = source_root / "README.md"
    source_path.write_text(
        "We use Feast for features and a model registry for tracking.\n",
        encoding="utf-8",
    )
    page = Page(slug="overview", title="Overview", source_path=source_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(collection,),
        extensions={"i18n": {"default_locale": "en", "locales": "en,pt-BR"}},
    )

    # Write the YAML catalog containing the glossary terms
    i18n_dir = tmp_path / "i18n"
    i18n_dir.mkdir()
    (i18n_dir / "pt-BR.yaml").write_text(
        "glossary:\n  Feast: Feast\n  model registry: registro de modelos\n",
        encoding="utf-8",
    )

    # The fallback translator expects the protected markers:
    fallback_translator = InMemoryTextTranslator(
        {
            "We use {99901} for features and a {99900} for tracking.": (
                "Usamos {99901} para features e um {99900} para rastreamento."
            )
        }
    )
    context = BuildContext(
        tmp_path / "site.yaml", tmp_path / "build", None, "test"
    )

    # Act
    variants = I18nSiteVariantProvider(
        fallback_translator,
        catalog_repository=YamlTranslationCatalogRepository(),
        machine_text_translator_factory=None,
    ).variants(site, context)

    # Assert
    translated_path = variants[1].site.collections[0].pages[0].source_path
    assert (
        translated_path.read_text(encoding="utf-8")
        == "Usamos Feast para features e um registro de modelos para rastreamento.\n"
    )


def test_variants_restores_mutated_markers_from_machine_translation(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    source_path = source_root / "README.md"
    source_path.write_text(
        "Optimize over strength $\\alpha$ using $$\\alpha = 0.5$$.\n",
        encoding="utf-8",
    )
    page = Page(slug="overview", title="Overview", source_path=source_path)
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(page,),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(collection,),
        extensions={"i18n": {"default_locale": "en", "locales": "en,pt-BR"}},
    )
    # The translator returns the markers with mutated casing, spacing, and missing braces:
    translator = InMemoryTextTranslator(
        {
            "Optimize over strength {99900} using {99901}.": (
                "Otimize sobre a forca 99900 usando { 99901 }."
            )
        }
    )
    context = BuildContext(
        tmp_path / "site.yaml", tmp_path / "build", None, "test"
    )

    # Act
    variants = I18nSiteVariantProvider(translator).variants(site, context)

    # Assert
    translated_path = variants[1].site.collections[0].pages[0].source_path
    assert (
        translated_path.read_text(encoding="utf-8")
        == "Otimize sobre a forca $\\alpha$ usando $$\\alpha = 0.5$$.\n"
    )
