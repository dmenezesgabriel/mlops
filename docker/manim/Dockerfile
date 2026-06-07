FROM manimcommunity/manim:v0.20.1

USER root
WORKDIR /app

COPY libs/videos/pyproject.toml pyproject.toml
COPY libs/videos/src/ src/

RUN pip install --no-cache-dir uv && \
    . /opt/venv/bin/activate && \
    uv pip install "pydantic>=2.0" "pyyaml>=6.0" "pytest>=8.0" && \
    uv pip install -e . --no-deps
