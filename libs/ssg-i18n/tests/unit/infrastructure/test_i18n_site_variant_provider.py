from pathlib import Path

from ssg.domain import BuildContext, ContentCollection, Page, Site
from ssg_i18n.application.ports.text_translator import TextTranslator
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.infrastructure.i18n_site_variant_provider import (
    I18nSiteVariantProvider,
)
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)
from ssg_i18n.infrastructure.yaml_translation_catalog_repository import (
    YamlTranslationCatalogRepository,
)


class RecordingTextTranslator:
    """TextTranslator fake recording every call's (source_text, locale.tag)."""

    def __init__(self, translations: dict[str, str]) -> None:
        self._delegate = InMemoryTextTranslator(translations)
        self.calls: list[tuple[str, str]] = []

    def translate(self, source_text: str, target_locale: Locale) -> str:
        self.calls.append((source_text, target_locale.tag))
        return self._delegate.translate(source_text, target_locale)


class RecordingTextTranslatorFactory:
    """Factory fake counting how often the machine translator is built."""

    def __init__(self, translator: TextTranslator) -> None:
        self._translator = translator
        self.creates = 0

    def create(self) -> TextTranslator:
        self.creates += 1
        return self._translator


def _write_collection(
    content_root: Path, name: str, page_specs: tuple[tuple[str, str], ...]
) -> ContentCollection:
    source_root = content_root / name
    source_root.mkdir(parents=True)
    pages = tuple(
        Page(
            slug=slug, title=slug, source_path=_write(source_root, slug, text)
        )
        for slug, text in page_specs
    )
    return ContentCollection(
        name=name,
        title=f"{name} title",
        source_root=source_root,
        output_slug=name,
        pages=pages,
        videos={},
    )


def _write(source_root: Path, slug: str, text: str) -> Path:
    source_path = source_root / f"{slug}.md"
    source_path.write_text(text, encoding="utf-8")
    return source_path


def _make_site(
    *collections: ContentCollection,
    translation_mode: str = "manual",
) -> Site:
    return Site(
        title="Learning Site",
        description="",
        collections=collections,
        extensions={
            "i18n": {
                "default_locale": "en",
                "locales": "en,pt-BR",
                "translation_mode": translation_mode,
            }
        },
    )


def _make_context(
    tmp_path: Path, collection_name: str | None = None
) -> BuildContext:
    return BuildContext(
        config_path=tmp_path / "site" / "site.yaml",
        output_path=tmp_path / "build",
        collection_name=collection_name,
        correlation_id="test-correlation",
    )


def _generated_page(tmp_path: Path, collection_name: str, slug: str) -> Path:
    return (
        tmp_path
        / "site"
        / ".ssg"
        / "generated-i18n"
        / "pt-BR"
        / collection_name
        / f"{slug}.md"
    )


def test_variants_scopes_localization_to_the_selected_collection(
    tmp_path: Path,
) -> None:
    # Arrange
    content_root = tmp_path / "content"
    coll0 = _write_collection(
        content_root, "coll0", (("a", "First words.\n"),)
    )
    coll1 = _write_collection(
        content_root, "coll1", (("b", "Other words.\n"),)
    )
    translator = RecordingTextTranslator({})
    context = _make_context(tmp_path, collection_name="coll0")

    # Act
    variants = I18nSiteVariantProvider(translator).variants(
        _make_site(coll0, coll1), context
    )

    # Assert
    portuguese_site = variants[1].site
    assert tuple(c.name for c in portuguese_site.collections) == ("coll0",)
    called_texts = {text for text, _ in translator.calls}
    assert "coll1 title" not in called_texts
    assert "Other words." not in called_texts
    assert not _generated_page(tmp_path, "coll1", "b").exists()


def test_variants_reuses_translated_output_on_an_unchanged_rebuild(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "First words.\n"), ("b", "Second words.\n")),
    )
    translator = RecordingTextTranslator({})
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)
    context = _make_context(tmp_path)
    provider.variants(site, context)
    generated = _generated_page(tmp_path, "coll0", "a")
    first_mtime = generated.stat().st_mtime_ns
    first_bytes = generated.read_bytes()
    first_call_count = len(translator.calls)

    # Act
    provider.variants(site, context)

    # Assert
    assert len(translator.calls) == first_call_count
    assert generated.stat().st_mtime_ns == first_mtime
    assert generated.read_bytes() == first_bytes


def test_variants_retranslates_only_the_changed_source(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "Alpha words.\n"), ("b", "Beta words.\n")),
    )
    translator = RecordingTextTranslator({})
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)
    context = _make_context(tmp_path)
    provider.variants(site, context)
    unchanged_generated = _generated_page(tmp_path, "coll0", "b")
    unchanged_mtime = unchanged_generated.stat().st_mtime_ns
    translator.calls.clear()

    # Act
    _write(collection.source_root, "a", "Alpha words changed.\n")
    provider.variants(site, context)

    # Assert
    called_texts = {text for text, _ in translator.calls}
    assert "Alpha words changed." in called_texts
    assert "Beta words." not in called_texts
    assert unchanged_generated.stat().st_mtime_ns == unchanged_mtime


def test_variants_does_not_recreate_the_translator_on_a_warm_rebuild(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    factory = RecordingTextTranslatorFactory(RecordingTextTranslator({}))
    provider = I18nSiteVariantProvider(
        InMemoryTextTranslator({}),
        machine_text_translator_factory=factory,
    )
    site = _make_site(collection, translation_mode="machine")
    context = _make_context(tmp_path)
    provider.variants(site, context)
    assert factory.creates == 1

    # Act
    provider.variants(site, context)

    # Assert
    assert factory.creates == 1


def test_variants_retranslates_when_the_catalog_changes(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    catalog_path = tmp_path / "site" / "i18n" / "pt-BR.yaml"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(
        "translations:\n"
        "  First words.: Primeiras palavras.\n"
        "  Learning Site: Sitio v1\n",
        encoding="utf-8",
    )
    provider = I18nSiteVariantProvider(
        RecordingTextTranslator({}),
        catalog_repository=YamlTranslationCatalogRepository(),
    )
    site = _make_site(collection)
    context = _make_context(tmp_path)
    first = provider.variants(site, context)
    generated = _generated_page(tmp_path, "coll0", "a")
    assert "Primeiras palavras." in generated.read_text(encoding="utf-8")
    assert first[1].site.title == "Sitio v1"

    # Act
    catalog_path.write_text(
        "translations:\n"
        "  First words.: Novas palavras.\n"
        "  Learning Site: Sitio v2\n",
        encoding="utf-8",
    )
    second = provider.variants(site, context)

    # Assert
    assert "Novas palavras." in generated.read_text(encoding="utf-8")
    assert second[1].site.title == "Sitio v2"


def test_variants_regenerates_a_deleted_output(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = _make_site(collection)
    context = _make_context(tmp_path)
    provider.variants(site, context)
    generated = _generated_page(tmp_path, "coll0", "a")
    generated.unlink()

    # Act
    provider.variants(site, context)

    # Assert
    assert generated.exists()
