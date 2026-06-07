FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/diagrams/pyproject.toml pyproject.toml
COPY libs/diagrams/src/ src/

RUN pip install --no-cache-dir uv && \
    uv pip install --system pyyaml diagrams pytest && \
    uv pip install --system -e . --no-deps
