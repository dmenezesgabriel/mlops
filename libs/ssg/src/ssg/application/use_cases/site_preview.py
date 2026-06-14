from collections.abc import Callable
from pathlib import Path

from ssg.application.ports.preview_server import PreviewServer
from ssg.application.ports.site_reloader import SiteReloader


class StaticSitePreview:
    """Use Case for serving a local preview server with auto-reload capabilities."""

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
            trigger_reload = getattr(
                self._preview_server, "trigger_reload", None
            )
            if trigger_reload is not None:
                trigger_reload()

        self._site_reloader.watch(
            watched_paths,
            rebuild_and_reload,
            reload_interval,
            ignored_paths=ignored_paths,
        )
        self._preview_server.serve(output_path, host, port)
