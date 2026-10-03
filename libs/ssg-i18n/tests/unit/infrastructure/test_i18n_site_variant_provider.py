import re
from pathlib import Path

import pytest
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
    i18n_settings: dict[str, str] | None = None,
) -> Site:
    settings = {
        "default_locale": "en",
        "locales": "en,pt-BR",
        "translation_mode": translation_mode,
    }
    settings.update(i18n_settings or {})
    return Site(
        title="Learning Site",
        description="",
        collections=collections,
        extensions={"i18n": settings},
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


def test_variants_compiles_the_glossary_pattern_once_per_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The glossary alternation is one compiled pattern per session,
    # not re.compile'd per term per page.
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "Use zebraterm here.\n"), ("b", "More zebraterm text.\n")),
    )
    catalog_path = tmp_path / "site" / "i18n" / "pt-BR.yaml"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(
        "glossary:\n  zebraterm: termo zebra\n", encoding="utf-8"
    )
    glossary_compiles: list[str] = []
    real_compile = re.compile

    def recording_compile(pattern: object, flags: int = 0) -> re.Pattern[str]:
        if "zebraterm" in str(pattern):
            glossary_compiles.append(str(pattern))
        return real_compile(str(pattern), flags)  # type: ignore[call-overload]

    monkeypatch.setattr(re, "compile", recording_compile)
    provider = I18nSiteVariantProvider(
        RecordingTextTranslator({}),
        catalog_repository=YamlTranslationCatalogRepository(),
    )
    provider.variants(_make_site(collection), _make_context(tmp_path))

    assert len(glossary_compiles) == 1


def test_variants_applies_yaml_catalog_to_span_bearing_source_sentences(
    tmp_path: Path,
) -> None:
    # Arrange — catalog keys are authored source sentences; inline-code
    # spans must not force authors to write generated marker text.
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "Use `MLflow` for tracking.\n"),),
    )
    catalog_path = tmp_path / "site" / "i18n" / "pt-BR.yaml"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(
        "translations:\n"
        '  "Use `MLflow` for tracking.": "Use MLflow para rastreamento."\n',
        encoding="utf-8",
    )
    provider = I18nSiteVariantProvider(
        RecordingTextTranslator({}),
        catalog_repository=YamlTranslationCatalogRepository(),
    )

    # Act
    provider.variants(_make_site(collection), _make_context(tmp_path))

    # Assert
    generated = _generated_page(tmp_path, "coll0", "a")
    assert (
        generated.read_text(encoding="utf-8")
        == "Use MLflow para rastreamento.\n"
    )


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


def test_variants_keeps_author_i18n_label_overrides(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    translator = RecordingTextTranslator({"Menu": "Menu-pt"})
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection, i18n_settings={"label_language": "Idioma!"})

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    portuguese_i18n = variants[1].site.extensions["i18n"]
    assert portuguese_i18n["label_language"] == "Idioma!"
    assert portuguese_i18n["label_menu"] == "Menu-pt"
    called_texts = {text for text, _ in translator.calls}
    assert "Language" not in called_texts


def test_variants_falls_back_to_injected_translator_in_machine_mode_without_factory(
    tmp_path: Path,
) -> None:
    # Arrange — `machine` mode with no entry-point factory degrades to the
    # provider's own translator instead of failing the build.
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "Hello world.\n"),)
    )
    manual = RecordingTextTranslator({"Hello world.": "Olá mundo."})
    provider = I18nSiteVariantProvider(manual)
    site = _make_site(collection, translation_mode="machine")

    # Act
    provider.variants(site, _make_context(tmp_path))

    # Assert
    assert ("Hello world.", "pt-BR") in manual.calls
    generated = _generated_page(tmp_path, "coll0", "a")
    assert "Olá mundo." in generated.read_text(encoding="utf-8")


def test_variants_rejects_unknown_translation_mode(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = _make_site(collection, translation_mode="machien")

    # Act / Assert
    with pytest.raises(ValueError, match="machien"):
        provider.variants(site, _make_context(tmp_path))


def test_variants_rejects_duplicate_locale_tags(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = _make_site(collection, i18n_settings={"locales": "en,en"})

    # Act / Assert
    with pytest.raises(ValueError, match="duplicate locale"):
        provider.variants(site, _make_context(tmp_path))


def test_variants_rejects_generated_path_outside_config_root(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = _make_site(
        collection, i18n_settings={"generated_path": "../escape-out"}
    )

    # Act / Assert
    with pytest.raises(ValueError, match="generated_path"):
        provider.variants(site, _make_context(tmp_path))
    assert not (tmp_path / "escape-out").exists()


def test_variants_rejects_translations_path_outside_config_root(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = _make_site(
        collection, i18n_settings={"translations_path": "../outside-catalogs"}
    )

    # Act / Assert
    with pytest.raises(ValueError, match="translations_path"):
        provider.variants(site, _make_context(tmp_path))
