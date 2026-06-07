import html
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined
from markupsafe import Markup


class NotebookFragmentRenderer:
    def __init__(self) -> None:
        self._environment = Environment(
            autoescape=True,
            loader=PackageLoader("ssg_notebook_render", "templates"),
            undefined=StrictUndefined,
        )

    def render_source_panel(self, source: str, source_path: str) -> Markup:
        return Markup(
            self._render_template(
                "source_panel.html",
                source=Markup(html.escape(source)),
                source_path=source_path,
                language_class=self._language_class_for_source(source_path),
            )
        )

    def render_video_frame(self, video_source: str, video_name: str) -> Markup:
        return Markup(
            self._render_template(
                "video_frame.html",
                video_source=video_source,
                video_name=video_name.replace("_", " ").title(),
            )
        )

    def render_image_frame(self, image_source: str, image_name: str) -> Markup:
        return Markup(
            self._render_template(
                "image_frame.html",
                image_source=image_source,
                image_name=image_name.replace("_", " ").title(),
            )
        )

    def render_code_cell(
        self, source: str, cell_index: int, outputs: str
    ) -> str:
        return self._render_template(
            "notebook_code_cell.html",
            source=Markup(html.escape(source)),
            cell_index=cell_index,
            outputs=Markup(outputs),
        )

    def render_stream_output(self, text: str) -> str:
        return self._render_output("Stream", text)

    def render_text_output(self, text: str) -> str:
        return self._render_output("Result", text)

    def render_image_output(self, image_name: str) -> str:
        return self._render_template(
            "notebook_image_output.html", image_name=image_name
        )

    def render_html_output(self, html_content: str) -> str:
        return self._render_template(
            "notebook_html_output.html",
            html_content=Markup(html_content),
        )

    def render_widget_view_output(self, widget_view_json: str) -> str:
        return self._render_template(
            "notebook_widget_view_output.html",
            widget_view_json=Markup(widget_view_json),
        )

    def _render_output(self, output_label: str, text: str) -> str:
        return self._render_template(
            "notebook_output.html",
            output_label=output_label,
            output=Markup(html.escape(text)),
        )

    def _render_template(self, template_name: str, **context: object) -> str:
        return self._environment.get_template(template_name).render(**context)

    def _language_class_for_source(self, source_path: str) -> str:
        suffix_languages = {
            ".py": "python",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".sql": "sql",
            ".sh": "bash",
            ".json": "json",
        }
        language = suffix_languages.get(
            Path(source_path).suffix.lower(), "text"
        )
        return f"language-{language}"
