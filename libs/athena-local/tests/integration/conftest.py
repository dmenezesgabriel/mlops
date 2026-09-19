"""Live uvicorn server fixture for real-HTTP botocore round-trips.

Mirrors the ``LiveMotoServer`` pattern used by sagemaker-local: an in-process
server on a random localhost port, so unit/integration tests need no docker
stack to exercise the JSON-1.1 wire protocol end to end.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from athena_local.main import app
from uvicorn.config import Config

STARTUP_TIMEOUT_SECONDS = 10.0


class LiveAthenaServer:
    """Threaded uvicorn server bound to a random localhost port."""

    def __init__(self) -> None:
        self.endpoint_url = ""
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        port = self._pick_free_port()
        config = Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        self._server = server
        self._thread = threading.Thread(target=server.run, daemon=True)
        self._thread.start()
        self._wait_until_started(server)
        self.endpoint_url = f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        if self._server is not None and self._thread is not None:
            self._server.should_exit = True
            self._thread.join(timeout=STARTUP_TIMEOUT_SECONDS)
            self._server = None
            self._thread = None

    @staticmethod
    def _pick_free_port() -> int:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    @staticmethod
    def _wait_until_started(server: uvicorn.Server) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while not server.started:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    "uvicorn did not finish startup within "
                    f"{STARTUP_TIMEOUT_SECONDS}s"
                )
            time.sleep(0.01)


@pytest.fixture()
def live_athena_server() -> Iterator[LiveAthenaServer]:
    server = LiveAthenaServer()
    server.start()
    yield server
    server.stop()
