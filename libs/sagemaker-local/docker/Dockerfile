FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 procps \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        numpy==1.26.4 \
        pandas==2.2.3 \
        scikit-learn==1.6.1 \
        xgboost==2.1.4 \
        lightgbm==4.6.0 \
        catboost==1.2.7 \
        joblib==1.4.2 \
        flask==3.1.1 \
        gunicorn==23.0.0 \
        'sagemaker-training==5.1.1'

# train.py's default `california_housing` dataset must load offline: job
# containers are ephemeral, so bake sklearn's ~/scikit_learn_data cache at
# build time rather than letting fetch_california_housing hit figshare per run.
RUN python -c "from sklearn.datasets import fetch_california_housing; fetch_california_housing()"

COPY --chmod=0755 serve serve_app.py /opt/ml/serve/
RUN ln -s /opt/ml/serve/serve /usr/local/bin/serve

WORKDIR /opt/ml