import subprocess
import sys
from pathlib import Path

from data_science_scaffold.scaffold import generate

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
