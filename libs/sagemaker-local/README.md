# sagemaker-local

Run the [Amazon SageMaker Python SDK](https://sagemaker.readthedocs.io/) local mode
fully offline: no AWS credentials, no ECR access, no telemetry. AWS APIs (S3, STS)
are served by [moto](https://getmoto.org/), and every docker-compose file generated
by SageMaker local mode is patched to join your project's docker network.

## What it does

- `sagemaker_local.session.make_local_session(cfg)` — builds a `boto3.Session`
  (static test credentials) plus a `sagemaker.local.LocalSession` whose S3 traffic
  goes to `cfg.s3_endpoint_url`, with telemetry disabled and a fixed bucket name.
- `sagemaker_local.session.make_local_pipeline_session(cfg)` — same, but returns a
  `LocalPipelineSession` so `Pipeline.start()` executes locally.
- `sagemaker_local.patches` — idempotent monkey-patches:
  - compose-file rewriting: inject an external docker network so job containers can
    reach `cfg.s3_endpoint_url` by service name; optional hardening (`init: true`,
    json-file log rotation).
  - compose v2 detection fix: newer `docker compose` versions (v5+) fail the SDK's
    literal `"v2"` version-string check; the patch restores detection.
  - `get_docker_host` gateway resolution so serving containers are reachable from
    inside another container.
  - container cleanup: `cleanup_stopped_containers()` removes exited job containers;
    `cleanup_stale_serving_containers()` reaps serving containers that linger (and
    hold the serving port) after host-process death.
- `sagemaker_local.images.build_image(tag)` — builds the bundled
  `docker/Dockerfile`: a local replacement for the AWS-managed framework images,
  providing the standard `train` command (via `sagemaker-training`) and a `serve`
  command implementing `/ping` + `/invocations` with the standard inference hooks.
  Serving resolves the inference hooks from the `SAGEMAKER_PROGRAM` script when
  one is mounted (framework estimators); when none is mounted (generic
  bring-your-own-container `Estimator`, which mounts no `/opt/ml/code`), it falls
  back to loading `model.joblib` with generic predict/JSON/CSV/npy handling.

## Usage

```python
from sagemaker_local.config import LocalModeConfig
from sagemaker_local.session import make_local_session

cfg = LocalModeConfig(s3_endpoint_url="http://moto:5000", bucket="my-bucket")
_, session = make_local_session(cfg)

estimator.fit({"train": "file://data/train.csv"})   # runs in a local container
```

Environment overrides via `SAGEMAKER_LOCAL_*` variables, see
`sagemaker_local.config`.
