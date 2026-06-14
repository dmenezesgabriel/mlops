FROM manimcommunity/manim:v0.20.1

USER root
WORKDIR /app

# Copy root workspace definition
COPY pyproject.toml pyproject.toml

# Copy videos library source files
COPY libs/videos/pyproject.toml libs/videos/pyproject.toml
COPY libs/videos/src/ libs/videos/src/

# Copy videos-linter library source files
COPY libs/videos-linter/pyproject.toml libs/videos-linter/pyproject.toml
COPY libs/videos-linter/src/ libs/videos-linter/src/

RUN pip install --no-cache-dir uv && \
    . /opt/venv/bin/activate && \
    uv pip install -e libs/videos && \
    uv pip install -e libs/videos-linter && \
    uv pip install pytest pytest-cov

USER manimuser
