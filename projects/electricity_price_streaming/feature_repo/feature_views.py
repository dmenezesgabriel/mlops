from datetime import timedelta

from data_sources import direction_labels_source, market_ticks
from entities import market_tick
from feast import FeatureView, Field
from feast.types import Float32, Int64

market_profile = FeatureView(
    name="market_profile",
    entities=[market_tick],
    ttl=timedelta(days=3650),
    schema=[
        Field(name=n, dtype=Float32)
        for n in [
            "day",
            "period",
            "nswprice",
            "nswdemand",
            "vicprice",
            "vicdemand",
            "transfer",
        ]
    ],
    online=True,
    source=market_ticks,
    tags={"team": "market", "tier": "serving"},
)

direction_labels = FeatureView(
    name="direction_labels",
    entities=[market_tick],
    ttl=timedelta(days=3650),
    schema=[Field(name="direction_up", dtype=Int64)],
    online=False,
    source=direction_labels_source,
    tags={"team": "market", "tier": "labels"},
)
