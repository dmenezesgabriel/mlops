import json
from pathlib import Path

from ssg.application.versioned_output import (
    emission_segments,
    finalize_versioned_output,
    prepare_versioned_output,
    read_versions_json,
)
from ssg.domain import Site, SiteVersion, SiteVersioning


def _versioning(
    current: str = "0.2",
    aliases: tuple[str, ...] = ("latest",),
    extra_versions: tuple[SiteVersion, ...] = (),
) -> SiteVersioning:
    return SiteVersioning(
        current=current,
        default="latest",
        versions=(
            SiteVersion(id=current, title=current, aliases=aliases),
            SiteVersion(id="0.1", title="0.1"),
            *extra_versions,
        ),
    )


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_emission_segments_unversioned_build_is_root_only() -> None:
    assert emission_segments(
        Site(title="S", description="", collections=())
    ) == ("",)


def test_emission_segments_versioned_build_is_current_only() -> None:
    site = Site(
        title="S",
        description="",
        collections=(),
        versioning=_versioning(),
    )
    assert emission_segments(site) == ("0.2",)


def test_prepare_sweeps_unversioned_era_output(tmp_path: Path) -> None:
    # Arrange — a root that previously held an unversioned build keeps
    # locale dirs, collection dirs and emitted files; the first versioned
    # build must clear them or the artifact ships ghosts. `.nojekyll` and
    # `versions.json` survive (deploy metadata, not page output).
    for name in (
        "pt-BR/index.html",
        "assets/site.css",
        "sample-collection/overview.html",
        "search-index.json",
        "sitemap.xml",
        "robots.txt",
        "sw.js",
    ):
        _write(tmp_path / name)
    (tmp_path / "index.html").write_text("stale", encoding="utf-8")
    (tmp_path / "404.html").write_text("stale", encoding="utf-8")
    (tmp_path / ".nojekyll").write_text("", encoding="utf-8")
    _write(tmp_path / "versions.json", "[]")

    # Act
    prepare_versioned_output(tmp_path, _versioning())

    # Assert
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        ".nojekyll",
        "404.html",
        "index.html",
        "versions.json",
    ]


def test_prepare_keeps_sibling_version_dirs_but_clears_owned_segments(
    tmp_path: Path,
) -> None:
    # Arrange — 0.1 was built by an earlier deploy (mike parity: old
    # versions are never re-emitted); the current version and its aliases
    # are rebuilt from scratch.
    _write(tmp_path / "0.1" / "index.html", "old version")
    _write(tmp_path / "0.2" / "index.html", "stale current")
    _write(tmp_path / "latest" / "index.html", "stale alias")
    _write(
        tmp_path / "versions.json",
        json.dumps([{"version": "0.1", "title": "0.1", "aliases": []}]),
    )

    # Act
    prepare_versioned_output(tmp_path, _versioning())

    # Assert
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "0.1",
        "versions.json",
    ]


def test_prepare_keeps_dirs_known_only_to_existing_versions_json(
    tmp_path: Path,
) -> None:
    # Arrange — an old checkout building an old version must not delete a
    # newer version's tree; the accumulated registry carries it.
    _write(tmp_path / "0.9" / "index.html", "newer version")
    _write(
        tmp_path / "versions.json",
        json.dumps([{"version": "0.9", "title": "0.9", "aliases": []}]),
    )

    # Act
    prepare_versioned_output(tmp_path, _versioning())

    # Assert
    assert (tmp_path / "0.9" / "index.html").exists()


def test_finalize_copies_the_current_tree_into_each_alias(
    tmp_path: Path,
) -> None:
    # Arrange — the alias is a byte copy of the built version: permalinks
    # under /latest/ stay browsable while canonical URLs inside still point
    # at the real version dir (mike's copy alias-type).
    _write(tmp_path / "0.2" / "index.html", "home")
    _write(tmp_path / "0.2" / "assets" / "site.css", "css")
    _write(tmp_path / "0.2" / "pt-BR" / "index.html", "inicio")
    _write(tmp_path / "0.2" / "404.html", "not found")

    # Act
    finalize_versioned_output(tmp_path, _versioning(), "REDIRECT")

    # Assert
    assert (tmp_path / "latest" / "index.html").read_text() == "home"
    assert (tmp_path / "latest" / "assets" / "site.css").read_text() == "css"
    assert (tmp_path / "latest" / "pt-BR" / "index.html").exists()
    # The default version's 404 is copied to the output root: hosts serve
    # the root 404.html for missing paths at any depth.
    assert (tmp_path / "404.html").read_text() == "not found"


def test_finalize_writes_versions_json_and_root_redirect(
    tmp_path: Path,
) -> None:
    # Arrange
    _write(tmp_path / "0.2" / "index.html", "home")
    _write(tmp_path / "0.1" / "index.html", "old")
    _write(tmp_path / "0.2" / "404.html", "not found")

    # Act
    finalize_versioned_output(tmp_path, _versioning(), "REDIRECT")

    # Assert — mike's schema: one entry per version, aliases inline.
    versions = json.loads((tmp_path / "versions.json").read_text())
    assert versions == [
        {
            "version": "0.2",
            "title": "0.2",
            "aliases": ["latest"],
        },
        {"version": "0.1", "title": "0.1", "aliases": []},
    ]
    assert (tmp_path / "index.html").read_text() == "REDIRECT"


def test_finalize_merges_existing_versions_json_and_prunes_missing_dirs(
    tmp_path: Path,
) -> None:
    # Arrange — existing.json knows a 0.9 the config predates (kept,
    # appended) and a 0.8 whose dir is gone (pruned).
    _write(
        tmp_path / "versions.json",
        json.dumps(
            [
                {"version": "0.9", "title": "0.9", "aliases": ["stable"]},
                {"version": "0.8", "title": "0.8", "aliases": []},
            ]
        ),
    )
    _write(tmp_path / "0.9" / "index.html", "newer")
    _write(tmp_path / "0.2" / "index.html", "home")
    _write(tmp_path / "0.1" / "index.html", "old")
    _write(tmp_path / "0.2" / "404.html", "not found")

    # Act
    finalize_versioned_output(tmp_path, _versioning(), "REDIRECT")

    # Assert
    versions = json.loads((tmp_path / "versions.json").read_text())
    assert [entry["version"] for entry in versions] == ["0.2", "0.1", "0.9"]
    assert versions[2]["aliases"] == ["stable"]


def test_finalize_marks_hidden_entries(tmp_path: Path) -> None:
    # Arrange
    _write(tmp_path / "0.2" / "index.html", "home")
    _write(tmp_path / "0.1" / "index.html", "old")
    _write(tmp_path / "0.0" / "index.html", "hidden")
    _write(tmp_path / "0.2" / "404.html", "not found")
    versioning = _versioning(
        extra_versions=(SiteVersion(id="0.0", title="0.0", hidden=True),)
    )

    # Act
    finalize_versioned_output(tmp_path, versioning, "REDIRECT")

    # Assert — mike's hidden property keeps the entry out of selectors
    # while the directory stays deployed.
    versions = json.loads((tmp_path / "versions.json").read_text())
    assert versions[2] == {
        "version": "0.0",
        "title": "0.0",
        "aliases": [],
        "properties": {"hidden": True},
    }


def test_finalize_without_aliases_writes_no_alias_dir(tmp_path: Path) -> None:
    # Arrange
    _write(tmp_path / "0.2" / "index.html", "home")
    _write(tmp_path / "0.1" / "index.html", "old")
    _write(tmp_path / "0.2" / "404.html", "not found")

    # Act
    finalize_versioned_output(tmp_path, _versioning(aliases=()), "REDIRECT")

    # Assert
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "0.1",
        "0.2",
        "404.html",
        "index.html",
        "versions.json",
    ]


def test_finalize_missing_current_version_fails(tmp_path: Path) -> None:
    # Arrange — copytree of a missing dir raises; guard it with a clear
    # error instead of a bare FileNotFoundError.
    _write(tmp_path / "0.1" / "index.html", "old")

    # Act / Assert
    try:
        finalize_versioned_output(tmp_path, _versioning(), "REDIRECT")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "0.2" in str(exc)


def test_prepare_on_empty_output_is_noop(tmp_path: Path) -> None:
    # Act / Assert — first versioned build on a clean root.
    prepare_versioned_output(tmp_path, _versioning())
    assert list(tmp_path.iterdir()) == []


def test_read_versions_json_missing_file_is_empty(tmp_path: Path) -> None:
    # Act / Assert — no registry yet is "nothing deployed", not an error.
    assert read_versions_json(tmp_path) == ()


def test_read_versions_json_malformed_text_is_empty(tmp_path: Path) -> None:
    # Arrange
    _write(tmp_path / "versions.json", "{not json")

    # Act / Assert — a corrupt registry is discarded, never raised.
    assert read_versions_json(tmp_path) == ()


def test_read_versions_json_non_list_payload_is_empty(tmp_path: Path) -> None:
    # Arrange
    _write(tmp_path / "versions.json", '{"version": "0.1"}')

    # Act / Assert
    assert read_versions_json(tmp_path) == ()


def test_read_versions_json_skips_entries_without_a_version_id(
    tmp_path: Path,
) -> None:
    # Arrange — a non-mapping item and a mapping with no version id are
    # both invisible; a valid entry among them still parses.
    _write(
        tmp_path / "versions.json",
        json.dumps(
            [
                "0.1",
                {"title": "no id"},
                {"version": ""},
                {"version": "0.2", "title": "0.2", "aliases": ["latest"]},
            ]
        ),
    )

    # Act
    entries = read_versions_json(tmp_path)

    # Assert
    assert [(e.id, e.title, e.aliases) for e in entries] == [
        ("0.2", "0.2", ("latest",))
    ]


def test_read_versions_json_defaults_title_and_ignores_bad_aliases(
    tmp_path: Path,
) -> None:
    # Arrange — no title falls back to the id; non-string aliases drop.
    _write(
        tmp_path / "versions.json",
        json.dumps(
            [
                {"version": "0.3", "aliases": ["stable", 7, None]},
                {"version": "0.4", "properties": {"hidden": True}},
            ]
        ),
    )

    # Act / Assert
    assert [(e.title, e.aliases) for e in read_versions_json(tmp_path)] == [
        ("0.3", ("stable",)),
        ("0.4", ()),
    ]
    assert read_versions_json(tmp_path)[1].hidden is True
