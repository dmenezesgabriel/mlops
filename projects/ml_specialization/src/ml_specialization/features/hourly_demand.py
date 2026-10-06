from pathlib import Path


class HourlyDemandFeatureBuilder:
    """Create Feast-compatible hourly demand features.

    Stub left for the specialization exercises — calls raise
    NotImplementedError.

    Example:
        HourlyDemandFeatureBuilder().build(training_path, features_path)
    """

    def build(self, training_dataset_path: Path, output_path: Path) -> Path:
        raise NotImplementedError(
            "HourlyDemandFeatureBuilder.build is not implemented"
        )
