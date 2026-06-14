# Backward-compatible re-exports — import from the canonical location instead.
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.locale_set import LocaleSet

__all__ = ["Locale", "LocaleSet"]
