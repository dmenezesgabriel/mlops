# Backward-compatible re-exports — import from the canonical location instead.
from ssg_i18n.domain.value_objects.translation_catalog import (
    EMPTY_TRANSLATION_CATALOG,
    TranslationCatalog,
)

__all__ = ["TranslationCatalog", "EMPTY_TRANSLATION_CATALOG"]
