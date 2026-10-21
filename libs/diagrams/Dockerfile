FROM python:3.11-slim@sha256:cce12316475d7d56d605f76e1d811d0dc4e7227f2d4afd29951521264f504ff8

ARG GIT_REVISION=unknown

LABEL org.opencontainers.image.title="diagrams" \
      org.opencontainers.image.source="https://github.com/dmenezesgabriel/mlops" \
      org.opencontainers.image.revision="${GIT_REVISION}" \
      org.opencontainers.image.licenses="NOASSERTION"

RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml pyproject.toml
COPY src/ src/

# uv ships as a static binary in the pinned distroless image; installing it
# from PyPI during the build would resolve an unpinned version (ADR-0014 §4).
COPY --from=ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b /uv /uvx /usr/local/bin/

# Non-editable keeps the runtime independent of the source tree
# (ADR-0014 §5). The container test target runs the suite inside this image,
# so the runner is part of the image contract.
RUN uv pip install --system --no-cache --no-editable ".[diagrams]" \
    && uv pip install --system --no-cache pytest==9.0.3 pytest-bdd==8.1.0

USER 1000:1000
