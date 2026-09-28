import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from cookiecutter.exceptions import (
    FailedHookException,
    OutputDirExistsException,
)
from data_science_scaffold.scaffold import TEMPLATE_DIR, generate

REPO_ROOT = Path(__file__).resolve().parents[4]
RUFF_CONFIG = REPO_ROOT / "pyproject.toml"


def test_generate_creates_mirror_project_tree(tmp_path: Path) -> None:
    # Act
    generated = generate("dummy_test_proj", tmp_path)

    # Assert
    assert generated == tmp_path / "dummy_test_proj"
    assert (generated / "configs" / "project.yaml").is_file()
    assert (generated / "feature_repo" / "feature_store.yaml").is_file()
    assert (generated / "docs" / "04_exploratory_data_analysis.md").is_file()
    assert (generated / "src" / "dummy_test_proj" / "py.typed").is_file()
    project_yaml = (generated / "configs" / "project.yaml").read_text(
        encoding="utf-8"
    )
    assert "tracking_uri: sqlite:///mlflow.db" in project_yaml


def test_generated_project_passes_ruff_gates(tmp_path: Path) -> None:
    # Arrange
    generated = generate("dummy_test_proj", tmp_path)
    _run_ruff("format", ".", cwd=generated)
    _run_ruff("check", "--fix", ".", cwd=generated)

    # Act
    format_result = _run_ruff("format", "--check", ".", cwd=generated)
    lint_result = _run_ruff("check", ".", cwd=generated)

    # Assert
    assert format_result.returncode == 0, format_result.stdout
    assert lint_result.returncode == 0, lint_result.stdout


def test_generated_project_gates_match_live_shape(tmp_path: Path) -> None:
    # Arrange
    generated = generate("dummy_test_proj", tmp_path)

    # Act
    makefile = (generated / "Makefile").read_text(encoding="utf-8")
    pyproject = tomllib.loads(
        (generated / "pyproject.toml").read_text(encoding="utf-8")
    )

    # Assert — rendered gates must match the live projects/* gate set
    assert '-e "*/node_modules/*"' in makefile
    assert '-x "*/node_modules/*"' not in makefile
    assert "--cov-fail-under" in makefile
    assert "bandit -q -r src -ll" in makefile
    assert "vulture --min-confidence 80 src" in makefile
    assert "xenon" in makefile
    assert "maintainability" in makefile
    assert pyproject["tool"]["pyright"]["typeCheckingMode"] == "strict"
    assert pyproject["tool"]["coverage"]["run"]["source"] == [
        "src",
        "tests",
    ]
    assert pyproject["tool"]["vulture"]["ignore_names"] == [
        "raw_directory",
        "n_trials",
    ]


def test_pre_gen_hook_exits_clean_inside_rendered_tree(tmp_path: Path) -> None:
    # Arrange — render and run the hook exactly as cookiecutter does
    # (template → script, cwd = the just-created project dir) with a stray
    # `projects/<slug>` planted inside it: a probe scoped to the rendered
    # tree must not gate generation.
    rendered_dir = tmp_path / "rendered"
    (rendered_dir / "projects" / "dummy_test_proj").mkdir(parents=True)
    hook_source = (
        (TEMPLATE_DIR / "hooks" / "pre_gen_project.py")
        .read_text(encoding="utf-8")
        .replace("{{ cookiecutter.project_slug }}", "dummy_test_proj")
    )
    hook_script = tmp_path / "pre_gen_project.py"
    hook_script.write_text(hook_source, encoding="utf-8")

    # Act
    result = subprocess.run(
        [sys.executable, str(hook_script)],
        cwd=rendered_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert result.returncode == 0, result.stderr + result.stdout


def test_generate_into_existing_directory_raises(tmp_path: Path) -> None:
    # Arrange — cookiecutter's own guard covers `<output_dir>/<slug>`
    # collisions before the pre_gen hook runs.
    generate("dummy_test_proj", tmp_path)

    # Act & Assert
    with pytest.raises(OutputDirExistsException):
        generate("dummy_test_proj", tmp_path)


def test_generate_rejects_invalid_slug(tmp_path: Path) -> None:
    # Act & Assert — the pre_gen hook still validates the slug pattern.
    with pytest.raises(FailedHookException):
        generate("9abc", tmp_path)


def _run_ruff(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "--config",
            str(RUFF_CONFIG),
            *arguments,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
