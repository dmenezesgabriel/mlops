import pytest
from ssg.presentation import cli
from ssg.presentation.cli import (
    create_parser,
    load_html_post_processors,
    load_site_variant_provider,
    validate_reload_interval,
)


class FakeHtmlPostProcessor:
    def process(self, rendered_html: str, _site: object) -> str:
        return rendered_html


class FakeEntryPoint:
    name = "fake-html-processor"

    def load(self) -> type[FakeHtmlPostProcessor]:
        return FakeHtmlPostProcessor


class FakeSiteVariantProvider:
    pass


class FakeSiteVariantEntryPoint:
    name = "fake-site-variant-provider"

    def load(self) -> type[FakeSiteVariantProvider]:
        return FakeSiteVariantProvider


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


def test_main_validates_preview_interval_before_building(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_load_html_post_processors_uses_html_processor_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    requested_groups: list[str] = []

    def fake_entry_points(group: str) -> tuple[FakeEntryPoint, ...]:
        requested_groups.append(group)
        return (FakeEntryPoint(),)

    monkeypatch.setattr(cli, "entry_points", fake_entry_points)

    # Act
    processors = load_html_post_processors()

    # Assert
    assert requested_groups == ["ssg.html_post_processors"]
    assert isinstance(processors[0], FakeHtmlPostProcessor)


def test_load_site_variant_provider_uses_site_variant_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    requested_groups: list[str] = []

    def fake_entry_points(group: str) -> tuple[FakeSiteVariantEntryPoint, ...]:
        requested_groups.append(group)
        return (FakeSiteVariantEntryPoint(),)

    monkeypatch.setattr(cli, "entry_points", fake_entry_points)

    # Act
    provider = load_site_variant_provider()

    # Assert
    assert requested_groups == ["ssg.site_variant_providers"]
    assert isinstance(provider, FakeSiteVariantProvider)
