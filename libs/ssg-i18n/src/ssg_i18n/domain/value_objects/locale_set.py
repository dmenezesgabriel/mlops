from dataclasses import dataclass

from ssg_i18n.domain.value_objects.locale import Locale


@dataclass(frozen=True)
class LocaleSet:
    default_locale: Locale
    locales: tuple[Locale, ...]

    def __post_init__(self) -> None:
        if any(
            locale.tag == self.default_locale.tag for locale in self.locales
        ):
            return

        configured_locales = ",".join(locale.tag for locale in self.locales)
        raise ValueError(
            f"Invalid i18n locales {configured_locales}: "
            f"expected default locale {self.default_locale.tag} to be included",
        )
