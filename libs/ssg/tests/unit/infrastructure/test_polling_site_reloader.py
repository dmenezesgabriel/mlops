from pathlib import Path

from ssg.infrastructure.polling_site_reloader import PollingSiteReloader


def test_signature_tracks_files_across_multiple_watched_paths(tmp_path: Path) -> None:
    # Arrange
    first_path = tmp_path / "first"
    second_path = tmp_path / "second"
    first_path.mkdir()
    second_path.mkdir()
    (first_path / "a.txt").write_text("a", encoding="utf-8")
    (second_path / "b.txt").write_text("bb", encoding="utf-8")

    # Act
    signature = PollingSiteReloader()._signature((first_path, second_path))

    # Assert
    signature_paths = {Path(file_path).name for file_path, _, _ in signature}
    signature_sizes = {file_size for _, _, file_size in signature}
    assert signature_paths == {"a.txt", "b.txt"}
    assert signature_sizes == {1, 2}


def test_rebuild_safely_swallows_rebuild_errors() -> None:
    # Arrange
    reloader = PollingSiteReloader()

    def failing_rebuild() -> None:
        raise RuntimeError("boom")

    # Act / Assert
    reloader._rebuild_safely(failing_rebuild)


def test_ignores_changes_in_ignored_paths(tmp_path: Path) -> None:
    # Arrange
    reloader = PollingSiteReloader()
    watched_dir = tmp_path / "watched"
    ignored_dir = watched_dir / "ignored"
    watched_dir.mkdir()
    ignored_dir.mkdir()

    (watched_dir / "watched.txt").write_text("content", encoding="utf-8")
    (ignored_dir / "ignored.txt").write_text("content", encoding="utf-8")

    # Act
    signature_with_ignored = reloader._signature((watched_dir,), ignored_paths=(ignored_dir,))
    signature_without_ignored = reloader._signature((watched_dir,))

    # Assert
    paths_with_ignored = {Path(p).name for p, _, _ in signature_with_ignored}
    paths_without_ignored = {Path(p).name for p, _, _ in signature_without_ignored}

    assert "watched.txt" in paths_with_ignored
    assert "ignored.txt" not in paths_with_ignored
    assert "ignored.txt" in paths_without_ignored
