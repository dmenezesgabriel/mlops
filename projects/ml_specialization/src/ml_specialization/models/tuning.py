import pandas as pd


class DemandModelTuner:
    """Tune the demand regressor hyperparameters via Optuna.

    Stub left for the specialization exercises — calls raise
    NotImplementedError.

    Example:
        DemandModelTuner().tune(dataset, n_trials=10)
    """

    def tune(self, dataset: pd.DataFrame, n_trials: int) -> float:
        raise NotImplementedError("DemandModelTuner.tune is not implemented")
