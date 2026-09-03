# sagemaker-scikit-learn

Fully offline SageMaker local mode example using scikit-learn.

Run it inside the repo's JupyterLab container, where `SAGEMAKER_LOCAL_*`
environment variables point at the moto service.

Two images are used (both built from `libs/sagemaker-local/docker` assets):

- `sagemaker-scikit-learn:train` — training (`Dockerfile`); also serves online
  endpoints, so it carries the full serving stack plus `sagemaker-training`.
- `sagemaker-scikit-learn:inference` — leaner inference-only image
  (`Dockerfile.inference`), used by offline batch transform.

Build them with `make build-images`.

- `notebooks/training.ipynb` — fit + deploy + predict on the
  `california_housing` regression dataset.
- `notebooks/batch_transform.ipynb` — offline batch inference through the
  inference-only image on the first 20 rows of `california_housing`.
- `notebooks/pipeline.ipynb` — a local `TrainingStep` pipeline on the
  `breast_cancer` classification dataset.

Tests: `make test` runs the fast wiring checks; `make test-notebooks` executes
every notebook end to end (docker + moto + a Jupyter kernel, run inside the
offline stack).
