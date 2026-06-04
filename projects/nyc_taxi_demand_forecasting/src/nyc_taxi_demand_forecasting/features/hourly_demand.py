from pathlib import Path

import pandas as pd


class HourlyDemandFeatureBuilder:
    """Create Feast-compatible hourly demand features.

    Example:
        HourlyDemandFeatureBuilder().build(training_path, features_path)
    """

    def build(self, training_dataset_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        training_dataset = pd.read_parquet(training_dataset_path)
        features = self.build_from_dataset(training_dataset)
        features.to_parquet(output_path, index=False)
        return output_path

    def build_from_dataset(self, training_dataset: pd.DataFrame) -> pd.DataFrame:
        feature_columns = [
            "pickup_location_id",
            "pickup_hour",
            "pickup_count",
            "hour",
            "day_of_week",
            "is_weekend",
            "month",
        ]
        features = training_dataset.loc[:, feature_columns].copy()
        return features.rename(columns={"pickup_hour": "event_timestamp"})
