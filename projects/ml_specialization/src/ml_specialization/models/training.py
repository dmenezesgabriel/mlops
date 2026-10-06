import math

import pandas as pd


class DemandDatasetSplitter:
    """Split ordered forecasting rows into train and holdout frames.

    The last ``ceil(n * test_size)`` rows form the holdout, clamped so the
    train frame always keeps at least one row.

    Example:
        DemandDatasetSplitter().split(dataset, test_size=0.2)
    """

    def split(
        self, dataset: pd.DataFrame, test_size: float
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not 0 < test_size < 1:
            raise ValueError(
                f"Invalid test_size {test_size}: expected 0 < test_size < 1"
            )
        if len(dataset) < 2:
            raise ValueError(
                f"Invalid dataset of {len(dataset)} rows: "
                "expected at least 2 rows to split"
            )
        holdout_size = min(
            math.ceil(len(dataset) * test_size), len(dataset) - 1
        )
        split_index = len(dataset) - holdout_size
        return dataset.iloc[:split_index].copy(), dataset.iloc[
            split_index:
        ].copy()
