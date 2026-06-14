"""Value objects for the i18n domain."""

from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.locale_set import LocaleSet
from ssg_i18n.domain.value_objects.translation_catalog import (
    EMPTY_TRANSLATION_CATALOG,
    TranslationCatalog,
)

__all__ = [
    "Locale",
    "LocaleSet",
    "TranslationCatalog",
    "EMPTY_TRANSLATION_CATALOG",
]
