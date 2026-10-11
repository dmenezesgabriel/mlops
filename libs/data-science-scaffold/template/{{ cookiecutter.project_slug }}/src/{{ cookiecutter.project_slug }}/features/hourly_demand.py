from pathlib import Path

import pandas as pd

# The hourly_pickup_demand feature contract — the feature_repo defs declare
# the same schema but cannot import this package, so a test pins the
# lockstep instead of a shared constant.
FEATURE_VIEW_NAME = "hourly_pickup_demand"
FEATURE_COLUMNS: tuple[str, ...] = (
    "pickup_count",
    "hour",
    "day_of_week",
    "is_weekend",
    "month",
)
FEATURE_REFS: tuple[str, ...] = tuple(
    f"{FEATURE_VIEW_NAME}:{name}" for name in FEATURE_COLUMNS
)
ENTITY_COLUMNS: tuple[str, ...] = (
    "pickup_location_id",
    "event_timestamp",
    "next_hour_pickup_count",
)


def load_entity_df(dataset_path: Path) -> pd.DataFrame:
    """Load a supervised dataset as the Feast entity frame for this view.

    Synthesizes ``event_timestamp`` from ``pickup_hour`` when absent and
    projects down to the entity key, timestamp, and label columns.

    Example:
        entity_df = load_entity_df(Path("data/processed/training.parquet"))
    """
    entity_df = pd.read_parquet(dataset_path)
    if "event_timestamp" not in entity_df.columns:
        entity_df["event_timestamp"] = pd.to_datetime(entity_df["pickup_hour"])
    entity_df["event_timestamp"] = pd.to_datetime(entity_df["event_timestamp"])
    return entity_df.loc[:, list(ENTITY_COLUMNS)]


class HourlyDemandFeatureBuilder:
    """Create Feast-compatible hourly demand features.

    Scaffolded stub — calls raise NotImplementedError.

    Example:
        HourlyDemandFeatureBuilder().build(training_path, features_path)
    """

    def build(self, training_dataset_path: Path, output_path: Path) -> Path:
        raise NotImplementedError(
            "HourlyDemandFeatureBuilder.build is not implemented"
        )
