import queue
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class LiveReloadRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self, sse_queues: list[queue.Queue[str]], *args: Any, **kwargs: Any
    ) -> None:
        self._sse_queues = sse_queues
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/__live_reload__":
            self._handle_live_reload()
            return

        super().do_GET()

    def _handle_live_reload(self) -> None:
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        client_queue: queue.Queue[str] = queue.Queue()
        self._sse_queues.append(client_queue)

        try:
            message = client_queue.get(timeout=3600)
            self.wfile.write(f"data: {message}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, queue.Empty):
            pass
        finally:
            if client_queue in self._sse_queues:
                self._sse_queues.remove(client_queue)


class LocalPreviewServer:
    def __init__(self) -> None:
        self._sse_queues: list[queue.Queue[str]] = []
        self._httpd: ThreadingHTTPServer | None = None

    def serve(self, directory: Path, host: str, port: int) -> None:
        handler = partial(
            LiveReloadRequestHandler,
            self._sse_queues,
            directory=str(directory),
        )
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._httpd.daemon_threads = True
        try:
            self._httpd.serve_forever(poll_interval=0.5)
        finally:
            self._httpd.server_close()

    def trigger_reload(self) -> None:
        for client_queue in list(self._sse_queues):
            client_queue.put("reload")

    def shutdown(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
