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
