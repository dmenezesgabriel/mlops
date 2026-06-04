from feast import FileSource

hourly_demand_source = FileSource(
    name="hourly_demand_source",
    path="../data/processed/hourly_demand_features.parquet",
    timestamp_field="event_timestamp",
)
