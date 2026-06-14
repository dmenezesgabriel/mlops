import pytest
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.locale_set import LocaleSet


class TestLocaleSet:
    def test_valid_set_includes_default(self) -> None:
        default = Locale("en")
        locale_set = LocaleSet(
            default_locale=default,
            locales=(Locale("en"), Locale("pt-BR")),
        )
        assert locale_set.default_locale == default

    def test_raises_when_default_not_in_locales(self) -> None:
        with pytest.raises(ValueError, match="expected default locale"):
            LocaleSet(
                default_locale=Locale("fr"),
                locales=(Locale("en"), Locale("pt-BR")),
            )
