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
from ssg.infrastructure.frontend.media_components import FrontendFragmentRenderer


class MarkdownContentRenderer(ContentRenderer):
    def __init__(self, fragment_renderer: FrontendFragmentRenderer | None = None) -> None:
        self._markdown = MarkdownIt("commonmark")
        self._fragment_renderer = fragment_renderer or FrontendFragmentRenderer()

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
        transclusions: dict[str, Markup] = {}
        transcluded_source = self._render_transclusions(
            source, collection, output_path, transclusions
        )
        linked_source = self._render_wikilinks(transcluded_source, collection)
        rendered_html = str(self._markdown.render(linked_source))
        return demote_top_level_headings(self._replace_transclusions(rendered_html, transclusions))

    def _render_transclusions(
        self,
        source: str,
        collection: ContentCollection,
        output_path: Path,
        transclusions: dict[str, Markup],
    ) -> str:
        environment = Environment(autoescape=True, undefined=StrictUndefined)
        template = environment.from_string(source)
        return template.render(
            include_source=lambda source_path: self._include_source(
                collection, source_path, transclusions
            ),
            embed_video=lambda video_name: self._embed_video(
                collection, output_path, video_name, transclusions
            ),
        )

    def _include_source(
        self,
        collection: ContentCollection,
        source_path: str,
        transclusions: dict[str, Markup],
    ) -> Markup:
        source = collection.source_file(source_path).read_text(encoding="utf-8")
        return self._store_transclusion(
            transclusions,
            self._fragment_renderer.render_source_panel(source, source_path),
        )

    def _embed_video(
        self,
        collection: ContentCollection,
        output_path: Path,
        video_name: str,
        transclusions: dict[str, Markup],
    ) -> Markup:
        source_path = collection.video_path(video_name).resolve()
        if not source_path.exists():
            raise FileNotFoundError(
                f"Missing rendered site video {source_path}: expected existing mp4 asset",
            )

        video_output_path = output_path / "assets" / "videos" / source_path.name
        video_output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, video_output_path)
        return self._store_transclusion(
            transclusions,
            self._fragment_renderer.render_video_frame(source_path.name, video_name),
        )

    def _store_transclusion(
        self, transclusions: dict[str, Markup], rendered_html: Markup
    ) -> Markup:
        marker = f"SSG_TRANSCLUSION_{len(transclusions)}"
        transclusions[marker] = rendered_html
        return Markup(marker)

    def _replace_transclusions(self, rendered_html: str, transclusions: dict[str, Markup]) -> str:
        processed_html = rendered_html
        for marker, transclusion in transclusions.items():
            processed_html = processed_html.replace(f"<p>{marker}</p>", str(transclusion))
            processed_html = processed_html.replace(marker, str(transclusion))

        return processed_html

    def _render_wikilinks(self, source: str, collection: ContentCollection) -> str:
        pattern = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")
        return pattern.sub(lambda match: self._wikilink(match, collection), source)

    def _wikilink(self, match: re.Match[str], collection: ContentCollection) -> str:
        page_slug = match.group(1)
        label = match.group(2) or page_slug.replace("-", " ").title()
        return f'<a href="{collection.page_href(page_slug)}">{html.escape(label)}</a>'
