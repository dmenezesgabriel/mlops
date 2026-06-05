import json
from pathlib import Path

import pytest
from ssg.application.static_site_builder import StaticSiteBuilder
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer
from ssg.infrastructure.markdown_content_renderer import MarkdownContentRenderer
from ssg.infrastructure.site_config_repository import SiteConfigRepository
from ssg_i18n.application.i18n_site_variant_provider import I18nSiteVariantProvider
from ssg_i18n.application.translation import InMemoryTextTranslator
from ssg_notebook_render.notebook_content_renderer import NotebookContentRenderer
from ssg_syntax_highlighting.presentation.plugin import create_pygments_html_post_processor


@pytest.mark.integration
def test_i18n_build_composes_with_content_and_html_extensions(tmp_path: Path) -> None:
    # Arrange
    config_path = _write_site_fixture(tmp_path)
    output_path = tmp_path / "site" / "build"
    translator = InMemoryTextTranslator(
        {
            "Learning Site": "Site de Aprendizado",
            "Sample Collection": "Colecao de Exemplo",
            "Overview": "Visao Geral",
            "Notebook": "Caderno",
            "Use {SSG_I18N_PROTECTED_0} for tracking.": (
                "Use {SSG_I18N_PROTECTED_0} para rastreamento."
            ),
            "Run {SSG_I18N_PROTECTED_0} after validation.": (
                "Execute {SSG_I18N_PROTECTED_0} apos a validacao."
            ),
        }
    )
    builder = StaticSiteBuilder(
        site_repository=SiteConfigRepository(),
        content_renderers=(MarkdownContentRenderer(), NotebookContentRenderer()),
        html_post_processors=(create_pygments_html_post_processor(),),
        page_renderer=JinjaPageRenderer(),
        site_variant_provider=I18nSiteVariantProvider(translator),
    )

    # Act
    builder.build(config_path, output_path)

    # Assert
    overview_html = (output_path / "pt-BR" / "sample-collection" / "overview.html").read_text(
        encoding="utf-8"
    )
    notebook_html = (output_path / "pt-BR" / "sample-collection" / "notebook.html").read_text(
        encoding="utf-8"
    )
    assert '<html lang="pt-BR">' in overview_html
    assert "Use <code>MLflow</code> para rastreamento." in overview_html
    assert "highlight-token" in overview_html
    assert "Execute <code>train_model()</code> apos a validacao." in notebook_html
    translated_notebook_path = (
        config_path.parent
        / ".ssg"
        / "generated-i18n"
        / "pt-BR"
        / "sample_collection"
        / "notebook.ipynb"
    )
    translated_notebook = json.loads(translated_notebook_path.read_text(encoding="utf-8"))
    assert translated_notebook["cells"][1]["source"] == "def train_model():\n    return 'ok'\n"


def _write_site_fixture(tmp_path: Path) -> Path:
    site_path = tmp_path / "site"
    content_path = tmp_path / "content" / "sample_collection"
    site_path.mkdir()
    content_path.mkdir(parents=True)
    _write_config(site_path)
    _write_markdown(content_path)
    _write_notebook(content_path)
    return site_path / "site.yaml"


def _write_config(site_path: Path) -> None:
    (site_path / "site.yaml").write_text(
        "site:\n"
        "  title: Learning Site\n"
        "extensions:\n"
        "  i18n:\n"
        "    default_locale: en\n"
        "    locales: en,pt-BR\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    output_slug: sample-collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "      - slug: notebook\n"
        "        title: Notebook\n"
        "        source: notebook.ipynb\n",
        encoding="utf-8",
    )


def _write_markdown(content_path: Path) -> None:
    (content_path / "README.md").write_text(
        "# Overview\n\nUse `MLflow` for tracking.\n\n"
        "```python\n"
        "def train_model():\n"
        "    return 'ok'\n"
        "```\n",
        encoding="utf-8",
    )


def _write_notebook(content_path: Path) -> None:
    (content_path / "notebook.ipynb").write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "id": "translated-markdown",
                        "metadata": {},
                        "source": "Run `train_model()` after validation.",
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "id": "preserved-code",
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
