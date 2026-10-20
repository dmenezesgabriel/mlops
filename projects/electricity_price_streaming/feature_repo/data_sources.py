from feast import FileSource
from feast.data_format import ParquetFormat

market_ticks = FileSource(
    name="market_ticks",
    path="data/market_features.parquet",
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)
direction_labels_source = FileSource(
    name="direction_labels_source",
    path="data/direction_labels.parquet",
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)
