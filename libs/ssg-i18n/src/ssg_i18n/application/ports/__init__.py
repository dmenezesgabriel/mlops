"""Application ports for the i18n plugin."""

from ssg_i18n.application.ports.text_translator import (
    CatalogAwareTextTranslator,
    TextTranslator,
)

__all__ = ["CatalogAwareTextTranslator", "TextTranslator"]
