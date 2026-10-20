"""Ordered feature contract shared by training data, Feast and serving.

The wine classifier consumes a positional float vector; the column order
below is the single source of truth for that layout.
"""

ENTITY_COLUMN: str = "wine_id"
TIMESTAMP_COLUMN: str = "event_timestamp"
LABEL_COLUMN: str = "cultivar"

# sklearn wine dataset's 13 physicochemical measures, in dataset order.
FEATURE_COLUMNS: list[str] = [
    "alcohol",
    "malic_acid",
    "ash",
    "alcalinity_of_ash",
    "magnesium",
    "total_phenols",
    "flavanoids",
    "nonflavanoid_phenols",
    "proanthocyanins",
    "color_intensity",
    "hue",
    "od280_od315_of_diluted_wines",
    "proline",
]

REQUIRED_COLUMNS: list[str] = [
    ENTITY_COLUMN,
    TIMESTAMP_COLUMN,
    *FEATURE_COLUMNS,
]
