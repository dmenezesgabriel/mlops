import base64
import html
import re
import shutil
from pathlib import Path

import nbformat
from jinja2 import Environment, StrictUndefined
from markdown_it import MarkdownIt
from markupsafe import Markup
from ssg.application.ports import ContentRenderer, MarkdownRenderer
from ssg.domain.site import ContentCollection, Page


class NotebookMarkdownRenderer(MarkdownRenderer):
    def __init__(self) -> None:
        self._markdown = MarkdownIt("commonmark")

    def render_markdown(
        self,
        source: str,
        collection: ContentCollection,
        output_path: Path,
    ) -> str:
        transcluded_source = self._render_transclusions(source, collection, output_path)
        linked_source = self._render_wikilinks(transcluded_source, collection)
        return str(self._markdown.render(linked_source))

    def _render_transclusions(
        self,
        source: str,
        collection: ContentCollection,
        output_path: Path,
    ) -> str:
        environment = Environment(autoescape=True, undefined=StrictUndefined)
        template = environment.from_string(source)
        return template.render(
            include_source=lambda path: self._include_source(collection, path),
            embed_video=lambda name: self._embed_video(collection, output_path, name),
        )

    def _include_source(self, collection: ContentCollection, source_path: str) -> Markup:
        source = collection.source_file(source_path).read_text(encoding="utf-8")
        return Markup(f"<pre><code>{html.escape(source)}</code></pre>")

    def _embed_video(
        self, collection: ContentCollection, output_path: Path, video_name: str
    ) -> Markup:
        source_path = collection.video_path(video_name).resolve()
        if not source_path.exists():
            raise FileNotFoundError(
                f"Missing rendered site video {source_path}: expected existing mp4 asset",
            )

        video_path = output_path / "assets" / "videos" / source_path.name
        video_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, video_path)
        return Markup(
            f'<video controls src="assets/videos/{html.escape(source_path.name)}"></video>'
        )

    def _render_wikilinks(self, source: str, collection: ContentCollection) -> str:
        pattern = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")
        return pattern.sub(lambda match: self._wikilink(match, collection), source)

    def _wikilink(self, match: re.Match[str], collection: ContentCollection) -> str:
        page_slug = match.group(1)
        label = match.group(2) or page_slug.replace("-", " ").title()
        return f'<a href="{collection.page_href(page_slug)}">{html.escape(label)}</a>'


class NotebookContentRenderer(ContentRenderer):
    def __init__(self, markdown_renderer: MarkdownRenderer | None = None) -> None:
        self._markdown_renderer = markdown_renderer or NotebookMarkdownRenderer()

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".ipynb"

    def render(self, collection: ContentCollection, page: Page, output_path: Path) -> str:
        notebook = nbformat.read(page.source_path, as_version=4)
        rendered_cells = [
            self._render_cell(cell, collection, page, output_path, index)
            for index, cell in enumerate(notebook.cells)
        ]
        return "\n".join(rendered_cells)

    def _render_cell(
        self,
        cell: object,
        collection: ContentCollection,
        page: Page,
        output_path: Path,
        cell_index: int,
    ) -> str:
        cell_type = getattr(cell, "cell_type", "")
        source = str(getattr(cell, "source", ""))
        if cell_type == "markdown":
            return self._markdown_renderer.render_markdown(source, collection, output_path)

        if cell_type == "code":
            outputs = self._render_outputs(cell, page, output_path, cell_index)
            return f"<pre><code>{html.escape(source)}</code></pre>\n{outputs}"

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
            self._render_output(output, page, output_path, cell_index, output_index)
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
            return f"<pre><code>{html.escape(str(getattr(output, 'text', '')))}</code></pre>"

        data = getattr(output, "data", {})
        if isinstance(data, dict) and "image/png" in data:
            return self._write_png_output(
                data["image/png"], page, output_path, cell_index, output_index
            )

        if isinstance(data, dict) and "text/plain" in data:
            return f"<pre><code>{html.escape(str(data['text/plain']))}</code></pre>"

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
        return f'<img src="assets/images/{image_name}" alt="Notebook output image">'


def create_notebook_content_renderer() -> NotebookContentRenderer:
    return NotebookContentRenderer()
