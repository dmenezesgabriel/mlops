import pytest
from ssg.presentation import cli
from ssg.presentation.cli import create_parser, validate_reload_interval


def test_create_parser_accepts_build_arguments() -> None:
    # Arrange
    parser = create_parser()

    # Act
    arguments = parser.parse_args(
        [
            "build",
            "--config",
            "site/site.yaml",
            "--output",
            "site/build",
            "--collection",
            "sample_collection",
        ],
    )

    # Assert
    assert arguments.command == "build"
    assert arguments.config == "site/site.yaml"
    assert arguments.collection == "sample_collection"


def test_create_parser_accepts_preview_arguments() -> None:
    # Arrange
    parser = create_parser()

    # Act
    arguments = parser.parse_args(
        [
            "preview",
            "--config",
            "site/site.yaml",
            "--output",
            "site/build",
            "--host",
            "127.0.0.1",
            "--port",
            "9000",
        ],
    )

    # Assert
    assert arguments.command == "preview"
    assert arguments.port == 9000


def test_validate_reload_interval_rejects_busy_loop_interval() -> None:
    # Arrange
    reload_interval = 0.0

    # Act / Assert
    with pytest.raises(ValueError, match="expected value greater than 0"):
        validate_reload_interval(reload_interval)


def test_main_validates_preview_interval_before_building(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    build_calls: list[str] = []
    monkeypatch.setattr(
        "sys.argv",
        [
            "ssg",
            "preview",
            "--config",
            "site/site.yaml",
            "--output",
            "site/build",
            "--reload-interval",
            "0",
        ],
    )
    monkeypatch.setattr(
        cli,
        "build_site",
        lambda *_arguments: build_calls.append("build"),
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected value greater than 0"):
        cli.main()
    assert build_calls == []
