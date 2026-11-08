# PyFlink runtime for the streaming stack. The stock Flink image ships no
# Python, so the mounted `flink_job` cannot run there. Flink's "Using Flink
# Python on Docker" guide recommends extending the image with Python and
# PyFlink. PyFlink 1.20 supports CPython 3.8-3.11; Ubuntu 22.04 (the base)
# provides 3.10. apache-flink 1.20.5 publishes no aarch64 wheel, so this
# image builds on linux/amd64, the platform the compose stack runs on.
FROM flink:1.20-scala_2.12-java11@sha256:671e890a10e783374d626a6870756c6ad86983e8f94e8a21b6d1408a1f86be2c

ARG GIT_REVISION=unknown

LABEL org.opencontainers.image.title="electricity-price-streaming-flink" \
      org.opencontainers.image.source="https://github.com/dmenezesgabriel/mlops" \
      org.opencontainers.image.revision="${GIT_REVISION}" \
      org.opencontainers.image.licenses="NOASSERTION"

# PyFlink's worker runs beside the JVM and resolves `python` by default;
# Flink's own guide symlinks it to the system interpreter.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# uv ships as a static binary in the pinned distroless image; installing it
# from PyPI during the build would resolve an unpinned version (ADR-0014 §4).
COPY --from=ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b /uv /uvx /usr/local/bin/

COPY requirements.txt /tmp/flink-requirements.txt
# The lock's apache-flink version must match the Flink distribution in the
# base image; a base bump therefore needs `make flink-lock` and a review.
RUN uv pip install --system --no-cache --require-hashes --requirement /tmp/flink-requirements.txt \
    && rm -f /tmp/flink-requirements.txt

# The connector is not part of the Flink distribution. Pin it by checksum so
# a changed Maven artifact fails the build instead of entering the image.
ADD --checksum=sha256:b860724fd97d7da0901bfc3859680442f4c1aa2b35ab944407558b393a1cf93e \
    --chmod=644 \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.4.0-1.20/flink-sql-connector-kafka-3.4.0-1.20.jar \
    /opt/flink/lib/flink-sql-connector-kafka-3.4.0-1.20.jar

# The job is mounted from the host and is not writable by uid 9999; never
# try to write __pycache__ beside it.
ENV PYTHONDONTWRITEBYTECODE=1

# The base image's own flink user; its entrypoint would gosu there anyway.
USER 9999:9999
