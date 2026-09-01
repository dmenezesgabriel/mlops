# sagemaker-scikit-learn

Fully offline SageMaker local mode example using scikit-learn.

Run it inside the repo's JupyterLab container, where `SAGEMAKER_LOCAL_*`
environment variables point at the moto service and `sagemaker-local:latest`
is the built image.

- `notebooks/training.ipynb` — fit + deploy + predict on the
  `california_housing` regression dataset.
- `notebooks/pipeline.ipynb` — a local `TrainingStep` pipeline on the
  `breast_cancer` classification dataset.
