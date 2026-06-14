# Backward-compatible re-exports — import from canonical location instead.
from ssg_i18n.infrastructure.i18n_site_variant_provider import (
    I18nSiteVariantProvider,
    TextTranslatorFactory,
    TranslationCatalogRepository,
)

__all__ = [
    "I18nSiteVariantProvider",
    "TextTranslatorFactory",
    "TranslationCatalogRepository",
]
