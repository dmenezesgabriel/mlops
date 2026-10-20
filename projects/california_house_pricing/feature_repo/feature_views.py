"""Feature views served by this repo.

`block_group_profile` is pushed to DynamoDB by `feast materialize` and read
per-request by the serving path. `house_values` is labels-only (offline).
"""

from datetime import timedelta

from data_sources import block_group_stats, house_values
from entities import block_group
from feast import FeatureView, Field
from feast.types import Float32

block_group_profile = FeatureView(
    name="block_group_profile",
    entities=[block_group],
    ttl=timedelta(days=365),
    schema=[
        Field(name="median_income", dtype=Float32),
        Field(name="house_age", dtype=Float32),
        Field(name="avg_rooms", dtype=Float32),
        Field(name="avg_bedrooms", dtype=Float32),
        Field(name="population", dtype=Float32),
        Field(name="avg_occupancy", dtype=Float32),
        Field(name="latitude", dtype=Float32),
        Field(name="longitude", dtype=Float32),
    ],
    online=True,
    source=block_group_stats,
    tags={"team": "pricing", "tier": "serving"},
)

house_value_labels = FeatureView(
    name="house_value_labels",
    entities=[block_group],
    ttl=timedelta(days=365),
    schema=[Field(name="median_house_value", dtype=Float32)],
    online=False,
    source=house_values,
    tags={"team": "pricing", "tier": "labels"},
)
