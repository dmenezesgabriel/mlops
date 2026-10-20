"""Offline sources for the pricing feature repo."""

from feast import FileSource
from feast.data_format import ParquetFormat

block_group_stats = FileSource(
    name="block_group_stats",
    path="data/block_group_features.parquet",
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)

house_values = FileSource(
    name="house_values",
    path="data/house_values.parquet",
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)
