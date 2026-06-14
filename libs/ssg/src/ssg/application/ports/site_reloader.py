from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class SiteReloader(Protocol):
    def watch(
        self,
        watched_paths: tuple[Path, ...],
        on_change: Callable[[set[Path]], None],
        interval_seconds: float,
        ignored_paths: tuple[Path, ...] = (),
    ) -> None: ...
