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

        # Detect markdown table row
        if body.strip().startswith("|") and body.count("|") >= 2:
            return (
                prefix
                + self._translate_table_row(body, target_locale)
                + line_ending
            )

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

    def _translate_table_row(self, row: str, target_locale: Locale) -> str:
        cells = row.split("|")
        translated_cells = []
        for i, cell in enumerate(cells):
            # First and last cells are empty if row starts/ends with |
            if (i == 0 or i == len(cells) - 1) and not cell.strip():
                translated_cells.append(cell)
                continue

            # Skip divider cells like " :--- "
            if re.fullmatch(r"\s*[-:]+\s*", cell):
                translated_cells.append(cell)
                continue

            if not cell.strip():
                translated_cells.append(cell)
                continue

            # Keep spacing for alignment/padding
            match = re.match(r"^(\s*)(.*?)(\s*)$", cell)
            if match:
                l_ws, content, t_ws = match.groups()
                translated_content = self._translate_text_with_protected_parts(
                    content, target_locale
                )
                translated_cells.append(l_ws + translated_content + t_ws)
            else:
                translated_cells.append(cell)

        return "|".join(translated_cells)

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

        # 1. Wikilinks pre-translation & protection
        def replace_wikilink(match: re.Match[str]) -> str:
            target = match.group(1)
            label = match.group(2)
            if label is not None:
                # Pre-translate the label recursively
                translated_label = self._translate_text_with_protected_parts(
                    label, target_locale
                )
                reconstructed = f"[[{target}|{translated_label}]]"
            else:
                reconstructed = f"[[{target}]]"

            marker = f"{{{99900 + len(protected_parts)}}}"
            protected_parts[marker] = reconstructed
            return marker

        wikilink_source = WIKILINK_PATTERN.sub(replace_wikilink, source_text)

        # 2. Inline markdown protection (bold & italic)
        wikilink_source = self._pre_translate_inline_spans(
            wikilink_source, protected_parts, target_locale
        )

        glossary_terms: dict[str, str] = {}
        from ssg_i18n.application.translation import CatalogFirstTextTranslator

        if isinstance(self.text_translator, CatalogFirstTextTranslator):
            glossary_terms = self.text_translator.catalog.glossary_terms

        # 3. Protect glossary terms (longest first to avoid substring conflicts)
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

        # 4. Protect LaTeX and URLs
        protected_source = PROTECTED_PATTERN.sub(
            lambda match: self._protect_match(match, protected_parts),
            wikilink_source,
        )

        # 5. Translate using the translation engine
        translated_source = self.text_translator.translate(
            protected_source, target_locale
        )

        # Normalize any spacing/braces inside markers
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

        # 6. Heal leading markers stripped from the beginning by the MT model
        leading_match = re.match(
            r"^(\{999\d+\}|\{888\d+\})(:?\s*)", protected_source
        )
        if leading_match:
            marker = leading_match.group(1)
            separator = leading_match.group(2)
            if marker not in translated_source:
                translated_source = marker + separator + translated_source

        # 7. Validation: if any markers are missing, fallback to protected_source
        if not self._all_markers_preserved(translated_source, protected_parts):
            translated_source = protected_source

        # 8. Restore the protected parts in reverse order
        for marker, protected_text in reversed(list(protected_parts.items())):
            translated_source = translated_source.replace(
                marker, protected_text
            )

        # 9. Post-translation terminology/grammar corrections
        translated_source = self._apply_terminology_corrections(
            translated_source
        )

        return translated_source

    def _pre_translate_inline_spans(
        self,
        text: str,
        protected_parts: dict[str, str],
        target_locale: Locale,
    ) -> str:
        """Pre-translate each ** and * span; store result as a single-occurrence marker."""

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

    def _apply_terminology_corrections(self, text: str) -> str:
        corrections = [
            (r"\bloja de recursos\b", "Feature Store"),
            (r"\blojas de recursos\b", "Feature Stores"),
            (r"\blago de dados\b", "data lake"),
            (r"\blagos de dados\b", "data lakes"),
            (r"\bloja de fluxo\b", "stream store"),
            (r"\blojas de fluxo\b", "stream stores"),
            (r"\bdrift característica\b", "feature drift"),
            (r"\bderiva de recurso\b", "feature drift"),
            (r"\bderiva de recursos\b", "feature drift"),
            (r"\bderiva de característica\b", "feature drift"),
            (r"\bderiva de características\b", "feature drift"),
            (r"\bdrift de recurso\b", "feature drift"),
            (r"\bdrift de recursos\b", "feature drift"),
            (r"\bdrift de característica\b", "feature drift"),
            (r"\bdrift de características\b", "feature drift"),
            (r"\bcaracterísticas do atraso\b", "lags de features"),
            (r"\batraso de coleta\b", "lag de embarques"),
            (r"\batrasos de coleta\b", "lags de embarques"),
            (r"\batraso horários\b", "lags horários"),
            (r"\batrasos horários\b", "lags horários"),
            (r"\bcaptadores de táxi\b", "embarques de táxi"),
            (r"\bcaptador de táxi\b", "embarque de táxi"),
            (r"\bcontagens de captação\b", "contagens de embarques"),
            (r"\bcontagem de captação\b", "contagem de embarques"),
            (r"\bcontagens de coleta\b", "contagens de embarques"),
            (r"\bcontagem de coleta\b", "contagem de tempo de embarque"),
            (r"\btempo de captação\b", "horário de embarque"),
            (r"\btempo de coleta\b", "horário de embarque"),
            (r"\btempo de entrega\b", "horário de desembarque"),
            (r"\bpreços de alta\b", "preço dinâmico"),
            (r"\bpreço de alta\b", "preço dinâmico"),
            (r"\bencanamento\b", "pipeline"),
            (r"\bencanamentos\b", "pipelines"),
            (r"\boleoduto\b", "pipeline"),
            (r"\boleodutos\b", "pipelines"),
            (r"\bMétricas Candida\b", "Métricas Candidatas"),
            (r"\bmétricas candida\b", "métricas candidatas"),
            (r"\bmétrica candida\b", "métrica candidata"),
            (r"\bimplantação Bloco\b", "Bloquear Implantação"),
            (r"\bimplantação bloco\b", "bloquear implantação"),
            (r"\bcavalos sazonalidade\b", "captura a sazonalidade"),
            (r"\bcavalga sazonalidade\b", "captura a sazonalidade"),
            (r"\bNegócios Trade-offs\b", "Trade-offs de Negócio"),
            (r"\bNegócio Trade-offs\b", "Trade-offs de Negócio"),
            (r"\bProblema Enquadramento\b", "Enquadramento do Problema"),
            (r"\bFases de Ciclo de Vida\b", "Fases do Ciclo de Vida de"),
        ]

        for pattern, replacement in corrections:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text
