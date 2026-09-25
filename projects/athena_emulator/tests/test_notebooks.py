"""Notebook execution tests (integration marker).

Executes the parity notebooks via nbclient against the running compose stack
(athena :5001 / moto :5000 / trino :8080, or their localhost ports from the
host). Skips when the emulator endpoint is unreachable so a cold stack never
fails collection. Run inside the JupyterLab container:

    /opt/mlops-venv/bin/python -m pytest projects/athena_emulator/tests -m integration

or from the host:

    uv run pytest projects/athena_emulator/tests -m integration

nbclient is imported lazily so non-notebook environments still collect this
module. Executed outputs are written back in place — the executed notebook
itself is the committed evidence.
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = PROJECT_DIR / "notebooks"

NOTEBOOKS = [
    "01_smoke_and_endpoints.ipynb",
    "02_boto3_control_plane.ipynb",
    "03_boto3_query_lifecycle.ipynb",
    "04_wrangler_read_paths.ipynb",
]

ATHENA_URL = os.environ.get("AWS_ENDPOINT_URL_ATHENA", "http://localhost:5001")


def _emulator_reachable() -> bool:
    try:
        urllib.request.urlopen(f"{ATHENA_URL}/health", timeout=2)
    except OSError:
        return False
    return True


def _execute_notebook(name: str) -> None:
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


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _emulator_reachable(),
        reason=f"athena emulator unreachable at {ATHENA_URL}",
    ),
]


@pytest.mark.parametrize("notebook_name", NOTEBOOKS)
def test_notebook_runs_end_to_end(notebook_name: str) -> None:
    """Each parity notebook must execute cleanly against the live stack."""
    _execute_notebook(notebook_name)
