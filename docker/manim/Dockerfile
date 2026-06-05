FROM manimcommunity/manim:v0.20.1

USER root
WORKDIR /app

COPY libs/videos/pyproject.toml pyproject.toml
COPY libs/videos/src/ src/

RUN . /opt/venv/bin/activate && \
    pip install --no-cache-dir "pydantic>=2.0" "pyyaml>=6.0" "pytest>=8.0" && \
    pip install -e . --no-deps
