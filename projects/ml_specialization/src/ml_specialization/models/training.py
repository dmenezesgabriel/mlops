import pandas as pd


class DemandDatasetSplitter:
    """Split ordered forecasting rows into train and holdout frames.

    Example:
        DemandDatasetSplitter().split(dataset, test_size=0.2)
    """

    def split(
        self, dataset: pd.DataFrame, test_size: float
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        split_index = max(1, int(len(dataset) * (1 - test_size)))
        return dataset.iloc[:split_index].copy(), dataset.iloc[
            split_index:
        ].copy()
