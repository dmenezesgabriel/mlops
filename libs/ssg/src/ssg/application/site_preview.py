from collections.abc import Callable
from pathlib import Path

from ssg.application.ports import PreviewServer, SiteReloader


class StaticSitePreview:
    def __init__(self, site_reloader: SiteReloader, preview_server: PreviewServer) -> None:
        self._site_reloader = site_reloader
        self._preview_server = preview_server

    def preview(
        self,
        watched_paths: tuple[Path, ...],
        output_path: Path,
        host: str,
        port: int,
        reload_interval: float,
        rebuild: Callable[[], None],
    ) -> None:
        self._site_reloader.watch(watched_paths, rebuild, reload_interval)
        self._preview_server.serve(output_path, host, port)
