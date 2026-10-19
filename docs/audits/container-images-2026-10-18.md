# Container image audit — 2026-10-18

Scope: every Dockerfile and compose file in the repo, read against
`docs/adr/0014-container-image-standard.md`. A deviation with a spec citation
is registered in `docs/gaps.md`; anything that needs a build or run to settle
stays in *Suspects* below. No image was built in this session (shared-host load
gate — AGENTS "Host resources"), so no size or start-time number appears here.
The one run measured was a throwaway `alpine` service, used to confirm that the
compose cap below actually binds.

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
(`projects/electricity_price_streaming/docker-compose.yml:15-18,36-39,51-54,69-72`).
The root `moto`/`athena`/`jupyterlab` and the california/telco/wine `moto`
stacks are uncapped. The electricity Flink services also run the stock `flink`
image, which ships no Python, so the PyFlink job they mount cannot execute
there (G-351).

Measured this session (not a build): on Compose v5.5.1 a
`deploy.resources.limits.memory: 64m` service came up with
`HostConfig.Memory=67108864` and `docker stats` reporting a 64 MiB limit — the
cap key does bind on a plain `docker compose up`, so the six uncapped services
(G-346) are genuinely unbounded today. Every tag named in the two compose
stacks resolves on its registry (`python:3.12-slim` ×2, `flink` ×2,
`apache/kafka`, `trinodb/trino`, `motoserver/moto`, `manimcommunity/manim`), so
the digest migration (G-341, G-342) has a live tag to pin for each.

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
| G-351 | the electricity Flink services mount a PyFlink job against the stock `flink` image, which ships no Python |

## Suspects (need a build or run)

| Suspect | Site | Why it is not registered |
|---|---|---|
| `build-essential` in the 4 training images | `projects/*/Dockerfile:8` | every pinned package ships a manylinux wheel, but removing the ~200 MB toolchain needs a build + serving test to confirm |
| `libgomp1` variance | `projects/wine_quality_classification/Dockerfile:8` and `Dockerfile.inference:7-8` install neither `libgomp1` nor a replacement, while the other 3 training and 3 inference images do | sklearn wheels vendor their OpenMP runtime; whether the wine image runs without the apt package is unmeasured |
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
  (digest pinning + automated bumps):
  https://docs.docker.com/build/building/best-practices/
- GitHub, *Dependabot — supported ecosystems and repositories* — `docker` (v1,
  Dockerfiles) and `docker-compose` (v2/v3, compose files) are separate
  ecosystems; digest pinning needs both:
  https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories
- Compose, *Deploy Specification — `resources.limits`* — the platform "must
  prevent the container to allocate more"; deploy is optional to a platform:
  https://github.com/compose-spec/compose-spec/blob/main/deploy.md
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
- Apache Kafka, `bin/kafka-server-start.sh` + `bin/kafka-run-class.sh` —
  `KAFKA_HEAP_OPTS` is passed to `exec java`, so the official image's heap is
  pin-able from compose (G-342, ADR-0014 §9):
  https://github.com/apache/kafka/blob/trunk/bin/kafka-server-start.sh
- Apache Flink, *Configuration* — `jobmanager.memory.process.size` and
  `taskmanager.memory.process.size` are the container memory knobs:
  https://nightlies.apache.org/flink/flink-docs-stable/docs/deployment/config/
- Apache Flink, *Docker — Using Flink Python on Docker* — the stock image has no
  Python; a custom image is required for PyFlink (G-351):
  https://nightlies.apache.org/flink/flink-docs-stable/docs/deployment/resource-providers/standalone/docker/
