FROM manimcommunity/manim:v0.22.0@sha256:3c3ce944c09d6fa73de59fe1e7a95e334e193ae9c2275d65937054e675f87b03

ARG GIT_REVISION=unknown

LABEL org.opencontainers.image.title="videos" \
      org.opencontainers.image.source="https://github.com/dmenezesgabriel/mlops" \
      org.opencontainers.image.revision="${GIT_REVISION}" \
      org.opencontainers.image.licenses="NOASSERTION"

USER root
WORKDIR /app

# uv ships as a static binary in the pinned distroless image; installing it
# from PyPI during the build would resolve an unpinned version. 0.13.4
# provides `uv pip install --no-editable`, which the workspace-member install
# needs to stay non-editable.
COPY --from=ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b /uv /uvx /usr/local/bin/

# Copy root workspace definition
COPY pyproject.toml pyproject.toml

# Copy videos library source files
COPY libs/videos/pyproject.toml libs/videos/pyproject.toml
COPY libs/videos/src/ libs/videos/src/

# Copy videos-linter library source files
COPY libs/videos-linter/pyproject.toml libs/videos-linter/pyproject.toml
COPY libs/videos-linter/src/ libs/videos-linter/src/

# Runtime installs are non-editable: uv resolves workspace members editable
# by default, so the flag keeps the runtime independent of the source tree
# (ADR-0014 §5).
RUN . /opt/venv/bin/activate && \
    uv pip install --no-cache --no-editable libs/videos libs/videos-linter && \
    uv pip install --no-cache pytest pytest-cov

USER 1000:1000
