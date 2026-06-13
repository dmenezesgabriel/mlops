import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ssg_i18n.application.translation import TextTranslator
from ssg_i18n.domain.locale import Locale

PROTECTED_PATTERN = re.compile(
    r"(`[^`]+`|https?://\S+|\$\$.*?\$\$|(?<!\$)\$[^\$\s](?:[^\$]*?[^\$\s])?\$(?!\d))",
    re.DOTALL,
)
WIKILINK_PATTERN = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")

# Matches the leading whitespace + list marker on a list item line.
# Captured as group(1) so it can be stripped before translation and re-added after.
LIST_PREFIX_PATTERN = re.compile(r"^(\s*(?:[*\-+]|\d+\.)\s+)(.*)", re.DOTALL)

# Match bold (**…**) before italic (*…*) to avoid treating ** as two * markers.
INLINE_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
INLINE_ITALIC_PATTERN = re.compile(
    r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL
)

# _protect_inline_markup was removed — replaced by _pre_translate_inline_spans
# (an instance method) which pre-translates each span's content and stores the
# fully-reconstructed replacement as a single-occurrence marker in protected_parts.


def _strip_list_prefix(line: str) -> tuple[str, str]:
    """Return (prefix, body) by splitting off any leading list marker.

    The prefix (e.g. '    *   ') is preserved verbatim so it can be
    re-appended after translation without passing through the MT model.
    Example: '    *   **Bold item**' -> ('    *   ', '**Bold item**')
    """
    match = LIST_PREFIX_PATTERN.match(line)
    if match:
        return match.group(1), match.group(2)
    return "", line


@dataclass(frozen=True)
class DocumentTranslator:
    text_translator: TextTranslator

    def translate_file(
        self, source_path: Path, output_path: Path, target_locale: Locale
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix == ".ipynb":
            output_path.write_text(
                self._translate_notebook(source_path, target_locale),
                encoding="utf-8",
            )
            return output_path

        output_path.write_text(
            self._translate_markdown(source_path, target_locale),
            encoding="utf-8",
        )
        return output_path

    def _translate_markdown(
        self, source_path: Path, target_locale: Locale
    ) -> str:
        source = source_path.read_text(encoding="utf-8")
        return self.translate_markdown_source(source, target_locale)

    def _translate_notebook(
        self, source_path: Path, target_locale: Locale
    ) -> str:
        notebook = json.loads(source_path.read_text(encoding="utf-8"))
        cells = notebook.get("cells", [])
        if not isinstance(cells, list):
            raise ValueError(
                f"Invalid notebook {source_path}: expected cells list"
            )

        notebook["cells"] = [
            self._translate_notebook_cell(cell, target_locale)
            for cell in cells
        ]
        return json.dumps(notebook, ensure_ascii=False, indent=2)

    def _translate_notebook_cell(
        self, cell: object, target_locale: Locale
    ) -> object:
        if not isinstance(cell, dict) or cell.get("cell_type") != "markdown":
            return cell

        translated_cell: dict[str, Any] = dict(cell)
        translated_cell["source"] = self._translate_notebook_source(
            cell.get("source"), target_locale
        )
        return translated_cell

    def _translate_notebook_source(
        self, source: object, target_locale: Locale
    ) -> object:
        if isinstance(source, list):
            return self.translate_markdown_source(
                "".join(str(line) for line in source), target_locale
            )

        return self.translate_markdown_source(str(source), target_locale)

    def translate_markdown_source(
        self, source: str, target_locale: Locale
    ) -> str:
        translated_lines: list[str] = []
        inside_code_fence = False
        for line in source.splitlines(keepends=True):
            if line.lstrip().startswith("```"):
                inside_code_fence = not inside_code_fence
                translated_lines.append(line)
                continue

            translated_lines.append(
                self._translate_markdown_line(
                    line, target_locale, inside_code_fence
                )
            )

        return "".join(translated_lines)

    def _translate_markdown_line(
        self, line: str, target_locale: Locale, inside_code_fence: bool
    ) -> str:
        if inside_code_fence or "{{" in line or "{%" in line:
            return line

        line_body = line.removesuffix("\n")
        line_ending = "\n" if line.endswith("\n") else ""
        if not line_body.strip():
            return line

        # Pass horizontal rules through unchanged; MT models duplicate the dashes.
        if re.fullmatch(r"\s*-{3,}\s*", line_body):
            return line

        # Strip the list-item prefix so indentation is never sent to the MT model.
        prefix, body = _strip_list_prefix(line_body)

        heading_match = re.fullmatch(r"(#{1,6}\s+)(.*)", body)
        if heading_match:
            return prefix + self._translate_heading(
                heading_match, target_locale, line_ending
            )

        return (
            prefix
            + self._translate_text_with_protected_parts(body, target_locale)
            + line_ending
        )

    def _translate_heading(
        self,
        heading_match: re.Match[str],
        target_locale: Locale,
        line_ending: str,
    ) -> str:
        heading_prefix = heading_match.group(1)
        heading_text = heading_match.group(2)
        return (
            heading_prefix
            + self._translate_text_with_protected_parts(
                heading_text, target_locale
            )
            + line_ending
        )

    def _translate_text_with_protected_parts(
        self, source_text: str, target_locale: Locale
    ) -> str:
        protected_parts: dict[str, str] = {}
        wikilink_targets: dict[str, str] = {}

        # Pre-translate each ** and * inline span, storing the fully-reconstructed
        # replacement in protected_parts as a single-occurrence marker.
        # Single-occurrence markers in the 999xx range are reliably copied by the model.
        source_text = self._pre_translate_inline_spans(
            source_text, protected_parts, target_locale
        )

        wikilink_source = WIKILINK_PATTERN.sub(
            lambda match: self._protect_wikilink_target(
                match, wikilink_targets
            ),
            source_text,
        )

        glossary_terms: dict[str, str] = {}
        from ssg_i18n.application.translation import CatalogFirstTextTranslator

        if isinstance(self.text_translator, CatalogFirstTextTranslator):
            glossary_terms = self.text_translator.catalog.glossary_terms

        # Protect glossary terms (longer terms first to prevent substring matching)
        sorted_glossary = sorted(
            glossary_terms.items(), key=lambda x: len(x[0]), reverse=True
        )
        for term, translated_term in sorted_glossary:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)

            def replace_term(
                match: re.Match[str], t_term: str = translated_term
            ) -> str:
                marker = f"{{{99900 + len(protected_parts)}}}"
                protected_parts[marker] = t_term
                return marker

            wikilink_source = pattern.sub(replace_term, wikilink_source)

        protected_source = PROTECTED_PATTERN.sub(
            lambda match: self._protect_match(match, protected_parts),
            wikilink_source,
        )
        translated_source = self.text_translator.translate(
            protected_source, target_locale
        )
        translated_source = re.sub(
            r"\{\s*(999\d+|888\d+)\s*\}",
            lambda m: f"{{{m.group(1)}}}",
            translated_source,
        )
        translated_source = re.sub(
            r"(?<!\{)(999\d+|888\d+)(?!\})",
            lambda m: f"{{{m.group(1)}}}",
            translated_source,
        )
        if not self._all_markers_preserved(
            translated_source, protected_parts | wikilink_targets
        ):
            translated_source = protected_source

        # Repair any machine-translated wikilinks where the pipe "|" was lost or deleted
        translated_source = re.sub(
            r"\[\[(\{888\d+\})\s*([^\|\]]+)\]\]",
            r"[[\1|\2]]",
            translated_source,
        )

        for marker, protected_text in protected_parts.items():
            translated_source = translated_source.replace(
                marker, protected_text
            )
        for marker, wikilink_target in wikilink_targets.items():
            translated_source = translated_source.replace(
                marker, wikilink_target
            )

        return translated_source

    def _pre_translate_inline_spans(
        self,
        text: str,
        protected_parts: dict[str, str],
        target_locale: Locale,
    ) -> str:
        """Pre-translate each ** and * span; store result as a single-occurrence marker.

        Each inline span is replaced by ONE {99900+N} marker whose value in
        protected_parts is the fully-translated, delimiter-wrapped replacement.
        Single-occurrence markers are reliably copied by the MT model, avoiding
        the split-closing-marker problem that affects paired open/close tokens.
        Bold is processed before italic to avoid treating ** as two *s.
        Example: '**bold** and *italic*'
                 -> '{99900} and {99901}' with
                    protected_parts = {'{99900}': '**negrito**', '{99901}': '*itálico*'}
        """

        def replace_bold(match: re.Match[str]) -> str:
            content = match.group(1)
            translated = self._translate_text_with_protected_parts(
                content, target_locale
            )
            marker = f"{{{99900 + len(protected_parts)}}}"
            protected_parts[marker] = f"**{translated}**"
            return marker

        def replace_italic(match: re.Match[str]) -> str:
            content = match.group(1)
            translated = self._translate_text_with_protected_parts(
                content, target_locale
            )
            marker = f"{{{99900 + len(protected_parts)}}}"
            protected_parts[marker] = f"*{translated}*"
            return marker

        text = INLINE_BOLD_PATTERN.sub(replace_bold, text)
        text = INLINE_ITALIC_PATTERN.sub(replace_italic, text)
        return text

    def _all_markers_preserved(
        self, translated_source: str, protected_parts: dict[str, str]
    ) -> bool:
        return all(marker in translated_source for marker in protected_parts)

    def _protect_match(
        self, match: re.Match[str], protected_parts: dict[str, str]
    ) -> str:
        marker = f"{{{99900 + len(protected_parts)}}}"
        protected_parts[marker] = match.group(0)
        return marker

    def _protect_wikilink_target(
        self, match: re.Match[str], wikilink_targets: dict[str, str]
    ) -> str:
        marker = f"{{{88800 + len(wikilink_targets)}}}"
        wikilink_targets[marker] = match.group(1)
        label = match.group(2)
        if label is None:
            return f"[[{marker}]]"

        return f"[[{marker}|{label}]]"
