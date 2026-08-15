# {{ cookiecutter.project_title }}

{{ cookiecutter.description }}

## Commands

```bash
make collect PROJECT={{ cookiecutter.project_slug }}
make preprocess PROJECT={{ cookiecutter.project_slug }}
make features PROJECT={{ cookiecutter.project_slug }}
make train PROJECT={{ cookiecutter.project_slug }}
make evaluate PROJECT={{ cookiecutter.project_slug }}
```

The project uses local parquet files, Feast with DuckDB, and MLflow with SQLite.
