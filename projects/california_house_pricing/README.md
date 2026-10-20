# california-house-pricing

Instant median-value estimates for California census block groups — the
same staged lifecycle as NYC taxi demand, deployed the way interactive
scoring ships: a **synchronous SageMaker endpoint + Feast online store**
(DynamoDB on moto, fully offline).

Block-group census features are materialized into the online store; a caller
looks the entity up, sends the vector to the local endpoint, and gets the
estimate in one round-trip.

## Stack

- `docker-compose.yml` — `california-house-pricing-moto` (S3/STS/DynamoDB)
  on `mlops_net`.
- `feature_repo/` — Feast repo: `block_group_profile` (online) +
  `house_value_labels` (offline).
- `src/california_house_pricing/` — `prepare_data.py`, `feature_contract.py`,
  `train.py` (LightGBM channel entrypoint).
- Images `california-house-pricing:train` / `:inference` — `make build-images`.

## Lifecycle notebooks

`index` → `eda` → `feature_engineering` (Feast apply + materialize) →
`training` → `tuning` → `evaluation` (R²/MAE gate) → `deploy` (endpoint +
online lookup + invoke) → `monitoring`. Narrative docs under `docs/`.

Run inside the repo JupyterLab container. `make test` for unit checks,
`make test-notebooks` for the end-to-end integration run.
