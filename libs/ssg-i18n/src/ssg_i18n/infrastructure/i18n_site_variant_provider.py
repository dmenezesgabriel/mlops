import functools
import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol

from ssg.application.ports import SiteVariantProvider
from ssg.domain import (
    BuildContext,
    ContentCollection,
    Page,
    Site,
    SiteVariant,
)

from ssg_i18n.application.ports.text_translator import TextTranslator
from ssg_i18n.application.use_cases.catalog_first_text_translator import (
    CatalogFirstTextTranslator,
)
from ssg_i18n.application.use_cases.document_translator import (
    DocumentTranslator,
)
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.domain.value_objects.locale_set import LocaleSet
from ssg_i18n.domain.value_objects.translation_catalog import (
    EMPTY_TRANSLATION_CATALOG,
    TranslationCatalog,
)


class TranslationCatalogRepository(Protocol):
    def load(self, catalog_path: Path) -> TranslationCatalog: ...


class TextTranslatorFactory(Protocol):
    def create(self) -> TextTranslator: ...


def _catalog_fingerprint(catalog: TranslationCatalog) -> str:
    items = (
        *sorted(catalog.translations.items()),
        *sorted(catalog.glossary_terms.items()),
    )
    return hashlib.sha256(repr(items).encode("utf-8")).hexdigest()


_DEFAULT_MARKER_TOKEN_FACTORY = functools.partial(secrets.token_hex, 8)


@dataclass
class _TranslationSession:
    """One locale's state for a variants() call: a memoized string funnel and
    a lazily resolved translator, so a fully cached rebuild never pays the
    fallback factory (a machine model load) for work it will not do."""

    locale: Locale
    catalog_fingerprint: str
    string_cache: dict[str, str]
    resolver: Callable[[], TextTranslator]
    marker_token_factory: Callable[[], str]
    _translator: TextTranslator | None = field(default=None, init=False)
    _document_translator: DocumentTranslator | None = field(
        default=None, init=False
    )

    def translate(self, source_text: str) -> str:
        if not source_text:
            return source_text
        if source_text not in self.string_cache:
            self.string_cache[source_text] = self.translator().translate(
                source_text, self.locale
            )
        return self.string_cache[source_text]

    def translator(self) -> TextTranslator:
        if self._translator is None:
            self._translator = self.resolver()
        return self._translator

    def document_translator(self) -> DocumentTranslator:
        if self._document_translator is None:
            self._document_translator = DocumentTranslator(
                self.translator(),
                marker_token_factory=self.marker_token_factory,
            )
        return self._document_translator


class I18nSiteVariantProvider(SiteVariantProvider):
    """Concrete SiteVariantProvider that produces one site variant per locale.

    Example:
        provider = I18nSiteVariantProvider(InMemoryTextTranslator({}))
        provider.variants(site, context)
    """

    def __init__(
        self,
        text_translator: TextTranslator,
        catalog_repository: TranslationCatalogRepository | None = None,
        machine_text_translator_factory: TextTranslatorFactory | None = None,
        marker_token_factory: Callable[[], str] = (
            _DEFAULT_MARKER_TOKEN_FACTORY
        ),
    ) -> None:
        self._text_translator = text_translator
        self._catalog_repository = catalog_repository
        self._machine_text_translator_factory = machine_text_translator_factory
        self._marker_token_factory = marker_token_factory
        # Preview rebuilds re-call variants() on this same provider (cli.py
        # closes one builder over every on_change). The caches let unchanged
        # pages skip re-translation and keep generated-file mtimes stable,
        # so their rewrites stop retriggering the watcher on every rebuild.
        self._string_caches: dict[str, tuple[str, dict[str, str]]] = {}
        self._translated_files: dict[tuple[Path, str], tuple[str, str]] = {}

    def variants(
        self, site: Site, context: BuildContext
    ) -> tuple[SiteVariant, ...]:
        locale_set = self._locale_set(site)
        return tuple(
            self._variant_for(site, context, locale_set, locale)
            for locale in locale_set.locales
        )

    def _variant_for(
        self,
        site: Site,
        context: BuildContext,
        locale_set: LocaleSet,
        locale: Locale,
    ) -> SiteVariant:
        localized_site = self._localized_site(
            site, context, locale_set.default_locale, locale
        )
        output_path = context.output_path
        if not locale.is_default(locale_set.default_locale):
            output_path = output_path / locale.tag

        return SiteVariant(site=localized_site, output_path=output_path)

    def _localized_site(
        self,
        site: Site,
        context: BuildContext,
        default_locale: Locale,
        locale: Locale,
    ) -> Site:
        if locale.is_default(default_locale):
            return replace(
                site, locale=locale.tag, default_locale=default_locale.tag
            )

        session = self._translation_session(site, context, locale)
        return Site(
            title=session.translate(site.title),
            description=session.translate(site.description),
            collections=tuple(
                self._localized_collection(collection, site, context, session)
                for collection in site.selected_collections(
                    context.collection_name
                )
            ),
            locale=locale.tag,
            default_locale=default_locale.tag,
            extensions=self._localized_extensions(site, session),
        )

    def _translation_session(
        self, site: Site, context: BuildContext, locale: Locale
    ) -> _TranslationSession:
        catalog = self._translation_catalog(site, context, locale)
        catalog_fingerprint = _catalog_fingerprint(catalog)
        return _TranslationSession(
            locale=locale,
            catalog_fingerprint=catalog_fingerprint,
            string_cache=self._string_cache_for(
                locale.tag, catalog_fingerprint
            ),
            resolver=lambda: CatalogFirstTextTranslator(
                catalog, self._fallback_text_translator(site)
            ),
            marker_token_factory=self._marker_token_factory,
        )

    def _string_cache_for(
        self, locale_tag: str, catalog_fingerprint: str
    ) -> dict[str, str]:
        cached = self._string_caches.get(locale_tag)
        if cached is not None and cached[0] == catalog_fingerprint:
            return cached[1]
        cache: dict[str, str] = {}
        self._string_caches[locale_tag] = (catalog_fingerprint, cache)
        return cache

    def _localized_extensions(
        self, site: Site, session: _TranslationSession
    ) -> dict[str, dict[str, str]]:
        extensions = {
            name: dict(settings)
            for name, settings in (site.extensions or {}).items()
        }
        i18n_settings = dict(extensions.get("i18n", {}))
        for setting_name, source_text in self._ui_label_sources().items():
            if setting_name in i18n_settings:
                continue
            i18n_settings[setting_name] = session.translate(source_text)

        extensions["i18n"] = i18n_settings
        return extensions

    def _ui_label_sources(self) -> dict[str, str]:
        return {
            "label_language": "Language",
            "label_menu": "Menu",
            "label_field_index": "Field Index",
            "label_on_this_page": "On this page",
            "label_previous": "Previous",
            "label_next": "Next",
            "label_reports": "reports",
            "label_dispatches": "Dispatches",
            "label_projects": "Projects",
            "hero_eyebrow": "Editorial machine-learning atlas",
            "article_lede": "A field report for reproducible machine-learning systems.",
            "footer_text": "Generated by the content-first static site generator.",
        }

    def _localized_collection(
        self,
        collection: ContentCollection,
        site: Site,
        context: BuildContext,
        session: _TranslationSession,
    ) -> ContentCollection:
        return ContentCollection(
            name=collection.name,
            title=session.translate(collection.title),
            source_root=collection.source_root,
            output_slug=collection.output_slug,
            pages=tuple(
                self._localized_page(collection, site, page, context, session)
                for page in collection.pages
            ),
            videos=collection.videos,
            images=collection.images,
        )

    def _localized_page(
        self,
        collection: ContentCollection,
        site: Site,
        page: Page,
        context: BuildContext,
        session: _TranslationSession,
    ) -> Page:
        source_path = page.source_path
        if source_path.suffix in {".md", ".ipynb"}:
            source_path = self._translated_source_path(
                collection, site, page, context, session.locale
            )
            self._ensure_translated_file(
                page.source_path, source_path, session
            )

        return Page(
            slug=page.slug,
            title=session.translate(page.title),
            source_path=source_path,
        )

    def _ensure_translated_file(
        self,
        source_path: Path,
        output_path: Path,
        session: _TranslationSession,
    ) -> None:
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        cache_key = (source_path, session.locale.tag)
        fingerprint = (session.catalog_fingerprint, source_hash)
        if (
            self._translated_files.get(cache_key) == fingerprint
            and output_path.exists()
        ):
            return
        session.document_translator().translate_file(
            source_path, output_path, session.locale
        )
        self._translated_files[cache_key] = fingerprint

    def _translated_source_path(
        self,
        collection: ContentCollection,
        site: Site,
        page: Page,
        context: BuildContext,
        locale: Locale,
    ) -> Path:
        generated_root = self._generated_root(
            site, context, collection, locale
        )
        relative_source_path = page.source_path.relative_to(
            collection.source_root
        )
        return generated_root / relative_source_path

    def _generated_root(
        self,
        site: Site,
        context: BuildContext,
        collection: ContentCollection,
        locale: Locale,
    ) -> Path:
        configured_path = site.extension_setting(
            "i18n", "generated_path", ".ssg/generated-i18n"
        )
        return self._path_under_config_root(
            context.config_path,
            "generated_path",
            configured_path,
            locale.tag,
            collection.name,
        )

    def _path_under_config_root(
        self,
        config_path: Path,
        setting_name: str,
        configured_path: str,
        *parts: str,
    ) -> Path:
        config_root = config_path.parent.resolve()
        path = (config_root / configured_path).joinpath(*parts).resolve()
        if path.is_relative_to(config_root):
            return path

        raise ValueError(
            f"Invalid i18n {setting_name} {configured_path!r}: "
            f"expected a path under {config_root}"
        )

    def _locale_set(self, site: Site) -> LocaleSet:
        default_locale = Locale(
            site.extension_setting("i18n", "default_locale", "en")
        )
        locales = tuple(
            Locale(locale.strip())
            for locale in site.extension_setting(
                "i18n", "locales", default_locale.tag
            ).split(",")
            if locale.strip()
        )
        return LocaleSet(default_locale=default_locale, locales=locales)

    def _fallback_text_translator(self, site: Site) -> TextTranslator:
        translation_mode = site.extension_setting(
            "i18n", "translation_mode", "manual"
        )
        if translation_mode == "manual":
            return self._text_translator
        if translation_mode not in {
            "machine",
            "manual_with_machine_fallback",
        }:
            raise ValueError(
                f"Invalid i18n translation_mode {translation_mode!r}: "
                "expected one of manual, machine, "
                "manual_with_machine_fallback"
            )

        if self._machine_text_translator_factory is None:
            return self._text_translator

        return self._machine_text_translator_factory.create()

    def _translation_catalog(
        self, site: Site, context: BuildContext, target_locale: Locale
    ) -> TranslationCatalog:
        translations_path = site.extension_setting(
            "i18n", "translations_path", "i18n"
        )
        catalog_path = self._path_under_config_root(
            context.config_path,
            "translations_path",
            translations_path,
            f"{target_locale.tag}.yaml",
        )
        if catalog_path.exists() and self._catalog_repository is not None:
            return self._catalog_repository.load(catalog_path)

        return EMPTY_TRANSLATION_CATALOG
