import threading
from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from time import sleep

from ssg.application.ports import SiteReloader

LOGGER = getLogger(__name__)


class PollingSiteReloader(SiteReloader):
    def watch(
        self,
        watched_paths: tuple[Path, ...],
        on_change: Callable[[set[Path]], None],
        interval_seconds: float,
        ignored_paths: tuple[Path, ...] = (),
    ) -> None:
        def rebuild_adapter() -> None:
            # PollingSiteReloader currently doesn't track which paths changed specifically
            # but SiteReloader protocol expects on_change(set[Path])
            # For now we pass empty set or we could pass all watched files
            on_change(set())

        reload_thread = threading.Thread(
            target=self._watch_forever,
            args=(
                watched_paths,
                rebuild_adapter,
                interval_seconds,
                ignored_paths,
            ),
            daemon=True,
        )
        reload_thread.start()

    def _watch_forever(
        self,
        watched_paths: tuple[Path, ...],
        rebuild: Callable[[], None],
        interval_seconds: float,
        ignored_paths: tuple[Path, ...] = (),
    ) -> None:
        last_signature = self._signature(watched_paths, ignored_paths)
        while True:
            sleep(interval_seconds)
            current_signature = self._signature(watched_paths, ignored_paths)
            if current_signature == last_signature:
                continue

            self._rebuild_safely(rebuild)
            last_signature = current_signature

    def _rebuild_safely(self, rebuild: Callable[[], None]) -> None:
        try:
            rebuild()
        except Exception:
            LOGGER.exception("site_reload_failed")

    def _signature(
        self,
        watched_paths: tuple[Path, ...],
        ignored_paths: tuple[Path, ...] = (),
    ) -> tuple[tuple[str, int, int], ...]:
        files = []
        for watched_path in watched_paths:
            for path in watched_path.rglob("*"):
                if not path.is_file():
                    continue

                if any(
                    path == ignored_path or ignored_path in path.parents
                    for ignored_path in ignored_paths
                ):
                    continue

                files.append(
                    (str(path), path.stat().st_mtime_ns, path.stat().st_size)
                )

        return tuple(sorted(files))
