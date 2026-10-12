import logging
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest
from ssg.infrastructure.watchdog_site_reloader import (
    DebouncedEventHandler,
    WatchdogSiteReloader,
)
from watchdog.events import (
    FileClosedEvent,
    FileClosedNoWriteEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileOpenedEvent,
    FileSystemEvent,
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

    @pytest.mark.parametrize(
        "event_class", [FileOpenedEvent, FileClosedNoWriteEvent]
    )
    def test_on_any_event_ignores_read_class_events(
        self, tmp_path: Path, event_class: type[FileSystemEvent]
    ) -> None:
        # Arrange — watchdog emits opened/closed_no_write on plain reads;
        # queuing them makes every rebuild's own reads retrigger the next.
        flushed = Event()
        reported: list[set[Path]] = []
        handler = DebouncedEventHandler(
            lambda paths: (reported.append(paths), flushed.set()),
            interval_seconds=0.05,
        )

        # Act
        handler.on_any_event(event_class(str(tmp_path / "page.md")))

        # Assert — nothing queued, so the debounce timer never fires
        assert not flushed.wait(timeout=0.5)
        assert reported == []

    @pytest.mark.parametrize(
        "event_class",
        [
            FileCreatedEvent,
            FileModifiedEvent,
            FileDeletedEvent,
            FileClosedEvent,
        ],
    )
    def test_on_any_event_queues_write_class_events(
        self, tmp_path: Path, event_class: type[FileSystemEvent]
    ) -> None:
        # Arrange
        flushed = Event()
        reported: list[set[Path]] = []
        handler = DebouncedEventHandler(
            lambda paths: (reported.append(paths), flushed.set()),
            interval_seconds=0.05,
        )

        # Act
        handler.on_any_event(event_class(str(tmp_path / "page.md")))

        # Assert
        assert flushed.wait(timeout=2.0)
        assert reported == [{(tmp_path / "page.md").resolve()}]

    def test_on_any_event_queues_moved_event(self, tmp_path: Path) -> None:
        # Arrange — FileMovedEvent carries a dest_path alongside src_path
        flushed = Event()
        reported: list[set[Path]] = []
        handler = DebouncedEventHandler(
            lambda paths: (reported.append(paths), flushed.set()),
            interval_seconds=0.05,
        )
        src = tmp_path / "old.md"
        dest = tmp_path / "new.md"

        # Act
        handler.on_any_event(FileMovedEvent(str(src), str(dest)))

        # Assert
        assert flushed.wait(timeout=2.0)
        assert reported == [{src.resolve()}]

    def test_reloader_does_not_retrigger_on_reads_inside_on_change(
        self, tmp_path: Path
    ) -> None:
        # Arrange — every rebuild reads the config and page sources inside
        # the watched dirs; those reads must not count as changes or the
        # rebuild requeues itself forever.
        reloader = WatchdogSiteReloader()
        watched_dir = tmp_path / "watched"
        watched_dir.mkdir()
        config_file = watched_dir / "site.yaml"
        config_file.write_text("site:\n  title: t\n", encoding="utf-8")

        calls: list[set[Path]] = []
        first_call = Event()

        def on_change(paths: set[Path]) -> None:
            calls.append(paths)
            config_file.read_text(encoding="utf-8")
            first_call.set()

        # Act — one edit must flush exactly once
        reloader.watch((watched_dir,), on_change, interval_seconds=0.05)
        (watched_dir / "page.md").write_text("# edited\n", encoding="utf-8")

        # Assert
        assert first_call.wait(timeout=5.0)
        deadline = monotonic() + 1.5
        while monotonic() < deadline and len(calls) <= 1:
            sleep(0.05)
        assert len(calls) == 1

    def test_on_any_event_decodes_bytes_src_path(self, tmp_path: Path) -> None:
        # Arrange — watchdog can report src_path as bytes on some backends;
        # the handler must decode before resolving/ignoring.
        flushed = Event()
        reported: list[set[Path]] = []
        handler = DebouncedEventHandler(
            lambda paths: (reported.append(paths), flushed.set()),
            interval_seconds=0.05,
        )
        event = FileModifiedEvent(str(tmp_path / "page.md").encode("utf-8"))

        # Act
        handler.on_any_event(event)

        # Assert
        assert flushed.wait(timeout=2.0)
        assert reported == [{(tmp_path / "page.md").resolve()}]

    def test_execute_safely_logs_and_swallows_on_change_failure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange — an on_change exception must not kill the observer timer
        # thread; it is logged and dropped.
        def exploding_on_change(paths: set[Path]) -> None:
            raise RuntimeError("rebuild blew up")

        handler = DebouncedEventHandler(
            exploding_on_change, interval_seconds=60
        )

        # Act
        with caplog.at_level(logging.ERROR):
            handler._execute_safely({tmp_path / "page.md"})

        # Assert
        assert any(
            record.getMessage() == "site_reload_failed"
            for record in caplog.records
        )

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
