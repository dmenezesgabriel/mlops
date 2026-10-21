FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ARG GIT_REVISION=unknown

LABEL org.opencontainers.image.title="sagemaker-local" \
      org.opencontainers.image.source="https://github.com/dmenezesgabriel/mlops" \
      org.opencontainers.image.revision="${GIT_REVISION}" \
      org.opencontainers.image.licenses="NOASSERTION"

# SageMaker requires this image to run as root: the platform writes model
# artifacts under /opt/ml and invokes the training/serving entry points as
# root. Do not add a USER instruction; see ADR-0014 §3.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/standard.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --requirement /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# train.py's default `california_housing` dataset must load offline: job
# containers are ephemeral, so bake sklearn's ~/scikit_learn_data cache at
# build time rather than letting fetch_california_housing hit figshare per run.
RUN python -c "from sklearn.datasets import fetch_california_housing; fetch_california_housing()"

COPY --chmod=0755 serve serve_app.py /opt/ml/serve/
RUN ln -s /opt/ml/serve/serve /usr/local/bin/serve

WORKDIR /opt/ml
