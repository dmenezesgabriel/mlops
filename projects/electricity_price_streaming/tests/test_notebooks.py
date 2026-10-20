"""Integration: execute every lifecycle notebook end to end."""

from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOKS = [
    "index",
    "eda",
    "feature_engineering",
    "training",
    "tuning",
    "evaluation",
    "deploy",
    "monitoring",
]

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("notebook", NOTEBOOKS)
def test_notebook_executes(notebook: str) -> None:
    nb = nbformat.read(PROJECT_DIR / "notebooks" / notebook, as_version=4)
    client = NotebookClient(
        nb,
        timeout=1800,
        kernel_name="python3",
        resources={"metadata": {"path": PROJECT_DIR}},
    )
    client.execute()
    errors = [
        o
        for c in nb.cells
        for o in c.get("outputs", [])
        if o.get("output_type") == "error"
    ]
    assert not errors, errors[0]["evalue"] if errors else ""
