from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationCatalog:
    translations: dict[str, str]
    glossary_terms: dict[str, str]

    def translation_for(self, source_text: str) -> str | None:
        return self.translations.get(source_text)


EMPTY_TRANSLATION_CATALOG = TranslationCatalog(
    translations={}, glossary_terms={}
)
