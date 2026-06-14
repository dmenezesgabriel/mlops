from typing import Protocol, runtime_checkable

from ssg_i18n.domain.value_objects.locale import Locale


@runtime_checkable
class TextTranslator(Protocol):
    def translate(self, source_text: str, target_locale: Locale) -> str: ...
