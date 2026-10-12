"""Step definitions for the preview-server BDD feature.

Steps drive `cli.main()` with real argv against a real tmp site, the real
WatchdogSiteReloader (inotify + debounce) and a real LocalPreviewServer
bound to a free port — the assembled edit→rebuild→serve loop that the
fake-seam unit tests cannot pin (G-316). The entry-point scan is stubbed to
empty so the scenarios stay independent of which ssg-* plugin packages
happen to be installed in the environment.
"""

from __future__ import annotations

import logging
import socket
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.client import HTTPConnection
from pathlib import Path
from time import monotonic, sleep

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from ssg.infrastructure import cli, watchdog_site_reloader
from ssg.infrastructure.local_preview_server import LocalPreviewServer
from watchdog.observers import Observer

scenarios("preview.feature")

_WAIT_TIMEOUT_SECONDS = 10


@dataclass
class PreviewRun:
    """State shared between the given/when/then steps of a scenario."""

    config_path: Path | None = None
    output_path: Path | None = None
    page_sources: dict[str, Path] = field(default_factory=dict)
    servers: list[LocalPreviewServer] = field(default_factory=list)
    observers: list[Observer] = field(default_factory=list)
    thread: threading.Thread | None = None
    error: BaseException | None = None
    port: int = 0


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> Iterator[PreviewRun]:
    """Capture each real server/observer so teardown can stop them.

    `cli.main()` force-replaces the root handlers; `watch()` starts a
    daemon Observer the reloader drops. Without teardown, a rebuild fires
    after the test's capture stream closed ("I/O on closed file" logging
    errors) and the observer keeps watching the tmp dir for the whole
    session.
    """
    context = PreviewRun()

    def capture_server() -> LocalPreviewServer:
        server = LocalPreviewServer()
        context.servers.append(server)
        return server

    def capture_observer() -> Observer:
        observer = Observer()
        context.observers.append(observer)
        return observer

    root_logger = logging.getLogger()
    previous_handlers = root_logger.handlers[:]
    previous_level = root_logger.level
    monkeypatch.setattr(cli, "LocalPreviewServer", capture_server)
    monkeypatch.setattr(cli, "entry_points", lambda **_kwargs: ())
    monkeypatch.setattr(watchdog_site_reloader, "Observer", capture_observer)
    yield context
    for server in context.servers:
        server.shutdown()
    if context.thread is not None:
        context.thread.join(timeout=_WAIT_TIMEOUT_SECONDS)
        assert not context.thread.is_alive()
    for observer in context.observers:
        observer.stop()
        observer.join(timeout=_WAIT_TIMEOUT_SECONDS)
    root_logger.handlers[:] = previous_handlers
    root_logger.level = previous_level


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _get_body(port: int, path: str) -> tuple[int, str]:
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        connection.close()


def _try_get(port: int, path: str) -> tuple[int, str] | None:
    try:
        return _get_body(port, path)
    except OSError:
        return None


def _status_is(run: PreviewRun, path: str, status: int) -> bool:
    result = _try_get(run.port, f"/{path}")
    return result is not None and result[0] == status


def _served_with(run: PreviewRun, path: str, needle: str) -> bool:
    result = _try_get(run.port, f"/{path}")
    return result is not None and result[0] == 200 and needle in result[1]


def _wait_for(
    run: PreviewRun, predicate: Callable[[], bool], description: str
) -> None:
    deadline = monotonic() + _WAIT_TIMEOUT_SECONDS
    while monotonic() < deadline:
        if run.error is not None:
            raise AssertionError(
                f"preview exited while waiting for {description}: {run.error}"
            )
        if predicate():
            return
        sleep(0.05)
    pytest.fail(f"timed out waiting for {description}")


@given("a site")
def _new_site(run: PreviewRun, tmp_path: Path) -> None:
    site_path = tmp_path / "site"
    site_path.mkdir()
    run.config_path = site_path / "site.yaml"
    run.config_path.write_text(
        "site:\n  title: Preview Site\ncollections:\n", encoding="utf-8"
    )
    run.output_path = tmp_path / "build"


@given(
    parsers.parse(
        'a "{name}" collection with a page "{slug}" showing "{text}"'
    )
)
def _collection_with_page(
    run: PreviewRun, tmp_path: Path, name: str, slug: str, text: str
) -> None:
    assert run.config_path is not None
    source_root = tmp_path / "content" / name
    source_root.mkdir(parents=True, exist_ok=True)
    page_source = source_root / f"{slug}.md"
    page_source.write_text(f"# {slug}\n\n{text}\n", encoding="utf-8")
    run.page_sources[slug] = page_source
    with run.config_path.open("a", encoding="utf-8") as config:
        config.write(
            f"  - name: {name}\n"
            f"    title: {name.title()} Collection\n"
            f"    source_root: ../content/{name}\n"
            "    pages:\n"
            f"      - slug: {slug}\n"
            f"        title: {slug.title()}\n"
            f"        source: {slug}.md\n"
        )


def _run_main(run: PreviewRun) -> None:
    try:
        cli.main()
    except (Exception, SystemExit) as exc:
        run.error = exc


def _launch(
    run: PreviewRun, monkeypatch: pytest.MonkeyPatch, *extra_args: str
) -> None:
    assert run.config_path is not None
    assert run.output_path is not None
    run.port = _free_port()
    monkeypatch.setattr(
        "sys.argv",
        [
            "ssg",
            "preview",
            "--config",
            str(run.config_path),
            "--output",
            str(run.output_path),
            "--port",
            str(run.port),
            "--reload-interval",
            "0.05",
            *extra_args,
        ],
    )
    run.thread = threading.Thread(target=_run_main, args=(run,), daemon=True)
    run.thread.start()


@when(parsers.parse('I run "ssg preview" for the site'))
def _start_preview(run: PreviewRun, monkeypatch: pytest.MonkeyPatch) -> None:
    _launch(run, monkeypatch)


@when(
    parsers.parse(
        'I run "ssg preview" for the site with "--collection" "{name}"'
    )
)
def _start_preview_collection(
    run: PreviewRun, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    _launch(run, monkeypatch, "--collection", name)


@when(parsers.parse('I edit the "{slug}" source to "{text}"'))
def _edit_source(run: PreviewRun, slug: str, text: str) -> None:
    run.page_sources[slug].write_text(
        f"# {slug}\n\n{text}\n", encoding="utf-8"
    )


@then(parsers.parse('the served "{path}" shows "{text}"'))
def _served_shows(run: PreviewRun, path: str, text: str) -> None:
    _wait_for(
        run,
        lambda: _served_with(run, path, text),
        f'"{path}" serving {text!r}',
    )


@then(parsers.parse('the page "{path}" is not served'))
def _page_not_served(run: PreviewRun, path: str) -> None:
    _wait_for(
        run,
        lambda: _status_is(run, path, 404),
        f'"{path}" answering 404',
    )


@then(parsers.parse('the served index lists "{shown}" and not "{hidden}"'))
def _index_lists_selection(run: PreviewRun, shown: str, hidden: str) -> None:
    _wait_for(run, lambda: _status_is(run, "index.html", 200), "index page")
    result = _try_get(run.port, "/index.html")
    assert result is not None
    assert shown in result[1]
    assert hidden not in result[1]
