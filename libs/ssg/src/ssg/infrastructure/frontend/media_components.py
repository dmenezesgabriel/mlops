import html
from pathlib import Path

from markupsafe import Markup


def render_source_panel(source: str, source_path: str) -> Markup:
    escaped_source = html.escape(source)
    escaped_path = html.escape(source_path)
    language_class = _language_class_for_source(source_path)
    return Markup(
        '<figure class="source-panel story-step">'
        '<figcaption><span class="data-label">Source</span>'
        f'<span class="source-panel__path">{escaped_path}</span></figcaption>'
        f'<pre><code class="{language_class}">{escaped_source}</code></pre>'
        "</figure>"
    )


def render_video_frame(video_source: str, video_name: str) -> Markup:
    escaped_source = html.escape(video_source)
    escaped_name = html.escape(video_name.replace("_", " ").title())
    return Markup(
        '<figure class="media-frame video-frame story-step">'
        f'<video controls src="assets/videos/{escaped_source}"></video>'
        f'<figcaption><span class="data-label">Video</span>{escaped_name}</figcaption>'
        "</figure>"
    )


def _language_class_for_source(source_path: str) -> str:
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
    language = suffix_languages.get(Path(source_path).suffix.lower(), "text")
    return f"language-{language}"
