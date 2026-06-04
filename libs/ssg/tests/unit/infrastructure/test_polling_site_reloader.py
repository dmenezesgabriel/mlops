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
