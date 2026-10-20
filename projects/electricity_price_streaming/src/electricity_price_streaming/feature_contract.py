"""Ordered feature contract shared by training, Feast and the Flink job.

The price-direction classifier consumes a positional float vector; the
column order below is the single source of truth for that layout.
"""

ENTITY_COLUMN: str = "market_tick_id"
TIMESTAMP_COLUMN: str = "event_timestamp"
LABEL_COLUMN: str = "direction_up"

# ELEC2 stream features: NSW/VIC market state at each half-hour tick.
FEATURE_COLUMNS: list[str] = [
    "day",
    "period",
    "nswprice",
    "nswdemand",
    "vicprice",
    "vicdemand",
    "transfer",
]

REQUIRED_COLUMNS: list[str] = [
    ENTITY_COLUMN,
    TIMESTAMP_COLUMN,
    *FEATURE_COLUMNS,
]
