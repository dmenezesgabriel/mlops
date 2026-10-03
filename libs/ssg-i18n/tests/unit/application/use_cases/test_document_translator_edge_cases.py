from pathlib import Path

import pytest
from ssg_i18n.application.use_cases.catalog_first_text_translator import (
    CatalogFirstTextTranslator,
)
from ssg_i18n.application.use_cases.document_translator import (
    DocumentTranslator,
)
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.translation_catalog import (
    TranslationCatalog,
)
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)

PT_BR = Locale("pt-BR")


def _fixed_marker_token() -> str:
    return "0123456789abcdef"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("- a\n- b", "- a\n- b", id="tight"),
        pytest.param("- a\n\n- b", "- a\n\n- b", id="loose"),
        pytest.param(
            "x\n\n- a\n- b\n\ny",
            "x\n\n- a\n- b\n\ny",
            id="tight-between-paragraphs",
        ),
    ],
)
def test_list_looseness_is_preserved(source: str, expected: str) -> None:
    translator = DocumentTranslator(
        InMemoryTextTranslator({}),
        marker_token_factory=_fixed_marker_token,
    )

    assert translator.translate_markdown_source(source, PT_BR) == expected


def test_glossary_skips_empty_terms() -> None:
    # An empty alternative in the combined pattern would match at every
    # word boundary — the `if not term` guard keeps it out.
    catalog = TranslationCatalog(
        translations={}, glossary_terms={"": "x", "real": "traduzido"}
    )
    translator = DocumentTranslator(
        CatalogFirstTextTranslator(catalog, InMemoryTextTranslator({})),
        marker_token_factory=_fixed_marker_token,
    )

    result = translator.translate_markdown_source("a real word", PT_BR)

    assert result == "a traduzido word"


def test_glossary_leaves_exotic_case_fold_match_verbatim() -> None:
    # "ſ" (U+017F) case-folds to "s" under IGNORECASE so the pattern
    # matches it, but "ſ".lower() stays "ſ" — no replacement exists, so
    # the word passes through verbatim instead of being marked.
    catalog = TranslationCatalog(translations={}, glossary_terms={"s": "x"})
    translator = DocumentTranslator(
        CatalogFirstTextTranslator(catalog, InMemoryTextTranslator({})),
        marker_token_factory=_fixed_marker_token,
    )

    result = translator.translate_markdown_source("a ſ b", PT_BR)

    assert result == "a ſ b"


def test_translate_file_rejects_non_list_notebook_cells(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "page.ipynb"
    notebook.write_text('{"cells": "not-a-list"}', encoding="utf-8")
    translator = DocumentTranslator(InMemoryTextTranslator({}))

    with pytest.raises(ValueError, match="expected cells list"):
        translator.translate_file(
            notebook, tmp_path / "out" / "page.ipynb", PT_BR
        )


def test_catalog_lookup_renders_line_break_in_source_keys() -> None:
    # Catalog keys are the authored source text: a soft break must reach
    # the lookup as "\n" for a multi-line catalog key to hit.
    catalog = TranslationCatalog(
        translations={"a\nb": "catalog hit"}, glossary_terms={}
    )
    translator = DocumentTranslator(
        CatalogFirstTextTranslator(catalog, InMemoryTextTranslator({})),
        marker_token_factory=_fixed_marker_token,
    )

    result = translator.translate_markdown_source("a\nb", PT_BR)

    assert result == "catalog hit"
