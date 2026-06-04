import html
import re
import shutil
from pathlib import Path

from jinja2 import Environment, StrictUndefined
from markdown_it import MarkdownIt
from markupsafe import Markup

from ssg.application.html_headings import demote_top_level_headings
from ssg.application.ports import ContentRenderer
from ssg.domain.site import ContentCollection, Page


class MarkdownContentRenderer(ContentRenderer):
    def __init__(self) -> None:
        self._markdown = MarkdownIt("commonmark")

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".md"

    def render(self, collection: ContentCollection, page: Page, output_path: Path) -> str:
        source = page.source_path.read_text(encoding="utf-8")
        return self.render_markdown(source, collection, output_path)

    def render_markdown(
        self,
        source: str,
        collection: ContentCollection,
        output_path: Path,
    ) -> str:
        transcluded_source = self._render_transclusions(source, collection, output_path)
        linked_source = self._render_wikilinks(transcluded_source, collection)
        return demote_top_level_headings(str(self._markdown.render(linked_source)))

    def _render_transclusions(
        self,
        source: str,
        collection: ContentCollection,
        output_path: Path,
    ) -> str:
        environment = Environment(autoescape=True, undefined=StrictUndefined)
        template = environment.from_string(source)
        return template.render(
            include_source=lambda source_path: self._include_source(collection, source_path),
            embed_video=lambda video_name: self._embed_video(collection, output_path, video_name),
        )

    def _include_source(self, collection: ContentCollection, source_path: str) -> Markup:
        source = collection.source_file(source_path).read_text(encoding="utf-8")
        return Markup(f"<pre><code>{html.escape(source)}</code></pre>")

    def _embed_video(
        self,
        collection: ContentCollection,
        output_path: Path,
        video_name: str,
    ) -> Markup:
        source_path = collection.video_path(video_name).resolve()
        if not source_path.exists():
            raise FileNotFoundError(
                f"Missing rendered site video {source_path}: expected existing mp4 asset",
            )

        video_output_path = output_path / "assets" / "videos" / source_path.name
        video_output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, video_output_path)
        video_source = html.escape(source_path.name)
        return Markup(f'<video controls src="assets/videos/{video_source}"></video>')

    def _render_wikilinks(self, source: str, collection: ContentCollection) -> str:
        pattern = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")
        return pattern.sub(lambda match: self._wikilink(match, collection), source)

    def _wikilink(self, match: re.Match[str], collection: ContentCollection) -> str:
        page_slug = match.group(1)
        label = match.group(2) or page_slug.replace("-", " ").title()
        return f'<a href="{collection.page_href(page_slug)}">{html.escape(label)}</a>'
