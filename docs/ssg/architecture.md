# Architecture

The repository separates reusable MLOps contracts, generic static publishing, and project-specific machine learning code.

Rules:

- Shared libraries never import projects.
- Projects never import other projects.
- SSG domain modules do not depend on infrastructure or presentation adapters.
- SSG application modules do not depend on infrastructure or presentation adapters.
- Notebook rendering is an optional SSG plugin.
- SSG and SSG plugins do not import MLOps project libraries.
- Site configuration points to project content; projects do not know the site exists.
- Package integration tests live inside each package or project.
- Unit tests mirror module paths under `tests/unit`.
