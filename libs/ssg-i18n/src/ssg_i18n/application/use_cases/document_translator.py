# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# mistletoe is untyped and this module adapts its internals on purpose:
# it patches block_token.remove_token/_token_types, dispatches through
# renderer.render_map (max_line_length is a real runtime kwarg),
# introspects token nodes via getattr, and swaps the charref pattern
# span_tokenizer installs for html.unescape.
import json
import re
import secrets
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import mistletoe
from mistletoe import block_token, span_token, span_tokenizer, token
from mistletoe.markdown_renderer import MarkdownRenderer

from ssg_i18n.application.ports.text_translator import (
    CatalogAwareTextTranslator,
    TextTranslator,
)
from ssg_i18n.application.use_cases.terminology_mapper import TerminologyMapper
from ssg_i18n.domain.value_objects.locale import Locale

# Monkeypatch mistletoe duplicate instantiation bug
_orig_remove_token = block_token.remove_token


def _safe_remove_token(token_cls: type) -> None:
    try:
        if token_cls in block_token._token_types:
            _orig_remove_token(token_cls)
    except ValueError:
        pass


block_token.remove_token = _safe_remove_token

# Authored entities must survive the parse→translate→re-render
# round-trip verbatim: make_tokens decodes every fallback span through
# html.unescape (span_tokenizer.py:81,89 — under tokenize()'s own
# _charref swap), so "&amp;copy;" re-emitted "&copy;" which renders ©
# where the author wrote text that displays "&copy;". A charref that
# never matches turns unescape into a no-op inside tokenize() only —
# and keeps entity escapes in link targets/titles verbatim too.
span_tokenizer._markdown_charref = re.compile(r"(?!)")


class _CustomMarkdownRenderer(MarkdownRenderer):
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.in_list_loose = None
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def blocks_to_lines(
        self, tokens: Iterable[block_token.BlockToken], max_line_length: int
    ) -> Iterable[str]:
        first = True
        for block in tokens:
            if not first:
                if (
                    block.__class__.__name__ in ("ListItem", "List")
                    and self.in_list_loose is False
                ):
                    pass
                else:
                    yield ""
            first = False
            # mistletoe's own render() passes max_line_length the same way;
            # its untyped stubs just don't model the render_map signatures.
            yield from self.render_map[block.__class__.__name__](
                block,
                max_line_length=max_line_length,  # pyright: ignore[reportCallIssue]
            )

    def render_list(  # type: ignore[override]
        self, token: block_token.List, max_line_length: int
    ) -> Iterable[str]:
        old_loose = self.in_list_loose
        self.in_list_loose = token.loose
        try:
            yield from self.blocks_to_lines(
                token.children or [],  # type: ignore[arg-type]
                max_line_length=max_line_length,
            )
        finally:
            self.in_list_loose = old_loose


_MATH_MARKER_REGEX = r"MATHEXPR\d+X[0-9a-fA-F]+"
# The MATHEXPR arm deliberately has no \b before it: markers glued to a
# preceding token ("hour:TR1MATHEXPR1") must still be protected. The hex
# suffix makes an authored literal unable to match, so \b buys nothing.
_PROTECTED_PATTERN = re.compile(
    r"(\{\{.*?\}\}|\{\%.*?\}\}|\$\$.*?\$\$|(?<!\$)\$[^\$\s](?:[^\$]*?[^\$\s])?\$(?!\d)|https?://\S+|"
    + _MATH_MARKER_REGEX
    + ")",
    re.DOTALL,
)
_WIKILINK_PATTERN = re.compile(r"\[\[([a-zA-Z0-9_-]+)(?:\|([^\]]+))?\]\]")

# mistletoe block names: containers hold block children (walked), leaves
# hold span children (translated as one unit). Any unlisted block with
# children still gets walked — an unlisted container must not silently
# skip its subtree (span children no-op on their own missing `children`).
_CONTAINER_BLOCK_NAMES = (
    "Document",
    "List",
    "ListItem",
    "Table",
    "TableRow",
    "Quote",
)
_LEAF_BLOCK_NAMES = (
    "Paragraph",
    "Heading",
    "TableCell",
    "SetextHeading",
)


def _default_marker_token() -> str:
    return secrets.token_hex(8)


def _heal_mangled_marker(translated: str, marker: str) -> str:
    tolerant = re.compile(
        r"\b" + r"\s*".join(re.escape(char) for char in marker) + r"\b",
        re.IGNORECASE,
    )
    return tolerant.sub(marker, translated)


def _reference_definition_lines(
    footnotes: dict[str, tuple[str, str]],
) -> list[str]:
    return [
        f"[{label}]: {dest}" + (f' "{title}"' if title else "")
        for label, (dest, title) in footnotes.items()
    ]


@dataclass(frozen=True)
class _GlossaryProtection:
    pattern: re.Pattern[str]
    replacements: dict[str, str]


def _glossary_protection_for(
    terms: Mapping[str, str],
) -> _GlossaryProtection | None:
    # Longest terms first so "machine learning" wins over "machine" inside
    # the single combined pass; one alternation compiled once per catalog.
    ordered = sorted(
        terms.items(), key=lambda item: len(item[0]), reverse=True
    )
    alternatives: list[str] = []
    replacements: dict[str, str] = {}
    for term, replacement in ordered:
        if not term:
            continue
        alternatives.append(re.escape(term))
        replacements.setdefault(term.lower(), replacement)
    if not alternatives:
        return None
    return _GlossaryProtection(
        pattern=re.compile(rf"\b({'|'.join(alternatives)})\b", re.IGNORECASE),
        replacements=replacements,
    )


@dataclass(frozen=True)
class DocumentTranslator:
    """Translates markdown and notebook files sentence by sentence.

    Example:
        DocumentTranslator(translator).translate_file(src, out, Locale("pt-BR"))
    """

    text_translator: TextTranslator
    terminology_mapper: TerminologyMapper = TerminologyMapper()
    marker_token_factory: Callable[[], str] = _default_marker_token
    _glossary_protection: _GlossaryProtection | None = field(
        init=False, default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_glossary_protection",
            _glossary_protection_for(self._get_glossary_terms()),
        )

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
        if not isinstance(notebook, dict):
            raise ValueError(
                f"Invalid notebook {source_path}: expected JSON object, "
                f"got {type(notebook).__name__}"
            )

        cells = notebook.get("cells", [])
        if not isinstance(cells, list):
            raise ValueError(
                f"Invalid notebook {source_path}: expected cells list"
            )

        notebook["cells"] = [
            self._translate_notebook_cell(cell, target_locale, source_path)
            for cell in cells
        ]
        return json.dumps(notebook, ensure_ascii=False, indent=2)

    def _translate_notebook_cell(
        self, cell: object, target_locale: Locale, source_path: Path
    ) -> object:
        if not isinstance(cell, dict) or cell.get("cell_type") != "markdown":
            return cell

        translated_cell: dict[str, object] = dict(cell)
        translated_cell["source"] = self._translate_notebook_source(
            cell.get("source"), target_locale, source_path
        )
        return translated_cell

    def _translate_notebook_source(
        self, source: object, target_locale: Locale, source_path: Path
    ) -> str:
        if isinstance(source, str):
            return self.translate_markdown_source(source, target_locale)

        if isinstance(source, list) and all(
            isinstance(line, str) for line in source
        ):
            return self.translate_markdown_source(
                "".join(source), target_locale
            )

        raise ValueError(
            f"Invalid notebook {source_path}: expected string or list of "
            f"strings markdown cell source, got {source!r} "
            f"({type(source).__name__})"
        )

    def translate_markdown_source(
        self, source: str, target_locale: Locale
    ) -> str:
        if not source.strip():
            return source

        math_map: dict[str, str] = {}

        def protect_math(match: re.Match[str]) -> str:
            placeholder = (
                f"MATHEXPR{len(math_map)}X{self.marker_token_factory()}"
            )
            math_map[placeholder] = match.group(0)
            return placeholder

        math_pattern = re.compile(
            r"(\$\$.*?\$\$|(?<!\$)\$[^\$\s](?:[^\$]*?[^\$\s])?\$(?!\d))",
            re.DOTALL,
        )
        source_protected = math_pattern.sub(protect_math, source)

        # Inline HTML must arrive as HtmlSpan tokens so the span dispatch
        # can protect each tag whole; without it "<em>" sits inside
        # RawText and reaches the translator as markup. (The re-tokenize
        # below already runs with HtmlSpan active — the renderer's extras
        # enable it inside `with`.)
        span_token.add_token(span_token.HtmlSpan)
        try:
            doc = mistletoe.Document(source_protected)  # type: ignore
        finally:
            span_token.remove_token(span_token.HtmlSpan)
        with _CustomMarkdownRenderer() as renderer:
            # tokenize_inner resolves `[label][ref]` via
            # token._root_node.footnotes, which Document clears after
            # parsing (block_token.py:158-160) — re-point it at this doc.
            token._root_node = doc
            try:
                self._translate_block(doc, target_locale, renderer, math_map)
                translated = renderer.render(doc)
            finally:
                token._root_node = None

        translated_str = str(translated)
        for placeholder, expr in math_map.items():
            translated_str = translated_str.replace(placeholder, expr)

        # Reference definitions parse into doc.footnotes, not the AST, so
        # the render drops them — re-emit or the output's `[x][r]` dangles.
        definitions = _reference_definition_lines(doc.footnotes)
        if definitions:
            translated_str += "\n" + "\n".join(definitions) + "\n"

        # Preserve trailing newline behavior
        if not source.endswith("\n") and translated_str.endswith("\n"):
            translated_str = translated_str.rstrip("\n")
        return translated_str

    def _translate_block(
        self,
        node: object,
        target_locale: Locale,
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> None:
        class_name = node.__class__.__name__
        children = getattr(node, "children", None)
        if not children:
            return
        if class_name in _CONTAINER_BLOCK_NAMES:
            header = getattr(node, "header", None)
            if class_name == "Table" and header is not None:
                self._translate_block(
                    header, target_locale, renderer, math_map
                )
            self._translate_children(
                children, target_locale, renderer, math_map
            )
            return
        if class_name in _LEAF_BLOCK_NAMES:
            self._translate_container(
                node, children, target_locale, renderer, math_map
            )
            return
        self._translate_children(children, target_locale, renderer, math_map)

    def _translate_children(
        self,
        children: list[object],
        target_locale: Locale,
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> None:
        for child in children:
            self._translate_block(child, target_locale, renderer, math_map)

    def _translate_container(
        self,
        node: object,
        children: list[object],
        target_locale: Locale,
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> None:
        setattr(  # noqa: B010
            node,
            "children",
            self._translate_inline_children(
                children, target_locale, renderer, math_map
            ),
        )

    def _translate_inline_children(
        self,
        children: list[object],
        target_locale: Locale,
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> list[object]:
        cataloged = self._catalog_translation(children, renderer, math_map)
        if cataloged is not None:
            return list(span_token.tokenize_inner(cataloged))
        protected_parts: dict[str, str] = {}
        english = self._translate_inline_nodes(
            children, target_locale, protected_parts, renderer, math_map
        )
        english = self._protect_and_translate_raw_text(
            english, protected_parts, target_locale
        )
        english = self._protect_glossary_terms(english, protected_parts)
        if not english.strip():
            return children
        translated = self.text_translator.translate(english, target_locale)
        translated = self._normalize_and_heal_markers(
            translated, protected_parts
        )
        finalized = self._restore_and_postprocess(
            translated, english, protected_parts, target_locale
        )
        return list(span_token.tokenize_inner(finalized))

    def _catalog_translation(
        self,
        children: list[object],
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> str | None:
        # Catalog keys are the authored sentence, so the lookup runs
        # before protection markers exist — an author never writes TRnX.
        if not isinstance(self.text_translator, CatalogAwareTextTranslator):
            return None
        source_sentence = self._source_sentence(children, renderer, math_map)
        if not source_sentence.strip():
            return None
        return self.text_translator.catalog_translation_for(source_sentence)

    def _source_sentence(
        self,
        children: list[object],
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> str:
        parts = [
            self._render_token_for_catalog_key(child, renderer)
            for child in children
        ]
        sentence = "".join(parts)
        for placeholder, expr in math_map.items():
            sentence = sentence.replace(placeholder, expr)
        return sentence

    def _render_token_for_catalog_key(
        self, child: object, renderer: _CustomMarkdownRenderer
    ) -> str:
        name = child.__class__.__name__
        if name == "RawText":
            return str(getattr(child, "content", ""))
        if name == "LineBreak":
            return "\n"
        return renderer.render(child).rstrip("\n")  # type: ignore[arg-type]

    def _get_glossary_terms(self) -> Mapping[str, str]:
        if not isinstance(self.text_translator, CatalogAwareTextTranslator):
            return {}
        return self.text_translator.glossary_terms

    def _protect_glossary_terms(
        self, sentence: str, protected_parts: dict[str, str]
    ) -> str:
        protection = self._glossary_protection
        if protection is None:
            return sentence

        def replace_term(match: re.Match[str]) -> str:
            # re.IGNORECASE can fold exotic chars the .lower() key map
            # misses — leave such text unprotected rather than crash.
            replacement = protection.replacements.get(match.group(0).lower())
            if replacement is None:
                return match.group(0)
            marker = self._new_marker(protected_parts)
            protected_parts[marker] = replacement
            return marker

        return protection.pattern.sub(replace_term, sentence)

    def _new_marker(self, protected_parts: dict[str, str]) -> str:
        # Markers carry an unguessable token so authored text like "TR0"
        # can neither collide with a marker nor be healed into one.
        return f"TR{len(protected_parts)}X{self.marker_token_factory()}"

    def _normalize_and_heal_markers(
        self,
        translated: str,
        protected_parts: dict[str, str],
    ) -> str:
        # Heal case/space-mangled copies of markers this sentence actually
        # placed — never pattern-match prose ("TR 9" stays literal). A
        # dropped marker falls back to the source sentence downstream.
        for marker in protected_parts:
            if marker in translated:
                continue
            translated = _heal_mangled_marker(translated, marker)
        return translated

    def _restore_and_postprocess(
        self,
        translated: str,
        original: str,
        protected_parts: dict[str, str],
        target_locale: Locale,
    ) -> str:
        if not all(marker in translated for marker in protected_parts):
            translated = original
        else:
            translated = self.terminology_mapper.map_text(
                translated, target_locale
            )
        for marker, text in reversed(list(protected_parts.items())):
            translated = translated.replace(marker, text)
        return translated

    def _translate_inline_nodes(
        self,
        tokens: list[object],
        target_locale: Locale,
        protected_parts: dict[str, str],
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> str:
        parts = []
        for child in tokens:
            parts.append(
                self._render_token_in_sentence(
                    child,
                    target_locale,
                    protected_parts,
                    renderer,
                    math_map,
                )
            )
        return "".join(parts)

    def _render_token_in_sentence(
        self,
        child: object,
        target_locale: Locale,
        protected_parts: dict[str, str],
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> str:
        name = child.__class__.__name__
        if name == "RawText":
            return str(getattr(child, "content", ""))
        if name in ("Strong", "Emphasis", "Strikethrough", "Link"):
            return self._translate_and_protect_children(
                child, target_locale, protected_parts, renderer, math_map
            )
        if name in (
            "InlineCode",
            "LineBreak",
            "Image",
            "AutoLink",
            "HtmlSpan",
            "EscapeSequence",
        ):
            return self._protect_node(child, protected_parts, renderer)
        return renderer.render(child).rstrip("\n")  # type: ignore[arg-type]

    def _translate_and_protect_children(
        self,
        node: object,
        target_locale: Locale,
        protected_parts: dict[str, str],
        renderer: _CustomMarkdownRenderer,
        math_map: dict[str, str],
    ) -> str:
        original_children = getattr(node, "children", None)
        if original_children is None:
            original_children = []
        translated_children = self._translate_inline_children(
            original_children, target_locale, renderer, math_map
        )
        setattr(node, "children", translated_children)  # noqa: B010
        rendered = renderer.render(node).rstrip("\n")  # type: ignore[arg-type]
        setattr(node, "children", original_children)  # noqa: B010
        marker = self._new_marker(protected_parts)
        protected_parts[marker] = rendered
        return marker

    def _protect_node(
        self,
        node: object,
        protected_parts: dict[str, str],
        renderer: _CustomMarkdownRenderer,
    ) -> str:
        rendered = renderer.render(node)  # type: ignore[arg-type]
        if node.__class__.__name__ != "LineBreak" and rendered.endswith("\n"):
            rendered = rendered.rstrip("\n")
        marker = self._new_marker(protected_parts)
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
            marker = self._new_marker(protected_parts)
            protected_parts[marker] = reconstructed
            return marker

        return _WIKILINK_PATTERN.sub(replace_wikilink, text)

    def _protect_patterns(
        self, text: str, protected_parts: dict[str, str]
    ) -> str:
        def replace_protected(match: re.Match[str]) -> str:
            marker = self._new_marker(protected_parts)
            protected_parts[marker] = match.group(0)
            return marker

        return _PROTECTED_PATTERN.sub(replace_protected, text)
