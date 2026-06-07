import sys
import threading
from http.client import HTTPConnection
from pathlib import Path
from time import sleep

import pytest
from ssg.infrastructure.local_preview_server import LocalPreviewServer


@pytest.mark.skipif(
    "coverage" in sys.modules or sys.gettrace() is not None,
    reason="Local preview server test hangs under coverage tracing due to thread/socket interference",
)
class TestLocalPreviewServer:
    def test_supports_sse_live_reload(self, tmp_path: Path) -> None:
        # Arrange
        server = LocalPreviewServer()
        server_thread = threading.Thread(
            target=server.serve, args=(tmp_path, "127.0.0.1", 0), daemon=True
        )
        server_thread.start()

        # Wait for server to start
        for _ in range(20):
            if hasattr(server, "_httpd") and server._httpd is not None:
                break
            sleep(0.05)

        assert server._httpd is not None
        port = server._httpd.server_port

        # Act
        conn = HTTPConnection("127.0.0.1", port)
        conn.request("GET", "/__live_reload__")
        response = conn.getresponse()

        assert response.status == 200
        assert response.getheader("Content-Type") == "text/event-stream"

        server.trigger_reload()

        # Read the data from the stream
        data = response.read(14).decode(
            "utf-8"
        )  # "data: reload\n\n" is 14 chars

        # Assert
        assert data == "data: reload\n\n"

        # Cleanup
        conn.close()
        server.shutdown()
