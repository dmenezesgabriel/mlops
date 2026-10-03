import re
from collections.abc import Mapping
from pathlib import Path

import sacrebleu
import yaml
from mistletoe.block_token import Document
from mistletoe.markdown_renderer import MarkdownRenderer
from ssg_i18n.application.ports.text_translator import TextTranslator
from ssg_i18n.application.use_cases.document_translator import (
    DocumentTranslator,
)
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.infrastructure.yaml_translation_catalog_repository import (
    YamlTranslationCatalogRepository,
)

from ssg_i18n_machine_translation.domain.value_objects.line_result import (
    LineResult,
)
from ssg_i18n_machine_translation.domain.value_objects.translation_evaluation_report import (
    TranslationEvaluationReport,
)

# mistletoe block names whose children are translated as one unit — kept in
# parity with document_translator._LEAF_BLOCK_NAMES: every block the
# translator can translate must be visible to the evaluator.
_LEAF_BLOCK_NAMES = (
    "Paragraph",
    "Heading",
    "TableCell",
    "SetextHeading",
)

# The {{…}}/{%…%} alternatives of document_translator._PROTECTED_PATTERN:
# the translator protects these spans verbatim, so the evaluator verifies
# they survive verbatim.
_DIRECTIVE_SPAN_PATTERN = re.compile(r"\{\{.*?\}\}|\{\%.*?\%\}", re.DOTALL)


def _require_directory(path: Path, name: str) -> None:
    if not path.is_dir():
        raise FileNotFoundError(
            f"{name} must be an existing directory, got: '{path}'"
        )


def _require_file(path: Path, name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"{name} must be an existing file, got: '{path}'"
        )


def clean_line_for_comparison(line: str) -> str:
    line = line.strip().removesuffix("\n")
    line = re.sub(r"^(\s*(?:[*\-+]|\d+\.)\s+)", "", line)
    return line.strip()


def extract_text_nodes(node: object) -> list[object]:
    if node.__class__.__name__ in _LEAF_BLOCK_NAMES:
        return [node]
    nodes: list[object] = []
    # Every non-leaf node is walked: a container whitelist could only route
    # to this same walk, and an unlisted container (Quote was one) must not
    # silently skip its subtree — eval-side mirror of the G-82 dispatch fix.
    header = getattr(node, "header", None)
    if header:
        nodes.extend(extract_text_nodes(header))
    for child in getattr(node, "children", []):
        nodes.extend(extract_text_nodes(child))
    return nodes


def _directive_spans(text: str) -> list[str]:
    return _DIRECTIVE_SPAN_PATTERN.findall(text)


def render_node(node: object, renderer: MarkdownRenderer) -> str:
    if node.__class__.__name__ == "TableCell":
        lines = renderer.span_to_lines(
            getattr(node, "children", None) or [], max_line_length=0
        )
        return next(iter(lines), "")
    wrapper = Document([])
    # extract_text_nodes yields only mistletoe block tokens, so node is a
    # valid children element; the throwaway Document is a render carrier —
    # MarkdownRenderer.render() only iterates .children.
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
    is_directive_mismatch = _directive_spans(src) != _directive_spans(trans)
    src_pipes, trans_pipes = src.count("|"), trans.count("|")
    if src.strip().startswith("|"):
        return LineResult(
            is_fallback=is_fallback,
            is_wiki_mismatch=False,
            is_table_mismatch=(src_pipes != trans_pipes),
            is_directive_mismatch=is_directive_mismatch,
        )
    src_opens, trans_opens = src.count("[["), trans.count("[[")
    src_closes, trans_closes = src.count("]]"), trans.count("]]")
    is_wiki = (
        src_pipes != trans_pipes
        or src_opens != trans_opens
        or src_closes != trans_closes
    )
    return LineResult(is_fallback, is_wiki, False, is_directive_mismatch)


class MachineTranslationEvaluator:
    """Evaluates machine-translated documents against quality thresholds.

    Example:
        evaluator = MachineTranslationEvaluator(translator=InMemoryTextTranslator({}))
        report = evaluator.evaluate(source_dir, translated_dir)
    """

    def __init__(
        self,
        translator: TextTranslator | None = None,
        max_fallback_rate_pct: float = 8.0,
        max_wikilink_syntax_mismatches: int = 0,
        max_table_formatting_mismatches: int = 0,
        min_bleu_score: float = 40.0,
    ) -> None:
        if translator is None:
            from ssg_i18n_machine_translation.infrastructure.transformers_text_translator import (
                TransformersTextTranslator,
            )

            translator = TransformersTextTranslator()
        self._translator = translator
        self._max_fallback_rate_pct = max_fallback_rate_pct
        self._max_wikilink_syntax_mismatches = max_wikilink_syntax_mismatches
        self._max_table_formatting_mismatches = max_table_formatting_mismatches
        self._min_bleu_score = min_bleu_score

    def _find_file_pairs(
        self,
        source_dir: Path,
        translated_dir: Path,
        failures: list[str],
    ) -> list[tuple[Path, Path]]:
        source_files = list(source_dir.rglob("*.md"))
        if not source_files:
            failures.append(f"No '*.md' source files found in '{source_dir}'")
        pairs: list[tuple[Path, Path]] = []
        for src_file in source_files:
            rel_path = src_file.relative_to(source_dir)
            trans_file = translated_dir / rel_path
            if not trans_file.exists():
                failures.append(f"Missing translated file: '{rel_path}'")
                continue
            pairs.append((src_file, trans_file))
        return pairs

    def _get_matched_nodes(
        self, src_file: Path, trans_file: Path, failures: list[str]
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
            failures.append(msg)
        return list(zip(src_nodes, trans_nodes, strict=False))

    def _evaluate_node_list(
        self,
        node_pairs: list[tuple[object, object]],
        filename: str,
        logs: list[str],
        failures: list[str],
    ) -> tuple[int, int, int, int]:
        total, fallback, wiki, table = 0, 0, 0, 0
        with MarkdownRenderer() as renderer:
            for src_node, trans_node in node_pairs:
                src_str = render_node(src_node, renderer)
                trans_str = render_node(trans_node, renderer)
                result = evaluate_node_pair(src_str, trans_str)
                total += 1
                self._log_violations(
                    result, src_str, trans_str, filename, logs
                )
                if result.is_directive_mismatch:
                    failures.append(
                        f"[DIRECTIVE MISMATCH] In '{filename}': "
                        f"'{src_str}' -> '{trans_str}'"
                    )
                fallback += int(result.is_fallback)
                wiki += int(result.is_wiki_mismatch)
                table += int(result.is_table_mismatch)
        return total, fallback, wiki, table

    def _log_violations(
        self,
        result: LineResult,
        src_str: str,
        trans_str: str,
        filename: str,
        logs: list[str],
    ) -> None:
        if result.is_fallback:
            logs.append(
                f"[FALLBACK] In '{filename}': '{src_str}' -> '{trans_str}'"
            )
        if result.is_wiki_mismatch:
            logs.append(
                f"[WIKILINK MISMATCH] In '{filename}': '{src_str}' -> '{trans_str}'"
            )
        if result.is_table_mismatch:
            logs.append(
                f"[TABLE MISMATCH] In '{filename}': '{src_str}' -> '{trans_str}'"
            )

    def _get_bleu_sentences(
        self, translations: Mapping[str, str]
    ) -> list[str]:
        return [key for key in translations.keys() if len(key.split()) > 5]

    def _calculate_bleu_score(
        self,
        catalog_path: Path,
        locale: Locale,
    ) -> float:
        try:
            catalog = YamlTranslationCatalogRepository().load(catalog_path)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"Invalid i18n catalog {catalog_path}: {exc}"
            ) from exc
        if not catalog.translations:
            raise ValueError(
                f"Invalid i18n catalog {catalog_path}: "
                "expected non-empty translations mapping"
            )
        translations = catalog.translations
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
        # sacrebleu ships no type stubs; corpus_bleu().score is float per
        # its public API contract.
        return float(sacrebleu.corpus_bleu(hypotheses, references).score)  # pyright: ignore[reportUnknownMemberType]

    def _gather_bleu_data(
        self,
        sentences: list[str],
        translations: Mapping[str, str],
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
        _require_directory(source_dir, "source_dir")
        _require_directory(translated_dir, "translated_dir")
        logs: list[str] = []
        structural_failures: list[str] = []
        pairs = self._find_file_pairs(
            source_dir, translated_dir, structural_failures
        )
        total, fallback, wiki, table = 0, 0, 0, 0
        for src_file, trans_file in pairs:
            node_pairs = self._get_matched_nodes(
                src_file, trans_file, structural_failures
            )
            pair_total, pair_fallback, pair_wiki, pair_table = (
                self._evaluate_node_list(
                    node_pairs, src_file.name, logs, structural_failures
                )
            )
            total += pair_total
            fallback += pair_fallback
            wiki += pair_wiki
            table += pair_table

        bleu = None
        if catalog_path is not None:
            _require_file(catalog_path, "catalog_path")
            bleu = self._calculate_bleu_score(catalog_path, locale)

        return self._build_report(
            total, fallback, wiki, table, bleu, logs, structural_failures
        )

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
        structural_failures: list[str],
    ) -> TranslationEvaluationReport:
        fallback_rate = (fallback / total * 100) if total > 0 else 0.0
        failures = structural_failures + self._check_thresholds(
            fallback_rate, wiki, table, bleu
        )
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
