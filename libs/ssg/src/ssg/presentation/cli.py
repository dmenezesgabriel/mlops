import argparse
from importlib.metadata import entry_points
from logging import getLogger
from pathlib import Path

from ssg.application.ports import (
    ContentRenderer,
    HtmlPostProcessor,
    SiteVariantProvider,
)
from ssg.application.site_preview import StaticSitePreview
from ssg.application.static_site_builder import StaticSiteBuilder
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer
from ssg.infrastructure.local_preview_server import LocalPreviewServer
from ssg.infrastructure.logging import StructuredLoggingConfigurator
from ssg.infrastructure.markdown_content_renderer import (
    MarkdownContentRenderer,
)
from ssg.infrastructure.site_config_repository import SiteConfigRepository
from ssg.infrastructure.watchdog_site_reloader import WatchdogSiteReloader

LOGGER = getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and preview static content sites."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    _add_build_arguments(build_parser)
    preview_parser = subparsers.add_parser("preview")
    _add_build_arguments(preview_parser)
    preview_parser.add_argument("--host", default="127.0.0.1")
    preview_parser.add_argument("--port", type=int, default=8000)
    preview_parser.add_argument("--reload-interval", type=float, default=0.2)
    return parser


def main() -> None:
    StructuredLoggingConfigurator().configure()
    arguments = create_parser().parse_args()
    config_path = Path(arguments.config)
    output_path = Path(arguments.output)
    collection_name = arguments.collection
    if arguments.command == "preview":
        validate_reload_interval(arguments.reload_interval)
        build_site(config_path, output_path, collection_name)
        preview_site(
            config_path,
            output_path,
            collection_name,
            arguments.host,
            arguments.port,
            arguments.reload_interval,
        )
        return

    build_site(config_path, output_path, collection_name)


def build_site(
    config_path: Path,
    output_path: Path,
    collection_name: str | None = None,
    changed_paths: set[Path] | None = None,
) -> None:
    builder = StaticSiteBuilder(
        site_repository=SiteConfigRepository(),
        content_renderers=load_content_renderers(),
        html_post_processors=load_html_post_processors(),
        site_variant_provider=load_site_variant_provider(),
        page_renderer=JinjaPageRenderer(),
    )
    builder.build(config_path, output_path, collection_name, changed_paths)


def preview_site(
    config_path: Path,
    output_path: Path,
    collection_name: str | None,
    host: str,
    port: int,
    reload_interval: float,
) -> None:
    repository = SiteConfigRepository()
    site = repository.load(config_path)
    watched_paths = (config_path.parent,) + tuple(
        collection.source_root
        for collection in site.selected_collections(collection_name)
    )
    StaticSitePreview(
        site_reloader=WatchdogSiteReloader(),
        preview_server=LocalPreviewServer(),
    ).preview(
        watched_paths=watched_paths,
        output_path=output_path,
        host=host,
        port=port,
        reload_interval=reload_interval,
        on_change=lambda changed_paths: build_site(
            config_path, output_path, collection_name, changed_paths
        ),
        ignored_paths=(output_path,),
    )


def load_content_renderers() -> tuple[ContentRenderer, ...]:
    plugin_renderers = []
    for entry_point in entry_points(group="ssg.renderers"):
        renderer = entry_point.load()()
        LOGGER.info(
            "content_renderer_loaded",
            extra={"context": {"renderer": entry_point.name}},
        )
        plugin_renderers.append(renderer)

    return (MarkdownContentRenderer(), *plugin_renderers)


def load_html_post_processors() -> tuple[HtmlPostProcessor, ...]:
    html_post_processors = []
    for entry_point in entry_points(group="ssg.html_post_processors"):
        html_post_processor = entry_point.load()()
        LOGGER.info(
            "html_post_processor_loaded",
            extra={"context": {"processor": entry_point.name}},
        )
        html_post_processors.append(html_post_processor)

    return tuple(html_post_processors)


def load_site_variant_provider() -> SiteVariantProvider | None:
    providers = []
    provider_names = []
    for entry_point in entry_points(group="ssg.site_variant_providers"):
        providers.append(entry_point.load()())
        provider_names.append(entry_point.name)
        LOGGER.info(
            "site_variant_provider_loaded",
            extra={"context": {"provider": entry_point.name}},
        )

    if len(providers) <= 1:
        return providers[0] if providers else None

    raise ValueError(
        f"Multiple site variant providers {provider_names}: expected at most one provider",
    )


def _add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--collection")


def validate_reload_interval(reload_interval: float) -> None:
    if reload_interval > 0:
        return

    raise ValueError(
        f"Invalid reload interval {reload_interval}: expected value greater than 0"
    )


if __name__ == "__main__":
    main()
