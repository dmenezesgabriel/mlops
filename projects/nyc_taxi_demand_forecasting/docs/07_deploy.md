# Deploy

In modern CD4ML systems, deployment does not mean copying binary files around. Instead, we use **Model Promotion** using registry aliases, which can then be served via online serving (FastAPI) or batch jobs.

## The `@champion` Alias
Our inference services (like batch prediction scripts or APIs) do not hardcode a specific model version number. Instead, they request the model using a logical alias:
`models:/nyc_taxi_demand_forecaster@champion`

The `deploy` pipeline promotes the newly evaluated model version by binding the alias `champion` to it. The promotion is instant and fully tracked:

```python
client.set_registered_model_alias(
    name=model_name,
    alias="champion",
    version=latest_version.version,
)
```

## Batch Inference
Once promoted, downstream consumers load and run the champion model to generate predictions. For example, our batch scoring script loads the model dynamically using the MLflow wrapper:
{{ include_source("src/nyc_taxi_demand_forecasting/inference/batch_predict.py") }}

## Online serving (FastAPI)
For real-time online predictions, we serve a minimal FastAPI endpoint. When queried, it connects to the Feast Feature Store to fetch recent demand features for a given taxi zone ID, and passes them to our champion model from MLflow to calculate expected demand:
{{ include_source("src/nyc_taxi_demand_forecasting/inference/api.py") }}

## Pipeline Implementation
Here is the code executing the model promotion:
{{ include_source("src/nyc_taxi_demand_forecasting/pipelines/deploy.py") }}
