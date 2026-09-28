# Backward-compatible re-exports — import from canonical locations instead.
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    MachineTranslationEvaluator,
    clean_line_for_comparison,
    evaluate_node_pair,
    extract_text_nodes,
    is_code_fence,
    is_empty_or_whitespace,
    is_horizontal_rule,
    is_math_block,
    render_node,
)
from ssg_i18n_machine_translation.domain.value_objects.line_result import (
    LineResult,
)
from ssg_i18n_machine_translation.domain.value_objects.translation_evaluation_report import (
    TranslationEvaluationReport,
)

__all__ = [
    "LineResult",
    "TranslationEvaluationReport",
    "is_code_fence",
    "is_empty_or_whitespace",
    "is_math_block",
    "is_horizontal_rule",
    "clean_line_for_comparison",
    "extract_text_nodes",
    "render_node",
    "evaluate_node_pair",
    "MachineTranslationEvaluator",
]
