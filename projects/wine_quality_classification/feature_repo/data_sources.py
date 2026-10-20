from feast import FileSource
from feast.data_format import ParquetFormat

wine_assays = FileSource(
    name="wine_assays",
    path="data/wine_features.parquet",
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)
wine_labels_source = FileSource(
    name="wine_labels_source",
    path="data/wine_labels.parquet",
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)
