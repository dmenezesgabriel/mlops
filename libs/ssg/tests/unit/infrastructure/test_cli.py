from collections.abc import Callable
from pathlib import Path

import pytest
from ssg.infrastructure import cli
from ssg.infrastructure.cli import (
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


class FakeSiteReloader:
    def __init__(self) -> None:
        self.on_change: Callable[[set[Path]], None] | None = None
        self.watch_calls: list[tuple[Path, ...]] = []

    def watch(
        self,
        watched_paths: tuple[Path, ...],
        on_change: Callable[[set[Path]], None],
        interval_seconds: float,
        ignored_paths: tuple[Path, ...] = (),
    ) -> None:
        self.watch_calls.append(watched_paths)
        self.on_change = on_change


class FakePreviewServer:
    def __init__(self) -> None:
        self.serve_calls: list[tuple[Path, str, int]] = []
        self.trigger_reload_calls = 0

    def serve(self, directory: Path, host: str, port: int) -> None:
        self.serve_calls.append((directory, host, port))

    def trigger_reload(self) -> None:
        self.trigger_reload_calls += 1


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


def test_main_preview_rebuild_renders_edited_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    site_path = tmp_path / "site"
    source_root = tmp_path / "content" / "docs"
    site_path.mkdir()
    source_root.mkdir(parents=True)
    config_path = site_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Preview Site\n"
        "collections:\n"
        "  - name: docs\n"
        "    title: Docs\n"
        "    source_root: ../content/docs\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n",
        encoding="utf-8",
    )
    page_source = source_root / "README.md"
    page_source.write_text("# Overview\n\nversion one\n", encoding="utf-8")
    output_path = tmp_path / "build"
    reloader = FakeSiteReloader()
    preview_server = FakePreviewServer()
    monkeypatch.setattr(cli, "WatchdogSiteReloader", lambda: reloader)
    monkeypatch.setattr(cli, "LocalPreviewServer", lambda: preview_server)
    monkeypatch.setattr(cli, "entry_points", lambda **_kwargs: ())
    monkeypatch.setattr(
        "sys.argv",
        [
            "ssg",
            "preview",
            "--config",
            str(config_path),
            "--output",
            str(output_path),
            "--reload-interval",
            "1",
        ],
    )
    cli.main()
    page_output = output_path / "docs" / "overview.html"
    assert "version one" in page_output.read_text(encoding="utf-8")
    page_source.write_text(
        "# Overview\n\nversion two EDITED\n", encoding="utf-8"
    )

    # Act
    assert reloader.on_change is not None
    reloader.on_change({page_source})

    # Assert
    assert "version two EDITED" in page_output.read_text(encoding="utf-8")
    assert preview_server.trigger_reload_calls == 1


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
