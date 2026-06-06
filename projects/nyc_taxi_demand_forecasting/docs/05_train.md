# Train

Once features are engineered and stored in Feast, model training retrieves them using point-in-time joins to avoid data leakage, trains a Ridge demand regressor, and registers it to the central model registry.

## Historical Feature Retrieval
During training, we read the training dataset (which functions as our "entity dataframe" containing keys and target values). We pass this dataframe to Feast to fetch the corresponding features:
- `pickup_count`
- `hour`
- `day_of_week`
- `is_weekend`
- `month`

Feast performs an offline join against the DuckDB backend and returns a training frame containing the features aligned with the target `next_hour_pickup_count`.

## The Ridge Regressor Model
To predict next-hour pickup counts, we train a custom regularized **Ridge Regression** model. The model computes optimal weights $\beta$ via the closed-form equation:
$$\beta = (X^T X + \alpha I)^{-1} X^T y$$

- $X$: Feature matrix (pre-appended with a column of ones for intercept).
- $I$: Identity matrix (modified to not penalize the intercept term).
- $\alpha$: Regularization hyperparameter.
- $y$: Target column.

## Model Registry & Versioning
When a training run completes, we catalog and version our model in the MLflow Model Registry:
1. Log the model artifact as a custom `PyfuncDemandModel` to the local **MLflow Tracking Store** (backed by SQLite).
2. Register the model under a canonical name: `nyc_taxi_demand_forecaster`.
3. MLflow assigns a unique version number (e.g. `Version 1`, `Version 2`) to the model artifact.

Our project wraps MLflow's registry client within a clean adapter class:
{{ include_source("src/nyc_taxi_demand_forecasting/models/registry.py") }}

## Code Reference
Below is the core training logic including the custom regressor, PyFunc wrapper, and training loop:
{{ include_source("src/nyc_taxi_demand_forecasting/models/training.py") }}
