from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)


class TestInMemoryTextTranslator:
    def test_returns_translation_when_present(self) -> None:
        translator = InMemoryTextTranslator({"Hello": "Olá"})
        assert translator.translate("Hello", Locale("pt-BR")) == "Olá"

    def test_returns_source_text_when_missing(self) -> None:
        translator = InMemoryTextTranslator({})
        assert translator.translate("fallback", Locale("pt-BR")) == "fallback"
