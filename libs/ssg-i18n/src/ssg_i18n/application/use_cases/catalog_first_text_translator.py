from dataclasses import dataclass

from ssg_i18n.application.ports.text_translator import TextTranslator
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.translation_catalog import (
    TranslationCatalog,
)


@dataclass(frozen=True)
class CatalogFirstTextTranslator:
    """Consults a manual catalog first; falls back to a delegate translator.

    Example:
        catalog = TranslationCatalog({"Hi": "Oi"}, {})
        translator = CatalogFirstTextTranslator(catalog, InMemoryTextTranslator({}))
        translator.translate("Hi", Locale("pt-BR"))  # "Oi"
    """

    catalog: TranslationCatalog
    fallback_translator: TextTranslator

    def translate(self, source_text: str, target_locale: Locale) -> str:
        manual_translation = self.catalog.translation_for(source_text)
        if manual_translation is not None:
            return manual_translation

        return self.fallback_translator.translate(source_text, target_locale)
