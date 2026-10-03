from importlib.metadata import EntryPoint, entry_points

from ssg.application.ports import SiteVariantProvider

from ssg_i18n.application.ports.text_translator import TextTranslator
from ssg_i18n.infrastructure.i18n_site_variant_provider import (
    I18nSiteVariantProvider,
    TextTranslatorFactory,
)
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)
from ssg_i18n.infrastructure.yaml_translation_catalog_repository import (
    YamlTranslationCatalogRepository,
)


def create_i18n_site_variant_provider() -> SiteVariantProvider:
    return I18nSiteVariantProvider(
        InMemoryTextTranslator({}),
        YamlTranslationCatalogRepository(),
        EntryPointTextTranslatorFactory(),
    )


def _load_text_translator(entry_point: EntryPoint) -> TextTranslator:
    """Instantiate the ssg_i18n.text_translators entry point: name →
    zero-arg factory → port-conforming instance. Failures name the
    entry point and group."""
    try:
        translator = entry_point.load()()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load entry point {entry_point.name!r} "
            f"in group 'ssg_i18n.text_translators': {exc}"
        ) from exc
    if not isinstance(translator, TextTranslator):
        raise TypeError(
            f"Invalid ssg_i18n.text_translators plugin "
            f"{entry_point.name!r}: expected TextTranslator "
            f"implementation, got {type(translator).__name__}"
        )
    return translator


class EntryPointTextTranslatorFactory(TextTranslatorFactory):
    def create(self) -> TextTranslator:
        translator_entry_points = tuple(
            entry_points(group="ssg_i18n.text_translators")
        )
        if not translator_entry_points:
            return InMemoryTextTranslator({})

        if len(translator_entry_points) == 1:
            return _load_text_translator(translator_entry_points[0])

        translator_names = [
            entry_point.name for entry_point in translator_entry_points
        ]
        raise ValueError(
            f"Multiple i18n text translators {translator_names}: expected at most one translator",
        )
