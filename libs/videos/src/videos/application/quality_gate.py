# Backward-compatible re-export — import from canonical location instead.
from videos.application.use_cases.quality_gate import (
    QualityGate,
    RuleValidator,
    ValidatorProtocol,
)

__all__ = ["RuleValidator", "ValidatorProtocol", "QualityGate"]
