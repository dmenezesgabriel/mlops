"""Unit tests for the sagemaker_local package distribution surface."""

from pathlib import Path

import sagemaker_local


def test_package_ships_py_typed_marker() -> None:
    # PEP 561 marker: without it consumers' pyright ignores the package's
    # strict annotations (every sibling lib ships one).
    package_dir = Path(sagemaker_local.__file__).parent
    assert (package_dir / "py.typed").is_file()
