"""Value objects for the machine translation domain."""

from ssg_i18n_machine_translation.domain.value_objects.line_result import (
    LineResult,
)
from ssg_i18n_machine_translation.domain.value_objects.translation_evaluation_report import (
    TranslationEvaluationReport,
)

__all__ = ["LineResult", "TranslationEvaluationReport"]
