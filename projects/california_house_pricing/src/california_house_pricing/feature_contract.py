"""Ordered feature contract shared by training data, Feast and serving.

Both the training job and the inference image consume a positional float
vector — the column order below is the single source of truth for that
layout. Changing it is a breaking model change, not a rename.
"""

ENTITY_COLUMN: str = "block_group_id"
TIMESTAMP_COLUMN: str = "event_timestamp"
LABEL_COLUMN: str = "median_house_value"

# Positional order consumed by the model; names align with the Feast view.
FEATURE_COLUMNS: list[str] = [
    "median_income",
    "house_age",
    "avg_rooms",
    "avg_bedrooms",
    "population",
    "avg_occupancy",
    "latitude",
    "longitude",
]

REQUIRED_COLUMNS: list[str] = [
    ENTITY_COLUMN,
    TIMESTAMP_COLUMN,
    *FEATURE_COLUMNS,
]
