# MLOps Monorepo

Local-first `uv` monorepo for real-world machine learning projects, shared MLOps utilities, generic static site generation, and Manim CE concept videos.

The first project is `nyc_taxi_demand_forecasting`, built from public NYC TLC trip records.

## Quick Start

```bash
uv sync --all-packages --dev
make test
make build-site PROJECT=nyc_taxi_demand_forecasting
```

## Architecture

Shared libraries and static-site tooling follow clean architecture. Project ML pipeline scripts use standard data science conventions with `argparse`, pandas, scikit-learn, Feast, and MLflow.

Static site generation is owned by `ssg`; notebook rendering is provided by `ssg_notebook_render`. The site config points at project content, while projects remain unaware of publishing. See `docs/ssg.md`.
