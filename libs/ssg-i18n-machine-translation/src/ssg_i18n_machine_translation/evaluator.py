import re
from dataclasses import dataclass
from pathlib import Path

import sacrebleu
import yaml
from mistletoe.block_token import Document
from mistletoe.markdown_renderer import MarkdownRenderer
from ssg_i18n.application.document_translation import DocumentTranslator
from ssg_i18n.application.translation import TextTranslator
from ssg_i18n.domain.locale import Locale


@dataclass(frozen=True)
class LineResult:
    is_fallback: bool
    is_wiki_mismatch: bool
    is_table_mismatch: bool


@dataclass(frozen=True)
class TranslationEvaluationReport:
    total_lines_evaluated: int
    english_fallback_lines: int
    english_fallback_rate_pct: float
    wikilink_syntax_mismatches: int
    table_formatting_mismatches: int
    bleu_score_against_catalog: float | None
    passed: bool
    failures: list[str]
    logs: list[str]


def is_code_fence(line: str) -> bool:
    stripped = line.strip()
    result = stripped.startswith("```")
    return result


def is_empty_or_whitespace(line: str) -> bool:
    stripped = line.strip()
    result = not stripped
    return result


def is_math_block(line: str) -> bool:
    s = line.strip()
    result = s.startswith("$$") or (s.startswith("$") and s.endswith("$"))
    return result


def is_horizontal_rule(line: str) -> bool:
    stripped = line.strip()
    result = bool(re.fullmatch(r"\s*-{3,}\s*", stripped))
    return result


def clean_line_for_comparison(line: str) -> str:
    line = line.strip().removesuffix("\n")
    line = re.sub(r"^(\s*(?:[*\-+]|\d+\.)\s+)", "", line)
    return line.strip()


def extract_text_nodes(node: object) -> list[object]:
    class_name = node.__class__.__name__
    if class_name in ("Document", "List", "ListItem", "Table", "TableRow"):
        nodes = []
        header = getattr(node, "header", None)
        if class_name == "Table" and header:
            nodes.extend(extract_text_nodes(header))
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


def render_node(node: object, renderer: MarkdownRenderer) -> str:
    if node.__class__.__name__ == "TableCell":
        lines = renderer.span_to_lines(
            getattr(node, "children", None) or [], max_line_length=0
        )
        return next(iter(lines), "")
    wrapper = Document([])
    wrapper.children = [node]  # type: ignore[list-item]
    return renderer.render(wrapper).strip()


def evaluate_node_pair(src: str, trans: str) -> LineResult:
    src_clean = clean_line_for_comparison(src)
    trans_clean = clean_line_for_comparison(trans)
    is_fallback = (
        src_clean == trans_clean
        and len(src_clean) > 3
        and not re.fullmatch(r"[^a-zA-Z]+", src_clean)
    )
    src_pipes, trans_pipes = src.count("|"), trans.count("|")
    if src.strip().startswith("|"):
        return LineResult(
            is_fallback=is_fallback,
            is_wiki_mismatch=False,
            is_table_mismatch=(src_pipes != trans_pipes),
        )
    src_opens, trans_opens = src.count("[["), trans.count("[[")
    src_closes, trans_closes = src.count("]]"), trans.count("]]")
    is_wiki = (
        src_pipes != trans_pipes
        or src_opens != trans_opens
        or src_closes != trans_closes
    )
    return LineResult(is_fallback, is_wiki, False)


class MachineTranslationEvaluator:
    def __init__(
        self,
        translator: TextTranslator | None = None,
        max_fallback_rate_pct: float = 8.0,
        max_wikilink_syntax_mismatches: int = 0,
        max_table_formatting_mismatches: int = 0,
        min_bleu_score: float = 40.0,
    ) -> None:
        if translator is None:
            from ssg_i18n_machine_translation.transformers_text_translator import (
                TransformersTextTranslator,
            )

            translator = TransformersTextTranslator()
        self._translator = translator
        self._max_fallback_rate_pct = max_fallback_rate_pct
        self._max_wikilink_syntax_mismatches = max_wikilink_syntax_mismatches
        self._max_table_formatting_mismatches = max_table_formatting_mismatches
        self._min_bleu_score = min_bleu_score

    def _find_file_pairs(
        self, source_dir: Path, translated_dir: Path
    ) -> list[tuple[Path, Path]]:
        pairs: list[tuple[Path, Path]] = []
        for src_file in source_dir.rglob("*.md"):
            rel_path = src_file.relative_to(source_dir)
            trans_file = translated_dir / rel_path
            if trans_file.exists():
                pairs.append((src_file, trans_file))
        return pairs

    def _get_matched_nodes(
        self, src_file: Path, trans_file: Path, logs: list[str]
    ) -> list[tuple[object, object]]:
        src_doc = Document(src_file.read_text(encoding="utf-8"))
        trans_doc = Document(trans_file.read_text(encoding="utf-8"))
        src_nodes = extract_text_nodes(src_doc)
        trans_nodes = extract_text_nodes(trans_doc)
        if len(src_nodes) != len(trans_nodes):
            msg = (
                f"[STRUCTURE MISMATCH] File '{src_file.name}' has "
                f"{len(src_nodes)} source nodes, but '{trans_file.name}' "
                f"has {len(trans_nodes)} translated nodes."
            )
            logs.append(msg)
        return list(zip(src_nodes, trans_nodes, strict=False))

    def _evaluate_node_list(
        self,
        node_pairs: list[tuple[object, object]],
        filename: str,
        logs: list[str],
    ) -> tuple[int, int, int, int]:
        total, fallback, wiki, table = 0, 0, 0, 0
        with MarkdownRenderer() as renderer:
            for src_node, trans_node in node_pairs:
                src_str = render_node(src_node, renderer)
                trans_str = render_node(trans_node, renderer)
                res = evaluate_node_pair(src_str, trans_str)
                total += 1
                self._log_violations(res, src_str, trans_str, filename, logs)
                fallback += int(res.is_fallback)
                wiki += int(res.is_wiki_mismatch)
                table += int(res.is_table_mismatch)
        return total, fallback, wiki, table

    def _log_violations(
        self,
        res: LineResult,
        src_str: str,
        trans_str: str,
        filename: str,
        logs: list[str],
    ) -> None:
        if res.is_fallback:
            logs.append(
                f"[FALLBACK] In '{filename}': '{src_str}' -> '{trans_str}'"
            )
        if res.is_wiki_mismatch:
            logs.append(
                f"[WIKILINK MISMATCH] In '{filename}': '{src_str}' -> '{trans_str}'"
            )
        if res.is_table_mismatch:
            logs.append(
                f"[TABLE MISMATCH] In '{filename}': '{src_str}' -> '{trans_str}'"
            )

    def _get_bleu_sentences(self, translations: dict[str, str]) -> list[str]:
        return [
            k
            for k in translations.keys()
            if len(k.split()) > 5
            and not k.startswith("Start with")
            and not k.startswith("The collector")
        ]

    def _calculate_bleu_score(
        self,
        catalog_path: Path,
        locale: Locale,
    ) -> float:
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        translations = catalog.get("translations", {})
        doc_translator = DocumentTranslator(self._translator)
        hypotheses: list[str] = []
        references: list[list[str]] = []
        sentences = self._get_bleu_sentences(translations)
        self._gather_bleu_data(
            sentences,
            translations,
            doc_translator,
            locale,
            hypotheses,
            references,
        )
        if not hypotheses:
            return 0.0
        return float(sacrebleu.corpus_bleu(hypotheses, references).score)

    def _gather_bleu_data(
        self,
        sentences: list[str],
        translations: dict[str, str],
        translator: DocumentTranslator,
        locale: Locale,
        hypotheses: list[str],
        references: list[list[str]],
    ) -> None:
        for eng_text in sentences:
            trans_text = translator.translate_markdown_source(
                eng_text, locale
            ).strip()
            hypotheses.append(trans_text)
            references.append([translations[eng_text]])

    def evaluate(
        self,
        source_dir: Path,
        translated_dir: Path,
        catalog_path: Path | None = None,
        target_locale: Locale | None = None,
    ) -> TranslationEvaluationReport:
        locale = target_locale or Locale("pt-BR")
        logs: list[str] = []
        pairs = self._find_file_pairs(source_dir, translated_dir)
        total, fallback, wiki, table = 0, 0, 0, 0
        for src_file, trans_file in pairs:
            node_pairs = self._get_matched_nodes(src_file, trans_file, logs)
            t, f, w, tab = self._evaluate_node_list(
                node_pairs, src_file.name, logs
            )
            total += t
            fallback += f
            wiki += w
            table += tab

        bleu = None
        if catalog_path is not None and catalog_path.exists():
            bleu = self._calculate_bleu_score(catalog_path, locale)

        return self._build_report(total, fallback, wiki, table, bleu, logs)

    def _check_thresholds(
        self,
        fallback_rate: float,
        wiki: int,
        table: int,
        bleu: float | None,
    ) -> list[str]:
        failures: list[str] = []
        if fallback_rate > self._max_fallback_rate_pct:
            failures.append(
                f"Fallback rate {fallback_rate:.2f}% exceeds threshold {self._max_fallback_rate_pct:.2f}%"
            )
        if wiki > self._max_wikilink_syntax_mismatches:
            failures.append(
                f"Wikilink syntax mismatches {wiki} exceeds threshold {self._max_wikilink_syntax_mismatches}"
            )
        if table > self._max_table_formatting_mismatches:
            failures.append(
                f"Table formatting mismatches {table} exceeds threshold {self._max_table_formatting_mismatches}"
            )
        if bleu is not None and bleu < self._min_bleu_score:
            failures.append(
                f"BLEU score {bleu:.2f} is below threshold {self._min_bleu_score:.2f}"
            )
        return failures

    def _build_report(
        self,
        total: int,
        fallback: int,
        wiki: int,
        table: int,
        bleu: float | None,
        logs: list[str],
    ) -> TranslationEvaluationReport:
        fallback_rate = (fallback / total * 100) if total > 0 else 0.0
        failures = self._check_thresholds(fallback_rate, wiki, table, bleu)
        return TranslationEvaluationReport(
            total_lines_evaluated=total,
            english_fallback_lines=fallback,
            english_fallback_rate_pct=round(fallback_rate, 2),
            wikilink_syntax_mismatches=wiki,
            table_formatting_mismatches=table,
            bleu_score_against_catalog=round(bleu, 2)
            if bleu is not None
            else None,
            passed=(len(failures) == 0),
            failures=failures,
            logs=logs,
        )
