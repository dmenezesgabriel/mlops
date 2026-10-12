import html
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined
from markupsafe import Markup


class FrontendFragmentRenderer:
    def __init__(self) -> None:
        # autoescape=True: the safe setup this Flask audit rule asks for
        self._environment = Environment(  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
            autoescape=True,
            loader=PackageLoader("ssg.infrastructure.frontend", "templates"),
            undefined=StrictUndefined,
        )

    def render_source_panel(self, source: str, source_path: str) -> Markup:
        # html.escape is the explicit escaping boundary for `source`
        escaped_source = Markup(html.escape(source))  # nosec B704  # nosemgrep: python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup
        rendered = self._environment.get_template(
            "fragments/source_panel.html"
        ).render(
            source=escaped_source,
            source_path=source_path,
            language_class=self._language_class_for_source(source_path),
        )
        # autoescape=True: the rendered output is already escaped
        return Markup(rendered)  # nosec B704  # nosemgrep: python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup

    def render_video_frame(self, video_source: str, video_name: str) -> Markup:
        rendered = self._environment.get_template(
            "fragments/video_frame.html"
        ).render(
            video_source=video_source,
            video_name=video_name.replace("_", " ").title(),
        )
        # autoescape=True: the rendered output is already escaped
        return Markup(rendered)  # nosec B704  # nosemgrep: python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup

    def render_image_frame(self, image_source: str, image_name: str) -> Markup:
        rendered = self._environment.get_template(
            "fragments/image_frame.html"
        ).render(
            image_source=image_source,
            image_name=image_name.replace("_", " ").title(),
        )
        # autoescape=True: the rendered output is already escaped
        return Markup(rendered)  # nosec B704  # nosemgrep: python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup

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
