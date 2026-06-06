# Data Collection

Data collection is the first physical step in our automated ML pipeline. In production, this step pulls raw trip record logs from external data lakes or stream stores.

## Data Source
We retrieve yellow taxi trip records published by the **NYC Taxi and Limousine Commission (TLC)**. These records are saved as monthly parquet files containing fields such as:
- `tpep_pickup_datetime`: The timestamp when the meter was engaged.
- `tpep_dropoff_datetime`: The timestamp when the meter was disengaged.
- `PULocationID`: TLC Taxi Zone ID where the passenger was picked up.
- `trip_distance`: The elapsed trip distance in miles.

## Local Raw Cache
Our collector downloads files from the cloud endpoint and saves them to a local raw directory:
`data/raw/yellow_tripdata_YYYY-MM.parquet`

If a file is already present locally, the collector skips the download to conserve bandwidth and ensure idempotent, repeatable runs.

## CLI Execution
To collect the datasets programmatically:
```bash
make collect PROJECT=nyc_taxi_demand_forecasting
```

## Python Implementation
The download code is structured as an isolated, single-responsibility collector class:
{{ include_source("src/nyc_taxi_demand_forecasting/data/collection.py") }}
