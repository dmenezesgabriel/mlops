# SSG

`ssg` owns generic static site generation. `ssg_notebook_render` is an optional plugin that renders notebooks. The site config owns publishing intent and points at content collections such as machine learning projects.

## Boundaries

- `ssg.domain`: generic site concepts such as `Site`, `ContentCollection`, and `Page`.
- `ssg.application`: build and preview use cases plus stable ports.
- `ssg.infrastructure`: filesystem manifests, Markdown rendering, Jinja page rendering, local preview server, polling reload, and SSG-local logging.
- `ssg_notebook_render`: optional `.ipynb` content renderer plugin.
- `projects/*`: project-specific notebooks, markdown, scripts, charts, and data science code.
- `site/site.yaml`: publishing configuration that maps project content to rendered pages and assets.

The application and domain layers must not import infrastructure or CLI adapters. The core SSG package and notebook plugin must not import MLOps packages or project packages.

## Notebook Directives

Notebook markdown cells may use Jinja directives:

```jinja2
{{ include_source("src/nyc_taxi_demand_forecasting/pipelines/features.py") }}
```

Notebook markdown cells may use wikilinks:

```text
[[problem-framing|Problem Framing]]
```

## Commands

```bash
make build-site PROJECT=nyc_taxi_demand_forecasting
make preview-site PROJECT=nyc_taxi_demand_forecasting
```
