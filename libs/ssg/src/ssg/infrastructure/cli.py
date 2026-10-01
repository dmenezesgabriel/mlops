import argparse
from importlib.metadata import EntryPoint, entry_points
from logging import getLogger
from pathlib import Path
from typing import TypeVar

from ssg.application import StaticSiteBuilder, StaticSitePreview
from ssg.application.ports import (
    ContentRenderer,
    HtmlPostProcessor,
    SiteVariantProvider,
)
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer
from ssg.infrastructure.local_preview_server import LocalPreviewServer
from ssg.infrastructure.logging import StructuredLoggingConfigurator
from ssg.infrastructure.markdown_content_renderer import (
    MarkdownContentRenderer,
)
from ssg.infrastructure.site_config_repository import SiteConfigRepository
from ssg.infrastructure.watchdog_site_reloader import WatchdogSiteReloader

LOGGER = getLogger(__name__)

_PluginT = TypeVar("_PluginT")


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
    try:
        _dispatch(arguments)
    except (
        ValueError,
        TypeError,
        FileNotFoundError,
        ImportError,
        RuntimeError,
    ) as exc:
        raise SystemExit(str(exc)) from exc


def _dispatch(arguments: argparse.Namespace) -> None:
    config_path = Path(arguments.config)
    output_path = Path(arguments.output)
    collection_name = arguments.collection
    if arguments.command == "preview":
        validate_reload_interval(arguments.reload_interval)
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


def create_site_builder() -> StaticSiteBuilder:
    from ssg.infrastructure.html_article_outline_builder import (
        HtmlArticleOutlineBuilder,
    )
    from ssg.infrastructure.in_memory_dependency_tracker import (
        InMemoryDependencyTracker,
    )
    from ssg.infrastructure.single_site_variant_provider import (
        SingleSiteVariantProvider,
    )

    return StaticSiteBuilder(
        site_repository=SiteConfigRepository(),
        content_renderers=load_content_renderers(),
        html_post_processors=load_html_post_processors(),
        site_variant_provider=load_site_variant_provider()
        or SingleSiteVariantProvider(),
        page_renderer=JinjaPageRenderer(),
        article_outline_builder=HtmlArticleOutlineBuilder(),
        dependency_tracker=InMemoryDependencyTracker(),
    )


def build_site(
    config_path: Path,
    output_path: Path,
    collection_name: str | None = None,
    changed_paths: set[Path] | None = None,
) -> None:
    create_site_builder().build(
        config_path, output_path, collection_name, changed_paths
    )


def preview_site(
    config_path: Path,
    output_path: Path,
    collection_name: str | None,
    host: str,
    port: int,
    reload_interval: float,
) -> None:
    # One builder (and so one dependency tracker) must serve the initial
    # build and every rebuild — a fresh tracker per on_change reports zero
    # affected pages and skips every page.
    builder = create_site_builder()
    builder.build(config_path, output_path, collection_name)
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
        on_change=lambda changed_paths: builder.build(
            config_path, output_path, collection_name, changed_paths
        ),
        ignored_paths=(output_path,),
    )


def _load_plugin(
    entry_point: EntryPoint, group: str, contract: type[_PluginT]
) -> _PluginT:
    """Instantiate one ssg.* entry point: name → zero-arg factory →
    port-conforming instance. Failures name the entry point and group."""
    try:
        plugin = entry_point.load()()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load entry point {entry_point.name!r} "
            f"in group {group!r}: {exc}"
        ) from exc
    if not isinstance(plugin, contract):
        raise TypeError(
            f"Invalid {group} plugin {entry_point.name!r}: "
            f"expected {contract.__name__} implementation, "
            f"got {type(plugin).__name__}"
        )
    return plugin


def load_content_renderers() -> tuple[ContentRenderer, ...]:
    plugin_renderers: list[ContentRenderer] = []
    for entry_point in entry_points(group="ssg.renderers"):
        renderer = _load_plugin(entry_point, "ssg.renderers", ContentRenderer)
        LOGGER.info(
            "content_renderer_loaded",
            extra={"context": {"renderer": entry_point.name}},
        )
        plugin_renderers.append(renderer)

    return (MarkdownContentRenderer(), *plugin_renderers)


def load_html_post_processors() -> tuple[HtmlPostProcessor, ...]:
    html_post_processors: list[HtmlPostProcessor] = []
    for entry_point in entry_points(group="ssg.html_post_processors"):
        html_post_processor = _load_plugin(
            entry_point, "ssg.html_post_processors", HtmlPostProcessor
        )
        LOGGER.info(
            "html_post_processor_loaded",
            extra={"context": {"processor": entry_point.name}},
        )
        html_post_processors.append(html_post_processor)

    return tuple(html_post_processors)


def load_site_variant_provider() -> SiteVariantProvider | None:
    providers: list[SiteVariantProvider] = []
    provider_names: list[str] = []
    for entry_point in entry_points(group="ssg.site_variant_providers"):
        providers.append(
            _load_plugin(
                entry_point, "ssg.site_variant_providers", SiteVariantProvider
            )
        )
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
