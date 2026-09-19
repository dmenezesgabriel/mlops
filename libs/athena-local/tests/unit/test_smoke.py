import athena_local


def test_package_exposes_version() -> None:
    # The version mirrors pyproject.toml; the smoke test proves the package
    # is importable and its build metadata is wired end-to-end.
    assert athena_local.__version__ == "0.1.0"
