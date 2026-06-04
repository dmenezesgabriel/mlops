import re


def demote_top_level_headings(rendered_html: str) -> str:
    """Keep generated pages to one document h1 by demoting article body h1 tags.

    Example:
        demote_top_level_headings("<h1>Intro</h1>")
    """
    opening_tags_demoted = re.sub(r"<h1(\s[^>]*)?>", r"<h2\1>", rendered_html)
    return opening_tags_demoted.replace("</h1>", "</h2>")
