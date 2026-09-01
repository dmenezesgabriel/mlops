# sagemaker-catboost

Fully offline SageMaker local mode example using CatBoost via the generic
bring-your-own-container `Estimator`.

Run it inside the repo's JupyterLab container, where `SAGEMAKER_LOCAL_*`
environment variables point at the moto service and `sagemaker-local:latest`
is the built image.

- `notebooks/training.ipynb` — fit + deploy + predict on the `diabetes`
  regression dataset.
- `notebooks/pipeline.ipynb` — a local `TrainingStep` pipeline on the
  `breast_cancer` binary classification dataset.
