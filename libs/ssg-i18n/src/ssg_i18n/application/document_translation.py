import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ssg_i18n.application.translation import TextTranslator
from ssg_i18n.domain.locale import Locale

PROTECTED_PATTERN = re.compile(r"(`[^`]+`|https?://\S+)")
WIKILINK_PATTERN = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")


@dataclass(frozen=True)
class DocumentTranslator:
    text_translator: TextTranslator

    def translate_file(self, source_path: Path, output_path: Path, target_locale: Locale) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix == ".ipynb":
            output_path.write_text(
                self._translate_notebook(source_path, target_locale), encoding="utf-8"
            )
            return output_path

        output_path.write_text(
            self._translate_markdown(source_path, target_locale), encoding="utf-8"
        )
        return output_path

    def _translate_markdown(self, source_path: Path, target_locale: Locale) -> str:
        source = source_path.read_text(encoding="utf-8")
        return self.translate_markdown_source(source, target_locale)

    def _translate_notebook(self, source_path: Path, target_locale: Locale) -> str:
        notebook = json.loads(source_path.read_text(encoding="utf-8"))
        cells = notebook.get("cells", [])
        if not isinstance(cells, list):
            raise ValueError(f"Invalid notebook {source_path}: expected cells list")

        notebook["cells"] = [self._translate_notebook_cell(cell, target_locale) for cell in cells]
        return json.dumps(notebook, ensure_ascii=False, indent=2)

    def _translate_notebook_cell(self, cell: object, target_locale: Locale) -> object:
        if not isinstance(cell, dict) or cell.get("cell_type") != "markdown":
            return cell

        translated_cell: dict[str, Any] = dict(cell)
        translated_cell["source"] = self._translate_notebook_source(
            cell.get("source"), target_locale
        )
        return translated_cell

    def _translate_notebook_source(self, source: object, target_locale: Locale) -> object:
        if isinstance(source, list):
            return self.translate_markdown_source(
                "".join(str(line) for line in source), target_locale
            )

        return self.translate_markdown_source(str(source), target_locale)

    def translate_markdown_source(self, source: str, target_locale: Locale) -> str:
        translated_lines: list[str] = []
        inside_code_fence = False
        for line in source.splitlines(keepends=True):
            if line.lstrip().startswith("```"):
                inside_code_fence = not inside_code_fence
                translated_lines.append(line)
                continue

            translated_lines.append(
                self._translate_markdown_line(line, target_locale, inside_code_fence)
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

        heading_match = re.fullmatch(r"(#{1,6}\s+)(.*)", line_body)
        if heading_match:
            return self._translate_heading(heading_match, target_locale, line_ending)

        return self._translate_text_with_protected_parts(line_body, target_locale) + line_ending

    def _translate_heading(
        self, heading_match: re.Match[str], target_locale: Locale, line_ending: str
    ) -> str:
        heading_prefix = heading_match.group(1)
        heading_text = heading_match.group(2)
        return (
            heading_prefix
            + self._translate_text_with_protected_parts(heading_text, target_locale)
            + line_ending
        )

    def _translate_text_with_protected_parts(self, source_text: str, target_locale: Locale) -> str:
        protected_parts: dict[str, str] = {}
        wikilink_targets: dict[str, str] = {}
        wikilink_source = WIKILINK_PATTERN.sub(
            lambda match: self._protect_wikilink_target(match, wikilink_targets), source_text
        )
        protected_source = PROTECTED_PATTERN.sub(
            lambda match: self._protect_match(match, protected_parts), wikilink_source
        )
        translated_source = self.text_translator.translate(protected_source, target_locale)
        if not self._all_markers_preserved(translated_source, protected_parts | wikilink_targets):
            translated_source = protected_source

        for marker, protected_text in protected_parts.items():
            translated_source = translated_source.replace(marker, protected_text)
        for marker, wikilink_target in wikilink_targets.items():
            translated_source = translated_source.replace(marker, wikilink_target)

        return translated_source

    def _all_markers_preserved(
        self, translated_source: str, protected_parts: dict[str, str]
    ) -> bool:
        return all(marker in translated_source for marker in protected_parts)

    def _protect_match(self, match: re.Match[str], protected_parts: dict[str, str]) -> str:
        marker = f"{{SSG_I18N_PROTECTED_{len(protected_parts)}}}"
        protected_parts[marker] = match.group(0)
        return marker

    def _protect_wikilink_target(
        self, match: re.Match[str], wikilink_targets: dict[str, str]
    ) -> str:
        marker = f"{{SSG_I18N_WIKILINK_{len(wikilink_targets)}}}"
        wikilink_targets[marker] = match.group(1)
        label = match.group(2)
        if label is None:
            return f"[[{marker}]]"

        return f"[[{marker}|{label}]]"
