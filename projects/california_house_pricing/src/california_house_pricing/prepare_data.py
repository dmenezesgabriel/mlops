"""Build Feast-ready parquet tables from the California housing dataset.

Splits the sklearn frame into a feature table (block-group attributes) and a
label table (median house value) with a shared event timestamp, so Feast can
produce point-in-time-correct training sets and materialize online features.

Run:  python -m california_house_pricing.prepare_data
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.datasets import fetch_california_housing

from .feature_contract import (
    ENTITY_COLUMN,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    TIMESTAMP_COLUMN,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PROCESSED_DIR = DATA_DIR / "processed"
EVENT_DATE = pd.Timestamp("2020-06-30", tz="UTC")

# sklearn raw names -> business names used everywhere downstream.
RENAME = {
    "MedInc": "median_income",
    "HouseAge": "house_age",
    "AveRooms": "avg_rooms",
    "AveBedrms": "avg_bedrooms",
    "Population": "population",
    "AveOccup": "avg_occupancy",
    "Latitude": "latitude",
    "Longitude": "longitude",
}


def load_frame() -> pd.DataFrame:
    """Fetch the dataset and return it renamed to the business schema."""
    dataset = fetch_california_housing(as_frame=True)
    frame = dataset.frame.rename(
        columns={"MedHouseVal": LABEL_COLUMN, **RENAME}
    )
    return frame


def build_tables(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the frame into (features, labels) Feast tables."""
    entities = pd.DataFrame(
        {
            ENTITY_COLUMN: [f"bg-{i:05d}" for i in range(len(frame))],
            TIMESTAMP_COLUMN: EVENT_DATE,
        }
    )
    features = pd.concat(
        [entities, frame[FEATURE_COLUMNS].reset_index(drop=True)], axis=1
    )
    labels = pd.concat(
        [entities, frame[[LABEL_COLUMN]].reset_index(drop=True)], axis=1
    )
    return features, labels


def main() -> None:
    frame = load_frame()
    features, labels = build_tables(frame)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    features.to_parquet(
        PROCESSED_DIR / "block_group_features.parquet", index=False
    )
    labels.to_parquet(PROCESSED_DIR / "house_values.parquet", index=False)
    schema = {
        "entity": ENTITY_COLUMN,
        "timestamp": TIMESTAMP_COLUMN,
        "label": LABEL_COLUMN,
        "features": FEATURE_COLUMNS,
        "rows": len(features),
    }
    (PROCESSED_DIR / "feature_schema.json").write_text(
        json.dumps(schema, indent=2)
    )
    print(f"wrote {len(features)} feature rows and {len(labels)} labels")


if __name__ == "__main__":
    main()
