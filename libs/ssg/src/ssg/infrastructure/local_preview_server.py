from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class LocalPreviewServer:
    def serve(self, directory: Path, host: str, port: int) -> None:
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        server = ThreadingHTTPServer((host, port), handler)
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            server.server_close()
