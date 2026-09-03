FROM python:3.12-slim

# Training image for the offline CatBoost example. Mirrors the
# libs/sagemaker-local/docker standard (same pins + serve runtime) but ships
# only catboost instead of every bundled framework. Serves online endpoints,
# so the serving stack is included here too.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 procps \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        numpy==1.26.4 \
        pandas==2.2.3 \
        scikit-learn==1.6.1 \
        catboost==1.2.7 \
        joblib==1.4.2 \
        flask==3.1.1 \
        gunicorn==23.0.0 \
        'sagemaker-training==5.1.1'

# The serving entry point and inference hooks come from the library's docker
# assets (single source of truth). Build with context = libs/sagemaker-local/docker
# so these COPY sources resolve.
COPY --chmod=0755 serve serve_app.py /opt/ml/serve/
RUN ln -s /opt/ml/serve/serve /usr/local/bin/serve

WORKDIR /opt/ml