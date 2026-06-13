import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import mistletoe
from mistletoe import block_token, span_token
from mistletoe.markdown_renderer import MarkdownRenderer

from ssg_i18n.application.terminology_mapper import TerminologyMapper
from ssg_i18n.application.translation import TextTranslator
from ssg_i18n.domain.locale import Locale

# Monkeypatch mistletoe duplicate instantiation bug
orig_remove_token = mistletoe.block_token.remove_token


def safe_remove_token(token_cls):
    try:
        if token_cls in mistletoe.block_token._token_types:
            orig_remove_token(token_cls)
    except ValueError:
        pass


mistletoe.block_token.remove_token = safe_remove_token


class CustomMarkdownRenderer(MarkdownRenderer):
    def __init__(self, *args, **kwargs):
        self.in_list_loose = None
        super().__init__(*args, **kwargs)

    def blocks_to_lines(
        self, tokens: Iterable[block_token.BlockToken], max_line_length: int
    ) -> Iterable[str]:
        first = True
        for token in tokens:
            if not first:
                if (
                    token.__class__.__name__ == "ListItem"
                    and self.in_list_loose is False
                ):
                    pass
                else:
                    yield ""
            first = False
            yield from self.render_map[token.__class__.__name__](
                token, max_line_length=max_line_length
            )

    def render_list(
        self, token: block_token.List, max_line_length: int
    ) -> Iterable[str]:
        old_loose = self.in_list_loose
        self.in_list_loose = token.loose
        try:
            yield from self.blocks_to_lines(
                token.children, max_line_length=max_line_length
            )
        finally:
            self.in_list_loose = old_loose


PROTECTED_PATTERN = re.compile(
    r"(\$\$.*?\$\$|(?<!\$)\$[^\$\s](?:[^\$]*?[^\$\s])?\$(?!\d)|https?://\S+)",
    re.DOTALL,
)
WIKILINK_PATTERN = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")


@dataclass(frozen=True)
class DocumentTranslator:
    text_translator: TextTranslator
    terminology_mapper: TerminologyMapper = TerminologyMapper()

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

        translated_cell: dict[str, object] = dict(cell)
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
        if not source.strip():
            return source

        doc = mistletoe.Document(source)
        with CustomMarkdownRenderer() as renderer:
            self._translate_block(doc, target_locale, renderer)
            translated = renderer.render(doc)

        # Preserve trailing newline behavior
        if not source.endswith("\n") and translated.endswith("\n"):
            translated = translated.rstrip("\n")
        return translated

    def _translate_block(
        self,
        node: object,
        target_locale: Locale,
        renderer: CustomMarkdownRenderer,
    ) -> None:
        class_name = node.__class__.__name__
        children = getattr(node, "children", None)
        if not children:
            return
        if class_name in ("Document", "List", "ListItem", "Table", "TableRow"):
            self._translate_children(children, target_locale, renderer)
            return
        if class_name in ("Paragraph", "Heading", "TableCell"):
            self._translate_container(node, children, target_locale, renderer)

    def _translate_children(
        self,
        children: list[object],
        target_locale: Locale,
        renderer: CustomMarkdownRenderer,
    ) -> None:
        for child in children:
            self._translate_block(child, target_locale, renderer)

    def _translate_container(
        self,
        node: object,
        children: list[object],
        target_locale: Locale,
        renderer: CustomMarkdownRenderer,
    ) -> None:
        has_jinja = any(
            isinstance(child, span_token.RawText)
            and ("{{" in child.content or "{%" in child.content)
            for child in children
        )
        if has_jinja:
            return
        node.children = self._translate_inline_children(
            children, target_locale, renderer
        )

    def _translate_inline_children(
        self,
        children: list[object],
        target_locale: Locale,
        renderer: CustomMarkdownRenderer,
    ) -> list[object]:
        protected_parts: dict[str, str] = {}
        english = self._translate_inline_nodes(
            children, target_locale, protected_parts, renderer
        )
        english = self._protect_and_translate_raw_text(
            english, protected_parts, target_locale
        )
        english = self._protect_glossary_terms(english, protected_parts)
        if not english.strip():
            return children
        translated = self.text_translator.translate(english, target_locale)
        translated = self._normalize_and_heal_markers(translated, english)
        finalized = self._restore_and_postprocess(
            translated, english, protected_parts
        )
        return span_token.tokenize_inner(finalized)

    def _get_glossary_terms(self) -> dict[str, str]:
        from ssg_i18n.application.translation import CatalogFirstTextTranslator

        if not isinstance(self.text_translator, CatalogFirstTextTranslator):
            return {}
        return self.text_translator.catalog.glossary_terms

    def _protect_glossary_terms(
        self, sentence: str, protected_parts: dict[str, str]
    ) -> str:
        terms = self._get_glossary_terms()
        sorted_terms = sorted(
            terms.items(), key=lambda x: len(x[0]), reverse=True
        )
        for term, translated_term in sorted_terms:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)

            def replace_term(
                match: re.Match[str], t_term: str = translated_term
            ) -> str:
                marker = f"{{{99900 + len(protected_parts)}}}"
                protected_parts[marker] = t_term
                return marker

            sentence = pattern.sub(replace_term, sentence)
        return sentence

    def _normalize_and_heal_markers(
        self,
        translated: str,
        original: str,
    ) -> str:
        normalized = re.sub(
            r"\{\s*(999\d+|888\d+)\s*\}",
            lambda m: f"{{{m.group(1)}}}",
            translated,
        )
        normalized = re.sub(
            r"(?<!\{)(999\d+|888\d+)(?!\})",
            lambda m: f"{{{m.group(1)}}}",
            normalized,
        )
        leading_match = re.match(r"^(\{999\d+\}|\{888\d+\})(:?\s*)", original)
        if not leading_match:
            return normalized
        marker = leading_match.group(1)
        if marker in normalized:
            return normalized
        return marker + leading_match.group(2) + normalized

    def _restore_and_postprocess(
        self,
        translated: str,
        original: str,
        protected_parts: dict[str, str],
    ) -> str:
        if not all(marker in translated for marker in protected_parts):
            translated = original
        for marker, text in reversed(list(protected_parts.items())):
            translated = translated.replace(marker, text)
        return self.terminology_mapper.map_text(translated)

    def _translate_inline_nodes(
        self,
        tokens: list[object],
        target_locale: Locale,
        protected_parts: dict[str, str],
        renderer: CustomMarkdownRenderer,
    ) -> str:
        parts = []
        for child in tokens:
            parts.append(
                self._render_token_in_sentence(
                    child, target_locale, protected_parts, renderer
                )
            )
        return "".join(parts)

    def _render_token_in_sentence(
        self,
        child: object,
        target_locale: Locale,
        protected_parts: dict[str, str],
        renderer: CustomMarkdownRenderer,
    ) -> str:
        name = child.__class__.__name__
        if name == "RawText":
            return getattr(child, "content", "")
        if name in ("Strong", "Emphasis"):
            return self._render_styled_nodes(
                child, target_locale, protected_parts, renderer
            )
        if name == "Link":
            return self._translate_and_protect_link(
                child, target_locale, protected_parts, renderer
            )
        if name in ("InlineCode", "LineBreak"):
            return self._protect_node(child, protected_parts, renderer)
        return renderer.render(child).rstrip("\n")

    def _render_styled_nodes(
        self,
        node: object,
        target_locale: Locale,
        protected_parts: dict[str, str],
        renderer: CustomMarkdownRenderer,
    ) -> str:
        children = self._translate_inline_nodes(
            node.children, target_locale, protected_parts, renderer
        )
        if node.__class__.__name__ == "Strong":
            return f"**{children}**"
        return f"*{children}*"

    def _translate_and_protect_link(
        self,
        link: object,
        target_locale: Locale,
        protected_parts: dict[str, str],
        renderer: CustomMarkdownRenderer,
    ) -> str:
        label = self._translate_inline_nodes(
            link.children, target_locale, protected_parts, renderer
        )
        original = link.children
        link.children = [span_token.RawText(label)]
        marker = self._protect_node(link, protected_parts, renderer)
        link.children = original
        return marker

    def _protect_node(
        self,
        node: object,
        protected_parts: dict[str, str],
        renderer: CustomMarkdownRenderer,
    ) -> str:
        rendered = renderer.render(node).rstrip("\n")
        marker = f"{{{99900 + len(protected_parts)}}}"
        protected_parts[marker] = rendered
        return marker

    def _protect_and_translate_raw_text(
        self, text: str, protected_parts: dict[str, str], target_locale: Locale
    ) -> str:
        text = self._protect_wikilinks(text, protected_parts, target_locale)
        return self._protect_patterns(text, protected_parts)

    def _protect_wikilinks(
        self, text: str, protected_parts: dict[str, str], target_locale: Locale
    ) -> str:
        def replace_wikilink(match: re.Match[str]) -> str:
            target = match.group(1)
            label = match.group(2)
            reconstructed = f"[[{target}]]"
            if label is not None:
                translated = self.text_translator.translate(
                    label, target_locale
                )
                reconstructed = f"[[{target}|{translated}]]"
            marker = f"{{{99900 + len(protected_parts)}}}"
            protected_parts[marker] = reconstructed
            return marker

        return WIKILINK_PATTERN.sub(replace_wikilink, text)

    def _protect_patterns(
        self, text: str, protected_parts: dict[str, str]
    ) -> str:
        def replace_protected(match: re.Match[str]) -> str:
            marker = f"{{{99900 + len(protected_parts)}}}"
            protected_parts[marker] = match.group(0)
            return marker

        return PROTECTED_PATTERN.sub(replace_protected, text)
