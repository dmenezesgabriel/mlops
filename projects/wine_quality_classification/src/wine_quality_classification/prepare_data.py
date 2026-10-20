"""Build Feast-ready parquet tables from the sklearn wine dataset.

Splits the frame into a physicochemical feature table and a cultivar label
table so Feast produces point-in-time-correct training sets for the pipeline.

Run:  python -m wine_quality_classification.prepare_data
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.datasets import load_wine

from .feature_contract import (
    ENTITY_COLUMN,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    TIMESTAMP_COLUMN,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PROCESSED_DIR = DATA_DIR / "processed"
EVENT_DATE = pd.Timestamp("2023-01-01", tz="UTC")

# sklearn slugs -> readable business names where they differ.
RENAME = {"od280/od315_of_diluted_wines": "od280_od315_of_diluted_wines"}


def load_frame() -> pd.DataFrame:
    dataset = load_wine(as_frame=True)
    frame = dataset.frame.rename(columns={**RENAME, "target": LABEL_COLUMN})
    frame[LABEL_COLUMN] = frame[LABEL_COLUMN].astype(int)
    return frame


def build_tables(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    entities = pd.DataFrame(
        {
            ENTITY_COLUMN: [f"wine-{i:03d}" for i in range(len(frame))],
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
    features, labels = build_tables(load_frame())
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    features.to_parquet(PROCESSED_DIR / "wine_features.parquet", index=False)
    labels.to_parquet(PROCESSED_DIR / "wine_labels.parquet", index=False)
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
