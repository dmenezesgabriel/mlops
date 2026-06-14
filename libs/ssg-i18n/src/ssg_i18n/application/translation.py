# Backward-compatible re-exports — import from canonical locations instead.
from ssg_i18n.application.ports.text_translator import TextTranslator
from ssg_i18n.application.use_cases.catalog_first_text_translator import (
    CatalogFirstTextTranslator,
)
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)

__all__ = [
    "TextTranslator",
    "InMemoryTextTranslator",
    "CatalogFirstTextTranslator",
]
