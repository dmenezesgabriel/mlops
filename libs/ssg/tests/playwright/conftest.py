from collections.abc import Iterator
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest
import yaml


@pytest.fixture
def built_site_url() -> Iterator[str]:
    # Content lives under the current version tree; serve that tree at the
    # artifact root so relative page paths and assets resolve unchanged.
    # Root-level layout (redirect stub, 404, versions.json) is site_root_url.
    content_root = _built_site_root() / _current_site_version()
    assert content_root.exists(), (
        f"Missing versioned build tree {content_root}: "
        "expected `make build-site` before e2e"
    )

    with _serve_directory(content_root) as base_url:
        yield base_url


@pytest.fixture
def site_root_url() -> Iterator[str]:
    with _serve_directory(_built_site_root()) as base_url:
        yield base_url


@pytest.fixture
def site_version() -> str:
    return _current_site_version()


def _repo_path(relative: str) -> Path:
    for candidate in (Path(relative), Path("../..") / relative):
        if candidate.exists():
            return candidate
    raise AssertionError(
        f"Missing {relative}: expected the repository root as cwd or its "
        "package directory"
    )


def _built_site_root() -> Path:
    return _repo_path("site/build")


def _current_site_version() -> str:
    config = yaml.safe_load(_repo_path("site/site.yaml").read_text())
    return _version_from_config(config)


def _version_from_config(config: object) -> str:
    if not isinstance(config, dict):
        return ""
    site = config.get("site")
    if not isinstance(site, dict):
        return ""
    versioning = site.get("versioning")
    if not isinstance(versioning, dict):
        return ""
    current = versioning.get("current")
    return current if isinstance(current, str) else ""


@contextmanager
def _serve_directory(directory: Path) -> Iterator[str]:
    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
