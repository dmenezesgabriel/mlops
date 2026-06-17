# Backward-compatible re-export — import from canonical location instead.
from videos.domain.value_objects.quality import QualityReport, RuleViolation

__all__ = ["RuleViolation", "QualityReport"]
