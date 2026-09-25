# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 AS uv

FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 AS dependency-export

ENV UV_CACHE_DIR=/tmp/uv-cache
WORKDIR /build
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY libs/ libs/
COPY projects/ projects/
COPY docker/moto/ docker/moto/
RUN ["/usr/local/bin/uv", "export", "--package", "athena-local", "--no-dev", "--no-emit-project", "--no-emit-workspace", "--no-emit-local", "--locked", "--python", "/usr/local/bin/python", "--no-python-downloads", "--output-file", "/tmp/athena-requirements.txt"]

FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 AS runtime

ENV HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/athena/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=dependency-export /tmp/athena-requirements.txt /tmp/athena-requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --requirement /tmp/athena-requirements.txt \
    && rm -f /tmp/athena-requirements.txt

WORKDIR /opt/athena
COPY --chown=10001:10001 libs/athena-local/src/athena_local/ /opt/athena/src/athena_local/

USER 10001:10001
EXPOSE 5001
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5001/health', timeout=3)"]
CMD ["uvicorn", "athena_local.main:app", "--host", "0.0.0.0", "--port", "5001", "--workers", "1"]
