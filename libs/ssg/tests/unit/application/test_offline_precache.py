from pathlib import Path

from ssg.application.offline_precache import precache_manifest
from ssg.domain import PrecacheManifest


def _emit(root: Path, relative: str, content: str = "content") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_precache_manifest_lists_emitted_tree_sorted_with_scope_root(
    tmp_path: Path,
) -> None:
    # Arrange — the worker's precache mirrors the deployed tree, so every
    # emitted file becomes a manifest URL and "./" covers the scope root.
    output = tmp_path / "out"
    _emit(output, "index.html")
    _emit(output, "search-index.json")
    _emit(output, "assets/site.css")
    _emit(output, "sample-collection/overview.html")

    # Act
    manifest = precache_manifest(output, ())

    # Assert
    assert manifest.urls == (
        "./",
        "assets/site.css",
        "index.html",
        "sample-collection/overview.html",
        "search-index.json",
    )


def test_precache_manifest_excludes_service_worker_and_nested_variants(
    tmp_path: Path,
) -> None:
    # Arrange — sw.js cannot precache itself (it is written after the walk),
    # and a non-default locale output nests inside the default root, so the
    # outer manifest must not claim the inner locale's files.
    output = tmp_path / "out"
    nested = output / "pt-BR"
    _emit(output, "index.html")
    _emit(output, "sw.js")
    _emit(nested, "index.html")
    _emit(nested, "sample-collection/overview.html")

    # Act
    manifest = precache_manifest(output, (nested,))

    # Assert
    assert manifest.urls == ("./", "index.html")


def test_precache_manifest_excludes_video_payloads(tmp_path: Path) -> None:
    # Arrange — embed_video ships under <collection>/assets/videos/, the only
    # unbounded-size artifact: a cache.addAll quota rejection aborts the
    # worker's install, so videos degrade to network-only instead.
    output = tmp_path / "out"
    _emit(output, "index.html")
    _emit(output, "sample-collection/assets/videos/demo.mp4")
    _emit(output, "sample-collection/assets/images/plot.png")

    # Act
    manifest = precache_manifest(output, ())

    # Assert
    assert manifest.urls == (
        "./",
        "index.html",
        "sample-collection/assets/images/plot.png",
    )


def test_precache_manifest_excludes_social_cards(tmp_path: Path) -> None:
    # Arrange — generated og:image cards ship under assets/social/ for
    # crawlers only; precaching tens of PNGs a browser never fetches would
    # inflate the install set for zero offline value.
    output = tmp_path / "out"
    _emit(output, "index.html")
    _emit(output, "assets/social/index.png")
    _emit(output, "assets/social/sample-collection/overview.png")
    _emit(output, "assets/site.css")

    # Act
    manifest = precache_manifest(output, ())

    # Assert
    assert manifest.urls == ("./", "assets/site.css", "index.html")


def test_precache_manifest_version_is_content_addressed(
    tmp_path: Path,
) -> None:
    # Arrange — identical trees must share a cache version (incremental
    # rebuilds re-emit the same bytes), while any content change bumps it.
    output = tmp_path / "out"
    _emit(output, "index.html", "v1")
    first = precache_manifest(output, ())

    # Act — same content, then a changed file.
    rebuilt = precache_manifest(output, ())
    _emit(output, "index.html", "v2")
    changed = precache_manifest(output, ())

    # Assert
    assert isinstance(first, PrecacheManifest)
    assert rebuilt.version == first.version
    assert changed.version != first.version


def test_precache_manifest_version_changes_with_the_file_set(
    tmp_path: Path,
) -> None:
    # Arrange — a page added or renamed between builds changes the URL list,
    # so the version must move even when shared contents are untouched.
    output = tmp_path / "out"
    _emit(output, "index.html")
    before = precache_manifest(output, ())

    # Act
    _emit(output, "sample-collection/overview.html")
    after = precache_manifest(output, ())

    # Assert
    assert after.version != before.version
