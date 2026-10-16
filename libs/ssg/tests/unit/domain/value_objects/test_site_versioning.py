from ssg.domain import SiteVersion, SiteVersioning


def _versioning() -> SiteVersioning:
    return SiteVersioning(
        current="0.2",
        default="latest",
        versions=(
            SiteVersion(id="0.2", title="0.2", aliases=("latest",)),
            SiteVersion(id="0.1", title="0.1"),
        ),
    )


def test_build_segments_is_the_current_version_only() -> None:
    # Aliases are filesystem copies of the current tree, not separate
    # emission passes — only the real version builds.
    assert _versioning().build_segments() == ("0.2",)


def test_output_segments_adds_the_current_version_aliases() -> None:
    # Arrange
    versioning = _versioning()

    # Act / Assert — the build owns (and refreshes) the version dir plus
    # each alias dir; sibling versions are untouched.
    assert versioning.output_segments() == ("0.2", "latest")


def test_default_version_id_resolves_alias_to_version() -> None:
    assert _versioning().default_version_id() == "0.2"


def test_default_version_id_accepts_a_plain_version_id() -> None:
    # Arrange
    versioning = SiteVersioning(
        current="0.2",
        default="0.1",
        versions=(SiteVersion(id="0.1", title="0.1"),),
    )

    # Act / Assert
    assert versioning.default_version_id() == "0.1"


def test_entry_for_matches_id_and_alias() -> None:
    # Arrange
    versioning = _versioning()

    # Act / Assert — material resolves the current entry the same way
    # (version or aliases includes the deployed path segment).
    assert versioning.entry_for("0.1") == SiteVersion(id="0.1", title="0.1")
    assert versioning.entry_for("latest") == versioning.versions[0]
    assert versioning.entry_for("unknown") is None
