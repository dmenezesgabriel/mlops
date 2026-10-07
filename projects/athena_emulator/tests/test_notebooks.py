"""Notebook execution tests (integration marker).

Executes the parity notebooks via nbclient against the running compose stack
(athena :5001 / moto :5000 / trino :8080, or their localhost ports from the
host — trino publishes :8485 there). Skips when the emulator endpoint is
unreachable so a cold stack never fails collection. Run inside the
JupyterLab container:

    /opt/mlops-venv/bin/python -m pytest projects/athena_emulator/tests -m integration

or from the host:

    uv run pytest projects/athena_emulator/tests -m integration

The emulator health probe runs in a fixture at test setup, not at module
import, so collecting this file never touches the network. nbclient/ipykernel
absence degrades to a skip, not an import error. Executed outputs are written
back in place — the executed notebook itself is the committed evidence.
"""

from __future__ import annotations

import http.client
import importlib.util
import io
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = PROJECT_DIR / "notebooks"
PARITY_DIR = PROJECT_DIR / "parity"

# Parametrized from the directory so a new .ipynb is executed automatically —
# a literal list would silently leave new notebooks unexecuted/unpersisted.
NOTEBOOKS = [path.name for path in sorted(NOTEBOOKS_DIR.glob("*.ipynb"))]

ATHENA_URL = os.environ.get("AWS_ENDPOINT_URL_ATHENA", "http://localhost:5001")


def _emulator_reachable() -> bool:
    try:
        # Only http(s) endpoints may answer the probe — file:// and other
        # schemes must never count as "reachable" via urlopen.
        if urllib.parse.urlparse(ATHENA_URL).scheme not in ("http", "https"):
            return False
        urllib.request.urlopen(f"{ATHENA_URL}/health", timeout=2)  # nosec B310
    except (OSError, http.client.HTTPException, ValueError):
        return False
    return True


@pytest.fixture(scope="module")
def live_emulator() -> None:
    """One health probe per module run, only when tests are selected."""
    if not _emulator_reachable():
        pytest.skip(f"athena emulator unreachable at {ATHENA_URL}")


def _execute_notebook(name: str) -> None:
    for package in ("nbclient", "ipykernel"):
        if importlib.util.find_spec(package) is None:
            pytest.skip(
                f"{package} not installed; sync the dev group or run "
                "inside the jupyterlab container"
            )
    import nbformat
    from nbclient import NotebookClient

    notebook_path = NOTEBOOKS_DIR / name
    notebook = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        notebook,
        kernel_name="python3",
        timeout=600,
        resources={"metadata": {"path": str(NOTEBOOKS_DIR)}},
    )
    client.execute()
    nbformat.write(notebook, notebook_path)


def _fragment_mtime(stem: str) -> int:
    fragment = PARITY_DIR / f"{stem}.md"
    return fragment.stat().st_mtime_ns if fragment.is_file() else 0


def _fail_rows(stem: str) -> list[str]:
    """Features whose rows in ``parity/<stem>.md`` recorded ``FAIL`` status.

    Splits table cells on unescaped ``|`` only (``_evidence._escape_cell``
    renders literal pipes as ``\\|``) and checks the status cell alone, so
    detail text like "FAILED execution" never counts as a FAIL row.
    """
    fragment = PARITY_DIR / f"{stem}.md"
    if not fragment.is_file():
        return []
    fails = []
    for line in fragment.read_text().splitlines():
        cells = re.split(r"(?<!\\)\|", line.strip())
        if len(cells) >= 3 and cells[2].strip() == "FAIL":
            fails.append(cells[1].strip())
    return fails


def test_notebooks_parametrized_from_disk() -> None:
    """Every ``notebooks/*.ipynb`` must be a test parameter."""
    expected = [path.name for path in sorted(NOTEBOOKS_DIR.glob("*.ipynb"))]
    assert NOTEBOOKS == expected


def test_every_notebook_persisted_a_fragment() -> None:
    """Each notebook stem needs a committed ``parity/<stem>.md`` — a
    notebook that never ran (or never persisted) shows up here."""
    stems = {path.stem for path in NOTEBOOKS_DIR.glob("*.ipynb")}
    fragments = {path.stem for path in PARITY_DIR.glob("*.md")}
    missing = stems - fragments
    assert not missing, (
        f"notebooks without a parity fragment: {sorted(missing)}"
    )


@pytest.mark.integration
@pytest.mark.parametrize("notebook_name", NOTEBOOKS)
def test_notebook_runs_end_to_end(
    notebook_name: str, live_emulator: None
) -> None:
    """Each parity notebook must execute cleanly and persist its fragment."""
    stem = Path(notebook_name).stem
    persisted_before = _fragment_mtime(stem)
    _execute_notebook(notebook_name)
    assert _fragment_mtime(stem) > persisted_before, (
        f"{notebook_name} executed without writing parity/{stem}.md"
    )
    fail_rows = _fail_rows(stem)
    assert not fail_rows, (
        f"{notebook_name} recorded FAIL parity rows: {fail_rows}"
    )


@pytest.mark.parametrize(
    "raised",
    [
        http.client.BadStatusLine("NOT-HTTP-GARBAGE"),
        http.client.LineTooLong("header"),
    ],
)
def test_probe_returns_false_on_http_exception(
    monkeypatch: pytest.MonkeyPatch, raised: Exception
) -> None:
    def refuse(request: object, timeout: float) -> object:
        raise raised

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(
        sys.modules[__name__], "ATHENA_URL", "http://localhost:59999"
    )
    assert _emulator_reachable() is False


def test_probe_rejects_non_http_scheme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "health").write_text("ok")
    monkeypatch.setattr(sys.modules[__name__], "ATHENA_URL", tmp_path.as_uri())
    assert _emulator_reachable() is False


def test_probe_returns_false_on_malformed_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys.modules[__name__], "ATHENA_URL", "not a url")
    assert _emulator_reachable() is False


@pytest.mark.parametrize(
    "raised",
    [urllib.error.URLError("down"), TimeoutError("timeout")],
)
def test_probe_returns_false_on_oserror(
    monkeypatch: pytest.MonkeyPatch, raised: OSError
) -> None:
    def refuse(request: object, timeout: float) -> object:
        raise raised

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(
        sys.modules[__name__], "ATHENA_URL", "http://10.255.255.1"
    )
    assert _emulator_reachable() is False


def test_probe_returns_true_when_health_responds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda _req, timeout: io.BytesIO(b"")
    )
    monkeypatch.setattr(
        sys.modules[__name__], "ATHENA_URL", "http://localhost:5001"
    )
    assert _emulator_reachable() is True


def test_collection_performs_no_network_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def record(request: object, timeout: float) -> object:
        calls.append(request)
        raise urllib.error.URLError("no network in unit tests")

    monkeypatch.setattr(urllib.request, "urlopen", record)
    spec = importlib.util.spec_from_file_location(
        "test_notebooks_copy", Path(__file__).resolve()
    )
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    assert calls == []


def test_execute_notebook_skips_without_kernel_deps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    with pytest.raises(pytest.skip.Exception):
        _execute_notebook("01_smoke_and_endpoints.ipynb")


@pytest.fixture
def parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(sys.modules[__name__], "PARITY_DIR", tmp_path)
    return tmp_path


def _fragment(parity_dir: Path, stem: str, rows: list[str]) -> None:
    table = "\n".join(
        [
            f"## {stem}",
            "",
            "| feature | status | detail | latency_ms |",
            "|---|---|---|---|",
            *rows,
            "",
        ]
    )
    (parity_dir / f"{stem}.md").write_text(table)


def test_fail_rows_detects_fail_status(parity: Path) -> None:
    _fragment(parity, "01_x", ["| f | FAIL | broken |  |"])
    assert _fail_rows("01_x") == ["f"]


def test_fail_rows_ignores_pass_gap_and_table_furniture(
    parity: Path,
) -> None:
    _fragment(
        parity,
        "01_x",
        ["| f | PASS | ok | 2 |", "| g | GAP | absent |  |"],
    )
    assert _fail_rows("01_x") == []


def test_fail_rows_checks_status_cell_only(parity: Path) -> None:
    _fragment(parity, "01_x", ["| f | PASS | FAILED execution detail |  |"])
    assert _fail_rows("01_x") == []


def test_fail_rows_respects_escaped_pipes(parity: Path) -> None:
    _fragment(parity, "01_x", [r"| a \| b | FAIL | d \| e |  |"])
    assert _fail_rows("01_x") == [r"a \| b"]


def test_fail_rows_missing_fragment_is_empty(parity: Path) -> None:
    assert _fail_rows("99_absent") == []


def test_committed_fragments_carry_no_fail_rows() -> None:
    """Committed parity evidence must be green — a FAIL row means a shipped
    feature is broken, and the suite must say so without the live stack."""
    offenders = {
        path.stem: _fail_rows(path.stem) for path in PARITY_DIR.glob("*.md")
    }
    assert not any(offenders.values()), (
        f"FAIL parity rows committed: {offenders}"
    )
