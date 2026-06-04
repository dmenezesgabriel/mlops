# Event Logs To Supervised Learning

Trip records are cleaned, grouped by pickup zone and hour, and shifted to create `next_hour_pickup_count` as the supervised target.

{{ include_source("src/nyc_taxi_demand_forecasting/data/supervised_dataset.py") }}
