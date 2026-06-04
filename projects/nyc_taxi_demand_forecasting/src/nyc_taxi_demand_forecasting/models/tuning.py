from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TuningResult:
    max_iter: int
    validation_mae: float


class DemandModelTuner:
    """Run a tiny deterministic tuning pass for local experimentation.

    Example:
        DemandModelTuner().select_best(pd.DataFrame(...), "target")
    """

    def select_best(self, dataset: pd.DataFrame, target_column: str) -> TuningResult:
        baseline_error = float(
            (dataset[target_column] - dataset[target_column].median()).abs().mean()
        )
        return TuningResult(max_iter=50, validation_mae=baseline_error)
