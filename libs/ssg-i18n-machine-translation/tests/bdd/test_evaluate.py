"""Step definitions for the evaluate-CLI BDD feature.

Steps drive `cli.main()` with real argv over real tmp source/translated
trees, real mistletoe parsing and real sacrebleu BLEU — the assembled
argv→report→exit-code loop the constructor-injected unit pins cannot
cover (G-317). Only the `transformers` module is faked at the
`sys.modules` seam: the `[transformers]` extra is absent on host and
gate, and the real `TransformersTextTranslator` path (lazy import →
Protocol check → `pipeline()` → `translation_text` extraction) still
runs end-to-end.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from ssg_i18n_machine_translation.infrastructure import cli

scenarios("evaluate.feature")


class FakeTranslationPipeline:
    """Dict-backed `transformers` pipeline — no HF download, no torch.

    The evaluator's BLEU arm feeds each long catalog key through
    `DocumentTranslator`; a lookup miss returns the source unchanged so
    the same fake class serves the faithful and identity arms.
    """

    def __init__(self, translations: dict[str, str]) -> None:
        self._translations = translations

    def __call__(
        self, source_text: str, **_generation_options: object
    ) -> list[dict[str, str]]:
        translated = self._translations.get(source_text.strip(), source_text)
        return [{"translation_text": translated}]


class FakeTransformersModule(ModuleType):
    """`TransformersModule`-conforming `sys.modules` stand-in."""

    def __init__(self, pipeline: FakeTranslationPipeline) -> None:
        super().__init__("transformers")
        self._pipeline = pipeline

    def pipeline(self, task: str, model: str) -> FakeTranslationPipeline:
        return self._pipeline


@dataclass
class EvaluationRun:
    """State shared between the given/when/then steps of a scenario."""

    source_dir: Path
    translated_dir: Path
    catalog_path: Path
    catalog_translations: dict[str, str] = field(default_factory=dict)
    use_catalog: bool = False
    exit_code: int | str | None = None
    output: str = ""


@pytest.fixture
def run(tmp_path: Path) -> EvaluationRun:
    return EvaluationRun(
        source_dir=tmp_path / "source",
        translated_dir=tmp_path / "translated",
        catalog_path=tmp_path / "catalog.yaml",
    )


def _write_page(
    directory: Path, slug: str, paragraphs: tuple[str, ...]
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    page = directory / f"{slug}.md"
    page.write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")


def _install_transformers_stub(
    monkeypatch: pytest.MonkeyPatch, translations: dict[str, str]
) -> None:
    module = FakeTransformersModule(FakeTranslationPipeline(translations))
    monkeypatch.setitem(sys.modules, "transformers", module)


@given(parsers.parse('a source tree with a page "{slug}" containing "{text}"'))
def _source_page(run: EvaluationRun, slug: str, text: str) -> None:
    _write_page(run.source_dir, slug, (text,))


@given(
    parsers.parse(
        'a source tree with a page "{slug}" containing two paragraphs '
        '"{first}" and "{second}"'
    )
)
def _source_page_two_blocks(
    run: EvaluationRun, slug: str, first: str, second: str
) -> None:
    _write_page(run.source_dir, slug, (first, second))


@given(parsers.parse('the translated tree has "{slug}" containing "{text}"'))
def _translated_page(run: EvaluationRun, slug: str, text: str) -> None:
    _write_page(run.translated_dir, slug, (text,))


@given("the translated tree is empty")
def _translated_empty(run: EvaluationRun) -> None:
    run.translated_dir.mkdir(parents=True, exist_ok=True)


@given(parsers.parse('a catalog mapping "{key}" to "{value}"'))
def _catalog(run: EvaluationRun, key: str, value: str) -> None:
    run.use_catalog = True
    run.catalog_translations[key] = value
    run.catalog_path.write_text(
        f'translations:\n  "{key}": "{value}"\n', encoding="utf-8"
    )


@given("the transformers pipeline returns catalog-faithful translations")
def _faithful_pipeline(
    run: EvaluationRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_transformers_stub(monkeypatch, dict(run.catalog_translations))


@given("the transformers pipeline returns the source text unchanged")
def _identity_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transformers_stub(monkeypatch, {})


def _launch(
    run: EvaluationRun,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *extra_args: str,
) -> None:
    argv = [
        "ssg-i18n-evaluate",
        "--source-dir",
        str(run.source_dir),
        "--translated-dir",
        str(run.translated_dir),
        "--locale",
        "pt-BR",
    ]
    if run.use_catalog:
        argv += ["--catalog-path", str(run.catalog_path)]
    argv += list(extra_args)
    monkeypatch.setattr(sys, "argv", argv)
    try:
        cli.main()
    except SystemExit as exc:
        run.exit_code = exc.code
    run.output = capsys.readouterr().out


@when(parsers.parse('I run "ssg-i18n-evaluate" over the trees'))
def _run_evaluate(
    run: EvaluationRun,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _launch(run, monkeypatch, capsys)


@when(
    parsers.parse(
        'I run "ssg-i18n-evaluate" over the trees with "{flag}" "{value}"'
    )
)
def _run_evaluate_with_flag(
    run: EvaluationRun,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flag: str,
    value: str,
) -> None:
    _launch(run, monkeypatch, capsys, flag, value)


@then(parsers.parse("the evaluation exits with code {code:d}"))
def _exit_code(run: EvaluationRun, code: int) -> None:
    assert run.exit_code == code


@then(parsers.parse('the output shows "{needle}"'))
def _output_shows(run: EvaluationRun, needle: str) -> None:
    assert needle in run.output
