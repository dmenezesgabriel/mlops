import pytest
from ssg_i18n.domain.value_objects.locale import Locale


class TestLocale:
    def test_valid_language_only_tag(self) -> None:
        locale = Locale("en")
        assert locale.tag == "en"

    def test_valid_language_region_tag(self) -> None:
        locale = Locale("pt-BR")
        assert locale.tag == "pt-BR"

    def test_normalizes_underscore_separator(self) -> None:
        locale = Locale("pt_BR")
        assert locale.tag == "pt-BR"

    def test_normalizes_lowercase_region(self) -> None:
        locale = Locale("pt-br")
        assert locale.tag == "pt-BR"

    def test_invalid_tag_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid locale"):
            Locale("not-valid-123")

    def test_is_default_true(self) -> None:
        locale = Locale("en")
        assert locale.is_default(Locale("en"))

    def test_is_default_false(self) -> None:
        locale = Locale("pt-BR")
        assert not locale.is_default(Locale("en"))
