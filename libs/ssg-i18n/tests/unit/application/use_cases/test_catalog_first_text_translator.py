from ssg_i18n.application.use_cases.catalog_first_text_translator import (
    CatalogFirstTextTranslator,
)
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.translation_catalog import (
    TranslationCatalog,
)
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)


class TestCatalogFirstTextTranslator:
    def test_uses_catalog_translation_when_present(self) -> None:
        catalog = TranslationCatalog(
            translations={"Hello": "Olá"}, glossary_terms={}
        )
        translator = CatalogFirstTextTranslator(
            catalog=catalog,
            fallback_translator=InMemoryTextTranslator({}),
        )
        assert translator.translate("Hello", Locale("pt-BR")) == "Olá"

    def test_falls_back_to_delegate_when_missing(self) -> None:
        catalog = TranslationCatalog(translations={}, glossary_terms={})
        fallback = InMemoryTextTranslator({"World": "Mundo"})
        translator = CatalogFirstTextTranslator(
            catalog=catalog, fallback_translator=fallback
        )
        assert translator.translate("World", Locale("pt-BR")) == "Mundo"

    def test_returns_source_when_both_miss(self) -> None:
        catalog = TranslationCatalog(translations={}, glossary_terms={})
        translator = CatalogFirstTextTranslator(
            catalog=catalog,
            fallback_translator=InMemoryTextTranslator({}),
        )
        assert translator.translate("unknown", Locale("pt-BR")) == "unknown"
