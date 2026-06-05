from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ssg_i18n.domain.locale import Locale
from ssg_i18n.domain.translation_catalog import TranslationCatalog


@runtime_checkable
class TextTranslator(Protocol):
    def translate(self, source_text: str, target_locale: Locale) -> str:
        pass


@dataclass(frozen=True)
class InMemoryTextTranslator(TextTranslator):
    translations: dict[str, str]

    def translate(self, source_text: str, _target_locale: Locale) -> str:
        return self.translations.get(source_text, source_text)


@dataclass(frozen=True)
class CatalogFirstTextTranslator(TextTranslator):
    catalog: TranslationCatalog
    fallback_translator: TextTranslator

    def translate(self, source_text: str, target_locale: Locale) -> str:
        manual_translation = self.catalog.translation_for(source_text)
        if manual_translation is not None:
            return manual_translation

        return self.fallback_translator.translate(source_text, target_locale)
