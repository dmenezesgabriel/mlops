import html

from markupsafe import Markup


def render_source_panel(source: str, source_path: str) -> Markup:
    escaped_source = html.escape(source)
    escaped_path = html.escape(source_path)
    return Markup(
        '<figure class="source-panel story-step">'
        '<figcaption><span class="data-label">Source</span>'
        f'<span class="source-panel__path">{escaped_path}</span></figcaption>'
        f"<pre><code>{escaped_source}</code></pre>"
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


def render_notebook_code_cell(source: str, cell_index: int, outputs: str) -> str:
    escaped_source = html.escape(source)
    return (
        '<section class="notebook-cell story-step">'
        f"{_notebook_cell_header('Code', cell_index)}"
        '<div class="notebook-input">'
        f"<pre><code>{escaped_source}</code></pre>"
        "</div>"
        f"{outputs}"
        "</section>"
    )


def render_notebook_stream_output(text: str) -> str:
    return _notebook_output("Stream", html.escape(text))


def render_notebook_text_output(text: str) -> str:
    return _notebook_output("Result", html.escape(text))


def render_notebook_image_output(image_name: str) -> str:
    escaped_image_name = html.escape(image_name)
    return (
        '<figure class="media-frame notebook-image story-step">'
        f'<img src="assets/images/{escaped_image_name}" alt="Notebook output image">'
        '<figcaption><span class="data-label">Chart</span>Notebook output image</figcaption>'
        "</figure>"
    )


def _notebook_cell_header(cell_type: str, cell_index: int) -> str:
    escaped_type = html.escape(cell_type)
    return (
        '<header class="notebook-cell__header">'
        f'<span class="notebook-cell__index">Cell {cell_index + 1:02d}</span>'
        f'<span class="data-label">{escaped_type}</span>'
        "</header>"
    )


def _notebook_output(output_label: str, escaped_output: str) -> str:
    escaped_label = html.escape(output_label)
    return (
        '<div class="notebook-output">'
        f'<span class="notebook-output__label">{escaped_label}</span>'
        f"<pre><code>{escaped_output}</code></pre>"
        "</div>"
    )
