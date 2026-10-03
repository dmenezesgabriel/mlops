from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from ssg_i18n.domain.value_objects.locale import Locale


@runtime_checkable
class TextTranslator(Protocol):
    def translate(self, source_text: str, target_locale: Locale) -> str: ...


@runtime_checkable
class CatalogAwareTextTranslator(TextTranslator, Protocol):
    """TextTranslator whose backing catalog also fixes glossary terms.

    Translators carrying a glossary expose it here so glossary terms can be
    protected verbatim instead of sent through statistical translation.
    """

    @property
    def glossary_terms(self) -> Mapping[str, str]: ...

    def catalog_translation_for(self, source_text: str) -> str | None:
        """Return the curated translation for a source sentence, or None.

        Keys are the authored source text — the markdown sentence as it
        appears in the document, before protection markers are inserted.
        A miss returns None (callers then protect and machine-translate);
        the fallback translator is never consulted here.
        """
        ...
