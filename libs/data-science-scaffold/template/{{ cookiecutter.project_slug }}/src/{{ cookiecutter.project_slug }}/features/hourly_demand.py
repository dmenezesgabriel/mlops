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
        training_dataset.to_parquet(output_path, index=False)
        return output_path
