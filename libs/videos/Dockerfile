FROM manimcommunity/manim:v0.20.1

USER root
WORKDIR /app

COPY pyproject.toml pyproject.toml
COPY src/ src/

RUN pip install --no-cache-dir uv && \
    . /opt/venv/bin/activate && \
    uv pip install -e .

USER manimuser
