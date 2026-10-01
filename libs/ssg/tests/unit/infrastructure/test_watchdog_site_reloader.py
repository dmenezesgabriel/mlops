import logging
from pathlib import Path
from threading import Event

import pytest
from ssg.infrastructure.watchdog_site_reloader import (
    DebouncedEventHandler,
    WatchdogSiteReloader,
)


class TestWatchdogSiteReloader:
    def test_triggers_on_change_with_debounced_paths(
        self, tmp_path: Path
    ) -> None:
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

    def test_is_ignored_matches_across_mixed_path_bases(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — event paths carry the watch's base (resolved
        # source_roots, as-passed config dir) while ignored paths keep the
        # caller's spelling, so both relative/absolute directions must match.
        monkeypatch.chdir(tmp_path)
        relative_ignored = DebouncedEventHandler(
            lambda paths: None, 0.1, ignored_paths=(Path("site/build"),)
        )
        absolute_ignored = DebouncedEventHandler(
            lambda paths: None,
            0.1,
            ignored_paths=(tmp_path / "site" / "build",),
        )

        # Act / Assert
        assert relative_ignored._is_ignored(
            tmp_path / "site" / "build" / "index.html"
        )
        assert absolute_ignored._is_ignored(Path("site/build/index.html"))

    def test_warns_when_watched_path_does_not_exist(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange — a mistyped source_root used to vanish silently: no
        # scheduled watch, no events, no log.
        reloader = WatchdogSiteReloader()
        missing_dir = tmp_path / "missing"

        # Act
        with caplog.at_level(logging.WARNING):
            reloader.watch(
                (missing_dir,), lambda paths: None, interval_seconds=0.1
            )

        # Assert
        assert any(
            record.getMessage() == "watched_path_missing"
            and getattr(record, "context", {}).get("path") == str(missing_dir)
            for record in caplog.records
        )
