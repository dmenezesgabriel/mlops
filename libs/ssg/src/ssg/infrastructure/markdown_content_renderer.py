import html
import importlib
import re
import secrets
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import cast

from markdown_it import MarkdownIt
from markupsafe import Markup

from ssg.application.ports import ContentRenderer
from ssg.domain import (
    BuildContext,
    ContentCollection,
    Page,
    demote_top_level_headings,
)
from ssg.infrastructure.frontend.media_components import (
    FrontendFragmentRenderer,
)

# mdit_py_plugins.table exists only in some releases (absent in 0.6.1); the
# GFM plugin below provides table parsing there. Bindings are declared first
# so the optional import never leaves an Unknown-typed symbol.
table_plugin: Callable[[MarkdownIt], None] | None = None
gfm_plugin: Callable[[MarkdownIt], None] | None = None
try:
    # Prefer the explicit table plugin when available; import_module keeps
    # the optional boundary typed since the submodule may not exist.
    table_plugin = cast(
        Callable[[MarkdownIt], None],
        getattr(
            importlib.import_module("mdit_py_plugins.table"),
            "table_plugin",
            None,
        ),
    )
except (
    Exception
):  # pragma: no cover - optional runtime dependency during tests
    pass
try:
    from mdit_py_plugins.gfm import gfm_plugin as _gfm_plugin
except (
    Exception
):  # pragma: no cover - optional runtime dependency during tests
    pass
else:
    gfm_plugin = _gfm_plugin

# Directives are the only template surface (docs/ssg/ssg.md): calls shaped
# `{{ helper("arg") }}` are extracted and run; every other `{{ … }}`/`{% … %}`
# is author text and must reach the Markdown pass verbatim — rendering the page
# source as a Jinja program evaluated arbitrary expressions and aborted the
# build on undefined names.
_DIRECTIVE_PATTERN = re.compile(
    r"\{\{\s*(include_source|embed_video|embed_image)"
    r'\s*\(\s*(["\'])(.*?)\2\s*\)\s*\}\}'
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
        def replace(match: re.Match[str]) -> str:
            directive, argument = match.group(1), match.group(3)
            if directive == "include_source":
                return self._include_source(
                    collection, argument, context, page, transclusions
                )
            if directive == "embed_video":
                return self._embed_video(
                    collection, context, page, argument, transclusions
                )
            return self._embed_image(
                collection, context, page, argument, transclusions
            )

        return _DIRECTIVE_PATTERN.sub(replace, source)

    def _include_source(
        self,
        collection: ContentCollection,
        source_path: str,
        context: BuildContext,
        page: Page,
        transclusions: dict[str, Markup],
    ) -> str:
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
    ) -> str:
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

    def _embed_image(
        self,
        collection: ContentCollection,
        context: BuildContext,
        page: Page,
        image_name: str,
        transclusions: dict[str, Markup],
    ) -> str:
        source_path = collection.image_path(image_name).resolve()
        if context.dependency_tracker is not None:
            context.dependency_tracker.register_dependency(page, source_path)

        if not source_path.exists():
            raise FileNotFoundError(
                f"Missing rendered site image {source_path}: expected existing png/jpg asset",
            )

        image_output_path = (
            context.output_path
            / collection.output_slug
            / "assets"
            / "images"
            / source_path.name
        )
        image_output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, image_output_path)
        return self._store_transclusion(
            transclusions,
            self._fragment_renderer.render_image_frame(
                source_path.name, image_name
            ),
        )

    def _store_transclusion(
        self, transclusions: dict[str, Markup], rendered_html: Markup
    ) -> str:
        # A random marker id keeps literal "SSG_TRANSCLUSION_…" author text
        # from colliding with a generated marker during _replace_transclusions.
        marker = f"SSG_TRANSCLUSION_{secrets.token_hex(8)}"
        transclusions[marker] = rendered_html
        return marker

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
