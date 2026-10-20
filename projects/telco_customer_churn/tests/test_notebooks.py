"""Notebook execution tests (integration marker).

Each notebook spins up real training/serving containers via sagemaker-local
(docker + the project's moto compose stack + a Jupyter kernel), so these
live behind the ``integration`` marker and are excluded from the default
``make test``. Run inside the offline JupyterLab stack where
/opt/mlops-venv is the kernel interpreter:

    make test-notebooks

nbclient is imported lazily so unit runs on the host (no notebook kernel
environment) can still collect this module.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]

NOTEBOOKS = [
    "index.ipynb",
    "eda.ipynb",
    "feature_engineering.ipynb",
    "training.ipynb",
    "tuning.ipynb",
    "evaluation.ipynb",
    "deploy.ipynb",
    "monitoring.ipynb",
]

INPUT_CSV = PROJECT_DIR / "data" / "input" / "population.csv"
PREDICTIONS_OUT = PROJECT_DIR / "data" / "output" / "population.csv.out"


def _execute_notebook(name: str) -> None:
    import nbformat
    from nbclient import NotebookClient

    notebook_path = PROJECT_DIR / "notebooks" / name
    notebook = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(notebook, kernel_name="python3", timeout=1800)
    client.execute()


@pytest.mark.integration
class TestNotebooks:
    """Each staged notebook must run cleanly end to end in the local stack."""

    @pytest.mark.parametrize("name", NOTEBOOKS)
    def test_notebook_runs_end_to_end(self, name: str) -> None:
        _execute_notebook(name)

    def test_deploy_scores_every_input_row(self) -> None:
        # A fresh, deterministic artifact set: remove stale data first so the
        # assertion below is not satisfied by a previous run.
        shutil.rmtree(PROJECT_DIR / "data" / "input", ignore_errors=True)
        shutil.rmtree(PROJECT_DIR / "data" / "output", ignore_errors=True)

        _execute_notebook("deploy.ipynb")

        assert INPUT_CSV.is_file(), "notebook must write population.csv"
        assert PREDICTIONS_OUT.is_file(), (
            "batch transform must write population.csv.out"
        )

        input_rows = [
            line for line in INPUT_CSV.read_text().splitlines() if line.strip()
        ]
        predictions = json.loads(PREDICTIONS_OUT.read_text())

        assert len(predictions) == len(input_rows), (
            "one prediction per input row expected; "
            f"got {len(predictions)} predictions for {len(input_rows)} rows"
        )
        assert all(
            isinstance(p, (int, float)) and math.isfinite(float(p))
            for p in predictions
        ), f"non-finite prediction in {predictions}"
