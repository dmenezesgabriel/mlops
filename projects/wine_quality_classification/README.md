# wine-quality-classification

Cultivar classification from wine lab assays — the same staged lifecycle as
NYC taxi demand, deployed the way routine retraining ships: a **SageMaker
Pipeline** (`LocalPipelineSession`) fed by a **Feast offline store**.

The pipeline is the product: the Feast-retrieved training channel flows into
a `TrainingStep`, and every retrain is one `pipeline.start()` with
inspectable, versioned artifacts on moto S3.

## Stack

- `docker-compose.yml` — `wine-quality-classification-moto` (S3/STS) on
  `mlops_net`.
- `feature_repo/` — Feast repo: `wine_assay_profile` + `wine_cultivar_labels`
  (offline only — the pipeline is the consumer).
- `src/wine_quality_classification/` — `prepare_data.py`,
  `feature_contract.py`, `train.py` (LogisticRegression channel entrypoint;
  the `StandardScaler` rides inside the model artifact).
- Images `wine-quality-classification:train` / `:inference` —
  `make build-images`.

## Lifecycle notebooks

`index` → `eda` → `feature_engineering` → `training` → `tuning` (C sweep) →
`evaluation` (accuracy gate ≥ 0.9) → `deploy` (**the pipeline**) →
`monitoring`. Narrative docs under `docs/`.
