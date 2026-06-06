from importlib.metadata import entry_points

from ssg.application.ports import SiteVariantProvider

from ssg_i18n.application.i18n_site_variant_provider import (
    I18nSiteVariantProvider,
    TextTranslatorFactory,
)
from ssg_i18n.application.translation import (
    InMemoryTextTranslator,
    TextTranslator,
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


class EntryPointTextTranslatorFactory(TextTranslatorFactory):
    def create(self) -> TextTranslator:
        translator_entry_points = tuple(
            entry_points(group="ssg_i18n.text_translators")
        )
        if not translator_entry_points:
            return InMemoryTextTranslator({})

        if len(translator_entry_points) == 1:
            loaded_translator = translator_entry_points[0].load()()
            if isinstance(loaded_translator, TextTranslator):
                return loaded_translator

            raise TypeError(
                f"Invalid i18n text translator {loaded_translator!r}: "
                "expected TextTranslator implementation",
            )

        translator_names = [
            entry_point.name for entry_point in translator_entry_points
        ]
        raise ValueError(
            f"Multiple i18n text translators {translator_names}: expected at most one translator",
        )
