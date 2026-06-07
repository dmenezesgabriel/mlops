from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ssg_latex.application.latex_processor import LatexRenderingError
from ssg_latex.infrastructure.subprocess_renderer import (
    SubprocessLatexRenderer,
)


def test_renderer_raises_runtime_error_if_node_missing() -> None:
    # Arrange
    package_dir = Path("/mock/dir")
    renderer = SubprocessLatexRenderer(package_dir)

    # Act & Assert
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda cmd: (
            None if cmd == "node" else "/usr/bin/npm"
        )

        with pytest.raises(RuntimeError) as exc_info:
            renderer.render("y = x", display_mode=False)

        assert "Node.js is required" in str(exc_info.value)


def test_renderer_raises_runtime_error_if_npm_missing() -> None:
    # Arrange
    package_dir = Path("/mock/dir")
    renderer = SubprocessLatexRenderer(package_dir)

    # Act & Assert
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda cmd: (
            "/usr/bin/node" if cmd == "node" else None
        )

        with pytest.raises(RuntimeError) as exc_info:
            renderer.render("y = x", display_mode=False)

        assert "npm is required" in str(exc_info.value)


def test_renderer_runs_npm_install_if_node_modules_missing() -> None:
    # Arrange
    package_dir = Path("/mock/dir")
    renderer = SubprocessLatexRenderer(package_dir)
    mock_run = MagicMock()
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="installed"),  # npm install
        MagicMock(returncode=0, stdout="HTML_RESULT"),  # npx katex
    ]

    # Act
    with (
        patch("shutil.which") as mock_which,
        patch.object(Path, "exists") as mock_exists,
        patch("subprocess.run", mock_run),
    ):
        mock_which.return_value = "/usr/bin/somepath"
        mock_exists.return_value = False

        result = renderer.render("y = x", display_mode=False)

    # Assert
    assert result == "HTML_RESULT"
    # The first run should be `npm install` inside package_dir
    assert mock_run.call_count == 2
    first_args = mock_run.call_args_list[0][0][0]
    assert first_args == ["npm", "install"]
    first_kwargs = mock_run.call_args_list[0][1]
    assert first_kwargs["cwd"] == package_dir


def test_renderer_runs_katex_without_npm_install_if_node_modules_present() -> (
    None
):
    # Arrange
    package_dir = Path("/mock/dir")
    renderer = SubprocessLatexRenderer(package_dir)
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=0, stdout="HTML_RESULT")

    # Act
    with (
        patch("shutil.which") as mock_which,
        patch.object(Path, "exists") as mock_exists,
        patch("subprocess.run", mock_run),
    ):
        mock_which.return_value = "/usr/bin/somepath"
        mock_exists.return_value = True

        result = renderer.render("y = x", display_mode=True)

    # Assert
    assert result == "HTML_RESULT"
    assert mock_run.call_count == 1
    call_args = mock_run.call_args[0][0]
    assert "npx" in call_args
    assert "--prefix" in call_args
    assert str(package_dir) in call_args
    assert "--no-install" in call_args
    assert "katex" in call_args
    assert "-d" in call_args


def test_renderer_raises_latex_rendering_error_on_subprocess_failure() -> None:
    # Arrange
    package_dir = Path("/mock/dir")
    renderer = SubprocessLatexRenderer(package_dir)
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(
        returncode=1, stderr="Invalid math expression"
    )

    # Act & Assert
    with (
        patch("shutil.which") as mock_which,
        patch.object(Path, "exists") as mock_exists,
        patch("subprocess.run", mock_run),
    ):
        mock_which.return_value = "/usr/bin/somepath"
        mock_exists.return_value = True

        with pytest.raises(LatexRenderingError) as exc_info:
            renderer.render("invalid\\math", display_mode=False)

        assert "Failed to render LaTeX" in str(exc_info.value)
        assert "Invalid math expression" in str(exc_info.value)
