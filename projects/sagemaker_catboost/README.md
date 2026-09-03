# sagemaker-catboost

Fully offline SageMaker local mode example using CatBoost via the generic
bring-your-own-container `Estimator`.

Run it inside the repo's JupyterLab container, where `SAGEMAKER_LOCAL_*`
environment variables point at the moto service.

Two images are used (both built from `libs/sagemaker-local/docker` assets):

- `sagemaker-catboost:train` — training (`Dockerfile`); also serves online
  endpoints, so it carries the full serving stack plus `sagemaker-training`.
- `sagemaker-catboost:inference` — leaner inference-only image
  (`Dockerfile.inference`), used by offline batch transform.

Build them with `make build-images`.

- `notebooks/training.ipynb` — fit + deploy + predict on the `diabetes`
  regression dataset.
- `notebooks/batch_transform.ipynb` — offline batch inference through the
  inference-only image on the first 20 rows of `diabetes`.
- `notebooks/pipeline.ipynb` — a local `TrainingStep` pipeline on the
  `breast_cancer` binary classification dataset.

Tests: `make test` runs the fast wiring checks; `make test-notebooks` executes
every notebook end to end (docker + moto + a Jupyter kernel, run inside the
offline stack).
