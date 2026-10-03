from dataclasses import dataclass

from ssg_i18n.domain.value_objects.locale import Locale


@dataclass(frozen=True)
class LocaleSet:
    default_locale: Locale
    locales: tuple[Locale, ...]

    def __post_init__(self) -> None:
        configured_locales = ",".join(locale.tag for locale in self.locales)
        duplicate_tag = _first_duplicate_tag(self.locales)
        if duplicate_tag is not None:
            raise ValueError(
                f"Invalid i18n locales {configured_locales}: "
                f"duplicate locale {duplicate_tag!r}"
            )
        if any(
            locale.tag == self.default_locale.tag for locale in self.locales
        ):
            return

        raise ValueError(
            f"Invalid i18n locales {configured_locales}: "
            f"expected default locale {self.default_locale.tag} to be included",
        )


def _first_duplicate_tag(locales: tuple[Locale, ...]) -> str | None:
    seen: set[str] = set()
    for locale in locales:
        if locale.tag in seen:
            return locale.tag
        seen.add(locale.tag)
    return None
