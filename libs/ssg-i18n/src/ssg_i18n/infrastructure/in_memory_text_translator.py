from dataclasses import dataclass

from ssg_i18n.domain.value_objects.locale import Locale


@dataclass(frozen=True)
class InMemoryTextTranslator:
    """In-memory TextTranslator — returns a fixed dict lookup or the source text.

    Example:
        translator = InMemoryTextTranslator({"Hello": "Olá"})
        translator.translate("Hello", Locale("pt-BR"))  # "Olá"
    """

    translations: dict[str, str]

    def translate(self, source_text: str, target_locale: Locale) -> str:
        return self.translations.get(source_text, source_text)
