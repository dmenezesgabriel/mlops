# telco-customer-churn

Telco customer churn scoring told as a production MLOps lifecycle — the same
staged narrative as the NYC taxi demand project, deployed the way batch
scoring actually ships: **SageMaker Batch Transform + Feast offline store**
(no AWS, fully offline via moto + SageMaker local mode).

Every active customer in the IBM Telco churn CRM snapshot is scored each
cycle; the output is a ranked risk list for the retention team. Nothing is
served per-request, so the feature store is offline-only (DuckDB + parquet)
and inference is a transform job that exits when the population is scored.

## Stack

- `docker-compose.yml` — one moto container (`telco-customer-churn-moto`)
  serving S3/STS on the shared `mlops_net` network.
- `feature_repo/` — Feast repo: FileSource → `customer_subscription` view,
  `online=False` (batch-only).
- `src/telco_customer_churn/` — `prepare_data.py` (raw CSV → feature tables),
  `feature_contract.py` (ordered column contract), `train.py` (SageMaker
  entrypoint reading the `train` channel).
- Images `telco-customer-churn:train` / `:inference` — `make build-images`
  (build context is `libs/sagemaker-local/docker`).

## Lifecycle pages (notebooks)

- `notebooks/index.ipynb` — lifecycle overview.
- `notebooks/eda.ipynb` — churn drivers and distributions.
- `notebooks/feature_engineering.ipynb` — compose stack, Feast apply,
  point-in-time retrieval.
- `notebooks/training.ipynb` — XGBoost training job on moto S3.
- `notebooks/tuning.ipynb` — hyperparameter sweep via multiple training jobs.
- `notebooks/evaluation.ipynb` — holdout scored through the inference image;
  confusion matrix + AUC quality gate.
- `notebooks/deploy.ipynb` — Batch Transform over the full population →
  ranked churn list on S3.
- `notebooks/monitoring.ipynb` — feature drift review + stack teardown.

Narrative stages live under `docs/` (problem framing, data collection,
data preprocessing).

Run inside the repo's JupyterLab container, where `docker`, `feast` and
`aws` are on the kernel PATH. Tests: `make test` runs the fast wiring and
unit checks; `make test-notebooks` executes every notebook end to end
(docker + moto + a Jupyter kernel).
