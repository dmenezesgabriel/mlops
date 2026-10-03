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
    def glossary_terms(self) -> dict[str, str]: ...
