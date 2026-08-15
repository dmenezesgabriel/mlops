from datetime import timedelta

from data_sources import hourly_demand_source
from entities import pickup_location
from feast import FeatureView, Field
from feast.types import Bool, Int64

hourly_pickup_demand_view = FeatureView(
    name="hourly_pickup_demand",
    entities=[pickup_location],
    ttl=timedelta(days=7),
    schema=[
        Field(name="pickup_count", dtype=Int64),
        Field(name="hour", dtype=Int64),
        Field(name="day_of_week", dtype=Int64),
        Field(name="is_weekend", dtype=Bool),
        Field(name="month", dtype=Int64),
    ],
    online=True,
    source=hourly_demand_source,
)
