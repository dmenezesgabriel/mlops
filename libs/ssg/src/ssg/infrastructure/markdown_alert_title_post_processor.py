import html
import re

from ssg.application.ports import HtmlPostProcessor
from ssg.domain import Site

# markdown-it's `alerts` option emits a fixed shape: a div per kind whose
# first paragraph carries the capitalized English kind
# (markdown_it/rules_block/blockquote.py). Localizing the title means
# rewriting that paragraph's text — only post-processors see the site
# variant's i18n extension settings.
_TITLE_PATTERN = re.compile(
    r'<p class="markdown-alert-title">(Note|Tip|Important|Warning|Caution)</p>'
)


# Octicon-shaped per-kind glyphs (GitHub's own alert icon vocabulary),
# styled through `currentColor` so each alert's accent var drives the fill.
def _icon(path: str) -> str:
    return (
        '<svg class="markdown-alert-icon" viewBox="0 0 16 16" width="16" '
        'height="16" fill="currentColor" aria-hidden="true">'
        f"{path}</svg>"
    )


_ICONS = {
    "note": _icon(
        '<path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a1.5 1.5 0 1 0 0 3 '
        "1.5 1.5 0 0 0 0-3ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 "
        ".75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25"
        'a.75.75 0 0 1-.75-.75Z"/>'
    ),
    "tip": _icon(
        '<path d="M8 1.5c-2.363 0-4 1.69-4 4 0 1.033.43 1.904 1.27 2.765.184'
        ".19.383.387.582.594l.002.002c.147.152.31.316.471.486.267.284.514.583"
        ".727.87.212.287.398.576.516.848.153.356.259.705.322 1.045l-.002.003a4"
        ".648 4.648 0 0 1 .059.462l.001.003c.011.19.02.395.029.615l.002.004c"
        ".011.271.023.559.04.864a.748.748 0 0 0 .055.388l.005.008c.03.072.077"
        ".134.135.192a.75.75 0 0 0 .498.217h.001a.75.75 0 0 0 .494-.163.75.75"
        " 0 0 0 .14-.14l.005-.009a.75.75 0 0 0 .058-.395l.001-.004c.017-.305"
        ".029-.594.04-.864l.002-.004c.01-.22.02-.425.03-.615v-.004a4.65 4.65 0"
        " 0 1 .06-.462 4.84 4.84 0 0 1 .322-1.045 6.73 6.73 0 0 1 .516-.848c"
        ".213-.287.46-.586.727-.87.16-.17.323-.335.471-.486l.002-.002c.2-.207"
        ".398-.404.582-.594.84-.861 1.27-1.732 1.27-2.765 0-2.31-1.637-4-4-4Z"
        "m-1.44 13.445a.75.75 0 0 0-.75.75v.355c-.004.018-.007.03-.011.043a1"
        ".48 1.48 0 0 1-.007.096c-.006.065-.016.126-.03.185a1.5 1.5 0 0 1-.055"
        ".143 1.59 1.59 0 0 1-.062.114 1.6 1.6 0 0 1-.07.104 1.49 1.49 0 0 1-.1"
        ".115 1.58 1.58 0 0 1-.09.093 1.48 1.48 0 0 1-.104.087 1.58 1.58 0 0 1"
        "-.116.074 1.45 1.45 0 0 1-.12.073 1.5 1.5 0 0 1-.136.064 1.55 1.55 0 0"
        " 1-.131.05 1.45 1.45 0 0 1-.139.041 1.48 1.48 0 0 1-.144.026 1.44 1.44"
        " 0 0 1-.145.014c-.178.006-.352-.007-.528-.045a.74.74 0 0 1-.048-.012.75"
        ".75 0 0 0-.705.282.75.75 0 0 0 .26 1.103c.244.14.55.23.885.242a3.1 3"
        ".1 0 0 0 .585-.05 3.14 3.14 0 0 0 .535-.148 3.16 3.16 0 0 0 .476-.22c"
        ".155-.086.306-.184.447-.293a3.15 3.15 0 0 0 .39-.36 3.13 3.13 0 0 0 "
        ".313-.437 3.18 3.18 0 0 0 .219-.5 3.16 3.16 0 0 0 .113-.508 3.12 3.12"
        ' 0 0 0 .024-.507v-.362a.75.75 0 0 0-.75-.75Z"/>'
    ),
    "important": _icon(
        '<path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v9'
        ".5A1.75 1.75 0 0 1 14.25 13H8.06l-2.573 2.573A1.458 1.458 0 0 1 3 14"
        ".543V13H1.75A1.75 1.75 0 0 1 0 11.25Zm1.75-.25a.25.25 0 0 0-.25.25v9"
        ".5c0 .138.112.25.25.25h2a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749"
        " 0 0 1 .53-.22h6.5a.25.25 0 0 0 .25-.25v-9.5a.25.25 0 0 0-.25-.25Zm7"
        " 2.25v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 9a1 1 0 1 1-2"
        ' 0 1 1 0 0 1 2 0Z"/>'
    ),
    "warning": _icon(
        '<path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75'
        " 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a"
        ".25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0"
        " 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0Z"
        'M9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"/>'
    ),
    "caution": _icon(
        '<path d="M4.47.22A.749.749 0 0 1 5 0h6c.199 0 .389.079.53.22l4.25 4.25'
        "c.141.141.22.331.22.53v6a.749.749 0 0 1-.22.53l-4.25 4.25a.749.749 0 0"
        " 1-.53.22H5a.749.749 0 0 1-.53-.22L.22 11.53A.749.749 0 0 1 0 11V5c0-"
        ".199.079-.389.22-.53Zm.84 1.28L1.5 5.31v5.38l3.81 3.81h5.38l3.81-3.81V"
        "5.31L10.69 1.5ZM8 4a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A"
        '.75.75 0 0 1 8 4Zm0 8a1 1 0 1 1 0-2 1 1 0 0 1 2 0Z"/>'
    ),
}


class MarkdownAlertTitlePostProcessor(HtmlPostProcessor):
    """Localize GitHub-alert titles and prepend each kind's icon.

    markdown-it renders `> [!NOTE]`-style alerts with a fixed English title;
    the translated chrome label comes from the variant's i18n extension
    settings, which renderers cannot see — only post-processors receive the
    localized `Site`.

    Example:
        MarkdownAlertTitlePostProcessor().process(body_html, site_variant)
    """

    def process(self, rendered_html: str, site: Site) -> str:
        if "markdown-alert-title" not in rendered_html:
            return rendered_html
        return _TITLE_PATTERN.sub(
            lambda match: _localized_title(match, site), rendered_html
        )


def _localized_title(match: re.Match[str], site: Site) -> str:
    kind = match.group(1).lower()
    label = site.extension_setting(
        "i18n", f"label_alert_{kind}", match.group(1)
    )
    return (
        '<p class="markdown-alert-title">'
        f"{_ICONS[kind]}{html.escape(label)}</p>"
    )
