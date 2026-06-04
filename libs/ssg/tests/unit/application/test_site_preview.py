from collections.abc import Callable
from pathlib import Path

from ssg.application.site_preview import StaticSitePreview


class SpySiteReloader:
    def __init__(self) -> None:
        self.watch_calls: list[tuple[tuple[Path, ...], Callable[[], None], float]] = []

    def watch(
        self,
        watched_paths: tuple[Path, ...],
        rebuild: Callable[[], None],
        interval_seconds: float,
    ) -> None:
        self.watch_calls.append((watched_paths, rebuild, interval_seconds))


class SpyPreviewServer:
    def __init__(self) -> None:
        self.serve_calls: list[tuple[Path, str, int]] = []

    def serve(self, directory: Path, host: str, port: int) -> None:
        self.serve_calls.append((directory, host, port))


def test_preview_starts_reloader_before_server(tmp_path: Path) -> None:
    # Arrange
    site_reloader = SpySiteReloader()
    preview_server = SpyPreviewServer()
    preview = StaticSitePreview(site_reloader=site_reloader, preview_server=preview_server)
    watched_paths = (tmp_path / "site", tmp_path / "content")
    output_path = tmp_path / "build"

    # Act
    preview.preview(
        watched_paths=watched_paths,
        output_path=output_path,
        host="127.0.0.1",
        port=8000,
        reload_interval=1.5,
        rebuild=lambda: None,
    )

    # Assert
    assert site_reloader.watch_calls[0][0] == watched_paths
    assert site_reloader.watch_calls[0][2] == 1.5
    assert preview_server.serve_calls == [(output_path, "127.0.0.1", 8000)]
