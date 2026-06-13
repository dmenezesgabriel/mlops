import json
import re
import sys
from pathlib import Path

import sacrebleu
import yaml

# Add ssg-i18n and ssg-i18n-machine-translation to path
repo_root = Path(__file__).resolve().parents[3]
sys.path.extend(
    [
        str(repo_root / "libs" / "ssg-i18n" / "src"),
        str(repo_root / "libs" / "ssg-i18n-machine-translation" / "src"),
    ]
)

from ssg_i18n.application.document_translation import (  # noqa: E402
    DocumentTranslator,
)
from ssg_i18n.domain.locale import Locale  # noqa: E402
from ssg_i18n_machine_translation.transformers_text_translator import (  # noqa: E402
    TransformersTextTranslator,
)

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


def evaluate_translation_files():
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

    total_lines_evaluated = 0
    fallback_lines_count = 0
    wikilink_mismatches = 0
    table_mismatches = 0

    # Process markdown docs
    for src_file in docs_dir.glob("*.md"):
        trans_file = translated_docs_dir / src_file.name
        if not trans_file.exists():
            continue

        src_lines = src_file.read_text(encoding="utf-8").splitlines()
        trans_lines = trans_file.read_text(encoding="utf-8").splitlines()

        inside_code = False
        for src, trans in zip(src_lines, trans_lines, strict=True):
            if is_code_fence(src):
                inside_code = not inside_code
                continue
            if (
                inside_code
                or is_empty_or_whitespace(src)
                or is_math_block(src)
                or is_horizontal_rule(src)
            ):
                continue

            total_lines_evaluated += 1

            src_clean = clean_line_for_comparison(src)
            trans_clean = clean_line_for_comparison(trans)

            # Check for English fallback
            # We ignore very short words or lines that are entirely markers or punctuation
            if (
                src_clean == trans_clean
                and len(src_clean) > 3
                and not re.fullmatch(r"[^a-zA-Z]+", src_clean)
            ):
                fallback_lines_count += 1

            # Check for Wikilink syntax preservation
            src_pipes = src.count("|")
            trans_pipes = trans.count("|")
            src_opens = src.count("[[")
            trans_opens = trans.count("[[")
            src_closes = src.count("]]")
            trans_closes = trans.count("]]")

            # If it's a table row, pipe counts are checked separately
            if src.strip().startswith("|"):
                if src_pipes != trans_pipes:
                    table_mismatches += 1
            else:
                if (
                    src_pipes != trans_pipes
                    or src_opens != trans_opens
                    or src_closes != trans_closes
                ):
                    wikilink_mismatches += 1

    # Evaluate BLEU score against manually translated catalog items
    catalog_path = repo_root / "site" / "i18n" / "pt-BR.yaml"
    bleu_score = 0.0

    if catalog_path.exists():
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        translations = catalog.get("translations", {})

        translator = TransformersTextTranslator()
        doc_translator = DocumentTranslator(translator)

        hypotheses = []
        references = []

        # Test a representative sample of 10 long sentences from the catalog
        # (avoiding simple titles to test translation capability)
        test_sentences = [
            k
            for k in translations.keys()
            if len(k.split()) > 5
            and not k.startswith("Start with")
            and not k.startswith("The collector")
        ]

        for eng_text in test_sentences:
            ref_text = translations[eng_text]
            # Translate using full document pipeline
            trans_text = doc_translator.translate_markdown_source(
                eng_text, PT_BR
            ).strip()
            hypotheses.append(trans_text)
            references.append([ref_text])

        if hypotheses:
            bleu = sacrebleu.corpus_bleu(hypotheses, references)
            bleu_score = bleu.score

    fallback_rate = (
        (fallback_lines_count / total_lines_evaluated * 100)
        if total_lines_evaluated > 0
        else 0.0
    )

    results = {
        "total_lines_evaluated": total_lines_evaluated,
        "english_fallback_lines": fallback_lines_count,
        "english_fallback_rate_pct": round(fallback_rate, 2),
        "wikilink_syntax_mismatches": wikilink_mismatches,
        "table_formatting_mismatches": table_mismatches,
        "bleu_score_against_catalog": round(bleu_score, 2),
    }

    return results


if __name__ == "__main__":
    print("Evaluating current translation outputs...")
    metrics = evaluate_translation_files()
    print(json.dumps(metrics, indent=2))

    # Save the results to baseline.json
    output_path = Path(__file__).parent / "baseline.json"
    output_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Baseline metrics saved to {output_path}")
