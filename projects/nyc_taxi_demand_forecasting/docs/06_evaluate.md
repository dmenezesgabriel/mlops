# Evaluate

A key requirement in CD4ML is ensuring that only high-quality models are allowed into production. We enforce this using automated **Quality Gates** and register evaluation status in the model registry.

## Gating Thresholds
Our project configuration defines maximum error thresholds in `configs/project.yaml`:
- **max_mae**: Maximum allowed Mean Absolute Error.
- **max_rmse**: Maximum allowed Root Mean Squared Error.

During the `evaluate` pipeline step, we load the candidate model from the MLflow registry and calculate its performance on our test split features (retrieved from Feast).

If the candidate's metrics exceed the thresholds, the pipeline raises a validation error and aborts, stopping the deployment process:
```python
metrics.require_within(config.evaluation)
```

## Auditable Tags in Model Registry
To ensure full observability, the evaluation step writes the validation metrics as permanent metadata tags on the candidate model version in the MLflow Model Registry:
- `evaluated = "true"`
- `mae = [calculated value]`
- `rmse = [calculated value]`

These tags provide a transparent audit trail for model promotion decisions.

## Pipeline Implementation
Here is the code executing the model evaluation and gating:
{{ include_source("src/nyc_taxi_demand_forecasting/pipelines/evaluate.py") }}
