import re
from dataclasses import replace
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


def _fingerprint_sidecar(generated: Path) -> Path:
    return generated.with_name(generated.name + ".translate-fingerprint")


def test_variants_reuses_disk_cached_output_on_a_fresh_provider(
    tmp_path: Path,
) -> None:
    # Arrange — a fresh provider instance simulates a cold CI process: its
    # in-memory cache is empty, so reuse must come from the fingerprint
    # sidecar written beside each generated file.
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "First words.\n"), ("b", "Second words.\n")),
    )
    site = _make_site(collection)
    context = _make_context(tmp_path)
    first_translator = RecordingTextTranslator({})
    I18nSiteVariantProvider(first_translator).variants(site, context)
    generated = _generated_page(tmp_path, "coll0", "a")
    first_bytes = generated.read_bytes()
    second_translator = RecordingTextTranslator({})

    # Act
    I18nSiteVariantProvider(second_translator).variants(site, context)

    # Assert — chrome strings legitimately re-translate on a cold
    # provider; the page bodies must not.
    called_texts = {text for text, _ in second_translator.calls}
    assert "First words." not in called_texts
    assert "Second words." not in called_texts
    assert generated.read_bytes() == first_bytes


def test_variants_retranslates_on_fresh_provider_when_source_changed(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "Alpha words.\n"),),
    )
    site = _make_site(collection)
    context = _make_context(tmp_path)
    I18nSiteVariantProvider(RecordingTextTranslator({})).variants(
        site, context
    )
    _write(collection.source_root, "a", "Alpha words changed.\n")
    second_translator = RecordingTextTranslator({})

    # Act
    I18nSiteVariantProvider(second_translator).variants(site, context)

    # Assert — the stored fingerprint no longer matches the source bytes.
    called_texts = {text for text, _ in second_translator.calls}
    assert "Alpha words changed." in called_texts


def test_variants_retranslates_on_fresh_provider_when_sidecar_corrupt(
    tmp_path: Path,
) -> None:
    # Arrange — a torn or tampered fingerprint must rebuild, never serve
    # output whose provenance cannot be verified.
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "Alpha words.\n"),),
    )
    site = _make_site(collection)
    context = _make_context(tmp_path)
    I18nSiteVariantProvider(RecordingTextTranslator({})).variants(
        site, context
    )
    generated = _generated_page(tmp_path, "coll0", "a")
    _fingerprint_sidecar(generated).write_text("bogus\n", encoding="utf-8")
    second_translator = RecordingTextTranslator({})

    # Act
    I18nSiteVariantProvider(second_translator).variants(site, context)

    # Assert
    called_texts = {text for text, _ in second_translator.calls}
    assert "Alpha words." in called_texts


def test_variants_retranslates_on_fresh_provider_when_output_missing(
    tmp_path: Path,
) -> None:
    # Arrange — a surviving fingerprint without its output file still
    # triggers a fresh translation (partial-cache direction is rebuild).
    collection = _write_collection(
        tmp_path / "content",
        "coll0",
        (("a", "Alpha words.\n"),),
    )
    site = _make_site(collection)
    context = _make_context(tmp_path)
    I18nSiteVariantProvider(RecordingTextTranslator({})).variants(
        site, context
    )
    generated = _generated_page(tmp_path, "coll0", "a")
    generated.unlink()
    second_translator = RecordingTextTranslator({})

    # Act
    I18nSiteVariantProvider(second_translator).variants(site, context)

    # Assert
    called_texts = {text for text, _ in second_translator.calls}
    assert "Alpha words." in called_texts
    assert generated.exists()


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


def test_variants_shares_one_machine_translator_across_non_default_locales(
    tmp_path: Path,
) -> None:
    # Arrange — creating the machine translator can load a model, so one
    # instance must serve every non-default locale, not one per locale.
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    factory = RecordingTextTranslatorFactory(RecordingTextTranslator({}))
    provider = I18nSiteVariantProvider(
        InMemoryTextTranslator({}),
        machine_text_translator_factory=factory,
    )
    site = _make_site(
        collection,
        translation_mode="machine",
        i18n_settings={"locales": "en,pt-BR,es"},
    )

    # Act
    provider.variants(site, _make_context(tmp_path))

    # Assert
    assert factory.creates == 1


def test_variants_reuses_the_machine_translator_on_a_rebuild_with_changes(
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

    # Act — a changed source forces re-translation; the rebuild must not
    # pay a fresh create() (a real factory reloads the model).
    _write(collection.source_root, "a", "First words changed.\n")
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


def test_variants_translates_theme_select_labels(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    translator = RecordingTextTranslator(
        {
            "Theme": "Tema",
            "Auto": "Automático",
            "Light": "Claro",
            "Dark": "Escuro",
        }
    )
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    portuguese_i18n = variants[1].site.extensions["i18n"]
    assert portuguese_i18n["label_theme"] == "Tema"
    assert portuguese_i18n["label_theme_auto"] == "Automático"
    assert portuguese_i18n["label_theme_light"] == "Claro"
    assert portuguese_i18n["label_theme_dark"] == "Escuro"


def test_variants_translates_alert_labels(tmp_path: Path) -> None:
    # Arrange — admonition titles are generated by the renderer, so they
    # localize through i18n extension settings like the other UI chrome.
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    translator = RecordingTextTranslator(
        {
            "Note": "Nota",
            "Tip": "Dica",
            "Important": "Importante",
            "Warning": "Aviso",
            "Caution": "Cuidado",
        }
    )
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    portuguese_i18n = variants[1].site.extensions["i18n"]
    assert portuguese_i18n["label_alert_note"] == "Nota"
    assert portuguese_i18n["label_alert_tip"] == "Dica"
    assert portuguese_i18n["label_alert_important"] == "Importante"
    assert portuguese_i18n["label_alert_warning"] == "Aviso"
    assert portuguese_i18n["label_alert_caution"] == "Cuidado"


def test_variants_translates_search_labels(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    translator = RecordingTextTranslator(
        {
            "Search": "Busca",
            "Search pages": "Buscar páginas",
            "No results found": "Nenhum resultado encontrado",
        }
    )
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    portuguese_i18n = variants[1].site.extensions["i18n"]
    assert portuguese_i18n["label_search"] == "Busca"
    assert portuguese_i18n["label_search_placeholder"] == "Buscar páginas"
    assert (
        portuguese_i18n["label_search_no_results"]
        == "Nenhum resultado encontrado"
    )


def test_variants_translates_not_found_labels(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    translator = RecordingTextTranslator(
        {
            "Page not found": "Página não encontrada",
            "Back to home": "Voltar ao início",
        }
    )
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    portuguese_i18n = variants[1].site.extensions["i18n"]
    assert portuguese_i18n["label_not_found"] == "Página não encontrada"
    assert portuguese_i18n["label_home"] == "Voltar ao início"


def test_variants_translates_back_to_top_label(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    translator = RecordingTextTranslator({"Back to top": "Voltar ao topo"})
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    portuguese_i18n = variants[1].site.extensions["i18n"]
    assert portuguese_i18n["label_back_to_top"] == "Voltar ao topo"


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


def test_variants_preserves_site_urls_in_non_default_locale(
    tmp_path: Path,
) -> None:
    # Arrange — url/repo_url must survive localization or canonical, og:url,
    # and repo links would silently vanish from non-default-locale pages.
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = replace(
        _make_site(collection),
        url="https://example.com/docs",
        repo_url="https://github.com/example/repo",
    )

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    assert variants[0].site.url == "https://example.com/docs"
    assert variants[1].site.url == "https://example.com/docs"
    assert variants[1].site.repo_url == "https://github.com/example/repo"


def test_variants_preserves_edit_meta_settings_in_non_default_locale(
    tmp_path: Path,
) -> None:
    # Arrange — edit_base_url/last_updated must survive localization or the
    # meta row would silently vanish from non-default-locale pages.
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = replace(
        _make_site(collection),
        edit_base_url="https://github.com/example/repo/edit/main",
        last_updated=True,
    )

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    for variant in variants:
        assert variant.site.edit_base_url == (
            "https://github.com/example/repo/edit/main"
        )
        assert variant.site.last_updated is True


def test_variants_preserves_site_image_in_non_default_locale(
    tmp_path: Path,
) -> None:
    # Arrange — site.image is a shared build asset: every variant copies it
    # into its own assets/ so og:image resolves under each locale root.
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    image_path = tmp_path / "card.png"
    image_path.write_bytes(b"png bytes")
    site = replace(_make_site(collection), image=image_path)

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    for variant in variants:
        assert variant.site.image == image_path


def test_variants_localized_page_keeps_original_source_path(
    tmp_path: Path,
) -> None:
    # Arrange — the pt-BR page renders a generated intermediate under
    # .ssg/generated-i18n (gitignored); original_source_path keeps pointing
    # at the authored file so git history and edit links stay real.
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    provider = I18nSiteVariantProvider(RecordingTextTranslator({}))
    site = _make_site(collection)
    authored = collection.pages[0].source_path

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    localized_page = variants[1].site.collections[0].pages[0]
    assert localized_page.source_path != authored
    assert localized_page.original_source_path == authored


def test_variants_translates_page_meta_labels(tmp_path: Path) -> None:
    # Arrange
    collection = _write_collection(
        tmp_path / "content", "coll0", (("a", "First words.\n"),)
    )
    translator = RecordingTextTranslator(
        {
            "Edit page": "Editar página",
            "Last updated:": "Última atualização:",
        }
    )
    provider = I18nSiteVariantProvider(translator)
    site = _make_site(collection)

    # Act
    variants = provider.variants(site, _make_context(tmp_path))

    # Assert
    portuguese_i18n = variants[1].site.extensions["i18n"]
    assert portuguese_i18n["label_edit_page"] == "Editar página"
    assert portuguese_i18n["label_last_updated"] == "Última atualização:"
