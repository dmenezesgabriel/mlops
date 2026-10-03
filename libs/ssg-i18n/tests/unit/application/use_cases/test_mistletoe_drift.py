# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
"""Drift alarms for the mistletoe internals DocumentTranslator adapts.

pyproject pins mistletoe==1.5.1 because document_translator reaches into
private surfaces: the block_token._token_types registry behind the
remove_token patch, the span_tokenizer._markdown_charref slot swapped
for a never-match, render_map class-name dispatch, the token._root_node
global, and mutable token.children. A deliberate bump that renames or
reshapes one must fail here naming it — not inside a translation run.
"""

import inspect

import mistletoe
from mistletoe import block_token, span_token, token
from ssg_i18n.application.use_cases import document_translator


def test_block_token_registry_surfaces_exist() -> None:
    # _safe_remove_token guards membership in _token_types before
    # delegating to the captured original remove_token.
    assert isinstance(block_token._token_types, list)
    assert block_token._token_types
    assert callable(block_token.add_token)
    assert callable(block_token.remove_token)


def test_span_token_surfaces_exist() -> None:
    assert callable(span_token.tokenize_inner)
    assert callable(span_token.add_token)
    assert callable(span_token.remove_token)
    assert hasattr(span_token, "HtmlSpan")
    assert hasattr(token, "_root_node")


def test_charref_swap_keeps_entities_verbatim() -> None:
    # Importing document_translator swaps the pattern span_tokenizer
    # installs as html._charref inside tokenize() for a never-match, so
    # unescape no-ops. A bump rerouting unescape around that slot starts
    # decoding authored entities again.
    tokens = list(span_token.tokenize_inner("&copy;"))
    contents = [getattr(t, "content", "") for t in tokens]
    assert "".join(contents) == "&copy;"


def test_document_parse_surfaces() -> None:
    doc = mistletoe.Document("[x][r]\n\n[r]: /dest\n")
    assert token._root_node is None
    assert doc.footnotes["r"] == ("/dest", "")

    list_block = mistletoe.Document("- a\n- b\n").children[0]
    assert hasattr(list_block, "loose")

    paragraph = mistletoe.Document("hello\n").children[0]
    original_children = paragraph.children
    paragraph.children = []
    assert paragraph.children == []
    paragraph.children = original_children


def test_render_map_dispatch_surfaces() -> None:
    dispatched_names = (
        "Document",
        "List",
        "ListItem",
        "Table",
        "TableRow",
        "Quote",
        "Paragraph",
        "Heading",
        "TableCell",
        "SetextHeading",
    )
    with document_translator._CustomMarkdownRenderer() as renderer:
        assert isinstance(renderer.render_map, dict)
        for name in dispatched_names:
            assert name in renderer.render_map
        params = inspect.signature(renderer.render_map["Paragraph"]).parameters
        assert "max_line_length" in params
