# Container image audit — 2026-10-18

Scope: every Dockerfile and compose file in the repo, read against
`docs/adr/0014-container-image-standard.md`. A deviation with a spec citation
is registered in `docs/gaps.md`; anything that needs a build or run to settle
stays in *Suspects* below. No image was built in this session (shared-host load
gate — AGENTS "Host resources"), so no size or start-time number appears here.

Inventory: 14 Dockerfiles, 5 compose files, 13 unpinned `FROM` lines, 9 unpinned
compose `image:` references.

## Conformance today

`uv export` = dependencies installed from the locked, hashed workspace export.

| Image (file) | Base pinned | User | Deps locked | OCI labels | Memory cap |
|---|---|---|---|---|---|
| athena — `docker/athena/Dockerfile` | yes `@sha256` | `10001:10001` | `uv export` + `--require-hashes` | no | no (compose `:60-89`) |
| jupyterlab — `Dockerfile` | no | `jupyter` (1000) | runtime `uv sync` | no | no |
| sagemaker-local — `libs/sagemaker-local/docker/Dockerfile` | no | root (required) | no | no | n/a |
| 4× project train — `projects/*/Dockerfile` | no | root (required) | no | no | n/a |
| 4× project inference — `projects/*/Dockerfile.inference` | no | root (required) | no | no | n/a |
| videos — `libs/videos/Dockerfile` | no | `manimuser` | editable install | no | n/a |
| diagrams — `libs/diagrams/Dockerfile` | no | root | editable install | no | n/a |
| termux — `termux/Dockerfile` (proot, not a runtime image) | no | `jupyter` (1000) | n/a | no | n/a |

Compose services: `trino` caps at 4 GiB (`docker-compose.yml:45-48`) and the
electricity stack caps moto/Kafka/both Flink roles with pinned heaps
(`projects/electricity_price_streaming/docker-compose.yml:15-18,35-39,51-54,69-72`).
The root `moto`/`athena`/`jupyterlab` and the california/telco/wine `moto`
stacks are uncapped.

## Registered deviations

| Gap | Deviation |
|---|---|
| G-341 | 13 `FROM` lines name a mutable tag (Athena and termux not counted twice) |
| G-342 | 9 compose `image:` references name a mutable tag |
| G-343 | the 9 SageMaker images pin direct versions but not transitive deps and install no hashes |
| G-344 | `videos` + `diagrams` install unpinned `uv` from PyPI instead of the pinned uv image |
| G-345 | `videos` + `diagrams` install their own package editable in the runtime image |
| G-346 | root `moto`/`athena`/`jupyterlab` + 3 project `moto` stacks carry no memory cap |
| G-347 | `diagrams` runs as root; `Makefile:151` (and `:118` for videos) works around the resulting host-UID mismatch with `chmod 777` |
| G-348 | no built image carries OCI annotations |

## Suspects (need a build or run)

| Suspect | Site | Why it is not registered |
|---|---|---|
| `build-essential` in the 4 training images | `projects/*/Dockerfile:8` | every pinned package ships a manylinux wheel, but removing the ~200 MB toolchain needs a build + serving test to confirm |
| `libgomp1` variance | `projects/wine_quality_classification/Dockerfile:8` and `Dockerfile.inference:7-8` install neither `libgomp1` nor a replacement, while the other 3 training and 3 inference images do | sklearn wheels vendor their OpenMP runtime; whether the wine image runs without the apt package is unmeasured |
| Athena has no memory cap | `docker-compose.yml:60-89` | the query semaphore bounds concurrency, not RSS; `docker stats` needed |
| image sizes / CVE counts | all | host load prevented builds this session |

## Not findings

- `libs/diagrams` on Python 3.11 while the rest use 3.12:
  `requires-python = ">=3.11"` + `pyright pythonVersion = "3.11"`
  (`libs/diagrams/pyproject.toml`) — intentional.
- `videos` ships pytest/pytest-cov (`libs/videos/Dockerfile:21`):
  `make test-videos-docker` runs pytest inside that image — needed, not bloat.
- Missing healthchecks in the california/wine `moto` stacks: nothing consumes
  them (`docker compose up` without `--wait`); noted, not a defect.
- SageMaker images running as root: platform contract (ADR-0014 §3).
- `docker/athena/Dockerfile` digest pins, hashes and non-root: already
  conformant — the reference implementation.

## Standards cited

- Docker, *Building best practices* — multi-stage, minimal base, `USER`,
  `LABEL`, `CMD` exec form, `.dockerignore`, "Pin base image versions"
  (digest pinning + Dependabot `package-ecosystem: docker`):
  https://docs.docker.com/build/building/best-practices/
- uv, *Using uv in Docker* — copy uv from the official image, pin the version
  or digest, cache mounts, `--no-editable`, cache/intermediate layers:
  https://docs.astral.sh/uv/guides/integration/docker/
- AWS, *Custom Inference Code with Hosting Services* — root users required,
  `/opt/ml/model` read-only, `tini` not usable as entrypoint:
  https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html
- pip, *Secure installs — hash-checking mode* (`--require-hashes`):
  https://pip.pypa.io/en/stable/topics/secure-installs/
- OCI, *image-spec — Annotations* (`org.opencontainers.image.*`):
  https://github.com/opencontainers/image-spec/blob/main/annotations.md
