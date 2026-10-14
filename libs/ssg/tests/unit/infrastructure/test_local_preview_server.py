import threading
from http.client import HTTPConnection
from pathlib import Path
from time import sleep

from ssg.infrastructure.local_preview_server import LocalPreviewServer


def _start_preview_server(
    tmp_path: Path,
) -> tuple[LocalPreviewServer, int]:
    server = LocalPreviewServer()
    server_thread = threading.Thread(
        target=server.serve, args=(tmp_path, "127.0.0.1", 0), daemon=True
    )
    server_thread.start()

    # Wait for server to start
    for _ in range(20):
        if getattr(server, "_httpd", None) is not None:
            break
        sleep(0.05)

    assert server._httpd is not None
    return server, server._httpd.server_port


def _wait_for_sse_client(server: LocalPreviewServer) -> None:
    # The handler appends its queue after the response headers flush, so a
    # reload fired the moment getresponse() returns races the subscription:
    # the put lands on an empty list and the handler keeps waiting on its own
    # queue — the hang this test used to skip under coverage for.
    for _ in range(20):
        if server._sse_queues:
            return
        sleep(0.05)
    raise AssertionError("SSE client never registered")


class TestLocalPreviewServer:
    def test_supports_sse_live_reload(self, tmp_path: Path) -> None:
        # Arrange
        server, port = _start_preview_server(tmp_path)
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            conn.request("GET", "/__live_reload__")
            response = conn.getresponse()
            assert response.status == 200
            assert response.getheader("Content-Type") == "text/event-stream"
            _wait_for_sse_client(server)

            # Act
            server.trigger_reload()

            # Assert — "data: reload\n\n" is 14 chars
            data = response.read(14).decode("utf-8")
            assert data == "data: reload\n\n"
        finally:
            conn.close()
            server.shutdown()

    def test_serves_static_files(self, tmp_path: Path) -> None:
        # Arrange
        (tmp_path / "page.html").write_text("<h1>hello</h1>", encoding="utf-8")
        server, port = _start_preview_server(tmp_path)
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            # Act
            conn.request("GET", "/page.html")
            response = conn.getresponse()

            # Assert
            assert response.status == 200
            assert response.read().decode("utf-8") == "<h1>hello</h1>"
        finally:
            conn.close()
            server.shutdown()

    def test_serves_404_html_for_missing_paths(self, tmp_path: Path) -> None:
        # Arrange — mkdocs serve answers missing paths with the built
        # 404.html (commands/serve.py:71-79); the preview mirrors that so the
        # emitted page is reachable locally at any depth.
        (tmp_path / "404.html").write_text(
            "<html>Not found</html>", encoding="utf-8"
        )
        server, port = _start_preview_server(tmp_path)
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            # Act
            conn.request("GET", "/missing/deep/path.html")
            response = conn.getresponse()

            # Assert
            assert response.status == 404
            assert response.read().decode("utf-8") == "<html>Not found</html>"
        finally:
            conn.close()
            server.shutdown()

    def test_missing_path_without_404_html_keeps_default_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange — no emitted 404.html means there is nothing to serve;
        # fall back to SimpleHTTPRequestHandler's default error page.
        server, port = _start_preview_server(tmp_path)
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            # Act
            conn.request("GET", "/missing.html")
            response = conn.getresponse()

            # Assert
            assert response.status == 404
            assert "File not found" in response.read().decode("utf-8")
        finally:
            conn.close()
            server.shutdown()

    def test_non_404_errors_keep_default_error_page(
        self, tmp_path: Path
    ) -> None:
        # Arrange — the 404 override must not swallow other error codes;
        # an unsupported method still gets the base handler's 501 page.
        (tmp_path / "404.html").write_text(
            "<html>Not found</html>", encoding="utf-8"
        )
        server, port = _start_preview_server(tmp_path)
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            # Act
            conn.request("POST", "/page.html")
            response = conn.getresponse()

            # Assert
            assert response.status == 501
            assert "Not found" not in response.read().decode("utf-8")
        finally:
            conn.close()
            server.shutdown()
