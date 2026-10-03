from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class TranslationCatalog:
    translations: Mapping[str, str]
    glossary_terms: Mapping[str, str]

    def translation_for(self, source_text: str) -> str | None:
        return self.translations.get(source_text)


EMPTY_TRANSLATION_CATALOG = TranslationCatalog(
    translations=MappingProxyType({}), glossary_terms=MappingProxyType({})
)
