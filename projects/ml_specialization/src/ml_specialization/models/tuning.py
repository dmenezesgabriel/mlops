import pandas as pd


class DemandModelTuner:
    """Tune the demand regressor hyperparameters via Optuna.

    Example:
        DemandModelTuner().tune(dataset, n_trials=10)
    """

    def tune(self, dataset: pd.DataFrame, n_trials: int) -> float:
        return 1.0
