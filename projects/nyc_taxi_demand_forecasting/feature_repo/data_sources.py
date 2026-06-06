from pathlib import Path

from feast import FileSource
from feast.data_format import ParquetFormat

# Resolve the path dynamically relative to this definitions file
current_dir = Path(__file__).parent.resolve()
parquet_path = (
    current_dir / "../data/processed/hourly_demand_features.parquet"
).resolve()

hourly_demand_source = FileSource(
    name="hourly_demand_source",
    path=str(parquet_path),
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)
