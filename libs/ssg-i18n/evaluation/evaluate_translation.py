import json
import re
from pathlib import Path
from typing import Any

import mistletoe
import sacrebleu
import yaml
from ssg_i18n.application.document_translation import DocumentTranslator
from ssg_i18n.domain.locale import Locale
from ssg_i18n_machine_translation.transformers_text_translator import (
    TransformersTextTranslator,
)

repo_root = Path(__file__).resolve().parents[3]
PT_BR = Locale("pt-BR")


def is_code_fence(line: str) -> bool:
    return line.strip().startswith("```")


def is_empty_or_whitespace(line: str) -> bool:
    return not line.strip()


def is_math_block(line: str) -> bool:
    s = line.strip()
    return s.startswith("$$") or (s.startswith("$") and s.endswith("$"))


def is_horizontal_rule(line: str) -> bool:
    return bool(re.fullmatch(r"\s*-{3,}\s*", line.strip()))


def clean_line_for_comparison(line: str) -> str:
    # Strip list prefixes, indentation, and trailing newlines
    line = line.strip().removesuffix("\n")
    line = re.sub(r"^(\s*(?:[*\-+]|\d+\.)\s+)", "", line)
    return line.strip()


def extract_text_nodes(node: object) -> list[object]:
    class_name = node.__class__.__name__
    if class_name in ("Document", "List", "ListItem", "Table", "TableRow"):
        nodes = []
        for child in getattr(node, "children", []):
            nodes.extend(extract_text_nodes(child))
        return nodes
    if class_name not in ("Paragraph", "Heading", "TableCell"):
        return []
    children = getattr(node, "children", [])
    has_jinja = any(
        c.__class__.__name__ == "RawText"
        and ("{{" in c.content or "{%" in c.content)
        for c in children
    )
    if has_jinja:
        return []
    return [node]


def _evaluate_node_pair(
    src: str,
    trans: str,
    stats: dict[str, int],
) -> None:
    stats["total"] += 1
    src_clean = clean_line_for_comparison(src)
    trans_clean = clean_line_for_comparison(trans)

    if (
        src_clean == trans_clean
        and len(src_clean) > 3
        and not re.fullmatch(r"[^a-zA-Z]+", src_clean)
    ):
        stats["fallback"] += 1

    src_pipes, trans_pipes = src.count("|"), trans.count("|")
    src_opens, trans_opens = src.count("[["), trans.count("[[")
    src_closes, trans_closes = src.count("]]"), trans.count("]]")

    if src.strip().startswith("|"):
        if src_pipes != trans_pipes:
            stats["table_mismatch"] += 1
        return

    if (
        src_pipes != trans_pipes
        or src_opens != trans_opens
        or src_closes != trans_closes
    ):
        stats["wiki_mismatch"] += 1


def _render_node(
    node: object, renderer: mistletoe.markdown_renderer.MarkdownRenderer
) -> str:
    if node.__class__.__name__ == "TableCell":
        return next(
            renderer.span_to_lines(
                getattr(node, "children", None) or [], max_line_length=None
            ),
            "",
        )
    wrapper = mistletoe.block_token.Document([])
    wrapper.children = [node]
    return renderer.render(wrapper).strip()


def _evaluate_file(
    src_file: Path,
    trans_file: Path,
    stats: dict[str, int],
) -> None:
    src_doc = mistletoe.Document(src_file.read_text(encoding="utf-8"))
    trans_doc = mistletoe.Document(trans_file.read_text(encoding="utf-8"))
    src_nodes = extract_text_nodes(src_doc)
    trans_nodes = extract_text_nodes(trans_doc)

    with mistletoe.markdown_renderer.MarkdownRenderer() as renderer:
        for src_node, trans_node in zip(src_nodes, trans_nodes, strict=True):
            src_str = _render_node(src_node, renderer)
            trans_str = _render_node(trans_node, renderer)
            _evaluate_node_pair(src_str, trans_str, stats)


def evaluate_translation_files() -> dict[str, Any]:
    docs_dir = repo_root / "projects" / "nyc_taxi_demand_forecasting" / "docs"
    translated_docs_dir = (
        repo_root
        / "site"
        / ".ssg"
        / "generated-i18n"
        / "pt-BR"
        / "nyc_taxi_demand_forecasting"
        / "docs"
    )
    stats = {
        "total": 0,
        "fallback": 0,
        "wiki_mismatch": 0,
        "table_mismatch": 0,
    }
    for src_file in docs_dir.glob("*.md"):
        trans_file = translated_docs_dir / src_file.name
        if trans_file.exists():
            _evaluate_file(src_file, trans_file, stats)
    return _compile_results(stats)


def _compile_results(stats: dict[str, int]) -> dict[str, Any]:
    bleu_score = _calculate_bleu_score()
    fallback_rate = (
        (stats["fallback"] / stats["total"] * 100)
        if stats["total"] > 0
        else 0.0
    )
    return {
        "total_lines_evaluated": stats["total"],
        "english_fallback_lines": stats["fallback"],
        "english_fallback_rate_pct": round(fallback_rate, 2),
        "wikilink_syntax_mismatches": stats["wiki_mismatch"],
        "table_formatting_mismatches": stats["table_mismatch"],
        "bleu_score_against_catalog": round(bleu_score, 2),
    }


def _calculate_bleu_score() -> float:
    catalog_path = repo_root / "site" / "i18n" / "pt-BR.yaml"
    if not catalog_path.exists():
        return 0.0
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    translations = catalog.get("translations", {})
    translator = TransformersTextTranslator()
    doc_translator = DocumentTranslator(translator)
    hypotheses: list[str] = []
    references: list[list[str]] = []
    test_sentences = [
        k
        for k in translations.keys()
        if len(k.split()) > 5
        and not k.startswith("Start with")
        and not k.startswith("The collector")
    ]
    _gather_bleu_data(
        test_sentences, translations, doc_translator, hypotheses, references
    )
    if not hypotheses:
        return 0.0
    return float(sacrebleu.corpus_bleu(hypotheses, references).score)


def _gather_bleu_data(
    sentences: list[str],
    translations: dict[str, str],
    translator: DocumentTranslator,
    hypotheses: list[str],
    references: list[list[str]],
) -> None:
    for eng_text in sentences:
        trans_text = translator.translate_markdown_source(
            eng_text, PT_BR
        ).strip()
        hypotheses.append(trans_text)
        references.append([translations[eng_text]])


if __name__ == "__main__":
    print("Evaluating current translation outputs...")
    metrics = evaluate_translation_files()
    print(json.dumps(metrics, indent=2))

    # Save the results to baseline.json
    output_path = Path(__file__).parent / "baseline.json"
    output_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Baseline metrics saved to {output_path}")
