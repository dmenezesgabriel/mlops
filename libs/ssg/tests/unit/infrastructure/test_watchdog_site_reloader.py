from pathlib import Path
from threading import Event

from ssg.infrastructure.watchdog_site_reloader import WatchdogSiteReloader


class TestWatchdogSiteReloader:
    def test_triggers_on_change_with_debounced_paths(self, tmp_path: Path) -> None:
        # Arrange
        reloader = WatchdogSiteReloader()
        watched_dir = tmp_path / "watched"
        watched_dir.mkdir()

        received_paths: list[set[Path]] = []
        called_event = Event()

        def on_change(paths: set[Path]) -> None:
            received_paths.append(paths)
            called_event.set()

        # Act
        reloader.watch((watched_dir,), on_change, interval_seconds=0.1)

        # Simulate rapid file changes
        file1 = watched_dir / "file1.txt"
        file2 = watched_dir / "file2.txt"
        file1.write_text("content", encoding="utf-8")
        file2.write_text("content", encoding="utf-8")

        # Assert
        assert called_event.wait(timeout=2.0)
        assert len(received_paths) == 1
        assert received_paths[0] == {file1, file2}

    def test_ignores_changes_in_ignored_paths(self, tmp_path: Path) -> None:
        # Arrange
        reloader = WatchdogSiteReloader()
        watched_dir = tmp_path / "watched"
        ignored_dir = watched_dir / "ignored"
        watched_dir.mkdir()
        ignored_dir.mkdir()

        received_paths: list[set[Path]] = []
        called_event = Event()

        def on_change(paths: set[Path]) -> None:
            received_paths.append(paths)
            called_event.set()

        # Act
        reloader.watch(
            (watched_dir,),
            on_change,
            interval_seconds=0.1,
            ignored_paths=(ignored_dir,),
        )

        # Change file in ignored directory
        ignored_file = ignored_dir / "ignored.txt"
        ignored_file.write_text("content", encoding="utf-8")

        # Change file in watched (not ignored) directory to ensure reloader is working
        watched_file = watched_dir / "watched.txt"
        watched_file.write_text("content", encoding="utf-8")

        # Assert
        assert called_event.wait(timeout=2.0)
        # Should only have received the watched_file, not the ignored_file
        assert len(received_paths) == 1
        assert received_paths[0] == {watched_file}
