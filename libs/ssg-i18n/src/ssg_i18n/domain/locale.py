import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Locale:
    tag: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tag", self._normalized_tag(self.tag))
        if re.fullmatch(r"[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-[A-Z]{2})?", self.tag):
            return

        raise ValueError(
            f"Invalid locale {self.tag}: expected BCP-47 tag like en or pt-BR",
        )

    def _normalized_tag(self, locale_tag: str) -> str:
        parts = locale_tag.replace("_", "-").split("-")
        if len(parts) == 2:
            return f"{parts[0].lower()}-{parts[1].upper()}"

        return locale_tag

    def is_default(self, default_locale: "Locale") -> bool:
        return self.tag == default_locale.tag


@dataclass(frozen=True)
class LocaleSet:
    default_locale: Locale
    locales: tuple[Locale, ...]

    def __post_init__(self) -> None:
        if any(locale.tag == self.default_locale.tag for locale in self.locales):
            return

        configured_locales = ",".join(locale.tag for locale in self.locales)
        raise ValueError(
            f"Invalid i18n locales {configured_locales}: "
            f"expected default locale {self.default_locale.tag} to be included",
        )
