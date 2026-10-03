import re
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


class _GlossaryAwareStubTranslator:
    """Catalog-bearing translator fake that is not CatalogFirstTextTranslator."""

    def __init__(
        self, glossary_terms: dict[str, str], translations: dict[str, str]
    ) -> None:
        self._glossary_terms = glossary_terms
        self._translations = translations

    @property
    def glossary_terms(self) -> dict[str, str]:
        return self._glossary_terms

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return self._translations.get(source_text, source_text)


class TestDocumentTranslator:
    def test_translate_file_markdown(self, tmp_path: Path) -> None:
        source = tmp_path / "page.md"
        source.write_text("Hello world", encoding="utf-8")
        output = tmp_path / "out" / "page.md"

        translator = DocumentTranslator(
            text_translator=InMemoryTextTranslator(
                {"Hello world": "Olá mundo"}
            )
        )
        result = translator.translate_file(source, output, Locale("pt-BR"))

        assert result == output
        assert output.read_text(encoding="utf-8") == "Olá mundo"

    def test_translate_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        source = tmp_path / "doc.md"
        source.write_text("text", encoding="utf-8")
        output = tmp_path / "deep" / "nested" / "doc.md"

        DocumentTranslator(
            text_translator=InMemoryTextTranslator({})
        ).translate_file(source, output, Locale("pt-BR"))

        assert output.exists()

    def test_translate_markdown_source_empty_string(self) -> None:
        translator = DocumentTranslator(
            text_translator=InMemoryTextTranslator({})
        )
        result = translator.translate_markdown_source("", Locale("pt-BR"))
        assert result == ""

    def test_glossary_applies_to_any_catalog_aware_translator(self) -> None:
        # Any translator exposing glossary_terms gets glossary protection —
        # the contract is the port, not CatalogFirstTextTranslator.
        stub = _GlossaryAwareStubTranslator(
            glossary_terms={"Zebraterm": "Termozebra"},
            translations={"Use TR0 here.": "Use TR0 aqui."},
        )
        translator = DocumentTranslator(stub)
        result = translator.translate_markdown_source(
            "Use Zebraterm here.\n", Locale("pt-BR")
        )
        assert result == "Use Termozebra aqui.\n"

    def test_glossary_skipped_when_translator_not_catalog_aware(self) -> None:
        translator = DocumentTranslator(InMemoryTextTranslator({}))
        result = translator.translate_markdown_source(
            "Zebraterm the model.\n", Locale("pt-BR")
        )
        assert result == "Zebraterm the model.\n"

    def test_glossary_protects_longest_matching_term(self) -> None:
        catalog = TranslationCatalog(
            translations={},
            glossary_terms={
                "machine": "maquina",
                "machine learning": "aprendizado de maquina",
            },
        )
        fallback = InMemoryTextTranslator({"TR0 works.": "TR0 funciona."})
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, fallback)
        )
        result = translator.translate_markdown_source(
            "Machine learning works.\n", Locale("pt-BR")
        )
        assert result == "aprendizado de maquina funciona.\n"

    def test_glossary_pattern_compiles_once_per_translator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        terms = {f"glossterm{i}": f"GT{i}" for i in range(50)}
        catalog = TranslationCatalog(translations={}, glossary_terms=terms)
        glossary_compiles: list[str] = []
        real_compile = re.compile

        def recording_compile(
            pattern: object, flags: int = 0
        ) -> re.Pattern[str]:
            if "glossterm" in str(pattern):
                glossary_compiles.append(str(pattern))
            return real_compile(str(pattern), flags)  # type: ignore[call-overload]

        monkeypatch.setattr(re, "compile", recording_compile)
        translator = DocumentTranslator(
            CatalogFirstTextTranslator(catalog, InMemoryTextTranslator({}))
        )
        translator.translate_markdown_source(
            "glossterm1 and glossterm49.\n", Locale("pt-BR")
        )
        translator.translate_markdown_source(
            "glossterm2 and glossterm48.\n", Locale("pt-BR")
        )

        assert len(glossary_compiles) == 1

    def test_terminology_rules_do_not_leak_into_non_pt_br_output(
        self,
    ) -> None:
        # The pt-BR "Batch Noun -> Noun em Batch" rule must not fire for
        # other target locales.
        translator = DocumentTranslator(InMemoryTextTranslator({}))
        result = translator.translate_markdown_source(
            "Batch Skript laeuft.\n", Locale("de")
        )
        assert result == "Batch Skript laeuft.\n"
