# Backward-compatible re-exports — import from canonical locations instead.
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    MachineTranslationEvaluator,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _clean_line_for_comparison as clean_line_for_comparison,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _evaluate_node_pair as evaluate_node_pair,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _extract_text_nodes as extract_text_nodes,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _is_code_fence as is_code_fence,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _is_empty_or_whitespace as is_empty_or_whitespace,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _is_horizontal_rule as is_horizontal_rule,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _is_math_block as is_math_block,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    _render_node as render_node,
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
