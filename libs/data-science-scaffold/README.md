# Data Science Scaffold

Cookiecutter template and registration helpers for bootstrapping new
data-science projects in this monorepo.

## Generate a project

```bash
make scaffold PROJECT=my_project
```

The recipe renders `template/` with cookiecutter into `projects/<slug>`,
registers the project in the root `pyproject.toml` (uv workspace, deptry,
importlinter contracts), syncs dependencies, and formats the output.

## Library API

```python
from data_science_scaffold.scaffold import generate
from data_science_scaffold.register import register_project

generate("my_project", output_dir="projects")
register_project("my_project")
```
