import pytest
from ssg_i18n.domain.locale import Locale, LocaleSet


def test_locale_normalizes_underscore_region_tag() -> None:
    assert Locale("pt_BR").tag == "pt-BR"


def test_locale_set_requires_default_locale_in_supported_locales() -> None:
    with pytest.raises(ValueError, match="expected default locale fr"):
        LocaleSet(default_locale=Locale("fr"), locales=(Locale("en"), Locale("pt-BR")))
