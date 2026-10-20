from pathlib import Path

from feast import FileSource
from feast.data_format import ParquetFormat

current_dir = Path(__file__).parent.resolve()
parquet_path = (
    current_dir / "../data/processed/customer_features.parquet"
).resolve()

customer_features_source = FileSource(
    name="customer_features_source",
    path=str(parquet_path),
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)
