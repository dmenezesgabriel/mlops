from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest
import videos.infrastructure.cli as cli
from videos.domain.entities.concept_registry import ConceptRegistry
from videos.infrastructure.cli import ConsoleTelemetry


class FakeDirector:
    """Named fake at the Director boundary — records ctor kwargs and
    produce() calls instead of driving the real pipeline."""

    instances: ClassVar[list[FakeDirector]] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.produce_calls: list[str] = []
        type(self).instances.append(self)

    def produce(self, quality: str = "preview") -> None:
        self.produce_calls.append(quality)


class FailingDirector(FakeDirector):
    def produce(self, quality: str = "preview") -> None:
        raise RuntimeError("Boom")


class RecordingRegisterAll:
    """Named fake for the register_all seam — captures the call."""

    def __init__(self) -> None:
        self.calls: list[tuple[ConceptRegistry, object]] = []

    def __call__(
        self,
        registry: ConceptRegistry,
        definitions_dir: str | Path | None = None,
    ) -> None:
        self.calls.append((registry, definitions_dir))


def _failing_register_default(registry: object) -> None:
    raise TypeError("Boom")


@pytest.fixture(autouse=True)
def fake_director(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    FakeDirector.instances.clear()
    monkeypatch.setattr(cli, "Director", FakeDirector)
    yield
    FakeDirector.instances.clear()


def _argv(
    tmp_path: Path, *args: str, definitions_dir: Path | None = None
) -> list[str]:
    return [
        "videos",
        "test",
        "--definitions-dir",
        str(definitions_dir or tmp_path),
        "--output-dir",
        str(tmp_path / "out"),
        *args,
    ]


_VALID_YAML = """\
concept:
  id: test
  metadata:
    title:
      short: Test
      subtitle: Sub
    description: Desc
    tags: [test]
narrative:
  beats:
    - kind: opening
      narration: {text: "Open", duration_seconds: 5.0}
      visual_key: title
    - kind: recap
      narration: {text: "End", duration_seconds: 5.0}
      visual_key: recap
"""


class TestCLI:
    def test_main_calls_register_all_with_definitions_dir(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Arrange
        register_all = RecordingRegisterAll()
        monkeypatch.setattr(cli, "register_all", register_all)
        monkeypatch.setattr(sys, "argv", _argv(tmp_path))

        # Act
        cli.main()

        # Assert
        assert len(register_all.calls) == 1
        registry, definitions_dir = register_all.calls[0]
        assert isinstance(registry, ConceptRegistry)
        assert definitions_dir == tmp_path

    def test_main_reports_missing_default_definitions_dir(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — no --definitions-dir: the documented default is named.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "argv", ["videos", "test", "--output-dir", str(tmp_path)]
        )

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            cli.main()
        assert excinfo.value.code == 1
        assert (
            "Definitions directory not found: videos/definition"
            in capsys.readouterr().err
        )

    def test_main_passes_quality_to_director(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Arrange
        monkeypatch.setattr(cli, "register_all", RecordingRegisterAll())
        monkeypatch.setattr(sys, "argv", _argv(tmp_path, "--quality", "final"))

        # Act
        cli.main()

        # Assert
        assert FakeDirector.instances[0].produce_calls == ["final"]

    def test_main_exits_on_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange
        monkeypatch.setattr(cli, "register_all", RecordingRegisterAll())
        monkeypatch.setattr(cli, "Director", FailingDirector)
        monkeypatch.setattr(sys, "argv", _argv(tmp_path))

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            cli.main()
        assert excinfo.value.code == 1
        assert "Failed to produce video: Boom" in capsys.readouterr().err

    def test_main_uses_advanced_linter_if_installed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Arrange — an installed videos_linter wins over the local fallback.
        class FakeAdvancedLinter:
            pass

        fake_module = ModuleType("videos_linter.linter_service")
        fake_module.LinterService = FakeAdvancedLinter  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "videos_linter", fake_module)
        monkeypatch.setitem(
            sys.modules, "videos_linter.linter_service", fake_module
        )
        monkeypatch.setattr(cli, "register_all", RecordingRegisterAll())
        monkeypatch.setattr(sys, "argv", _argv(tmp_path))

        # Act
        cli.main()

        # Assert
        linter = FakeDirector.instances[0].kwargs["linter_service"]
        assert isinstance(linter, FakeAdvancedLinter)

    def test_main_uses_local_linter_if_not_installed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Arrange
        monkeypatch.setitem(sys.modules, "videos_linter", None)
        monkeypatch.setitem(sys.modules, "videos_linter.linter_service", None)
        monkeypatch.setattr(cli, "register_all", RecordingRegisterAll())
        monkeypatch.setattr(sys, "argv", _argv(tmp_path))

        # Act
        cli.main()

        # Assert
        from videos.infrastructure.validation.linter_service import (
            LinterService as LocalLinterService,
        )

        linter = FakeDirector.instances[0].kwargs["linter_service"]
        assert isinstance(linter, LocalLinterService)

    def test_main_reports_missing_definitions_dir(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — register_all stays real: the check must fire first.
        absent = tmp_path / "absent"
        monkeypatch.setattr(
            sys, "argv", _argv(tmp_path, definitions_dir=absent)
        )

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            cli.main()
        assert excinfo.value.code == 1
        assert "Definitions directory not found" in capsys.readouterr().err
        assert FakeDirector.instances == []

    @pytest.mark.parametrize(
        "bad_yaml", ["concept: [unclosed", "- not\n- a\n- mapping\n"]
    )
    def test_main_exits_cleanly_on_bad_definition_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        bad_yaml: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — real register_all against a dir holding a bad yaml;
        # the error must exit(1) with the file named, not traceback out.
        defs = tmp_path / "defs"
        defs.mkdir()
        (defs / "bad.yaml").write_text(bad_yaml)
        monkeypatch.setattr(sys, "argv", _argv(tmp_path, definitions_dir=defs))

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            cli.main()
        assert excinfo.value.code == 1
        assert "bad.yaml" in capsys.readouterr().err

    def test_main_exits_cleanly_on_wiring_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — a wiring failure (not just produce) must be caught.
        monkeypatch.setattr(cli, "register_all", RecordingRegisterAll())
        monkeypatch.setattr(
            cli, "register_default_components", _failing_register_default
        )
        monkeypatch.setattr(sys, "argv", _argv(tmp_path))

        # Act & Assert
        with pytest.raises(SystemExit) as excinfo:
            cli.main()
        assert excinfo.value.code == 1
        assert "Failed to produce video" in capsys.readouterr().err

    def test_main_produces_with_real_argv(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange — real argparse, real registration of a valid yaml,
        # real adapter wiring; only the pipeline-driving Director is faked.
        defs = tmp_path / "defs"
        defs.mkdir()
        (defs / "test.yaml").write_text(_VALID_YAML)
        monkeypatch.setattr(sys, "argv", _argv(tmp_path, definitions_dir=defs))

        # Act
        cli.main()

        # Assert
        director = FakeDirector.instances[0]
        assert director.produce_calls == ["preview"]
        registry = director.kwargs["concept_registry"]
        assert isinstance(registry, ConceptRegistry)
        assert len(registry.all()) == 1
        assert (
            "Successfully produced video for concept: test"
            in capsys.readouterr().out
        )

    def test_main_failure_report_goes_to_stderr_not_stdout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The failure line must stay off stdout — piping success output
        # must never carry an error message.
        monkeypatch.setattr(cli, "register_all", RecordingRegisterAll())
        monkeypatch.setattr(cli, "Director", FailingDirector)
        monkeypatch.setattr(sys, "argv", _argv(tmp_path))

        with pytest.raises(SystemExit):
            cli.main()

        captured = capsys.readouterr()
        assert "Failed to produce video" in captured.err
        assert "Failed to produce video" not in captured.out


class TestConsoleTelemetry:
    def test_record_event_prints_structured_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        telemetry = ConsoleTelemetry()

        telemetry.record_event("scene_rendered", {"scene_id": "s1"})

        assert (
            "[EVENT] scene_rendered: {'scene_id': 's1'}"
            in capsys.readouterr().out
        )


class TestCliRegistryWiring:
    def test_director_receives_the_registered_registry(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # The registry the Director gets must be the object register_all
        # was handed — a second instance would silently drop every concept.
        register_all = RecordingRegisterAll()
        monkeypatch.setattr(cli, "register_all", register_all)
        monkeypatch.setattr(sys, "argv", _argv(tmp_path))

        cli.main()

        director = FakeDirector.instances[0]
        registry, _ = register_all.calls[0]
        assert director.kwargs["concept_registry"] is registry
