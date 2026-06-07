import html
import re
import shutil
from pathlib import Path

from jinja2 import Environment, StrictUndefined
from markdown_it import MarkdownIt

try:
    # Prefer the explicit table plugin when available
    from mdit_py_plugins.table import table_plugin
except (
    Exception
):  # pragma: no cover - optional runtime dependency during tests
    table_plugin = None

# Some releases expose table support as part of the GFM plugin. Import the
# GFM plugin as a fallback so we still get table parsing if available.
try:
    from mdit_py_plugins.gfm import gfm_plugin
except (
    Exception
):  # pragma: no cover - optional runtime dependency during tests
    gfm_plugin = None  # type: ignore[assignment]
from markupsafe import Markup

from ssg.application.html_headings import demote_top_level_headings
from ssg.application.ports import ContentRenderer
from ssg.domain.site import BuildContext, ContentCollection, Page
from ssg.infrastructure.frontend.media_components import (
    FrontendFragmentRenderer,
)


class MarkdownContentRenderer(ContentRenderer):
    def __init__(
        self, fragment_renderer: FrontendFragmentRenderer | None = None
    ) -> None:
        md = MarkdownIt("commonmark")
        # Enable GFM-style table parsing by preferring the dedicated table
        # plugin, otherwise fall back to the bundled GFM plugin which also
        # provides table parsing.
        if table_plugin is not None:
            md.use(table_plugin)
        elif gfm_plugin is not None:
            md.use(gfm_plugin)
        self._markdown = md
        self._fragment_renderer = (
            fragment_renderer or FrontendFragmentRenderer()
        )

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".md"

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str:
        if context.dependency_tracker is not None:
            context.dependency_tracker.register_dependency(
                page, page.source_path
            )

        source = page.source_path.read_text(encoding="utf-8")
        return self.render_markdown(source, collection, context, page)

    def render_markdown(
        self,
        source: str,
        collection: ContentCollection,
        context: BuildContext,
        page: Page,
    ) -> str:
        transclusions: dict[str, Markup] = {}
        transcluded_source = self._render_transclusions(
            source, collection, context, page, transclusions
        )
        linked_source = self._render_wikilinks(transcluded_source, collection)
        rendered_html = str(self._markdown.render(linked_source))
        return demote_top_level_headings(
            self._replace_transclusions(rendered_html, transclusions)
        )

    def _render_transclusions(
        self,
        source: str,
        collection: ContentCollection,
        context: BuildContext,
        page: Page,
        transclusions: dict[str, Markup],
    ) -> str:
        environment = Environment(autoescape=True, undefined=StrictUndefined)
        template = environment.from_string(source)
        return template.render(
            include_source=lambda source_path: self._include_source(
                collection, source_path, context, page, transclusions
            ),
            embed_video=lambda video_name: self._embed_video(
                collection, context, page, video_name, transclusions
            ),
        )

    def _include_source(
        self,
        collection: ContentCollection,
        source_path: str,
        context: BuildContext,
        page: Page,
        transclusions: dict[str, Markup],
    ) -> Markup:
        resolved_source_path = collection.source_file(source_path)
        if context.dependency_tracker is not None:
            context.dependency_tracker.register_dependency(
                page, resolved_source_path
            )

        source = resolved_source_path.read_text(encoding="utf-8")
        return self._store_transclusion(
            transclusions,
            self._fragment_renderer.render_source_panel(source, source_path),
        )

    def _embed_video(
        self,
        collection: ContentCollection,
        context: BuildContext,
        page: Page,
        video_name: str,
        transclusions: dict[str, Markup],
    ) -> Markup:
        source_path = collection.video_path(video_name).resolve()
        if context.dependency_tracker is not None:
            context.dependency_tracker.register_dependency(page, source_path)

        if not source_path.exists():
            raise FileNotFoundError(
                f"Missing rendered site video {source_path}: expected existing mp4 asset",
            )

        video_output_path = (
            context.output_path
            / collection.output_slug
            / "assets"
            / "videos"
            / source_path.name
        )
        video_output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, video_output_path)
        return self._store_transclusion(
            transclusions,
            self._fragment_renderer.render_video_frame(
                source_path.name, video_name
            ),
        )

    def _store_transclusion(
        self, transclusions: dict[str, Markup], rendered_html: Markup
    ) -> Markup:
        marker = f"SSG_TRANSCLUSION_{len(transclusions)}"
        transclusions[marker] = rendered_html
        return Markup(marker)

    def _replace_transclusions(
        self, rendered_html: str, transclusions: dict[str, Markup]
    ) -> str:
        processed_html = rendered_html
        for marker, transclusion in transclusions.items():
            processed_html = processed_html.replace(
                f"<p>{marker}</p>", str(transclusion)
            )
            processed_html = processed_html.replace(marker, str(transclusion))

        return processed_html

    def _render_wikilinks(
        self, source: str, collection: ContentCollection
    ) -> str:
        pattern = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")
        return pattern.sub(
            lambda match: self._wikilink(match, collection), source
        )

    def _wikilink(
        self, match: re.Match[str], collection: ContentCollection
    ) -> str:
        page_slug = match.group(1)
        label = match.group(2) or page_slug.replace("-", " ").title()
        return f'<a href="{collection.page_href(page_slug)}">{html.escape(label)}</a>'
