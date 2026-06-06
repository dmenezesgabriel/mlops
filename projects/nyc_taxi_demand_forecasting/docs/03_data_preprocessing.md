# Data Preprocessing

Raw trip records are unstructured transaction logs (one record per trip). To train a supervised forecasting model, we must transform these event logs into a structured, tabular dataset.

## The Transformation Process
Our preprocessing pipeline implements three key transformations:

1. **Filtering & Cleaning**:
   - Trip durations must be positive (i.e. dropoff time > pickup time).
   - Pickup locations must be valid TLC zone IDs (> 0).
   - Trip distances must be non-negative.
   
2. **Hourly Time-Series Grouping**:
   - We aggregate trip counts by grouping records by `PULocationID` (pickup zone) and the floored `pickup_hour` (e.g. `2023-01-01 14:00:00`).
   
3. **Supervised Target Creation**:
   - For each location ID, we sort the records sequentially and shift the hourly pickup count back by 1 hour. This aligned shift forms the target variable `next_hour_pickup_count`.

## Code Reference
Below is the core Python logic for constructing the supervised training frame:
{{ include_source("src/nyc_taxi_demand_forecasting/data/supervised_dataset.py") }}
