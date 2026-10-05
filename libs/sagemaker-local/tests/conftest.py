"""Shared test fixtures: an in-process moto server for real-HTTP round-trips."""

from __future__ import annotations

from pathlib import Path

import pytest
from moto.server import ThreadedMotoServer
from sagemaker_local import patches


@pytest.fixture(autouse=True)
def restore_global_patches():
    """Every test starts and ends with unpatched SDK modules.

    ``make_local_session``/``make_local_pipeline_session`` install real
    monkey-patches on the sagemaker SDK; without a reset the leak is
    order-dependent — the suite only passed because the patching file
    sorted last.
    """
    patches.reset_all()
    yield
    patches.reset_all()


class LiveMotoServer:
    """Threaded moto server bound to a random localhost port."""

    def __init__(self, tmpdir: Path) -> None:
        self.tmpdir = tmpdir
        self.url = ""
        self._server: ThreadedMotoServer | None = None

    def start(self) -> None:
        self._server = ThreadedMotoServer(ip_address="127.0.0.1", port=0)
        self._server.start()
        host, port = self._server.get_host_and_port()
        self.url = f"http://{host}:{port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.stop()
            self._server = None


@pytest.fixture()
def live_moto_server(tmp_path: Path) -> LiveMotoServer:
    server = LiveMotoServer(tmp_path)
    server.start()
    yield server
    server.stop()
