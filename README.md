# MLOps Monorepo

Local-first `uv` monorepo for real-world machine learning projects, shared MLOps utilities, generic static site generation, and Manim CE concept videos.

The first project is `nyc_taxi_demand_forecasting`, built from public NYC TLC trip records.

## Quick Start

```bash
make install
make test
make preview-site
```

## Commands

### Setup & Development
- `make install`: Install all dependencies and pre-commit hooks.
- `make format`: Automatically format code using Ruff.
- `make mlflow`: Start the MLflow tracking server for experiment tracking.

### Quality Assurance
- `make quality`: Run the full quality gate (lint, type-check, tests, coverage, complexity, architecture).
- `make test`: Run unit and integration tests (excludes heavy Docker/Playwright tests).
- `make test-e2e`: Run browser-based smoke tests using Playwright.
- `make lint`: Verify code style and linting rules.
- `make type-check`: Run static type analysis with Pyright.
- `make coverage`: Run tests and display a coverage report.

### Static Site (SSG)
- `make preview-site`: **Live view** with automatic reload and incremental builds.
  - **Default**: `http://127.0.0.1:8000`.
  - **Customization**: Use `uv run python -m ssg.infrastructure.cli preview --help` for full options.
  - **Key Arguments**:
    - `--host`: Host to bind the server (default: `127.0.0.1`).
    - `--port`: Port to run the server (default: `8000`).
    - `--reload-interval`: Debounce interval for reloads in seconds (default: `0.2`).
  - **Live Reload**: Automatically detects changes in the site configuration, project documentation, and notebooks. It safely ignores its own `build/` directory to prevent infinite reload loops.
- `make build-site`: Generate the final production static site.

### Machine Learning Pipeline
- `make <step>`: Execute pipeline steps for a specific project.
  - **Steps**: `collect`, `preprocess`, `features`, `train`, `tune`, `evaluate`, `deploy`, `monitor`.
  - **Usage**: `make train PROJECT=nyc_taxi_demand_forecasting`.

### Videos (Manim)
- `make render-video`: Render a single Manim scene (requires Docker).
- `make check-videos`: Run the full quality gate for videos (render all, lint, and test).

### Local Stack (Docker)
- **Prerequisite**: `docker network create mlops_net` — once per Docker daemon. The compose services share this external network with the sagemaker-local job containers the SDK spawns.
- `make jupyterlab-build`: Build the `mlops-jupyterlab` image.
- `make jupyterlab`: Bring up the stack — JupyterLab plus its moto/trino/athena dependencies (creates `mlops_net` if missing).
- **Endpoints**: JupyterLab `http://localhost:8888` (token disabled); moto S3/Glue/STS `:5000`; Athena emulator `:5001`; Trino `:8485` host / `:8080` in-network.
- The `sagemaker_*` training images bake sklearn's `california_housing` cache and JupyterLab seeds it read-only, so the `sagemaker_*` notebooks run fully offline.

## Architecture

Shared libraries and static-site tooling follow clean architecture. Project ML pipeline scripts use standard data science conventions with `argparse`, pandas, scikit-learn, Feast, and MLflow.

Static site generation is owned by `ssg`; notebook rendering is provided by the separate `ssg_notebook_render` plugin package. The site config points at project content, while projects remain unaware of publishing. See `docs/ssg.md`.
