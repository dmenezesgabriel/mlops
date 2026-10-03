import base64
import html
import importlib
import json
import re
import secrets
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import nbformat
from markdown_it import MarkdownIt
from markupsafe import Markup
from ssg.application.ports import ContentRenderer, MarkdownRenderer
from ssg.domain import (
    BuildContext,
    ContentCollection,
    Page,
    demote_top_level_headings,
)

from ssg_notebook_render.notebook_fragment_renderer import (
    NotebookFragmentRenderer,
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
# is author text and must reach the Markdown pass verbatim — rendering the
# cell source as a Jinja program evaluated arbitrary expressions and aborted
# the build on undefined names.
_DIRECTIVE_PATTERN = re.compile(
    r"\{\{\s*(include_source|embed_video|embed_image)"
    r'\s*\(\s*(["\'])(.*?)\2\s*\)\s*\}\}'
)

# Jupyter tracebacks carry ANSI SGR color codes; strip them before the text
# reaches the page or it renders as literal escape bytes.
_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _joined_text(value: object) -> str:
    # nbformat stores multi-line output strings as lists of lines
    if isinstance(value, list):
        return "".join(cast(list[str], value))
    return str(value)


def _script_safe_json(payload: object) -> str:
    # A literal "</" inside a JSON string ends the enclosing script element
    # early (payload markup leaks into the DOM); "<\/" is the JSON-legal
    # escape Jupyter/nbconvert embeds use.
    return json.dumps(payload).replace("</", "<\\/")


class NotebookMarkdownRenderer(MarkdownRenderer):
    def __init__(
        self, fragment_renderer: NotebookFragmentRenderer | None = None
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
            fragment_renderer or NotebookFragmentRenderer()
        )

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

        video_path = (
            context.output_path
            / collection.output_slug
            / "assets"
            / "videos"
            / source_path.name
        )
        video_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, video_path)
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

        image_path = (
            context.output_path
            / collection.output_slug
            / "assets"
            / "images"
            / source_path.name
        )
        image_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, image_path)
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


class NotebookContentRenderer(ContentRenderer):
    def __init__(
        self,
        markdown_renderer: MarkdownRenderer | None = None,
        fragment_renderer: NotebookFragmentRenderer | None = None,
    ) -> None:
        self._fragment_renderer = (
            fragment_renderer or NotebookFragmentRenderer()
        )
        self._markdown_renderer = (
            markdown_renderer
            or NotebookMarkdownRenderer(self._fragment_renderer)
        )

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".ipynb"

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str:
        if context.dependency_tracker is not None:
            context.dependency_tracker.register_dependency(
                page, page.source_path
            )

        # nbformat's NotebookNode tree is untyped JSON; treating it as Any
        # keeps every downstream cell/metadata access honest about that.
        try:
            notebook = cast(
                Any,
                nbformat.read(  # pyright: ignore[reportUnknownMemberType]
                    page.source_path, as_version=4
                ),
            )
        except nbformat.ValidationError as exc:
            # ValidationError is a plain Exception — without the wrap it
            # escapes the CLI's user-facing error catch as a traceback.
            raise ValueError(
                f"Invalid notebook {page.source_path}: {exc}"
            ) from exc
        rendered_cells = [
            self._render_cell(cell, collection, page, context, index)
            for index, cell in enumerate(notebook.cells)
        ]
        html_content = "\n".join(rendered_cells)

        widgets_metadata = notebook.metadata.get("widgets", {})
        widget_state = widgets_metadata.get(
            "application/vnd.jupyter.widget-state+json", None
        )
        if widget_state:
            state_json = _script_safe_json(widget_state)
            widget_state_html = f'<script type="application/vnd.jupyter.widget-state+json">{state_json}</script>'
            html_content = widget_state_html + "\n" + html_content

        return html_content

    def _render_cell(
        self,
        cell: object,
        collection: ContentCollection,
        page: Page,
        context: BuildContext,
        cell_index: int,
    ) -> str:
        cell_type = getattr(cell, "cell_type", "")
        source = str(getattr(cell, "source", ""))
        if cell_type == "markdown":
            return self._markdown_renderer.render_markdown(
                source, collection, context, page
            )

        if cell_type == "code":
            outputs = self._render_outputs(
                cell,
                page,
                context.output_path / collection.output_slug,
                cell_index,
            )
            return self._fragment_renderer.render_code_cell(
                source, cell_index, outputs
            )

        return ""

    def _render_outputs(
        self,
        cell: object,
        page: Page,
        output_path: Path,
        cell_index: int,
    ) -> str:
        outputs = getattr(cell, "outputs", [])
        rendered_outputs = [
            self._render_output(
                output, page, output_path, cell_index, output_index
            )
            for output_index, output in enumerate(outputs)
        ]
        return "\n".join(rendered_outputs)

    def _render_output(
        self,
        output: object,
        page: Page,
        output_path: Path,
        cell_index: int,
        output_index: int,
    ) -> str:
        output_type = getattr(output, "output_type", "")
        if output_type == "stream":
            return self._fragment_renderer.render_stream_output(
                _joined_text(getattr(output, "text", ""))
            )
        if output_type == "error":
            return self._render_error_output(output)

        # nbformat validates `data` is a MIME-bundle dict at read time, so
        # anything reaching here is already a dict.
        return self._render_data_output(
            getattr(output, "data", {}),
            page,
            output_path,
            cell_index,
            output_index,
        )

    def _render_error_output(self, output: object) -> str:
        ename = str(getattr(output, "ename", ""))
        evalue = str(getattr(output, "evalue", ""))
        traceback_text = _joined_text(getattr(output, "traceback", ""))
        detail = _ANSI_PATTERN.sub("", f"{ename}: {evalue}\n{traceback_text}")
        return self._fragment_renderer.render_error_output(detail)

    def _render_data_output(
        self,
        data_map: dict[str, Any],
        page: Page,
        output_path: Path,
        cell_index: int,
        output_index: int,
    ) -> str:
        if "application/vnd.jupyter.widget-view+json" in data_map:
            widget_view = data_map["application/vnd.jupyter.widget-view+json"]
            return self._fragment_renderer.render_widget_view_output(
                _script_safe_json(widget_view)
            )

        if "text/html" in data_map:
            return self._fragment_renderer.render_html_output(
                _joined_text(data_map["text/html"])
            )

        if "image/svg+xml" in data_map:
            return self._fragment_renderer.render_svg_output(
                _joined_text(data_map["image/svg+xml"])
            )

        if "image/png" in data_map:
            return self._write_image_output(
                data_map["image/png"],
                "png",
                page,
                output_path,
                cell_index,
                output_index,
            )

        if "image/jpeg" in data_map:
            return self._write_image_output(
                data_map["image/jpeg"],
                "jpeg",
                page,
                output_path,
                cell_index,
                output_index,
            )

        if "text/plain" in data_map:
            return self._fragment_renderer.render_text_output(
                _joined_text(data_map["text/plain"])
            )

        # Sole-MIME JSON outputs render as text rather than dropping; a
        # text/plain sibling stays the preferred representation.
        if "application/json" in data_map:
            return self._fragment_renderer.render_text_output(
                json.dumps(data_map["application/json"], indent=2, default=str)
            )

        return ""

    def _write_image_output(
        self,
        encoded_image: object,
        extension: str,
        page: Page,
        output_path: Path,
        cell_index: int,
        output_index: int,
    ) -> str:
        image_name = (
            f"{page.slug}-cell-{cell_index}-output-{output_index}.{extension}"
        )
        image_path = output_path / "assets" / "images" / image_name
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(base64.b64decode(str(encoded_image)))
        return self._fragment_renderer.render_image_output(image_name)


def create_notebook_content_renderer() -> NotebookContentRenderer:
    return NotebookContentRenderer()
