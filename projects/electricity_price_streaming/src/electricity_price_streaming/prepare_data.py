"""Build Feast-ready tables + a replayable event stream from ELEC2.

Splits the electricity dataset into market-state features and direction
labels (Feast offline + online), and writes `stream_events.jsonl` — the
tick-by-tick replay the Kafka producer feeds to the streaming pipeline.

Run:  python -m electricity_price_streaming.prepare_data
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.datasets import fetch_openml

from .feature_contract import (
    ENTITY_COLUMN,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    TIMESTAMP_COLUMN,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PROCESSED_DIR = DATA_DIR / "processed"


def load_frame() -> pd.DataFrame:
    dataset = fetch_openml("electricity", version=1, as_frame=True)
    frame = dataset.data.copy()
    # OpenML splits the target out of the data frame; join it back under the
    # raw dataset's name so downstream code sees one table.
    frame["class"] = dataset.target.astype(str).str.upper().values
    for col in FEATURE_COLUMNS:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    return frame


def build_tables(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = frame.reset_index(drop=True)
    # ELEC2 rows are half-hour ticks from 1996-05-07; rebase onto real dates
    # so point-in-time semantics stay honest.
    timestamps = pd.Timestamp("1996-05-07", tz="UTC") + pd.to_timedelta(
        frame.index * 30, unit="m"
    )
    entities = pd.DataFrame(
        {
            ENTITY_COLUMN: [f"tick-{i:05d}" for i in range(len(frame))],
            TIMESTAMP_COLUMN: timestamps,
        }
    )
    features = pd.concat(
        [entities, frame[FEATURE_COLUMNS].reset_index(drop=True)], axis=1
    )
    labels = pd.concat(
        [
            entities,
            (frame["class"] == "UP")
            .astype(int)
            .rename(LABEL_COLUMN)
            .reset_index(drop=True),
        ],
        axis=1,
    )
    return features, labels


def write_stream(frame: pd.DataFrame, path: Path) -> None:
    """Replay source: one JSON market tick per line for the Kafka producer."""
    features, _ = build_tables(frame)
    records = features[
        [ENTITY_COLUMN, TIMESTAMP_COLUMN, *FEATURE_COLUMNS]
    ].copy()
    records[TIMESTAMP_COLUMN] = records[TIMESTAMP_COLUMN].astype(str)
    records.to_json(path, orient="records", lines=True)


def main() -> None:
    frame = load_frame()
    features, labels = build_tables(frame)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    features.to_parquet(PROCESSED_DIR / "market_features.parquet", index=False)
    labels.to_parquet(PROCESSED_DIR / "direction_labels.parquet", index=False)
    write_stream(frame, PROCESSED_DIR / "stream_events.jsonl")
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
    print(f"wrote {len(features)} ticks + stream_events.jsonl")


if __name__ == "__main__":
    main()
