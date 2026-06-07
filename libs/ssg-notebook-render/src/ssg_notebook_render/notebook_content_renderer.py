import base64
import html
import re
import shutil
from pathlib import Path

import nbformat
from jinja2 import Environment, StrictUndefined
from markdown_it import MarkdownIt
from markupsafe import Markup
from ssg.application.html_headings import demote_top_level_headings
from ssg.application.ports import ContentRenderer, MarkdownRenderer
from ssg.domain.site import BuildContext, ContentCollection, Page

from ssg_notebook_render.notebook_fragment_renderer import (
    NotebookFragmentRenderer,
)


class NotebookMarkdownRenderer(MarkdownRenderer):
    def __init__(
        self, fragment_renderer: NotebookFragmentRenderer | None = None
    ) -> None:
        self._markdown = MarkdownIt("commonmark")
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
        environment = Environment(autoescape=True, undefined=StrictUndefined)
        template = environment.from_string(source)
        return template.render(
            include_source=lambda source_path: self._include_source(
                collection, source_path, context, page, transclusions
            ),
            embed_video=lambda video_name: self._embed_video(
                collection, context, page, video_name, transclusions
            ),
            embed_image=lambda image_name: self._embed_image(
                collection, context, page, image_name, transclusions
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

    def _resolve_output_path(
        self, base_output_path: Path, source_path: Path
    ) -> Path:
        parts = source_path.parts
        if "generated-i18n" in parts:
            index = parts.index("generated-i18n")
            if index + 1 < len(parts):
                return base_output_path / parts[index + 1]
        return base_output_path

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

        video_path = (
            self._resolve_output_path(context.output_path, page.source_path)
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
    ) -> Markup:
        source_path = collection.image_path(image_name).resolve()
        if context.dependency_tracker is not None:
            context.dependency_tracker.register_dependency(page, source_path)

        if not source_path.exists():
            raise FileNotFoundError(
                f"Missing rendered site image {source_path}: expected existing png/jpg asset",
            )

        image_path = (
            self._resolve_output_path(context.output_path, page.source_path)
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

        notebook = nbformat.read(page.source_path, as_version=4)
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
            import json

            state_json = json.dumps(widget_state)
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
            stream_text = getattr(output, "text", "")
            if isinstance(stream_text, list):
                stream_text = "".join(stream_text)
            return self._fragment_renderer.render_stream_output(
                str(stream_text)
            )

        data = getattr(output, "data", {})
        if not isinstance(data, dict):
            return ""

        if "application/vnd.jupyter.widget-view+json" in data:
            import json

            widget_view = data["application/vnd.jupyter.widget-view+json"]
            return self._fragment_renderer.render_widget_view_output(
                json.dumps(widget_view)
            )

        if "text/html" in data:
            html_content = data["text/html"]
            if isinstance(html_content, list):
                html_content = "".join(html_content)
            return self._fragment_renderer.render_html_output(
                str(html_content)
            )

        if "image/png" in data:
            return self._write_png_output(
                data["image/png"], page, output_path, cell_index, output_index
            )

        if "text/plain" in data:
            plain_text = data["text/plain"]
            if isinstance(plain_text, list):
                plain_text = "".join(plain_text)
            return self._fragment_renderer.render_text_output(str(plain_text))

        return ""

    def _write_png_output(
        self,
        encoded_png: object,
        page: Page,
        output_path: Path,
        cell_index: int,
        output_index: int,
    ) -> str:
        image_name = f"{page.slug}-cell-{cell_index}-output-{output_index}.png"
        image_path = output_path / "assets" / "images" / image_name
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(base64.b64decode(str(encoded_png)))
        return self._fragment_renderer.render_image_output(image_name)


def create_notebook_content_renderer() -> NotebookContentRenderer:
    return NotebookContentRenderer()
