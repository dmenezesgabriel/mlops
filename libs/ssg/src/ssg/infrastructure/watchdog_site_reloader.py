import threading
from collections.abc import Callable
from logging import getLogger
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ssg.application.ports import SiteReloader

LOGGER = getLogger(__name__)


class DebouncedEventHandler(FileSystemEventHandler):
    def __init__(self, on_change: Callable[[set[Path]], None], interval_seconds: float) -> None:
        super().__init__()
        self._on_change = on_change
        self._interval_seconds = interval_seconds
        self._changed_paths: set[Path] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        with self._lock:
            src_path = event.src_path
            if isinstance(src_path, bytes):
                src_path = src_path.decode("utf-8")
            self._changed_paths.add(Path(src_path))
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._interval_seconds, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            paths_to_report = set(self._changed_paths)
            self._changed_paths.clear()

        if paths_to_report:
            self._execute_safely(paths_to_report)

    def _execute_safely(self, paths: set[Path]) -> None:
        try:
            self._on_change(paths)
        except Exception:
            LOGGER.exception("site_reload_failed")


class WatchdogSiteReloader(SiteReloader):
    def watch(
        self,
        watched_paths: tuple[Path, ...],
        on_change: Callable[[set[Path]], None],
        interval_seconds: float,
    ) -> None:
        event_handler = DebouncedEventHandler(on_change, interval_seconds)
        observer = Observer()
        for path in watched_paths:
            if path.exists():
                observer.schedule(event_handler, str(path), recursive=True)

        observer.daemon = True
        observer.start()
