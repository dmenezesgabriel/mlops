"""Step definitions for the diagrams-cli BDD feature.

Steps drive `cli.main()` with real argv over real tmp definition/output
trees, the real YAML loader and the real `MingrammerDiagramRenderer` —
the assembled argv→load→render→artifact loop the constructor-level unit
pins cannot cover. Only the `diagrams` (mingrammer) module is faked at
the `sys.modules` seam: the `[diagrams]` extra and graphviz are absent
on host and gate.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from diagrams_generation.infrastructure import cli
from pytest_bdd import given, parsers, scenarios, then, when
from tests.unit.infrastructure._diagrams_fakes import RenderRecorder

scenarios("diagrams_cli.feature")

_VALID_YAML = """\
name: "MLOps Lifecycle"
filename: "mlops_lifecycle"
direction: "LR"
nodes:
  - id: raw_data
    label: "Raw Data"
    type: "onprem.mlops.Mlflow"
  - id: model
    label: "Model"
    type: "custom.Custom"
connections:
  - from: raw_data
    to: model
    label: "trains"
"""

_MALFORMED_YAML = 'name: "n"\nfilename: "f"\nnodes: 42\n'


@dataclass
class DiagramCliRun:
    """State shared between the given/when/then steps of a scenario."""

    definitions_dir: Path
    output_dir: Path
    exit_code: int | str | None = 0
    stderr: str = ""


@pytest.fixture
def run(tmp_path: Path) -> DiagramCliRun:
    return DiagramCliRun(
        definitions_dir=tmp_path / "definitions",
        output_dir=tmp_path / "output",
    )


@given(
    parsers.parse(
        'a definitions directory with a valid diagram "{diagram_id}"'
    )
)
def _valid_diagram(run: DiagramCliRun, diagram_id: str) -> None:
    run.definitions_dir.mkdir(parents=True, exist_ok=True)
    (run.definitions_dir / f"{diagram_id}.yaml").write_text(_VALID_YAML)


@given(
    parsers.parse(
        'a definitions directory with a malformed diagram "{diagram_id}"'
    )
)
def _malformed_diagram(run: DiagramCliRun, diagram_id: str) -> None:
    run.definitions_dir.mkdir(parents=True, exist_ok=True)
    (run.definitions_dir / f"{diagram_id}.yaml").write_text(_MALFORMED_YAML)


@when(parsers.parse('I run "diagrams-cli" for "{diagram_id}"'))
def _run_cli(
    run: DiagramCliRun,
    diagram_id: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_diagrams: RenderRecorder,
) -> None:
    argv = [
        "diagrams-cli",
        diagram_id,
        "--definitions-dir",
        str(run.definitions_dir),
        "--output-dir",
        str(run.output_dir),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    try:
        cli.main()
    except SystemExit as exc:
        run.exit_code = exc.code
    run.stderr = capsys.readouterr().err


@then(parsers.parse("the command exits with code {code:d}"))
def _exit_code(run: DiagramCliRun, code: int) -> None:
    assert run.exit_code == code


@then(
    parsers.parse('the artifact "{filename}" exists in the output directory')
)
def _artifact_exists(run: DiagramCliRun, filename: str) -> None:
    artifact = run.output_dir / filename
    assert artifact.is_file()


@then(parsers.parse('stderr shows "{needle}"'))
def _stderr_shows(run: DiagramCliRun, needle: str) -> None:
    assert needle in run.stderr


@then(
    parsers.parse(
        'the diagram records the edge from "{source}" to "{target}" '
        'labeled "{label}"'
    )
)
def _edge_recorded(
    fake_diagrams: RenderRecorder,
    source: str,
    target: str,
    label: str,
) -> None:
    assert (source, label, target) in fake_diagrams.edges
