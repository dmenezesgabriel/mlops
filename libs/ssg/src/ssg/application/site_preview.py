from collections.abc import Callable
from pathlib import Path

from ssg.application.ports import PreviewServer, SiteReloader


class StaticSitePreview:
    def __init__(
        self, site_reloader: SiteReloader, preview_server: PreviewServer
    ) -> None:
        self._site_reloader = site_reloader
        self._preview_server = preview_server

    def preview(
        self,
        watched_paths: tuple[Path, ...],
        output_path: Path,
        host: str,
        port: int,
        reload_interval: float,
        on_change: Callable[[set[Path]], None],
        ignored_paths: tuple[Path, ...] = (),
    ) -> None:
        def rebuild_and_reload(changed_paths: set[Path]) -> None:
            on_change(changed_paths)
            if hasattr(self._preview_server, "trigger_reload"):
                self._preview_server.trigger_reload()

        self._site_reloader.watch(
            watched_paths,
            rebuild_and_reload,
            reload_interval,
            ignored_paths=ignored_paths,
        )
        self._preview_server.serve(output_path, host, port)
