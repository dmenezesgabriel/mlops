from ssg_i18n.application.ports.text_translator import (
    CatalogAwareTextTranslator,
    TextTranslator,
)
from ssg_i18n.application.use_cases.catalog_first_text_translator import (
    CatalogFirstTextTranslator,
)
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.translation_catalog import (
    TranslationCatalog,
)


class _StubTranslator:
    """Minimal TextTranslator implementation used for protocol conformance check."""

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return source_text


class TestTextTranslatorProtocol:
    def test_stub_satisfies_protocol(self) -> None:
        # Runtime check that the protocol is satisfied structurally.
        assert isinstance(_StubTranslator(), TextTranslator)


class TestCatalogAwareTextTranslatorProtocol:
    def test_catalog_first_satisfies_sub_port(self) -> None:
        catalog = TranslationCatalog(translations={}, glossary_terms={})
        translator = CatalogFirstTextTranslator(catalog, _StubTranslator())
        assert isinstance(translator, CatalogAwareTextTranslator)

    def test_plain_translator_is_not_catalog_aware(self) -> None:
        assert not isinstance(_StubTranslator(), CatalogAwareTextTranslator)
