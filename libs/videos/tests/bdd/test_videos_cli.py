"""Step definitions for the videos-cli BDD feature.

Steps drive `cli.main()` with real argv over real tmp definition/output
trees — the assembled argv → registry → pipeline → artifact-lint loop the
constructor-level unit pins cannot cover. Only `manim` is faked (renderer +
scene builder, see conftest): the absent extra has no host/gate presence,
while the real videos-linter seam the scenarios pin stays live.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import videos.infrastructure.cli as cli
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.conftest import RenderPlan

scenarios("videos_cli.feature")


def _valid_yaml(concept_id: str) -> str:
    return f"""\
concept:
  id: {concept_id}
  metadata:
    title: {{short: Test, subtitle: Sub}}
    description: Desc
    tags: [test]
narrative:
  beats:
    - kind: opening
      narration: {{text: "Open", duration_seconds: 5.0}}
      visual_key: title
    - kind: recap
      narration: {{text: "End", duration_seconds: 5.0}}
      visual_key: recap
"""


@dataclass
class VideosCliRun:
    """State shared between the given/when/then steps of a scenario."""

    definitions_dir: Path
    output_dir: Path
    exit_codes: list[int | str | None] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


@pytest.fixture
def run(tmp_path: Path) -> VideosCliRun:
    return VideosCliRun(
        definitions_dir=tmp_path / "definitions",
        output_dir=tmp_path / "output",
    )


def _invoke(
    run: VideosCliRun,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    try:
        cli.main()
        run.exit_codes.append(0)
    except SystemExit as exc:
        run.exit_codes.append(exc.code)
    captured = capsys.readouterr()
    run.stdout += captured.out
    run.stderr += captured.err


@given(
    parsers.parse(
        'a definitions directory with a valid concept "{concept_id}"'
    )
)
def _valid_concept(run: VideosCliRun, concept_id: str) -> None:
    run.definitions_dir.mkdir(parents=True, exist_ok=True)
    (run.definitions_dir / f"{concept_id}.yaml").write_text(
        _valid_yaml(concept_id)
    )


@given("a renderer producing a blank preview image")
def _blank_image(cli_fakes: RenderPlan) -> None:
    cli_fakes.image = "blank"


@given("a renderer producing a corrupt scene video")
def _corrupt_video(cli_fakes: RenderPlan) -> None:
    cli_fakes.video = "corrupt"


@when(parsers.parse('I run "videos" for "{concept_id}"'))
def _run_videos(
    run: VideosCliRun,
    concept_id: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _invoke(
        run,
        monkeypatch,
        capsys,
        [
            "videos",
            concept_id,
            "--definitions-dir",
            str(run.definitions_dir),
            "--output-dir",
            str(run.output_dir),
        ],
    )


@when(
    parsers.parse('I run "videos" for "{concept_id}" at "{quality}" quality')
)
def _run_videos_quality(
    run: VideosCliRun,
    concept_id: str,
    quality: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _invoke(
        run,
        monkeypatch,
        capsys,
        [
            "videos",
            concept_id,
            "--definitions-dir",
            str(run.definitions_dir),
            "--output-dir",
            str(run.output_dir),
            "--quality",
            quality,
        ],
    )


@when(
    parsers.parse(
        'I run "videos" for "{concept_id}" against a missing '
        "definitions directory"
    )
)
def _run_videos_missing_dir(
    run: VideosCliRun,
    concept_id: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _invoke(
        run,
        monkeypatch,
        capsys,
        [
            "videos",
            concept_id,
            "--definitions-dir",
            str(run.definitions_dir / "absent"),
            "--output-dir",
            str(run.output_dir),
        ],
    )


@then(parsers.parse("the command exits with code {code:d}"))
def _exit_code(run: VideosCliRun, code: int) -> None:
    assert run.exit_codes[-1] == code


@then(parsers.parse("every command exits with code {code:d}"))
def _every_exit_code(run: VideosCliRun, code: int) -> None:
    assert run.exit_codes == [code] * len(run.exit_codes)


@then(parsers.parse('stdout shows "{needle}"'))
def _stdout_shows(run: VideosCliRun, needle: str) -> None:
    assert needle in run.stdout


@then(parsers.parse('stderr shows "{needle}"'))
def _stderr_shows(run: VideosCliRun, needle: str) -> None:
    assert needle in run.stderr


@then(
    parsers.parse('the artifact "{relative}" exists in the output directory')
)
def _artifact_exists(run: VideosCliRun, relative: str) -> None:
    assert (run.output_dir / relative).is_file()
