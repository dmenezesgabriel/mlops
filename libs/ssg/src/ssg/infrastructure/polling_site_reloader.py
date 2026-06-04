import threading
from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from time import sleep

LOGGER = getLogger(__name__)


class PollingSiteReloader:
    def watch(
        self,
        watched_paths: tuple[Path, ...],
        rebuild: Callable[[], None],
        interval_seconds: float,
    ) -> None:
        reload_thread = threading.Thread(
            target=self._watch_forever,
            args=(watched_paths, rebuild, interval_seconds),
            daemon=True,
        )
        reload_thread.start()

    def _watch_forever(
        self,
        watched_paths: tuple[Path, ...],
        rebuild: Callable[[], None],
        interval_seconds: float,
    ) -> None:
        last_signature = self._signature(watched_paths)
        while True:
            sleep(interval_seconds)
            current_signature = self._signature(watched_paths)
            if current_signature == last_signature:
                continue

            self._rebuild_safely(rebuild)
            last_signature = current_signature

    def _rebuild_safely(self, rebuild: Callable[[], None]) -> None:
        try:
            rebuild()
        except Exception:
            LOGGER.exception("site_reload_failed")

    def _signature(self, watched_paths: tuple[Path, ...]) -> tuple[tuple[str, int, int], ...]:
        return tuple(
            sorted(
                (str(path), path.stat().st_mtime_ns, path.stat().st_size)
                for watched_path in watched_paths
                for path in watched_path.rglob("*")
                if path.is_file()
            ),
        )
